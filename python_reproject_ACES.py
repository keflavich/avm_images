import numpy as np
import os
import shutil
import PIL.Image
import pyavm
from astropy import log
from scipy.ndimage import label, binary_dilation

from tqdm.auto import tqdm
from reproject.hips import reproject_to_hips
from reproject import reproject_interp

import glob


def reproject_image(filename, output_directory):
    try:
        avm = pyavm.AVM.from_image(filename)
    except pyavm.exceptions.NoXMPPacketFound:
        print(f"No XMP packet found for {filename}")
        return

    output_hips = os.path.join(output_directory,
                               filename.replace('.png', '_hips').replace('.jpg', '_hips'))

    if os.path.exists(output_hips):
        print(f"Found existing directory {output_hips}; skipping {filename}")

    else:
        reproject_to_hips(filename,
                    coord_system_out='galactic',
                    level=None,
                    reproject_function=reproject_interp,
                    output_directory=output_hips,
                    threads=8,
                    progress_bar=tqdm)

def main():
    filelist = glob.glob('/orange/adamginsburg/ACES/mosaics/cubes/moments/*max.png') + glob.glob('/orange/adamginsburg/ACES/mosaics/cubes/moments/*hlsig_dilated_masked_mom0.png')
    for filename in tqdm(filelist):
        reproject_image(filename, '/orange/adamginsburg/ACES/mosaics/cubes/moments/hips')


if __name__ == "__main__":
    main()