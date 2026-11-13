#!/usr/bin/env python3
"""lsbfetch.py - LandSandBoat zone data (data/zones/<dir>/{mobs,npcs,regions,zone}.yaml), from a local checkout or
from a download cache pinned to one commit.

LandSandBoat (https://github.com/LandSandBoat/server, "LSB") carries retail entity ids with per-id spawn points and
region polygons. lsb_flow.py uses it as the reference for how SE placed ids on the map. Two sources, chosen by the
`--lsb` option or the P75_LSB environment variable:

  * LOCAL CHECKOUT (--lsb DIR / P75_LSB): files are read from <DIR>/data/zones. Nothing is downloaded or cached and
    the commit recorded in the output is `git -C DIR rev-parse HEAD` ("local" if DIR is not a git checkout).
  * DOWNLOAD (default): files are fetched on demand from GitHub at ONE pinned commit and cached:

      <cache>/<commit12>/tree.json           every data/zones/* path at that commit (1 API call)
      <cache>/<commit12>/zones.json          {zone id: dir}, from the ids inside each dir's files
      <cache>/<commit12>/<dir>/<file>.yaml   downloaded files
      <cache>/PINNED                         the commit in use

    The commit is, in order: --pin SHA (or P75_LSB_COMMIT), the sha stored in <cache>/PINNED, else the current tip
    of branch `base` (then stored in PINNED). `--repin` moves it to the current tip. Network: api.github.com (tree
    + commit lookup, unauthenticated) and raw.githubusercontent.com. Nothing is written outside the cache.

Paths (none are hardcoded): cache = --cache DIR, else P75_LSB_CACHE, else ./lsb-cache in the working directory.

Library: `lsbfetch.zone_files(zone_id) -> {"dir", "commit", "mobs", "npcs", "regions", "zone"}` (parsed YAML dicts,
missing file -> {}; None if LSB has no such zone). CLI: `python lsbfetch.py [--repin] [--all | <zone id> ...]`
prefetches (and lists) zones. Needs PyYAML (`pip install pyyaml`).
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

CACHE = os.path.abspath(os.environ.get("P75_LSB_CACHE") or "lsb-cache")
LOCAL = os.environ.get("P75_LSB") or None  # LSB checkout; when set, nothing is downloaded
PIN = os.environ.get("P75_LSB_COMMIT") or None
REPO = "LandSandBoat/server"
BRANCH = "base"
FILES = ("mobs", "npcs", "regions", "zone")
UA = {"User-Agent": "p75-mob-placement-paths/lsbfetch"}


def set_cache(path):
    """Use another cache dir."""
    global CACHE
    CACHE = os.path.abspath(path)


def set_local(path):
    """Read a local LSB checkout (<path>/data/zones) instead of downloading."""
    global LOCAL
    LOCAL = os.path.abspath(path) if path else None


def set_pin(sha):
    """Use this commit for downloads (ignored with a local checkout)."""
    global PIN
    PIN = sha or None


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def pinned(repin=False):
    """The commit in use (40 hex): the local checkout's HEAD, else --pin, else the PINNED file, else the tip of base."""
    if LOCAL:
        try:
            return subprocess.check_output(["git", "-C", LOCAL, "rev-parse", "HEAD"], text=True,
                                           stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return "local"
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, "PINNED")
    if PIN:
        sha = PIN
    elif os.path.exists(p) and not repin:
        return open(p).read().strip()
    else:
        sha = json.loads(_get("https://api.github.com/repos/%s/commits/%s" % (REPO, BRANCH)))["sha"]
    open(p, "w").write(sha + "\n")
    return sha


def _dir(sha):
    d = os.path.join(CACHE, sha[:12])
    os.makedirs(d, exist_ok=True)
    return d


def zone_dirs(sha):
    """Sorted list of data/zones/<dir> names (local folder listing, or the cached tree listing at the commit)."""
    if LOCAL:
        root = os.path.join(LOCAL, "data", "zones")
        return sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    p = os.path.join(_dir(sha), "tree.json")
    if not os.path.exists(p):
        t = json.loads(_get("https://api.github.com/repos/%s/git/trees/%s?recursive=1" % (REPO, sha)))
        paths = [e["path"] for e in t["tree"] if e["path"].startswith("data/zones/")]
        json.dump(paths, open(p, "w"))
    paths = json.load(open(p))
    return sorted({q.split("/")[2] for q in paths if q.count("/") >= 3})


def fetch(sha, zdir, name):
    """Parsed data/zones/<zdir>/<name>.yaml ({} if LSB has no such file)."""
    if LOCAL:
        p = os.path.join(LOCAL, "data", "zones", zdir, name + ".yaml")
        if not os.path.exists(p):
            return {}
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    d = os.path.join(_dir(sha), zdir)
    p = os.path.join(d, name + ".yaml")
    if not os.path.exists(p):
        os.makedirs(d, exist_ok=True)
        try:
            raw = _get("https://raw.githubusercontent.com/%s/%s/data/zones/%s/%s.yaml" % (REPO, sha, zdir, name))
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            raw = b""
        open(p, "wb").write(raw)
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _zone_of(sha, zdir):
    """Zone id of an LSB dir: (entity id >> 12) & 0xFFF of the first npc or mob spawn id."""
    for name, key in (("npcs", "npcs"), ("mobs", "spawns")):
        ids = (fetch(sha, zdir, name).get(key) or {})
        for k in ids:
            try:
                return (int(k) >> 12) & 0xFFF
            except (TypeError, ValueError):
                continue
    return None


_MEM = {}  # local mode: {zone id: dir} built once per run, never written to disk


def zone_map(sha, need=None):
    """{zone id: dir}. Resolving a dir reads (downloads) its npcs.yaml (and mobs.yaml if npcs is empty); in download
    mode the result is cached in zones.json. `need` = a zone id: stop as soon as it is found."""
    if LOCAL:
        if not _MEM:
            for d in zone_dirs(sha):
                z = _zone_of(sha, d)
                if z is not None:
                    _MEM[z] = d
        return _MEM
    p = os.path.join(_dir(sha), "zones.json")
    m = {int(k): v for k, v in json.load(open(p)).items()} if os.path.exists(p) else {}
    if need is not None and need in m:
        return m
    known = set(m.values())
    for d in zone_dirs(sha):
        if d in known:
            continue
        z = _zone_of(sha, d)
        if z is not None:
            m[z] = d
            json.dump({str(k): v for k, v in sorted(m.items())}, open(p, "w"), indent=0)
            if need is not None and z == need:
                break
    return m


def zone_files(zone, repin=False):
    sha = pinned(repin)
    zd = zone_map(sha, need=zone).get(zone)
    if zd is None:
        return None
    out = {"dir": zd, "commit": sha}
    for f in FILES:
        out[f] = fetch(sha, zd, f)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zones", nargs="*", type=int)
    ap.add_argument("--all", action="store_true", help="resolve and read/download every LSB zone dir")
    ap.add_argument("--lsb", default=LOCAL, help="LSB checkout to read instead of downloading (env P75_LSB)")
    ap.add_argument("--pin", default=PIN, help="LSB commit to download (env P75_LSB_COMMIT; default: PINNED file)")
    ap.add_argument("--repin", action="store_true", help="pin the current tip of LSB `base`")
    ap.add_argument("--cache", default=CACHE, help="download cache dir (env P75_LSB_CACHE; default %(default)s)")
    a = ap.parse_args()
    set_cache(a.cache)
    set_local(a.lsb)
    set_pin(a.pin)
    sha = pinned(a.repin)
    if a.all:
        a.zones = sorted(zone_map(sha))
    for z in a.zones:
        r = zone_files(z)
        print(z, r["dir"] if r else "(not in LSB)")
    print("LSB commit", sha)


if __name__ == "__main__":
    sys.exit(main())
