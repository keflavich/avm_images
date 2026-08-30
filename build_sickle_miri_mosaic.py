#!/usr/bin/env python
"""
Rebuild Sickle_RGB_1500-1130-770 from the 2-observation MIRI mosaic.

The web layer (2025-07-04, 683x610) was built from obs o001 only -- half the
field.  The pipeline now provides combined o001-002 mosaics (713x1132) for all
three MIRI filters:

  F1500W/F1130W/F770W  jw03958-o001-002_t001_miri_clear-<f>-mirimage_data_i2d.fits

R=F1500W, G=F1130W, B=F770W (descending wavelength, as elsewhere in this repo),
read directly and stacked with no reprojection.  The three grids are not
byte-identical: the corners agree to ~0.5-0.8 pixel (0.06-0.09", against a
~0.5" F1500W beam), so the per-channel misregistration is below the beam and
stacking is safe -- but that is a measured tolerance, not an assumption, so
`check_shared_grid` compares sky footprints rather than array shapes.  Two
same-shape mosaics on genuinely different pointings are rejected.

Orientation is verified with hips_orientation (same ROTATE_180 trap as
SgrB2/CloudC): re-embed the matching CDMatrix AVM, confirm identity, then
rebuild the edge-transparent PNG + HiPS and jwst_miri_hips.  See
hips_orientation.py for a glossary of AVM / CDMatrix / HiPS / i2d / coadd.

Run order: the jwst_miri_hips rebuild needs every layer in MIRI_LAYERS,
including the Cloud C layers from build_cloudc_miri_layers.py.  Those inputs are
checked before any published layer is touched, and --no-coadd skips the coadd.

Usage:
  build_sickle_miri_mosaic.py [--out-dir DIR] [--no-coadd] [--max-offset-pix N]
"""
import argparse
import os
import shutil
import sys

import numpy as np
from astropy.io import fits
from astropy.coordinates import SkyCoord
from astropy.visualization import simple_norm
from astropy.wcs import WCS
from astropy.wcs.utils import proj_plane_pixel_scales
from PIL import Image
import astropy.units as u

sys.path.insert(0, "/orange/adamginsburg/jwst/jwst_scripts/scripts")

from jwst_rgb.save_rgb import save_rgb, faithful_avm  # noqa: E402
from python_reproject_to_hips import convert_black_to_transparent  # noqa: E402
from rebuild_jwst_cmz_hips import MIRI_LAYERS, build_coadd, check_layers  # noqa: E402
from hips_orientation import build_hips_staged, fix_orientation  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))

BASE = "/orange/adamginsburg/jwst/sickle"
MOS = ("pipeline/jw03958-o001-002_t001_miri_clear-{f}-mirimage_data_i2d.fits")
FITS = {
    "f1500w": f"{BASE}/F1500W/{MOS.format(f='f1500w')}",
    "f1130w": f"{BASE}/F1130W/{MOS.format(f='f1130w')}",
    "f770w":  f"{BASE}/F770W/{MOS.format(f='f770w')}",
}
REF = "f1130w"                   # visual-orientation and grid reference band
LABEL = "Sickle_RGB_1500-1130-770"
PNGDIR = f"{BASE}/pngs_miri_mosaic"

# corner agreement required before the bands may be stacked without
# reprojection, in pixels of the reference grid
MAX_OFFSET_PIX = 1.0


def check_shared_grid(headers, shapes, max_offset_pix=MAX_OFFSET_PIX):
    """Verify the bands really share a grid, by sky footprint not array shape.

    Compares each band's four sky corners against the reference band's and
    reports the worst separation in reference pixels.  Same-shape mosaics on
    different pointings fail here; sub-pixel resampling jitter does not.
    """
    ref_wcs = WCS(headers[REF]).celestial
    scale = float(np.mean(proj_plane_pixel_scales(ref_wcs))) * u.deg
    ref_corners = SkyCoord(ref_wcs.calc_footprint(axes=shapes[REF][::-1]),
                           unit=(u.deg, u.deg))
    worst = 0.0
    for band in FITS:
        if shapes[band] != shapes[REF]:
            raise ValueError(f"{band} shape {shapes[band]} != {shapes[REF]}")
        wcs = WCS(headers[band]).celestial
        corners = SkyCoord(wcs.calc_footprint(axes=shapes[band][::-1]),
                           unit=(u.deg, u.deg))
        off = float((corners.separation(ref_corners) / scale).max())
        print(f"  {band}: max corner offset {off:.3f} pix "
              f"({off * scale.to(u.arcsec).value:.4f}\")")
        worst = max(worst, off)
    if worst > max_offset_pix:
        raise ValueError(
            f"bands differ by up to {worst:.2f} pixels (limit {max_offset_pix}); "
            "these mosaics are on different pointings and must be reprojected "
            "onto a common grid before stacking")
    return worst


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", default=HERE,
                   help="directory the layer is written to (default: the "
                        "directory this script lives in)")
    p.add_argument("--no-coadd", action="store_true",
                   help="skip the jwst_miri_hips rebuild")
    p.add_argument("--max-offset-pix", type=float, default=MAX_OFFSET_PIX,
                   help="largest tolerated corner disagreement between bands, "
                        f"in pixels (default {MAX_OFFSET_PIX})")
    args = p.parse_args()
    os.chdir(args.out_dir)

    if not args.no_coadd:
        check_layers(MIRI_LAYERS, ignore=[f"{LABEL}_transparent_hips"])

    os.makedirs(PNGDIR, exist_ok=True)
    headers = {f: fits.getheader(p_, ext=("SCI", 1)) for f, p_ in FITS.items()}
    data = {f: fits.getdata(p_, ext=("SCI", 1)).astype(float)
            for f, p_ in FITS.items()}
    shapes = {f: d.shape for f, d in data.items()}
    print("Checking the three bands share a grid:")
    check_shared_grid(headers, shapes, args.max_offset_pix)

    def stretch(d):
        return simple_norm(d, stretch="asinh", min_percent=1, max_percent=99.5)(d)

    rgb = np.stack([stretch(data["f1500w"]), stretch(data["f1130w"]),
                    stretch(data["f770w"])], axis=2)
    orig = np.stack([data["f1500w"], data["f1130w"], data["f770w"]], axis=2)

    png = f"{PNGDIR}/{LABEL}.png"
    # hips=False: the pyramid is built below, after the orientation fix.  Left
    # at its default, save_rgb would build a full pyramid here from the
    # uncorrected metadata and leave it on disk unused.
    save_rgb(rgb, png, avm=faithful_avm(headers[REF]), original_data=orig,
             hips=False)

    fix_orientation(png, FITS[REF], label=LABEL, indent="")

    dst = f"{LABEL}.png"
    shutil.copy2(png, dst)
    trans = f"{LABEL}_transparent.png"
    if os.path.exists(trans):
        os.remove(trans)
    t = convert_black_to_transparent(dst)
    if os.path.abspath(t) != os.path.abspath(trans):
        raise ValueError(f"convert_black_to_transparent wrote {t}, expected {trans}")
    build_hips_staged(trans, f"{LABEL}_transparent_hips")

    if args.no_coadd:
        print("Done: Sickle MIRI 2-obs mosaic built (coadd skipped).")
        return
    print("Rebuilding jwst_miri_hips coadd...")
    build_coadd(MIRI_LAYERS, "jwst_miri_hips")
    print("Done: Sickle MIRI 2-obs mosaic built, jwst_miri_hips rebuilt.")


if __name__ == "__main__":
    main()
