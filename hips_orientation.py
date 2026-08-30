#!/usr/bin/env python
"""
Shared orientation check + staged HiPS publication helpers.

Glossary (these terms recur throughout this repo):

  AVM       Astronomy Visualization Metadata -- the world coordinate solution
            embedded inside the PNG/JPEG itself (XMP), which is what Aladin and
            reproject read when they place an image on the sky.
  CDMatrix  the AVM field holding the 2x2 pixel->sky matrix (the AVM analogue of
            the FITS CDi_j keywords).
  HiPS      Hierarchical Progressive Survey -- the directory of nested sky tiles
            an Aladin layer is served from.
  i2d       the JWST pipeline's resampled ("stage 3") mosaic product.
  layer     one published `*_hips` directory.
  coadd     a HiPS built by stacking several layer HiPSs (`coadd_hips`).

Why an orientation check is needed at all: `jwst_rgb.save_rgb` lays pixels down
with `transpose=Image.ROTATE_180`, while `faithful_avm` embeds the FITS CDMatrix
unchanged.  For some position angles that pairing renders the image rotated by
180 degrees relative to the sky even though the metadata is self-consistent, so
the flip has to be *measured* rather than assumed.

`visual_best_flip` below reprojects each of the four dihedrals of the PNG
luminance through the embedded AVM onto the reference FITS grid and keeps the
best correlation.  Note the difference from `check_hips_orientation.py` in
jwst_scripts, which flips the *reprojected* image instead: both are
self-consistent, and this module exists so the semantics used by the build
scripts live in exactly one place instead of being copied per script.
"""
import importlib.util
import os
import shutil

import numpy as np
from PIL import Image
from reproject import reproject_interp
from reproject.hips import reproject_to_hips
from tqdm import tqdm

JWST_SCRIPTS = os.environ.get(
    "JWST_SCRIPTS", "/orange/adamginsburg/jwst/jwst_scripts/scripts")

_spec = importlib.util.spec_from_file_location(
    "chk", os.path.join(JWST_SCRIPTS, "check_hips_orientation.py"))
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

DIHEDRALS = ("identity", "fliplr", "flipud", "rot180")


def visual_best_flip(png, fits_path):
    """Return (dihedral, correlation) the HiPS would show relative to the sky.

    `identity` means the embedded AVM already places the pixels correctly.
    """
    import pyavm
    fw, fdata = chk.load_fits_wcs_and_data(fits_path)
    im = Image.open(png).convert("RGB")
    lum = np.asarray(im).mean(2).astype(float)[::-1, :]  # PIL top-origin -> bottom
    awcs = pyavm.AVM.from_image(png).to_wcs().celestial
    variants = {"identity": lum, "fliplr": lum[:, ::-1],
                "flipud": lum[::-1, :], "rot180": lum[::-1, ::-1]}
    best, bestc = "identity", -2.0
    for name in DIHEDRALS:
        rep, _ = reproject_interp((variants[name], awcs), fw, shape_out=fdata.shape)
        m = np.isfinite(rep) & np.isfinite(fdata)
        a = rep[m] - rep[m].mean()
        b = fdata[m] - fdata[m].mean()
        c = float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-30))
        if c > bestc:
            best, bestc = name, c
    return best, bestc


def fix_orientation(png, fits_path, label="", indent="  "):
    """Measure the flip, re-embed the matching CDMatrix AVM, re-measure.

    Raises RuntimeError if the corrected image still does not land on identity.
    """
    from apply_cdmatrix_flip import load_wcs_shape, cdmatrix_avm

    best, c = visual_best_flip(png, fits_path)
    print(f"{indent}visual best (raw faithful_avm) = {best} (corr {c:.3f})")
    if best == "identity":
        return best
    fwcs, ny, nx = load_wcs_shape(fits_path)
    avm = cdmatrix_avm(fwcs, ny, nx, best)
    tmp = png + ".t.png"
    avm.embed(png, tmp)
    shutil.move(tmp, png)
    best2, c2 = visual_best_flip(png, fits_path)
    print(f"{indent}after embedding {best} CDMatrix -> visual best = "
          f"{best2} (corr {c2:.3f})")
    if best2 != "identity":
        raise RuntimeError(f"{label or png}: still {best2} after flip fix")
    return best


def replace_dir(new, dest):
    """Atomically swap `new` into `dest`, then delete whatever `dest` was.

    `os.replace` on a directory requires the destination not to exist, so the
    old tree is first renamed aside; the window in which `dest` is absent is two
    renames long rather than the several minutes a rebuild-in-place takes.
    """
    old = dest + ".old"
    if os.path.exists(old):
        shutil.rmtree(old)
    if os.path.islink(dest):
        os.remove(dest)
    elif os.path.exists(dest):
        os.rename(dest, old)
    os.replace(new, dest)
    if os.path.exists(old):
        shutil.rmtree(old)


def build_hips_staged(png, hips_dir, threads=8):
    """Build a HiPS into a sibling staging dir, then swap it into place.

    The published layer is never deleted before its replacement is complete, so
    a rebuild does not open a 404 window and a run that dies partway leaves the
    previous layer intact.
    """
    staging = hips_dir + ".new"
    if os.path.exists(staging):
        shutil.rmtree(staging)
    print(f"  reprojecting -> {staging}")
    reproject_to_hips(png, coord_system_out="galactic", level=None,
                      reproject_function=reproject_interp,
                      output_directory=staging, threads=threads,
                      progress_bar=tqdm)
    replace_dir(staging, hips_dir)
    print(f"  published {hips_dir}")
