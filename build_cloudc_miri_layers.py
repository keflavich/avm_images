#!/usr/bin/env python
"""
Build the two Cloud C MIRI grayscale HiPS layers and rebuild jwst_miri_hips.

Cloud C MIRI is two separate single-band fields with DIFFERENT pointings:

  F770W   program 2526 obs 021 (1178x1171, PA~-79.6) -- target "G0", Cloud C
  F2550W  program 2221 obs 001 (1503x1185, PA~93.9)  -- the Brick programme,
          whose obs 001 MIRI pointing sits on Cloud C.  Its header therefore
          reads TARGPROP = 'BRICK-IKP2016-G0.253+0.015' while the product is
          named for the field actually observed; that mismatch is expected.

The previous combined RGB (CloudC_MIRI_RGB_2550-770-770) reprojected F2550W
onto the F770W grid, which cropped it to a corner and mis-placed it -- only
~9.5% of the F2550W field falls inside the F770W field.  Each band is instead
rendered as its own grayscale layer in its native frame.

Orientation: save_rgb lays pixels with transpose=ROTATE_180 while faithful_avm
embeds the FITS CDMatrix unchanged, and at these MIRI position angles that
pairing can render flipped (the same trap as SgrB2).  hips_orientation measures
the actual pixel<->sky dihedral, re-embeds the matching CDMatrix AVM, and
confirms identity before the HiPS is built.  See hips_orientation.py for a
glossary of AVM / CDMatrix / HiPS / i2d / layer / coadd.

Run order: this script rebuilds jwst_miri_hips, which needs every layer in
MIRI_LAYERS to exist -- including the Sickle layer from
build_sickle_miri_mosaic.py.  The inputs are checked before any layer is
touched, and --no-coadd skips the coadd entirely.

Usage:
  build_cloudc_miri_layers.py [--out-dir DIR] [--no-coadd]
"""
import argparse
import os
import shutil
import sys

import numpy as np
from astropy.io import fits
from astropy.visualization import simple_norm
from PIL import Image

sys.path.insert(0, "/orange/adamginsburg/jwst/jwst_scripts/scripts")

from jwst_rgb.save_rgb import save_rgb, faithful_avm  # noqa: E402
from python_reproject_to_hips import convert_black_to_transparent  # noqa: E402
from rebuild_jwst_cmz_hips import MIRI_LAYERS, build_coadd, check_layers  # noqa: E402
from hips_orientation import build_hips_staged, fix_orientation  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))

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
    # hips=False: the pyramid is built below, after the orientation fix.  Left
    # at its default, save_rgb would build a full pyramid here from the
    # uncorrected metadata and leave it on disk unused.
    save_rgb(rgb, png, avm=faithful_avm(header), original_data=orig, hips=False)

    fix_orientation(png, fits_path, label=label)

    # copy into the output tree, make edge-transparent, build HiPS
    dst = f"{label}.png"
    shutil.copy2(png, dst)
    trans = f"{label}_transparent.png"
    if os.path.exists(trans):
        os.remove(trans)
    t = convert_black_to_transparent(dst)
    if os.path.abspath(t) != os.path.abspath(trans):
        raise ValueError(f"convert_black_to_transparent wrote {t}, expected {trans}")
    build_hips_staged(trans, f"{label}_transparent_hips")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", default=HERE,
                   help="directory the layers are written to (default: the "
                        "directory this script lives in)")
    p.add_argument("--no-coadd", action="store_true",
                   help="skip the jwst_miri_hips rebuild")
    args = p.parse_args()
    os.chdir(args.out_dir)

    built_here = [f"{lbl}_transparent_hips" for lbl, _ in FIELDS]
    if not args.no_coadd:
        # fail before touching any published layer if the coadd cannot run
        check_layers(MIRI_LAYERS, ignore=built_here)

    for label, fp in FIELDS:
        build_field(label, fp)
    # drop the broken combined layer if present
    for stale in ("CloudC_MIRI_RGB_2550-770-770_transparent_hips",):
        if os.path.isdir(stale):
            print(f"Removing broken layer {stale}")
            shutil.rmtree(stale)
    if args.no_coadd:
        print("Done: cloud C MIRI grayscale layers built (coadd skipped).")
        return
    print("\nRebuilding jwst_miri_hips coadd...")
    build_coadd(MIRI_LAYERS, "jwst_miri_hips")
    print("Done: cloud C MIRI grayscale layers built, jwst_miri_hips rebuilt.")


if __name__ == "__main__":
    main()
