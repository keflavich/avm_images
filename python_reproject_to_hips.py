import numpy as np
import os
import shutil
import PIL.Image
import pyavm
from astropy import log

from tqdm.auto import tqdm
from reproject.hips import reproject_to_hips
from reproject import reproject_interp

import glob

log.setLevel('INFO')

def main():
    for filename in ['SgrB2_2550_770_480_avm.png', 'Cloudef_RGB_4802-3602-2102.png', 'SGRC_RGB_480-360-212.png', 'cloudcJWST_merged_R-F466N_B-F405N_rotated.png', 'SgrB2_RGB_2550-1280-770.png', 'BrickJWST_merged_longwave_narrowband.png', 'BrickJWST_merged_longwave_narrowband_withstars.png', 'BrickJWST_1182p2221_405_356_200.png', 'SgrB2_RGB_480-405-187_scaled.png', 'feathered_MGPS_ALMATCTE7m.png', 'MUSTANG_12m_feather_noaxes.png', 'rgb_final_uncropped.png', 'SgrB2M_RGB.png', 'SgrB2N_RGB.png']:

        try:
            avm = pyavm.AVM.from_image(filename)
        except pyavm.exceptions.NoXMPPacketFound:
            print(f"No XMP packet found for {filename}")
            continue

        output_directory = filename.replace('.png', '_hips').replace('.jpg', '_hips')

        if os.path.exists(output_directory):
            print(f"Found existing directory; skipping {filename}")
            continue
            #shutil.rmtree(output_directory)

        print(filename, output_directory, np.array(PIL.Image.open(filename)).shape ) #pyavm.AVM.from_image(filename))

        if np.array(PIL.Image.open(filename)).shape[2] == 4:
            print("RGBA image")
            filename_noalpha = filename.replace('.png', '_noalpha.png').replace('.jpg', '_noalpha.jpg')
            if os.path.exists(filename_noalpha):
                filename = filename_noalpha
                print(f"Found existing no-alpha image {filename}")
            else:
                # Convert RGBA to RGB by dropping alpha channel
                img = PIL.Image.open(filename)
                img_rgb = img.convert('RGB')
                img_rgb.save(filename_noalpha)

                # restore AVM
                avm = pyavm.AVM.from_image(filename)
                avm.embed(filename_noalpha, filename_noalpha)

                assert np.array(PIL.Image.open(filename_noalpha)).shape[2] == 3

                # Update filename to use the no-alpha version
                filename = filename_noalpha
                output_directory = filename.replace('.png', '_hips').replace('.jpg', '_hips')
                print(f"Converted RGBA to RGB: {filename}")

        #print(filename, output_directory, np.array(PIL.Image.open(filename)).shape) #pyavm.AVM.from_image(filename))

        reproject_to_hips(filename,
                    coord_system_out='galactic',
                    level=None,
                    reproject_function=reproject_interp,
                    output_directory=output_directory,
                    threaded=True,
                    progress_bar=tqdm)

    output_directory = 'rgb_final_uncropped_hips'
    if not os.path.exists(output_directory):
        raise("rgb_final_uncropped.jpg did not reproject, which is nonsense. Forcing.")
        filename = 'rgb_final_uncropped.jpg'
        reproject_to_hips(filename,
                    coord_system_out='galactic',
                    level=6,
                    reproject_function=reproject_interp,
                    output_directory=output_directory,
                    progress_bar=tqdm)


    from reproject.hips import coadd_hips
    if os.path.exists('AshFigureWithACES'):
        shutil.rmtree('AshFigureWithACES')
    coadd_hips(['rgb_final_uncropped_hips', 'MUSTANG_12m_feather_noaxes_hips'], 'AshFigureWithACES')
    if os.path.exists('AshFigureWithACES_MUSTANGfirst'):
        shutil.rmtree('AshFigureWithACES_MUSTANGfirst')
    coadd_hips(['MUSTANG_12m_feather_noaxes_hips', 'rgb_final_uncropped_hips', ], 'AshFigureWithACES_MUSTANGfirst')

    if os.path.exists('jwst_cmz_hips'):
        shutil.rmtree('jwst_cmz_hips')
    coadd_hips(['cloudcJWST_merged_R-F466N_B-F405N_rotated_hips',
                'SgrB2_RGB_480-405-187_scaled_hips',
                'SgrB2_2550_770_480_avm_hips',
                'Cloudef_RGB_4802-3602-2102_hips',
                'SGRC_RGB_480-360-212_hips',
                'BrickJWST_merged_longwave_narrowband_hips'],
               'jwst_cmz_hips')

if __name__ == "__main__":
    main()