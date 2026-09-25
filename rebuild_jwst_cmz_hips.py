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

Stacking order: `coadd_hips` uses the LAST input directory where inputs overlap
(reproject/hips/high_level.py: "the last image in the order of
input_directories is used"), so the lists below run bottom -> top and the
gc2211 wide-field layers are listed FIRST to sit underneath the per-target RGB
layers.  (Until 2026-08 they were appended last, which put them on top of the
per-target layers; jwst_nir_hips needs a rebuild for this ordering to take
effect.)

Keep the layer lists in sync with python_reproject_to_hips.py.
"""

import os
import shutil
from reproject.hips import coadd_hips

from hips_naming import stamp_properties
from hips_orientation import replace_dir


HERE = os.path.dirname(os.path.abspath(__file__))


EXTRA_HIPS = [
    # Brick NIRCam RGB (F444W/F356W/F200W), replacing the local
    # Brick_RGB_444-356-200_transparent_hips copy, which had gone stale (the
    # coadd was last rebuilt against a since-superseded version of that
    # directory and carried visible tiling/color-block artifacts across the
    # Brick). Symlinked straight to the canonical build under
    # /orange/adamginsburg/jwst/brick/pngs_444/ -- the same tree served at
    # https://data.rc.ufl.edu/secure/adamginsburg/jwst/brick/pngs_444/ --
    # rather than copied, so avm_images stays in sync with the source.
    ("Brick_RGB_444-356-200_hips",
     "/orange/adamginsburg/jwst/brick/pngs_444/Brick_RGB_444-356-200_hips"),
    # Cloud E/F MIRI (program 2092), F770W + F2100W.  o004+o008 are the main
    # field's two MIRI tiles; the control field's MIRI pointing (o006) is a
    # SEPARATE field, ~0.2 deg away, despite living in the cloudef/ directory
    # tree -- see scripts/cloudef_miri_images.py's module docstring for how
    # that was confirmed from the mosaic headers rather than the directory
    # name. Built by cloudef_miri_images.py --all in jwst_scripts.
    ("Cloudef_MIRI_F770W_hips",
     "/orange/adamginsburg/jwst/cloudef/pngs_miri/Cloudef_MIRI_F770W_hips"),
    ("Cloudef_MIRI_F2100W_hips",
     "/orange/adamginsburg/jwst/cloudef/pngs_miri/Cloudef_MIRI_F2100W_hips"),
    ("CloudefControl_MIRI_F770W_hips",
     "/orange/adamginsburg/jwst/cloudef_controlfield/pngs_miri/"
     "CloudefControl_MIRI_F770W_hips"),
    ("CloudefControl_MIRI_F2100W_hips",
     "/orange/adamginsburg/jwst/cloudef_controlfield/pngs_miri/"
     "CloudefControl_MIRI_F2100W_hips"),
]


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


# NIRCam + NIRISS layers (bottom -> top; last entry wins on overlap).
NIR_LAYERS = [name for name, _ in GC2211_HIPS] + [   # NIRCam wide-field, bottom
    'cloudcJWST_merged_R-F466N_B-F405N_rotated_transparent_hips',   # NIRCam
    'SgrB2_RGB_480-405-187_scaled_transparent_hips',                # NIRCam
    'Cloudef_RGB_4802-3602-2102_transparent_hips',                  # NIRCam
    # cloud e/f CONTROL field (prog 2092 o005) -- a SEPARATE pointing at
    # l=0.4137 b=+0.1899, ~0.2 deg from the main cloudef field at l=0.4857
    # b=+0.0074, with no overlap, so it is its own layer rather than merged in.
    'CloudefControl_RGB_480-360-210_hips',                          # NIRCam
    'SGRC_RGB_480-360-212_transparent_hips',                        # NIRCam
    # NIRISS Sgr C parallel field (proj 4147, F480M/F356W/F200W), faithful
    # CDMatrix AVM.  Above the NIRCam SgrC layer so it fills its offset coverage.
    'SGRC_NIRISS_RGB_480-356-200_transparent_hips',                 # NIRISS
    'Brick_RGB_444-356-200_hips',                                   # NIRCam
    'BrickJWST_merged_longwave_narrowband_transparent_hips',        # NIRCam
    'ArchesQuintuplet_RGB_323-average-212_log_transparent_hips',    # NIRCam
    'Quintuplet_RGB_323-average-212_log_transparent_hips',          # NIRCam
    'SgrA_RGB_NIRCam_444-323-212_transparent_hips',                 # NIRCam
]


# All MIRI coverage across the CMZ fields (bottom -> top; last wins on overlap).
MIRI_LAYERS = [
    # cloud C MIRI is two separate grayscale fields with different pointings:
    # F2550W from program 2221, F770W from program 2526.  The old combined RGB
    # (CloudC_MIRI_RGB_2550-770-770) reprojected F2550W onto the F770W grid,
    # cropping it to a corner, and no longer exists on disk.
    'CloudC_MIRI_F770W_transparent_hips',              # cloudc F770W (prog 2526)
    'CloudC_MIRI_F2550W_transparent_hips',             # cloudc F2550W (prog 2221)
    'Brick_RGB_1500-1130-770_transparent_hips',        # brick MIRI
    # brick F2550W monochrome, native 2858x1058 grid (no reprojection onto a
    # finer NIRCam grid the 25um data cannot support).  Corrected per-group
    # re-reduction, MIRICOR='20260904pergroup' in the SCI header.
    'Brick_MIRI_F2550W_hips',                          # brick F2550W mono
    'SgrB2_RGB_2550-1280-770_transparent_hips',        # sgrb2 full-MIRI F2550W
    'Sickle_RGB_1500-1130-770_transparent_hips',       # sickle MIRI
    'SgrA_RGB_MIRI_1500-1000-560_transparent_hips',    # sgra MIRI
    'Cloudef_MIRI_F770W_hips',                         # cloudef MIRI (prog 2092 o004+o008)
    'Cloudef_MIRI_F2100W_hips',                        # cloudef MIRI (prog 2092 o004+o008)
    'CloudefControl_MIRI_F770W_hips',                  # cloudef control MIRI (prog 2092 o006)
    'CloudefControl_MIRI_F2100W_hips',                 # cloudef control MIRI (prog 2092 o006)
]


def ensure_symlink(link_name, target):
    if os.path.islink(link_name) or os.path.exists(link_name):
        if os.path.islink(link_name) and os.readlink(link_name) == target:
            return
        os.remove(link_name) if os.path.islink(link_name) else shutil.rmtree(link_name)
    os.symlink(target, link_name)
    print(f"  linked {link_name} -> {target}")


def unreadable_layers(layers):
    """Which inputs coadd_hips would fail to read.

    It opens every layer's properties before writing anything, and
    reproject_to_hips writes a layer's tiles first and its properties last, so
    a directory that exists with tiles in it may still be mid-build.
    """
    bad = []
    for layer in layers:
        if not os.path.isdir(layer):
            bad.append(f"{layer}: missing")
        elif not os.path.exists(os.path.join(layer, "properties")):
            bad.append(f"{layer}: no properties (still building?)")
        elif not os.path.isdir(os.path.join(layer, "Norder3")):
            bad.append(f"{layer}: no Norder3")
    return bad


def check_layers(layers, ignore=()):
    """Raise if any input layer is unusable, skipping ones about to be rebuilt.

    Call this before a script starts replacing published layers, so an
    unsatisfiable coadd fails while the web tree is still intact.  `ignore`
    names the layers the caller is about to rebuild, which legitimately do not
    exist yet -- or exist mid-build, which is why the check is
    `unreadable_layers` rather than a bare isdir.
    """
    bad = unreadable_layers([x for x in layers if x not in ignore])
    if bad:
        raise FileNotFoundError(
            "Layer(s) not usable for the coadd: " + "; ".join(bad))


def build_coadd(layers, out):
    """Coadd into <out>.new, then swap it into place.

    avm_images is the live docroot.  Rebuilding in place leaves a partial HiPS
    served under that name for the length of the rebuild, and leaves it there
    for good if the rebuild fails.
    """
    bad = unreadable_layers(layers)
    if bad:
        print(f"NOT rebuilding {out}: {len(bad)} input layer(s) unreadable")
        for b in bad:
            print(f"  {b}")
        raise FileNotFoundError(f"{len(bad)} unreadable input layer(s) for {out}")

    stage = out + ".new"
    if os.path.islink(stage):
        os.remove(stage)
    elif os.path.exists(stage):
        shutil.rmtree(stage)
    print(f"Coadding {len(layers)} layers -> {stage}")
    coadd_hips(layers, stage)
    # coadd_hips copies all_properties[0], so without this the coadd is, to a
    # HiPS client, the same dataset as whichever field sorted first.  The
    # staging name is declined by describe(), hence name=out.
    stamp_properties(stage, name=os.path.basename(out))

    # Only now is the live tree touched.  A crash above leaves it serving.
    # replace_dir removes a symlinked destination rather than renaming it,
    # which matters because several layers here are symlinks into build trees.
    replace_dir(stage, out)
    print(f"Done: {out}")


def main():
    os.chdir(HERE)
    print("Linking extra HiPS into avm_images...")
    for link, target in EXTRA_HIPS + GC2211_HIPS:
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
