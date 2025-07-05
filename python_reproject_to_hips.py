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

def convert_black_to_transparent(image_path):
    """Convert solid black pixels to transparent in an image"""
    img = PIL.Image.open(image_path)

    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    # Convert to numpy array for easier manipulation
    img_array = np.array(img)

    # Find solid black pixels (R=0, G=0, B=0)
    black_pixels = (img_array[:, :, 0] == 0) & (img_array[:, :, 1] == 0) & (img_array[:, :, 2] == 0)

    # Set alpha to 0 for black pixels (make them transparent)
    img_array[black_pixels, 3] = 0

    # Convert back to PIL Image
    img_transparent = PIL.Image.fromarray(img_array, 'RGBA')

    # Save with transparent suffix
    transparent_path = image_path.replace('.png', '_transparent.png').replace('.jpg', '_transparent.jpg')
    img_transparent.save(transparent_path)

    return transparent_path

def main():
    for filename in ['Sickle_RGB_1500-1130-770.png',
                     'SgrA_RGB_MIRI_1500-1000-560.png',
                     'SgrA_RGB_NIRCam_444-323-212.png',
                     'ArchesQuintuplet_RGB_323-average-212_log.png',
                     'SgrB2_2550_770_480_avm.png', 'Cloudef_RGB_4802-3602-2102.png', 'SGRC_RGB_480-360-212.png', 'cloudcJWST_merged_R-F466N_B-F405N_rotated.png', 'SgrB2_RGB_2550-1280-770.png', 'BrickJWST_merged_longwave_narrowband.png', 'BrickJWST_merged_longwave_narrowband_withstars.png', 'BrickJWST_1182p2221_405_356_200.png', 'SgrB2_RGB_480-405-187_scaled.png', 'feathered_MGPS_ALMATCTE7m.png', 'MUSTANG_12m_feather_noaxes.png', 'rgb_final_uncropped.png', 'SgrB2M_RGB.png', 'SgrB2N_RGB.png']:

        try:
            avm = pyavm.AVM.from_image(filename)
        except pyavm.exceptions.NoXMPPacketFound:
            print(f"No XMP packet found for {filename}")
            continue

        # Convert black pixels to transparent
        print(f"Converting black pixels to transparent for {filename}")
        filename_transparent = filename.replace('.png', '_transparent.png').replace('.jpg', '_transparent.jpg')
        if not os.path.exists(filename_transparent):
            filename_transparent = convert_black_to_transparent(filename)

            # Copy AVM metadata to the transparent version
            avm.embed(filename_transparent, filename_transparent)

        # Use the transparent version for processing
        processing_filename = filename_transparent

        output_directory = processing_filename.replace('.png', '_hips').replace('.jpg', '_hips')

        if os.path.exists(output_directory):
            print(f"Found existing directory; skipping {filename}")
            continue
            #shutil.rmtree(output_directory)

        print(filename, processing_filename, output_directory, np.array(PIL.Image.open(processing_filename)).shape ) #pyavm.AVM.from_image(filename))


        # PRESERVE transparency...
        # if np.array(PIL.Image.open(processing_filename)).shape[2] == 4:
        #     print("RGBA image")
        #     filename_noalpha = processing_filename.replace('.png', '_noalpha.png').replace('.jpg', '_noalpha.jpg')
        #     if os.path.exists(filename_noalpha):
        #         processing_filename = filename_noalpha
        #         print(f"Found existing no-alpha image {processing_filename}")
        #     else:
        #         # Convert RGBA to RGB by dropping alpha channel
        #         img = PIL.Image.open(processing_filename)
        #         img_rgb = img.convert('RGB')
        #         img_rgb.save(filename_noalpha)

        #         # restore AVM
        #         avm = pyavm.AVM.from_image(filename)
        #         avm.embed(filename_noalpha, filename_noalpha)

        #         assert np.array(PIL.Image.open(filename_noalpha)).shape[2] == 3

        #         # Update filename to use the no-alpha version
        #         processing_filename = filename_noalpha
        #         output_directory = processing_filename.replace('.png', '_hips').replace('.jpg', '_hips')
        #         print(f"Converted RGBA to RGB: {processing_filename}")

        #print(filename, output_directory, np.array(PIL.Image.open(filename)).shape) #pyavm.AVM.from_image(filename))

        reproject_to_hips(processing_filename,
                    coord_system_out='galactic',
                    level=None,
                    reproject_function=reproject_interp,
                    output_directory=output_directory,
                    threads=8,
                    progress_bar=tqdm)

    # output_directory = 'rgb_final_uncropped_hips'
    # if not os.path.exists(output_directory):
    #     raise("rgb_final_uncropped.jpg did not reproject, which is nonsense. Forcing.")
    #     filename = 'rgb_final_uncropped.jpg'
    #     reproject_to_hips(filename,
    #                 coord_system_out='galactic',
    #                 level=6,
    #                 reproject_function=reproject_interp,
    #                 output_directory=output_directory,
    #                 progress_bar=tqdm)


    from reproject.hips import coadd_hips
    if os.path.exists('AshFigureWithACES'):
        shutil.rmtree('AshFigureWithACES')
    coadd_hips(['rgb_final_uncropped_hips', 'MUSTANG_12m_feather_noaxes_hips'], 'AshFigureWithACES')
    if os.path.exists('AshFigureWithACES_MUSTANGfirst'):
        shutil.rmtree('AshFigureWithACES_MUSTANGfirst')
    coadd_hips(['MUSTANG_12m_feather_noaxes_hips', 'rgb_final_uncropped_hips', ], 'AshFigureWithACES_MUSTANGfirst')

    if os.path.exists('jwst_cmz_hips'):
        shutil.rmtree('jwst_cmz_hips')
    coadd_hips(['cloudcJWST_merged_R-F466N_B-F405N_rotated_transparent_hips',
                'SgrB2_2550_770_480_avm_transparent_hips',
                'SgrB2_RGB_480-405-187_scaled_transparent_hips',
                'Cloudef_RGB_4802-3602-2102_transparent_hips',
                'SGRC_RGB_480-360-212_transparent_hips',
                'BrickJWST_merged_longwave_narrowband_transparent_hips',
                'ArchesQuintuplet_RGB_323-average-212_log_transparent_hips',
                'Sickle_RGB_1500-1130-770_transparent_hips',
                'SgrA_RGB_NIRCam_444-323-212_transparent_hips',
                'SgrA_RGB_MIRI_1500-1000-560_transparent_hips',
                ],
               'jwst_cmz_hips')

if __name__ == "__main__":
    main()