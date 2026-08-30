#!/usr/bin/env python
"""
Refresh one or more NIR release layers from freshly-regenerated pipeline PNGs.

Usage:
  refresh_nir_layer.py arches quintuplet [...]        # refresh named targets
  refresh_nir_layer.py --all                          # every ready target
  refresh_nir_layer.py arches --no-coadd              # skip the coadd rebuild

The 2026 reprocessing left the jwst_nir_hips coadd built from 2025-era PNGs.
For each target this copies the regenerated pipeline PNG into avm_images,
verifies orientation with hips_orientation (a metadata-clean faithful_avm can
still render rot180 because save_rgb lays pixels with transpose=ROTATE_180),
re-embeds the matching CDMatrix AVM if needed, rebuilds the edge-transparent PNG
+ _transparent_hips, and finally rebuilds jwst_nir_hips.  Layers are staged and
swapped in atomically, so a rebuild does not blank the published page.
"""
import argparse
import os
import shutil
import sys

from PIL import Image

sys.path.insert(0, "/orange/adamginsburg/jwst/jwst_scripts/scripts")

from python_reproject_to_hips import convert_black_to_transparent  # noqa: E402
from rebuild_jwst_cmz_hips import NIR_LAYERS, build_coadd, check_layers  # noqa: E402
from hips_orientation import build_hips_staged, fix_orientation  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
HERE = os.path.dirname(os.path.abspath(__file__))

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
        "jw01939-o001_t001_nircam_clear-f212n_i2d_pipeline_v0.1_reprj_f444.fits",
    ),
    # NOTE: the 2026-08 cloudef run added observations (new filters 2105/3605/
    # 4805/7706/21006), which shifted the consecutive-triple combo names, so
    # Cloudef_RGB_4802-3602-2102 was NOT rewritten by it.  The newest copy of
    # that combo is 2026-07-21 -- still far newer than the 2025-06 web copy.
    "cloudef": (
        f"{JW}/cloudef/pngs_480mo/Cloudef_RGB_4802-3602-2102.png",
        f"{JW}/cloudef/data_reprojected/"
        "jw02092-o002_t001_nircam_clear-f210m_i2d_pipeline_v0.1_reprj_f480mo.fits",
    ),
}


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
        fix_orientation(dst, ref, label=target)
    else:
        print(f"  WARNING: reference FITS missing, orientation NOT verified: {ref}")

    trans = f"{label}_transparent.png"
    if os.path.exists(trans):
        os.remove(trans)
    t = convert_black_to_transparent(dst)
    if os.path.abspath(t) != os.path.abspath(trans):
        raise ValueError(f"convert_black_to_transparent wrote {t}, expected {trans}")
    build_hips_staged(trans, f"{label}_transparent_hips")
    return True


def main():
    p = argparse.ArgumentParser()
    p.add_argument("targets", nargs="*", choices=list(TARGETS) + [])
    p.add_argument("--all", action="store_true")
    p.add_argument("--no-coadd", action="store_true")
    p.add_argument("--out-dir", default=HERE,
                   help="directory the layers are written to (default: the "
                        "directory this script lives in)")
    args = p.parse_args()
    os.chdir(args.out_dir)
    todo = list(TARGETS) if args.all else args.targets
    if not todo:
        p.error("name at least one target or pass --all")
    if not args.no_coadd:
        # fail before touching a published layer if the coadd cannot run
        check_layers(NIR_LAYERS)
    done = [t for t in todo if refresh(t)]
    if done and not args.no_coadd:
        print("\nRebuilding jwst_nir_hips coadd...")
        build_coadd(NIR_LAYERS, "jwst_nir_hips")
    print(f"Done: refreshed {done}")


if __name__ == "__main__":
    main()
