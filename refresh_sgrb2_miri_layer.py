#!/usr/bin/env python
"""
Refresh the SgrB2_RGB_2550-1280-770 MIRI layer with the correct orientation.

Two problems stacked here:

1. The web copy dated 2026-07-21 used the old pyavm.AVM.from_header embed; at
   SgrB2's PA~90 that hits the pyavm Scale+Rotation degeneracy (fits_avm_check:
   best_flip=rot180, clean_dihedral=false).

2. The re-run pipeline PNG (pngs_150/SgrB2_RGB_2550-1280-770.png, same 11463x5195
   grid) embeds a *self-consistent* flat CDMatrix AVM (fits_avm_check identity,
   0.0"), BUT save_rgb lays SgrB2 pixels with transpose=ROTATE_180, so an
   identity-of-FITS AVM still renders the field rot180-flipped on sky.  The
   VISUAL checker (check_hips_orientation.py, forward-reproject vs MIRI F770W)
   confirms: identity AVM -> best=rot180; a rot180 CDMatrix AVM -> best=identity
   (corr 0.907).

So: copy the pipeline pixels in, but embed a rot180 CDMatrix AVM (the dihedral
of the FITS grid that matches the ROTATE_180 pixel layout), then rebuild the
edge-transparent PNG + HiPS and rebuild jwst_miri_hips.
"""
import os
import shutil
import sys

from PIL import Image
from tqdm import tqdm
from reproject import reproject_interp
from reproject.hips import reproject_to_hips, coadd_hips

from python_reproject_to_hips import convert_black_to_transparent
from rebuild_jwst_cmz_hips import MIRI_LAYERS, build_coadd

sys.path.insert(0, "/orange/adamginsburg/jwst/jwst_scripts/scripts")
from apply_cdmatrix_flip import load_wcs_shape, cdmatrix_avm  # noqa: E402

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

SRC = "/orange/adamginsburg/jwst/sgrb2/pngs_150/SgrB2_RGB_2550-1280-770.png"
# any reprj_f150 FITS shares the 11463x5195 target grid WCS
GRID = ("/orange/adamginsburg/jwst/sgrb2/data_reprojected/"
        "jw05365-o001_t001_nircam_clear-f466n-merged_i2d_pipeline_v0.1_reprj_f150.fits")
FLIP = "rot180"  # matches save_rgb transpose=ROTATE_180 pixel layout for SgrB2
DST = "SgrB2_RGB_2550-1280-770.png"
TRANS = "SgrB2_RGB_2550-1280-770_transparent.png"
HIPS = "SgrB2_RGB_2550-1280-770_transparent_hips"


def main():
    print(f"Copying pipeline PNG {SRC} -> {DST}")
    shutil.copy2(SRC, DST)
    print(f"Embedding {FLIP} CDMatrix AVM (grid {GRID})")
    fwcs, ny, nx = load_wcs_shape(GRID)
    avm = cdmatrix_avm(fwcs, ny, nx, FLIP)
    tmp = "avm_" + DST
    avm.embed(DST, tmp)
    shutil.move(tmp, DST)
    for stale in (TRANS, HIPS):
        if os.path.isdir(stale):
            print(f"Removing stale dir {stale}")
            shutil.rmtree(stale)
        elif os.path.exists(stale):
            print(f"Removing stale file {stale}")
            os.remove(stale)
    print("Building edge-transparent PNG...")
    trans = convert_black_to_transparent(DST)
    assert os.path.abspath(trans) == os.path.abspath(TRANS), trans
    print(f"Reprojecting {TRANS} -> {HIPS}")
    reproject_to_hips(TRANS, coord_system_out='galactic', level=None,
                      reproject_function=reproject_interp,
                      output_directory=HIPS, threads=8, progress_bar=tqdm)
    print("Rebuilding jwst_miri_hips coadd...")
    build_coadd(MIRI_LAYERS, 'jwst_miri_hips')
    print("Done: sgrb2 MIRI layer refreshed, jwst_miri_hips rebuilt.")


if __name__ == "__main__":
    main()
