#!/usr/bin/env python3
"""Generate the JWST CMZ Aladin Lite viewer index.html.

Enumerates every valid HiPS dir in the web avm_images folder, groups them by
target, and emits toggle buttons.  jwst_nir_hips + jwst_miri_hips are the two
default-on overlay layers.
"""
import os
import html

WEB = "/orange/adamginsburg/web/public/avm_images"

# default-on overlay layers (bottom -> top)
DEFAULT_ON = ["jwst_miri_hips", "jwst_nir_hips"]

# ordered (group title, predicate) -- first match wins
def _grp(name):
    n = name.lower()
    if name in ("jwst_cmz_hips", "jwst_nir_hips", "jwst_miri_hips"):
        return "CMZ full mosaics"
    if n.startswith("rgb_final_uncropped") or n.startswith("gc_fullres"):
        return "CMZ full mosaics"
    if any(k in n for k in ("_check_", "_identity_", "_test_", "brick200",
                            "_restored_hips")):
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


def main():
    dirs = []
    for d in sorted(os.listdir(WEB)):
        if not d.endswith("_hips"):
            continue
        p = os.path.join(WEB, d)
        if os.path.islink(p) or os.path.isfile(os.path.join(p, "properties")):
            dirs.append(d)

    groups = {}
    for d in dirs:
        groups.setdefault(_grp(d), []).append(d)

    # prefer transparent variant when both transparent+plain exist; keep both
    # available but mark plain ones.
    def has_transparent_twin(name):
        if name.endswith("_transparent_hips"):
            return False
        base = name[: -len("_hips")]
        return (base + "_transparent_hips") in dirs

    parts = []
    for g in GROUP_ORDER:
        if g not in groups:
            continue
        names = groups[g]
        # transparent first, then plain
        names = sorted(names, key=lambda x: (not x.endswith("_transparent_hips"), x))
        gid = g.lower().replace(" ", "-").replace("/", "").replace("(", "").replace(")", "")
        buttons = []
        for name in names:
            lbl = html.escape(short_label(name))
            default = name in DEFAULT_ON
            cls = "layer-btn hips-btn " + gid + (" active" if default else "")
            title = html.escape(name)
            plain = " plain" if has_transparent_twin(name) else ""
            buttons.append(
                f'<button class="{cls}{plain}" data-layer="{html.escape(name)}" '
                f'title="{title}">{lbl}</button>'
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

    groups_html = "\n".join(parts)

    default_js = ", ".join(f'"{n}"' for n in DEFAULT_ON)

    page = TEMPLATE.replace("__GROUPS__", groups_html).replace("__DEFAULT_ON__", default_js)
    out = "/blue/adamginsburg/adamginsburg/tmp/claude-3663/-orange-adamginsburg-jwst-jwst-scripts/461d110c-a961-4d9b-b0dc-af3002dcd6e4/scratchpad/index_new.html"
    with open(out, "w") as fh:
        fh.write(page)
    print(f"wrote {out} ({len(dirs)} layers, {len(parts)} groups)")


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
    button.hips-btn.plain{opacity:.7;font-style:italic}
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
    document.querySelectorAll('button.hips-btn.' + grp).forEach(b => {
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
// JWST program 6927 (Brick NIRSpec MSA, 4 pointings) target list, from the
// APT file 6927.aptx. The 4 pointings coincide to ~0.2"; PA~228.86 deg.
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
});
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
