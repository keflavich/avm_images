#!/usr/bin/env python
"""
Refresh the SGRC_RGB_480-360-212 cmz layer from the CDMatrix-corrected sgrc PNG.

The standalone sgrc HiPS were re-flipped (CDMatrix rot180, verified 0.0" clean).
This copies that corrected PNG into avm_images, rebuilds its edge-transparent
version, and regenerates SGRC_RGB_480-360-212_transparent_hips so the cmz coadd
picks up the correct orientation.  Only the sgrc layer changes; gc2211 layers
are symlinks already pointing at the corrected per-OBS HiPS.
"""
import os
import shutil

from PIL import Image
from tqdm import tqdm
from reproject import reproject_interp
from reproject.hips import reproject_to_hips

from python_reproject_to_hips import convert_black_to_transparent

Image.MAX_IMAGE_PIXELS = None

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

SRC = "/orange/adamginsburg/jwst/sgrc/pngs_480/SGRC_RGB_480-360-212.png"
DST = "SGRC_RGB_480-360-212.png"
TRANS = "SGRC_RGB_480-360-212_transparent.png"
HIPS = "SGRC_RGB_480-360-212_transparent_hips"


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
    print("Done: sgrc layer refreshed.")


if __name__ == "__main__":
    main()
