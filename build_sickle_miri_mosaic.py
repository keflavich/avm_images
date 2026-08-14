#!/usr/bin/env python
"""
Rebuild Sickle_RGB_1500-1130-770 from the 2-observation MIRI mosaic.

The web layer (2025-07-04, 683x610) was built from obs o001 only -- half the
field.  The pipeline now provides combined o001-002 mosaics (713x1132) for all
three MIRI filters, covering both observations on a shared grid:

  F1500W/F1130W/F770W  jw03958-o001-002_t001_miri_clear-<f>-mirimage_data_i2d.fits

R=F1500W, G=F1130W, B=F770W, read directly (shared grid, no reprojection),
faithful_avm.  Orientation verified with the visual checker (same ROTATE_180
trap as SgrB2/CloudC): re-embed the matching CDMatrix AVM, confirm identity,
then rebuild the edge-transparent PNG + HiPS and jwst_miri_hips.
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

BASE = "/orange/adamginsburg/jwst/sickle"
MOS = ("pipeline/jw03958-o001-002_t001_miri_clear-{f}-mirimage_data_i2d.fits")
FITS = {
    "f1500w": f"{BASE}/F1500W/{MOS.format(f='f1500w')}",
    "f1130w": f"{BASE}/F1130W/{MOS.format(f='f1130w')}",
    "f770w":  f"{BASE}/F770W/{MOS.format(f='f770w')}",
}
REF_FITS = FITS["f1130w"]        # visual-orientation reference band
LABEL = "Sickle_RGB_1500-1130-770"
PNGDIR = f"{BASE}/pngs_miri_mosaic"

_spec = importlib.util.spec_from_file_location(
    "chk", "/orange/adamginsburg/jwst/jwst_scripts/scripts/check_hips_orientation.py")
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)


def visual_best_flip(png, fits_path):
    fw, fdata = chk.load_fits_wcs_and_data(fits_path)
    import pyavm
    im = Image.open(png).convert("RGB")
    lum = np.asarray(im).mean(2).astype(float)[::-1, :]
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


def main():
    os.makedirs(PNGDIR, exist_ok=True)
    header = fits.getheader(REF_FITS, ext=("SCI", 1))
    data = {f: fits.getdata(p, ext=("SCI", 1)).astype(float) for f, p in FITS.items()}
    shp = data["f1130w"].shape
    for f, d in data.items():
        if d.shape != shp:
            raise ValueError(f"{f} shape {d.shape} != {shp}; mosaics must share grid")

    def stretch(d):
        return simple_norm(d, stretch="asinh", min_percent=1, max_percent=99.5)(d)

    rgb = np.stack([stretch(data["f1500w"]), stretch(data["f1130w"]),
                    stretch(data["f770w"])], axis=2)
    orig = np.stack([data["f1500w"], data["f1130w"], data["f770w"]], axis=2)

    png = f"{PNGDIR}/{LABEL}.png"
    save_rgb(rgb, png, avm=faithful_avm(header), original_data=orig)

    best, c = visual_best_flip(png, REF_FITS)
    print(f"visual best (raw faithful_avm) = {best} (corr {c:.3f})")
    if best != "identity":
        fwcs, ny, nx = load_wcs_shape(REF_FITS)
        avm = cdmatrix_avm(fwcs, ny, nx, best)
        tmp = png + ".t.png"
        avm.embed(png, tmp)
        shutil.move(tmp, png)
        best2, c2 = visual_best_flip(png, REF_FITS)
        print(f"after embedding {best} CDMatrix -> visual best = {best2} (corr {c2:.3f})")
        if best2 != "identity":
            raise RuntimeError(f"still {best2} after flip fix")

    dst = f"{LABEL}.png"
    shutil.copy2(png, dst)
    trans = f"{LABEL}_transparent.png"
    hips = f"{LABEL}_transparent_hips"
    for stale in (trans, hips):
        if os.path.isdir(stale):
            shutil.rmtree(stale)
        elif os.path.exists(stale):
            os.remove(stale)
    t = convert_black_to_transparent(dst)
    assert os.path.abspath(t) == os.path.abspath(trans), t
    print(f"reprojecting -> {hips}")
    reproject_to_hips(trans, coord_system_out="galactic", level=None,
                      reproject_function=reproject_interp,
                      output_directory=hips, threads=8, progress_bar=tqdm)
    print(f"built {hips}")

    print("Rebuilding jwst_miri_hips coadd...")
    build_coadd(MIRI_LAYERS, "jwst_miri_hips")
    print("Done: Sickle MIRI 2-obs mosaic built, jwst_miri_hips rebuilt.")


if __name__ == "__main__":
    main()
