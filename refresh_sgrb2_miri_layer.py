#!/usr/bin/env python
"""
Refresh the SgrB2_RGB_2550-1280-770 MIRI layer from the CDMatrix-corrected PNG.

The web copy of SgrB2_RGB_2550-1280-770.png dated 2026-07-21 was built with the
old pyavm.AVM.from_header embed; at SgrB2's PA~90 that hits the pyavm
Scale+Rotation degeneracy (fits_avm_check: best_flip=rot180, clean_dihedral=false),
so it renders rot180-flipped in the viewer.  The pipeline was re-run 2026-07-22
with faithful_avm (flat CDMatrix); pngs_150/SgrB2_RGB_2550-1280-770.png is clean
(fits_avm_check identity, 0.0", same 11463x5195 grid).  This copies that corrected
PNG in, rebuilds its edge-transparent version + HiPS, and rebuilds jwst_miri_hips
so the coadd picks up the correct orientation.
"""
import os
import shutil

from PIL import Image
from tqdm import tqdm
from reproject import reproject_interp
from reproject.hips import reproject_to_hips, coadd_hips

from python_reproject_to_hips import convert_black_to_transparent
from rebuild_jwst_cmz_hips import MIRI_LAYERS, build_coadd

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

SRC = "/orange/adamginsburg/jwst/sgrb2/pngs_150/SgrB2_RGB_2550-1280-770.png"
DST = "SgrB2_RGB_2550-1280-770.png"
TRANS = "SgrB2_RGB_2550-1280-770_transparent.png"
HIPS = "SgrB2_RGB_2550-1280-770_transparent_hips"


def main():
    print(f"Copying corrected PNG {SRC} -> {DST}")
    shutil.copy2(SRC, DST)
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
