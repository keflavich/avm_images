#!/usr/bin/env python
"""
Rebuild the CMZ JWST HiPS coadds.

Two coadds are produced:

  jwst_nir_hips   -- NIRCam + NIRISS layers only
  jwst_miri_hips  -- all MIRI coverage across the CMZ fields

`jwst_cmz_hips` is a symlink to `jwst_nir_hips` (the NIR coadd is the primary
CMZ product; the historical name is kept for back-compat).

gc2211 per-OBS HiPS (produced by scripts/gc2211_rgb_images.py) are symlinked
into this directory and painted as the lowest NIR layers, overwritten by the
brighter per-target RGB layers above.

Keep the layer lists in sync with python_reproject_to_hips.py.
"""

import os
import shutil
from reproject.hips import coadd_hips


HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


GC2211_HIPS = [
    ("GC2211_o023_F277_asinh_hips",
     "/orange/adamginsburg/jwst/gc2211/pngs/o023/GC2211_o023_F277_asinh_hips"),
    ("GC2211_o028_RGB_277-mean-150_asinh_hips",
     "/orange/adamginsburg/jwst/gc2211/pngs/o028/GC2211_o028_RGB_277-mean-150_asinh_hips"),
    ("GC2211_o046_RGB_277-mean-200_asinh_hips",
     "/orange/adamginsburg/jwst/gc2211/pngs/o046/GC2211_o046_RGB_277-mean-200_asinh_hips"),
    ("GC2211_o049_RGB_277-mean-200_asinh_hips",
     "/orange/adamginsburg/jwst/gc2211/pngs/o049/GC2211_o049_RGB_277-mean-200_asinh_hips"),
    ("GC2211_o050_RGB_277-mean-200_asinh_hips",
     "/orange/adamginsburg/jwst/gc2211/pngs/o050/GC2211_o050_RGB_277-mean-200_asinh_hips"),
]


# NIRCam + NIRISS layers (bottom -> top).
NIR_LAYERS = [
    'cloudcJWST_merged_R-F466N_B-F405N_rotated_transparent_hips',   # NIRCam
    'SgrB2_RGB_480-405-187_scaled_transparent_hips',                # NIRCam
    'Cloudef_RGB_4802-3602-2102_transparent_hips',                  # NIRCam
    'SGRC_RGB_480-360-212_transparent_hips',                        # NIRCam
    # NIRISS Sgr C parallel field (proj 4147, F480M/F356W/F200W), faithful
    # CDMatrix AVM.  Above the NIRCam SgrC layer so it fills its offset coverage.
    'SGRC_NIRISS_RGB_480-356-200_transparent_hips',                 # NIRISS
    'Brick_RGB_444-356-200_transparent_hips',                       # NIRCam
    'BrickJWST_merged_longwave_narrowband_transparent_hips',        # NIRCam
    'ArchesQuintuplet_RGB_323-average-212_log_transparent_hips',    # NIRCam
    'Quintuplet_RGB_323-average-212_log_transparent_hips',          # NIRCam
    'SgrA_RGB_NIRCam_444-323-212_transparent_hips',                 # NIRCam
] + [name for name, _ in GC2211_HIPS]                              # NIRCam


# All MIRI coverage across the CMZ fields (bottom -> top).
MIRI_LAYERS = [
    # cloud C MIRI = two separate grayscale fields (different pointings):
    # F2550W from program 2221, F770W from program 2526.  A combined RGB was
    # wrong (reprojecting one onto the other's grid cropped it to a corner).
    'CloudC_MIRI_F770W_transparent_hips',              # cloudc F770W (prog 2526)
    'CloudC_MIRI_F2550W_transparent_hips',             # cloudc F2550W (prog 2221)
    'Brick_RGB_1500-1130-770_transparent_hips',        # brick MIRI
    'SgrB2_RGB_2550-1280-770_transparent_hips',        # sgrb2 full-MIRI F2550W
    'Sickle_RGB_1500-1130-770_transparent_hips',       # sickle MIRI
    'SgrA_RGB_MIRI_1500-1000-560_transparent_hips',    # sgra MIRI
]


def ensure_symlink(link_name, target):
    if os.path.islink(link_name) or os.path.exists(link_name):
        if os.path.islink(link_name) and os.readlink(link_name) == target:
            return
        os.remove(link_name) if os.path.islink(link_name) else shutil.rmtree(link_name)
    os.symlink(target, link_name)
    print(f"  linked {link_name} -> {target}")


def build_coadd(layers, out):
    for layer in layers:
        if not os.path.isdir(layer):
            raise FileNotFoundError(f"Missing layer: {layer}")
    if os.path.islink(out):
        os.remove(out)
    elif os.path.exists(out):
        print(f"Removing existing {out}")
        shutil.rmtree(out)
    print(f"Coadding {len(layers)} layers -> {out}")
    coadd_hips(layers, out)
    print(f"Done: {out}")


def main():
    print("Linking gc2211 HiPS into avm_images...")
    for link, target in GC2211_HIPS:
        if not os.path.isdir(target):
            raise FileNotFoundError(f"Missing source HiPS: {target}")
        ensure_symlink(link, target)

    build_coadd(NIR_LAYERS, 'jwst_nir_hips')
    build_coadd(MIRI_LAYERS, 'jwst_miri_hips')

    # jwst_cmz_hips == the NIR coadd (historical primary name).
    ensure_symlink('jwst_cmz_hips', os.path.join(HERE, 'jwst_nir_hips'))
    print("All coadds rebuilt.")


if __name__ == "__main__":
    main()
