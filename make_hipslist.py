#!/usr/bin/env python
"""Stamp descriptive HiPS identities and emit the HiPS list for the network.

The HiPS network is joined by publishing one text file that repeats four
keywords from each HiPS's `properties` (CDS, Thomas Boch).  The list has to
point at the copies that are actually served, which for this tree means
starformation.astro.ufl.edu rather than the /orange docroot -- see
`push_trees.sh`.

Three steps, in order:

  --check   report which served HiPS still carry a builder UUID or a
            placeholder obs_title
  --stamp   write creator_did / obs_title / hips_creator into the docroot
            copy and the served copy
  --list    emit `hipslist` from the served copies

The identity keywords live in the properties file, so a rebuild of a layer
overwrites them: `reproject` writes a fresh uuid4 each time it tiles.  --stamp
is therefore re-runnable and --check exists to find the drift after a rebuild.
"""

import argparse
import os
import re
import subprocess
import sys

import hips_naming

DOCROOT = "/orange/adamginsburg/web/public/avm_images"
REMOTE_HOST = "starformation"
REMOTE_ROOT = ("/h/cnswww-starformation.astro/starformation.astro.ufl.edu"
               "/htdocs/avm_images")
BASE_URL = "https://starformation.astro.ufl.edu/avm_images"
LIST_URL = f"{BASE_URL}/hipslist"

CREATOR = "Adam Ginsburg (University of Florida)"

# Keys this script owns.  Everything else in a properties file is the
# builder's and is passed through untouched.
OWNED = ("creator_did", "obs_title", "hips_creator")


def parse_properties(text):
    """Ordered (key, value) pairs; comments and blanks keep their position."""
    out = []
    for line in text.splitlines():
        m = re.match(r"^(\w+)\s*=\s*(.*)$", line)
        out.append((m.group(1), m.group(2).strip()) if m else (None, line))
    return out


def render_properties(pairs):
    return "".join(f"{k:<20} = {v}\n" if k else f"{v}\n" for k, v in pairs)


def restamp(text, did, title):
    """Properties text with our keys set, others left alone."""
    pairs = [(k, v) for k, v in parse_properties(text) if k not in OWNED]
    new = dict(creator_did=did, obs_title=title, hips_creator=CREATOR)
    # creator_did leads the file by convention, the rest follow it.
    return render_properties([("creator_did", new["creator_did"]),
                              ("obs_title", new["obs_title"]),
                              ("hips_creator", new["hips_creator"])] + pairs)


def remote_run(cmd):
    return subprocess.run(["ssh", REMOTE_HOST, cmd], capture_output=True,
                          text=True, check=True).stdout


def served_names():
    """HiPS directories on the serving host, as a sorted list."""
    out = remote_run(
        f"cd {REMOTE_ROOT} && for d in */; do "
        f'[ -f "$d/properties" ] && echo "${{d%/}}"; done')
    return sorted(x for x in out.split() if x)


def served_properties(names):
    """{name: properties text} fetched in one ssh round trip."""
    script = (f"cd {REMOTE_ROOT} && for d in " + " ".join(names) + "; do "
              'echo "===HIPS:$d"; cat "$d/properties"; done')
    blocks = remote_run(script).split("===HIPS:")
    got = {}
    for b in blocks:
        if not b.strip():
            continue
        head, _, body = b.partition("\n")
        got[head.strip()] = body
    return got


def served_tiles(names):
    """{name: 1 if the tree holds at least one tile, else 0}.

    A HiPS whose directories exist but hold no tiles serves HTTP 403 or an
    empty listing, with nothing to say it is broken -- 12 Brick layers sat
    like that on this host from 2025 until they were re-pushed.  Advertising
    one would publish a dead entry, so tile presence gates the list.

    `find -L` because most entries here are symlinks into a per-project tree
    (Brick_RGB_444-356-200_hips -> ../jwst/...); without it find stops at the
    link and calls every one of them empty.  The script goes over stdin
    rather than as an ssh argument: it is quoted twice otherwise, once by
    python and once by the remote shell, and the second round silently turns
    the -name pattern into a literal that matches nothing.
    """
    script = f"""cd {REMOTE_ROOT} || exit 1
while read -r d; do
  n=$(find -L "$d" -name 'Npix*' -print -quit 2>/dev/null | wc -l)
  echo "$d|$n"
done
"""
    proc = subprocess.run(["ssh", REMOTE_HOST, "bash -s"],
                          input=script + "\n".join(names) + "\n",
                          capture_output=True, text=True, check=True)
    out = {}
    for line in proc.stdout.splitlines():
        name, _, n = line.partition("|")
        if name.strip():
            out[name.strip()] = int(n.strip() or 0)
    return out


def value(text, key):
    for k, v in parse_properties(text):
        if k == key:
            return v
    return None


def plan(names):
    """[(name, did, title)] for the HiPS that belong in the list."""
    rows = []
    for n in names:
        described = hips_naming.describe(n)
        if described is None:
            continue
        rows.append((n, described[0], described[1]))
    empty = [n for n, c in served_tiles([r[0] for r in rows]).items() if c == 0]
    if empty:
        print(f"no tiles, left out of the list: {', '.join(sorted(empty))}")
        rows = [r for r in rows if r[0] not in empty]
    dupes = {d for d in (r[1] for r in rows)
             if [r[1] for r in rows].count(d) > 1}
    if dupes:
        raise SystemExit(f"duplicate creator_did: {sorted(dupes)}")
    return rows


def cmd_check(args):
    names = served_names()
    rows = plan(names)
    props = served_properties([r[0] for r in rows])
    stale = 0
    for name, did, title in rows:
        text = props.get(name, "")
        now_did, now_title = value(text, "creator_did"), value(text, "obs_title")
        if now_did != did or now_title != title:
            stale += 1
            if args.verbose:
                print(f"{name}\n  did   {now_did} -> {did}\n"
                      f"  title {now_title!r} -> {title!r}")
    skipped = len(names) - len(rows)
    print(f"{len(rows)} HiPS to advertise, {stale} needing a stamp, "
          f"{skipped} served but not advertised")
    return stale


def cmd_stamp(args):
    names = served_names()
    rows = plan(names)
    props = served_properties([r[0] for r in rows])
    remote_edits = []
    for name, did, title in rows:
        text = props.get(name)
        if text is None:
            print(f"  {name}: no served properties, skipped")
            continue
        if value(text, "creator_did") == did and value(text, "obs_title") == title:
            continue
        new = restamp(text, did, title)
        remote_edits.append((name, new))
        # The docroot copy is the master; several entries are symlinks into
        # build trees, so writing through the link updates the build tree too,
        # which is what keeps a later re-publish from undoing this.
        local = os.path.join(DOCROOT, name, "properties")
        if os.path.exists(local):
            local_new = restamp(open(local).read(), did, title)
            if not args.dry_run:
                with open(local, "w") as fh:
                    fh.write(local_new)
        print(f"  {name}: {title}")
    print(f"{len(remote_edits)} to write on {REMOTE_HOST}")
    if args.dry_run or not remote_edits:
        return 0
    # One ssh, one heredoc per file: the alternative is a few hundred
    # round trips.
    script = []
    for name, new in remote_edits:
        script.append(f"cat > {REMOTE_ROOT}/{name}/properties <<'EOF_PROPS'\n"
                      f"{new}EOF_PROPS")
    subprocess.run(["ssh", REMOTE_HOST, "bash -s"], input="\n".join(script),
                   text=True, check=True)
    print("written")
    return 0


def cmd_list(args):
    names = served_names()
    rows = plan(names)
    props = served_properties([r[0] for r in rows])
    out = [
        "# HiPS list for the University of Florida star formation group",
        f"# {LIST_URL}",
        "# Contact: Adam Ginsburg <adamginsburg@ufl.edu>",
        "",
    ]
    missing = []
    for name, did, title in rows:
        text = props.get(name, "")
        release = value(text, "hips_release_date")
        if release is None:
            missing.append(name)
            continue
        out += [
            f"creator_did          = {did}",
            f"obs_title            = {title}",
            f"hips_release_date    = {release}",
            f"hips_service_url     = {BASE_URL}/{name}",
            f"hips_status          = {value(text, 'hips_status')}",
            "",
        ]
    path = args.out or os.path.join(DOCROOT, "hipslist")
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    print(f"wrote {path}: {len(rows) - len(missing)} HiPS")
    if missing:
        print(f"  no hips_release_date, omitted: {missing}")
    if not args.dry_run:
        subprocess.run(["scp", "-q", path, f"{REMOTE_HOST}:{REMOTE_ROOT}/"],
                       check=True)
        print(f"  copied to {LIST_URL}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()
    if not (args.check or args.stamp or args.list):
        ap.error("pick --check, --stamp or --list")
    if args.check:
        cmd_check(args)
    if args.stamp:
        cmd_stamp(args)
    if args.list:
        cmd_list(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
