import numpy as np
import os
import shutil
import PIL.Image
import pyavm
from astropy.wcs import WCS
from astropy import log
from scipy.ndimage import label, binary_dilation

from tqdm.auto import tqdm
from reproject.hips import reproject_to_hips
from reproject import reproject_interp

import glob
from astropy.io import fits

import matplotlib.pyplot as pl
import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap
from astropy.visualization import simple_norm

colors1 = pl.cm.gray_r(np.linspace(0., 1, 128))
colors2 = pl.cm.hot(np.linspace(0, 1, 128))

colors = np.vstack((colors1, colors2))
mymap = LinearSegmentedColormap.from_list('my_colormap', colors)



for fn in (
"/Users/adam/work/w51/alma/w51n.spw0thru19.14500.robust0.thr0.075mJy.mfs.I.startmod.selfcal7.image.tt0.pbcor.fits",
"/Users/adam/work/w51/alma/w51n.spw0thru19.14500.robust0.thr0.1mJy.mfs.I.startmod.selfcal7.image.tt0.pbcor.fits",
"/Users/adam/work/w51/alma/w51e2.spw0thru19.14500.robust0.thr0.15mJy.mfs.I.startmod.selfcal7.image.tt0.pbcor.fits",
"/Users/adam/work/w51/alma/w51e2.spw0thru19.14500.robust0.thr0.075mJy.mfs.I.startmod.selfcal7.image.tt0.pbcor.fits",
):
    fh = fits.open(fn)
    norm = simple_norm(fh[0].data, vmin=-5e-6, vmax=3e-3, stretch='log')#min_percent=1, max_percent=99.995, stretch='log')
    cmap = mymap
    colored = cmap(norm(fh[0].data.squeeze()[600:-600, 600:-600]))
    #alpha = colored[:,:,3]
    #alpha[~np.isfinite(fh[0].data.squeeze())] = 0

    print(colored.mean(), colored.std(), 'size', colored.size, colored.size/4/178956970)

    #img_transparent = PIL.Image.fromarray(colored, 'RGBA')

    transparent_path = fn.replace(".fits", ".png")
    #img_transparent.save(transparent_path)
    pl.imsave(transparent_path, colored[::-1, :, :])
    print(f"saved {fn}", flush=True)

    ww = WCS(fh[0].header).celestial[600:-600, 600:-600]
    # these might be swapped, but it's ok b/c it's symmetric
    ww._naxis1 = colored.shape[0]
    ww._naxis2 = colored.shape[1]
    avm = pyavm.AVM.from_wcs(ww)
    avm.embed(transparent_path, transparent_path)
