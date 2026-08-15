#!/usr/bin/env python
"""
Refresh one or more NIR release layers from freshly-regenerated pipeline PNGs.

Usage:
  refresh_nir_layer.py arches quintuplet [...]        # refresh named targets
  refresh_nir_layer.py --all                          # every ready target
  refresh_nir_layer.py arches --no-coadd              # skip the coadd rebuild

The 2026 reprocessing left the jwst_nir_hips coadd built from 2025-era PNGs.
For each target this copies the regenerated pipeline PNG into avm_images,
verifies orientation with the VISUAL checker (check_hips_orientation -- a
metadata-clean faithful_avm can still render rot180 because save_rgb lays pixels
with transpose=ROTATE_180), re-embeds the matching CDMatrix AVM if needed,
rebuilds the edge-transparent PNG + _transparent_hips, and finally rebuilds
jwst_nir_hips.
"""
import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from tqdm import tqdm
from reproject import reproject_interp
from reproject.hips import reproject_to_hips

sys.path.insert(0, "/orange/adamginsburg/jwst/jwst_scripts/scripts")
import importlib.util  # noqa: E402
from apply_cdmatrix_flip import load_wcs_shape, cdmatrix_avm  # noqa: E402

from python_reproject_to_hips import convert_black_to_transparent  # noqa: E402
from rebuild_jwst_cmz_hips import NIR_LAYERS, build_coadd  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

JW = "/orange/adamginsburg/jwst"

# target -> (source PNG, reference FITS for the visual orientation check)
TARGETS = {
    "arches": (
        f"{JW}/arches/pngs_323/ArchesQuintuplet_RGB_323-average-212_log.png",
        f"{JW}/arches/data_reprojected/"
        "jw02045-o001_t001_nircam_clear-f212n_i2d_pipeline_v0.1_reprj_f323.fits",
    ),
    "quintuplet": (
        f"{JW}/quintuplet/pngs_323/Quintuplet_RGB_323-average-212_log.png",
        f"{JW}/quintuplet/data_reprojected/"
        "jw02045-o003_t002_nircam_clear-f212n_i2d_pipeline_v0.1_reprj_f323.fits",
    ),
    "brick": (
        f"{JW}/brick/pngs_444/Brick_RGB_444-356-200.png",
        f"{JW}/brick/data_reprojected/"
        "jw01182-o004_t001_nircam_clear-f200w-merged_i2d_pipeline_v0.1_reprj_f444.fits",
    ),
    "sgra": (
        f"{JW}/sgra/pngs_444/SgrA_RGB_NIRCam_444-323-212.png",
        f"{JW}/sgra/data_reprojected/"
        "jw01939-o001_t001_nircam_clear-f212n-merged_i2d_pipeline_v0.1_reprj_f444.fits",
    ),
    "cloudef": (
        f"{JW}/cloudef/pngs_480/Cloudef_RGB_4802-3602-2102.png",
        f"{JW}/cloudef/data_reprojected/"
        "jw02092-o002_t001_nircam_clear-f210m-merged_i2d_pipeline_v0.1_reprj_f480.fits",
    ),
}

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


def refresh(target):
    src, ref = TARGETS[target]
    if not os.path.exists(src):
        print(f"SKIP {target}: missing {src}")
        return False
    label = os.path.basename(src)[:-4]
    print(f"\n=== {target}: {label} ===\n  src {src}")
    dst = f"{label}.png"
    shutil.copy2(src, dst)

    if os.path.exists(ref):
        best, c = visual_best_flip(dst, ref)
        print(f"  visual best = {best} (corr {c:.3f})")
        if best != "identity":
            fwcs, ny, nx = load_wcs_shape(ref)
            avm = cdmatrix_avm(fwcs, ny, nx, best)
            tmp = dst + ".t.png"
            avm.embed(dst, tmp)
            shutil.move(tmp, dst)
            best2, c2 = visual_best_flip(dst, ref)
            print(f"  after {best} CDMatrix -> {best2} (corr {c2:.3f})")
            if best2 != "identity":
                raise RuntimeError(f"{target}: still {best2} after flip fix")
    else:
        print(f"  WARNING: reference FITS missing, orientation NOT verified: {ref}")

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
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("targets", nargs="*", choices=list(TARGETS) + [])
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-coadd", action="store_true")
    args = p.parse_args()
    todo = list(TARGETS) if args.all else args.targets
    if not todo:
        p.error("name at least one target or pass --all")
    done = [t for t in todo if refresh(t)]
    if done and not args.no_coadd:
        print("\nRebuilding jwst_nir_hips coadd...")
        build_coadd(NIR_LAYERS, "jwst_nir_hips")
    print(f"Done: refreshed {done}")


if __name__ == "__main__":
    main()
