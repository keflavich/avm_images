#!/usr/bin/env python3
"""Generate the JWST CMZ Aladin Lite viewer index.html.

Enumerates every publishable HiPS dir in an avm_images tree, groups them by
target, and emits toggle buttons.  jwst_nir_hips + jwst_miri_hips are the two
default-on overlay layers.

Terms: a *layer* is one `*_hips` directory (a HiPS = Hierarchical Progressive
Survey, the nested sky-tile pyramid Aladin reads); a *coadd* is a HiPS built by
stacking several layers.

What is deliberately NOT published (see EXCLUDE_PATTERNS and
has_transparent_twin): orientation-QA renders, `*_stale` / `*_flipped_aug`
snapshots, and any plain `X_hips` whose edge-transparent twin
`X_transparent_hips` also exists.  Those twins carry the same visible label as
the corrected layer while some of them are the mis-registered pre-fix builds, so
listing both put a broken layer one click from the good one under an identical
name.  `--include-diagnostics` restores them for local inspection.

The page loads Aladin Lite and its background surveys from CDS; if CDS is
unreachable the viewer does not come up.  That is inherent to an Aladin viewer
and there is no local fallback.

Usage:
  gen_index.py [--web DIR] [--out FILE] [--include-diagnostics]
"""
import argparse
import html
import os
import re

WEB = "/orange/adamginsburg/web/public/avm_images"

# default-on overlay layers (bottom -> top, so jwst_nir_hips paints over
# jwst_miri_hips where NIRCam/NIRISS coverage exists)
DEFAULT_ON = ["jwst_miri_hips", "jwst_nir_hips"]

# layers never published to the viewer: deliberately-wrong orientation renders,
# superseded snapshots, and flood-fill experiments
EXCLUDE_PATTERNS = [
    re.compile(p) for p in (
        r"_test_", r"_check_", r"_identity_", r"_stale$", r"_flipped_aug$",
        r"_flooded$",
    )
]


def is_diagnostic(name):
    n = name.lower()
    return any(p.search(n) for p in EXCLUDE_PATTERNS)


# ordered (group title, predicate) -- first match wins
def _grp(name):
    n = name.lower()
    if name in ("jwst_cmz_hips", "jwst_nir_hips", "jwst_miri_hips"):
        return "CMZ full mosaics"
    if n.startswith("rgb_final_uncropped") or n.startswith("gc_fullres"):
        return "CMZ full mosaics"
    if is_diagnostic(n):
        return "Diagnostics / orientation QA"
    if n.startswith("brick") or n.startswith("brickjwst"):
        return "Brick"
    if n.startswith("sgra"):
        return "Sgr A*"
    if n.startswith("sgrb2"):
        return "Sgr B2"
    if n.startswith("sgrc"):
        return "Sgr C (NIRCam/NIRISS)"
    if n.startswith("cloudc"):
        return "Cloud C"
    if n.startswith("cloudef"):
        return "Cloud e/f"
    if n.startswith("sickle"):
        return "Sickle"
    if "quintuplet" in n or n.startswith("arches"):
        return "Arches / Quintuplet"
    if n.startswith("gc2211"):
        return "GC2211 per-OBS"
    if n.startswith("w51"):
        return "W51"
    if n.startswith("wd2"):
        return "Westerlund 2"
    if n.startswith("ngc6334"):
        return "NGC 6334"
    if n.startswith("trapezium") or n.startswith("heic"):
        return "Orion / misc extragalactic"
    if n.startswith("mustang") or n.startswith("feathered") or n.startswith("aces"):
        return "Radio (MUSTANG / feathered)"
    return "Other"


GROUP_ORDER = [
    "CMZ full mosaics", "Brick", "Sgr A*", "Sgr B2",
    "Sgr C (NIRCam/NIRISS)", "Cloud C", "Cloud e/f", "Sickle",
    "Arches / Quintuplet", "GC2211 per-OBS", "W51", "Westerlund 2",
    "NGC 6334", "Orion / misc extragalactic", "Radio (MUSTANG / feathered)",
    "Other", "Diagnostics / orientation QA",
]


def short_label(name):
    lbl = name
    for suf in ("_transparent_hips", "_hips"):
        if lbl.endswith(suf):
            lbl = lbl[: -len(suf)]
            break
    return lbl


def group_id(title):
    """CSS/attribute-safe id for a group title.

    Only [a-z0-9-] survives: 'Sgr A*' has to become 'sgr-a', because '*' is not
    a valid CSS identifier character and made `querySelectorAll` throw on the
    group's all/none buttons.
    """
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def collect(web, include_diagnostics=False):
    """Return the layer directory names to publish, in listing order."""
    found = []
    for d in sorted(os.listdir(web)):
        if not d.endswith("_hips"):
            continue
        # follows symlinks, so a symlinked layer needs no special case and a
        # broken symlink is dropped rather than published as a dead button
        if os.path.isfile(os.path.join(web, d, "properties")):
            found.append(d)

    def has_transparent_twin(name):
        if name.endswith("_transparent_hips"):
            return False
        return (name[: -len("_hips")] + "_transparent_hips") in found

    return [d for d in found
            if (include_diagnostics or not is_diagnostic(d))
            and not has_transparent_twin(d)]


def build_page(dirs):
    groups = {}
    for d in dirs:
        groups.setdefault(_grp(d), []).append(d)

    parts = []
    for g in GROUP_ORDER:
        if g not in groups:
            continue
        # transparent first, then plain
        names = sorted(groups[g],
                       key=lambda x: (not x.endswith("_transparent_hips"), x))
        gid = group_id(g)
        buttons = []
        for name in names:
            lbl = html.escape(short_label(name))
            cls = "layer-btn hips-btn" + (" active" if name in DEFAULT_ON else "")
            buttons.append(
                f'<button class="{cls}" data-grp="{gid}" '
                f'data-layer="{html.escape(name)}" '
                f'title="{html.escape(name)}">{lbl}</button>'
            )
        parts.append(f'''    <div class="section">
      <div class="section-label">{html.escape(g)}
        <span class="grp-mini">
          <button class="mini-btn" data-grp="{gid}" data-on="1">all</button>
          <button class="mini-btn" data-grp="{gid}" data-on="0">none</button>
        </span>
      </div>
      <div class="btn-row">
        {chr(10).join("        " + b for b in buttons).strip()}
      </div>
    </div>''')

    default_js = ", ".join(f'"{n}"' for n in DEFAULT_ON)
    return (TEMPLATE.replace("__GROUPS__", "\n".join(parts))
                    .replace("__DEFAULT_ON__", default_js), len(parts))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--web", default=WEB,
                   help=f"avm_images tree to enumerate (default {WEB})")
    p.add_argument("--out", default=None,
                   help="output HTML file (default: index.html inside --web)")
    p.add_argument("--include-diagnostics", action="store_true",
                   help="also publish orientation-QA and superseded layers")
    args = p.parse_args()
    out = args.out or os.path.join(args.web, "index.html")

    dirs = collect(args.web, args.include_diagnostics)
    page, ngroups = build_page(dirs)
    with open(out, "w") as fh:
        fh.write(page)
    print(f"wrote {out} ({len(dirs)} layers, {ngroups} groups)")


TEMPLATE = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>JWST CMZ — Aladin Lite</title>
  <meta name="viewport" content="width=device-width, height=device-height, initial-scale=1.0, user-scalable=no">
  <style>
    html,body{height:100%;margin:0;font-family:system-ui,'Segoe UI',Roboto,sans-serif;background:#000}
    #aladin{position:absolute;inset:0}
    #ui{
      position:absolute;top:10px;right:10px;z-index:10;width:288px;
      max-height:calc(100vh - 20px);overflow-y:auto;
      background:rgba(12,12,18,.90);color:#e8e8e8;
      border:1px solid rgba(255,255,255,.12);border-radius:8px;font-size:12px;
      backdrop-filter:blur(6px);
    }
    #ui h3{margin:0;padding:8px 12px;font-size:13px;font-weight:600;
      background:rgba(255,255,255,.06);border-bottom:1px solid rgba(255,255,255,.1);
      position:sticky;top:0;z-index:1}
    .section{padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.07)}
    .section-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;
      color:#8ab4ff;margin-bottom:5px;display:flex;align-items:center;
      justify-content:space-between;gap:4px;flex-wrap:wrap}
    .grp-mini{display:flex;gap:3px}
    .btn-row{display:flex;gap:4px;flex-wrap:wrap}
    button{cursor:pointer;padding:3px 7px;border:1px solid rgba(255,255,255,.18);
      border-radius:4px;background:rgba(255,255,255,.07);color:#ddd;
      font-size:11px;transition:background .15s,color .15s,border-color .15s}
    button:hover{background:rgba(255,255,255,.16);color:#fff}
    button.survey.active{background:rgba(180,180,255,.2);color:#c0c0ff;border-color:#c0c0ff}
    button.layer-btn.active{border-color:#7fd0ff;color:#fff;
      background:rgba(120,190,255,.22);font-weight:600}
    button.cat-btn.active{border-color:var(--bc,#ffdd33);color:var(--bc,#ffdd33);
      background:rgba(255,221,51,.15);font-weight:600}
    .mini-btn{font-size:9px;padding:1px 5px;color:#999;border-color:rgba(255,255,255,.2)}
    .mini-btn:hover{color:#fff}
    .op-row{display:flex;align-items:center;gap:6px;margin-top:4px}
    .op-row input[type=range]{flex:1;accent-color:#64c8ff}
    #info{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);
      z-index:10;pointer-events:none;background:rgba(10,10,15,.72);color:#aaa;
      padding:4px 14px;border-radius:4px;font-size:11px;
      border:1px solid rgba(255,255,255,.1);white-space:nowrap}
    a.legacy{color:#7fd0ff;text-decoration:none;font-size:10px}
  </style>
</head>
<body>
<div id="aladin"></div>

<div id="ui">
  <h3>JWST CMZ HiPS layers</h3>

  <div class="section">
    <div class="section-label">Background survey</div>
    <div class="btn-row">
      <button class="survey active" data-survey="https://alasky.cds.unistra.fr/VISTA/VVV_DR4/VISTA-VVV-DR4-H-Bulge">VVV H</button>
      <button class="survey" data-survey="P/2MASS/color">2MASS</button>
      <button class="survey" data-survey="P/allWISE/color">WISE</button>
      <button class="survey" data-survey="P/DSS2/color">DSS2</button>
      <button class="survey" data-survey="P/GLIMPSE360">GLIMPSE</button>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Overlay opacity</div>
    <div class="op-row">
      <input id="op-range" type="range" min="0" max="1" step="0.05" value="1">
      <span id="op-val" style="width:34px;text-align:right">100%</span>
    </div>
  </div>

  <div class="section">
    <div class="section-label">Catalog overlays</div>
    <div class="btn-row">
      <button class="cat-btn active" data-cat="jwst6927" style="--bc:#ffdd33">JWST 6927 targets</button>
    </div>
  </div>

__GROUPS__

  <div class="section">
    <a class="legacy" href="index_legacy.html">→ legacy flat link list</a>
  </div>
</div>

<div id="info">JWST CMZ — NIR + MIRI mosaics on by default · click layer buttons to toggle</div>

<script src="https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js" charset="utf-8"></script>
<script>
let aladin;
const DEFAULT_ON = [__DEFAULT_ON__];
// Every handler below needs `aladin`, which only exists once A.init resolves.
// Disable the panel until then so a click cannot mark a button active without
// loading anything.
const PANEL_BUTTONS = '#ui button';
document.querySelectorAll(PANEL_BUTTONS).forEach(b => { b.disabled = true; });
const loaded = {};   // layerName -> HiPS object
let overlayOpacity = 1.0;

function addLayer(name){
  if (loaded[name]) return;
  const survey = A.HiPS(name + '/', {name: name});
  aladin.setOverlayImageLayer(survey, name);
  loaded[name] = survey;
  applyOpacity(name);
}
function removeLayer(name){
  if (!loaded[name]) return;
  aladin.removeImageLayer(name);
  delete loaded[name];
}
function applyOpacity(name){
  const s = loaded[name];
  if (!s) return;
  if (typeof s.setAlpha === 'function') s.setAlpha(overlayOpacity);
  else if (typeof s.setOpacity === 'function') s.setOpacity(overlayOpacity);
}

// layer toggle buttons
document.querySelectorAll('button.hips-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const name = btn.dataset.layer;
    if (btn.classList.contains('active')){
      removeLayer(name); btn.classList.remove('active');
    } else {
      if (aladin) addLayer(name);
      btn.classList.add('active');
    }
  });
});

// group all/none
document.querySelectorAll('.mini-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const grp = btn.dataset.grp, on = btn.dataset.on === '1';
    document.querySelectorAll('button.hips-btn[data-grp="' + grp + '"]').forEach(b => {
      const name = b.dataset.layer, isOn = b.classList.contains('active');
      if (on && !isOn){ if (aladin) addLayer(name); b.classList.add('active'); }
      if (!on && isOn){ removeLayer(name); b.classList.remove('active'); }
    });
  });
});

// background survey buttons
document.querySelectorAll('button.survey').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('button.survey').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    if (!aladin) return;
    const tgt = btn.dataset.survey;
    aladin.setBaseImageLayer(A.HiPS(tgt));
  });
});

// opacity slider
const opRange = document.getElementById('op-range');
const opVal = document.getElementById('op-val');
opRange.addEventListener('input', () => {
  overlayOpacity = parseFloat(opRange.value);
  opVal.textContent = Math.round(overlayOpacity * 100) + '%';
  for (const name in loaded) applyOpacity(name);
});

// ── catalog overlays ──────────────────────────────────────────
// JWST program 6927 (Brick NIRSpec MSA): the 4 pointing centres, transcribed
// from the programme's APT target list.  The .aptx file is not in this repo, so
// these literals are the only record here; they coincide to ~0.2", PA~228.86
// deg, and sit on the Brick (l=0.251, b=0.020).
const CATALOGS = {
  jwst6927: {
    name: 'JWST 6927 (Brick NIRSpec MSA)',
    color: '#ffdd33', shape: 'cross', sourceSize: 16,
    sources: [
      {ra: 266.534907, dec: -28.711541, name: 'Brick Pointing 1 of 4', PA: '228.862'},
      {ra: 266.534895, dec: -28.711489, name: 'Brick Pointing 2 of 4', PA: '228.862'},
      {ra: 266.534870, dec: -28.711478, name: 'Brick Pointing 3 of 4', PA: '228.869'},
      {ra: 266.534878, dec: -28.711497, name: 'Brick Pointing 4 of 4', PA: '228.408'},
    ],
  },
};
const catObjs = {};  // id -> Aladin catalog
function addCatalog(id){
  if (catObjs[id] || !aladin) return;
  const c = CATALOGS[id];
  const cat = A.catalog({name: c.name, color: c.color, shape: c.shape,
                         sourceSize: c.sourceSize, labelColumn: 'name',
                         displayLabel: true, labelColor: c.color, labelFont: '11px sans-serif'});
  aladin.addCatalog(cat);
  cat.addSources(c.sources.map(s => A.source(s.ra, s.dec,
      {name: s.name, PA_deg: s.PA, program: 'JWST 6927'})));
  catObjs[id] = cat;
}
function removeCatalog(id){
  if (!catObjs[id]) return;
  aladin.removeLayer ? aladin.removeLayer(catObjs[id]) : catObjs[id].hide();
  delete catObjs[id];
}
document.querySelectorAll('button.cat-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const id = btn.dataset.cat;
    if (btn.classList.contains('active')){ removeCatalog(id); btn.classList.remove('active'); }
    else { addCatalog(id); btn.classList.add('active'); }
  });
});

// Aladin Lite itself, the base surveys and the sky-tile fetches all come from
// CDS; there is no local fallback, so the viewer needs CDS to be reachable.
A.init.then(() => {
  aladin = A.aladin('#aladin', {
    survey:   'https://alasky.cds.unistra.fr/VISTA/VVV_DR4/VISTA-VVV-DR4-H-Bulge',
    target:   '0.2 -0.05',
    fov:      3.2,
    cooFrame: 'galactic',
    showCooGridControl: true,
    showSimbadPointerControl: true,
  });
  // base = VISTA VVV DR4 H Bulge (higher res than 2MASS over the whole bulge FOV)
  aladin.setBaseImageLayer(A.HiPS('https://alasky.cds.unistra.fr/VISTA/VVV_DR4/VISTA-VVV-DR4-H-Bulge'));
  // paint default layers bottom -> top
  for (const name of DEFAULT_ON) addLayer(name);
  // default-on catalog overlays
  document.querySelectorAll('button.cat-btn.active').forEach(b => addCatalog(b.dataset.cat));
  // the panel is live only now that aladin exists
  document.querySelectorAll(PANEL_BUTTONS).forEach(b => { b.disabled = false; });
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
