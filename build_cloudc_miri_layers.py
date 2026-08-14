#!/usr/bin/env python
"""
Build the two Cloud C MIRI grayscale HiPS layers and rebuild jwst_miri_hips.

Cloud C MIRI is two separate single-band fields with DIFFERENT pointings:
  F2550W from program 2221 (1503x1185, PA~93.9)
  F770W  from program 2526 (1165x1166, PA~-79.6)

The previous combined RGB (CloudC_MIRI_RGB_2550-770-770) reprojected F2550W
onto the F770W grid, which cropped it to a tiny corner and mis-placed it.  Each
band is instead rendered as its own grayscale layer in its native frame.

Orientation: save_rgb lays pixels with transpose=ROTATE_180, and faithful_avm
embeds an identity-of-FITS CDMatrix -- at these MIRI PAs that pairing can render
flipped (same trap as SgrB2).  So after save_rgb we run the VISUAL checker
(check_hips_orientation) to find the actual pixel<->sky flip, re-embed the
matching CDMatrix AVM, and confirm identity before building the HiPS.
"""
import os
import shutil
import sys

import numpy as np
from astropy.io import fits
from astropy.visualization import simple_norm
from PIL import Image
from tqdm import tqdm
from reproject import reproject_interp
from reproject.hips import reproject_to_hips

sys.path.insert(0, "/orange/adamginsburg/jwst/jwst_scripts/scripts")
import importlib.util  # noqa: E402
from apply_cdmatrix_flip import load_wcs_shape, cdmatrix_avm  # noqa: E402

from jwst_rgb.save_rgb import save_rgb, faithful_avm  # noqa: E402
from python_reproject_to_hips import convert_black_to_transparent  # noqa: E402
from rebuild_jwst_cmz_hips import MIRI_LAYERS, build_coadd  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

CLOUDC = "/orange/adamginsburg/jwst/cloudc"
PNGDIR = f"{CLOUDC}/pngs_miri_gray"

FIELDS = [
    ("CloudC_MIRI_F770W",
     f"{CLOUDC}/F770W/pipeline/"
     "jw02526-o021_t001_miri_clear-f770w-mirimage_data_i2d.fits"),
    ("CloudC_MIRI_F2550W",
     f"{CLOUDC}/F2550W/pipeline/"
     "jw02221-o001_t001_miri_clear-f2550w-mirimage_data_i2d.fits"),
]

# load the visual orientation checker as a module
_spec = importlib.util.spec_from_file_location(
    "chk", "/orange/adamginsburg/jwst/jwst_scripts/scripts/check_hips_orientation.py")
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def visual_best_flip(png, fits_path):
    """Return the dihedral the HiPS would show relative to sky (identity = ok)."""
    fw, fdata = chk.load_fits_wcs_and_data(fits_path)
    import pyavm
    im = Image.open(png).convert("RGB")
    lum = np.asarray(im).mean(2).astype(float)[::-1, :]  # PIL top-origin -> bottom
    awcs = pyavm.AVM.from_image(png).to_wcs().celestial
    best, bestc = "identity", -2.0
    for name, arr in [("identity", lum), ("fliplr", lum[:, ::-1]),
                      ("flipud", lum[::-1, :]), ("rot180", lum[::-1, ::-1])]:
        rep, _ = reproject_interp((arr, awcs), fw, shape_out=fdata.shape)
        m = np.isfinite(rep) & np.isfinite(fdata)
        a = rep[m] - rep[m].mean()
        b = fdata[m] - fdata[m].mean()
        c = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-30))
        if c > bestc:
            best, bestc = name, c
    return best, bestc


def build_field(label, fits_path):
    print(f"\n=== {label} ===\n  {fits_path}")
    os.makedirs(PNGDIR, exist_ok=True)
    header = fits.getheader(fits_path, ext=("SCI", 1))
    data = fits.getdata(fits_path, ext=("SCI", 1)).astype(float)

    norm = simple_norm(data, stretch="asinh", min_percent=1, max_percent=99.5)
    gray = norm(data)
    rgb = np.stack([gray, gray, gray], axis=2)
    orig = np.stack([data, data, data], axis=2)

    png = f"{PNGDIR}/{label}.png"
    save_rgb(rgb, png, avm=faithful_avm(header), original_data=orig)

    # verify + fix orientation with the visual checker
    best, c = visual_best_flip(png, fits_path)
    print(f"  visual best (raw faithful_avm) = {best} (corr {c:.3f})")
    if best != "identity":
        fwcs, ny, nx = load_wcs_shape(fits_path)
        avm = cdmatrix_avm(fwcs, ny, nx, best)
        tmp = png + ".t.png"
        avm.embed(png, tmp)
        shutil.move(tmp, png)
        best2, c2 = visual_best_flip(png, fits_path)
        print(f"  after embedding {best} CDMatrix -> visual best = {best2} (corr {c2:.3f})")
        if best2 != "identity":
            raise RuntimeError(f"{label}: still {best2} after flip fix")

    # copy into avm_images, make edge-transparent, build HiPS
    dst = f"{label}.png"
    shutil.copy2(png, dst)
    trans = f"{label}_transparent.png"
    hips = f"{label}_transparent_hips"
    for stale in (trans, hips):
        if os.path.isdir(stale):
            shutil.rmtree(stale)
        elif os.path.exists(stale):
            os.remove(stale)
    t = convert_black_to_transparent(dst)
    assert os.path.abspath(t) == os.path.abspath(trans), t
    print(f"  reprojecting -> {hips}")
    reproject_to_hips(trans, coord_system_out="galactic", level=None,
                      reproject_function=reproject_interp,
                      output_directory=hips, threads=8, progress_bar=tqdm)
    print(f"  built {hips}")


def main():
    for label, fp in FIELDS:
        build_field(label, fp)
    # drop the broken combined layer if present
    for stale in ("CloudC_MIRI_RGB_2550-770-770_transparent_hips",):
        if os.path.isdir(stale):
            print(f"Removing broken layer {stale}")
            shutil.rmtree(stale)
    print("\nRebuilding jwst_miri_hips coadd...")
    build_coadd(MIRI_LAYERS, "jwst_miri_hips")
    print("Done: cloud C MIRI grayscale layers built, jwst_miri_hips rebuilt.")


if __name__ == "__main__":
    main()
