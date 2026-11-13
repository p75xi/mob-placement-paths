#!/usr/bin/env python3
"""lsb_flow.py - how entity ids are laid out on the map, from LSB retail data (placement patterns).

Purpose: learn how SE numbered mobs/NPCs (which camp gets which id block, which direction the blocks walk, where a
zone's numbering starts), so an older client's roster (names by id, no positions) can be laid onto the same walk.
LandSandBoat (LSB: retail ids, per-id spawn points / region polygons) is the reference; Eden's positions and its
client renamer are hand fixes and are NOT used. Deterministic, no AI: re-run on any zone.

Method (first worked out by hand on Dangruf Wadi, then automated here):
  * spawn point of an id = LSB `at` (x, y, z), or the centroid of its LSB `region` polygon; `at` within 1.01 of
    0/1 on x and z (the [1,1,1] fished/scripted placeholder) and ids with neither are `unplaced`.
  * block = run of CONSECUTIVE ids that share one LSB region, or (fixed points) each within BLOCK_GAP yalms of the
    previous id's point. A block = one camp.
  * route: for each block, rank of the next block among all LATER blocks by centroid distance (1 = the nearest
    remaining). nearest_pct / top3_pct / median_rank summarise it (Dangruf: 45% / 86% / 2).
  * entry test (user hypothesis: the first mob id sits at an entry point): entries = LSB zone.yaml zonelines
    (`from` = where the line is in THIS zone). For the first block: distance to the nearest entry, and its rank
    among all blocks ordered by distance to their nearest entry (rank 1 = the block closest to any entrance).
    Also, per entry, the nearest block and that block's position in the id order.
  * PRIMARY = regular mob spawns only (they are the main test of the placement pattern): an id whose LSB template
    (or spawn) has spawn type scripted/lottery is excluded (fished placeholders, scripted/pop NMs, lottery NMs).
    `mobs_all` repeats the analysis with every placed mob.
  * the same for NPCs that have an `at` (NPC ids are a separate sequence in the same id space).
  Distances are 2D (x, z); FFXI y is height.

Limits: the route and entry rank are computed over the WHOLE zone in 2D, so multi-floor / multi-map zones (Castle
Oztroja, Promyvion, Uggalepih) need a per-floor split first; not done here. Client map assignment and laying a
client roster onto the walk are not done here either.

Usage (needs PyYAML; LSB files come from a local checkout or a download cache, see lsbfetch.py):
  python lsb_flow.py 191 18 159 100 151                 (zone ids; output under ./flow-out)
  python lsb_flow.py --zones-file zones.txt --out DIR   (ids from a file, one per line, '#' starts a comment)
  python lsb_flow.py --all --out DIR                    (every zone that already has an NNN_* folder in DIR)
Options:
  --out DIR          output root (env P75_FLOW_OUT; default ./flow-out)
  --lsb DIR          LandSandBoat checkout to read (env P75_LSB); without it the files are downloaded from GitHub
  --lsb-cache DIR    download cache (env P75_LSB_CACHE; default ./lsb-cache); --lsb-commit SHA pins the download
  --eden DIR         Eden checkout (env P75_EDEN), only used to name the zone folders NNN_<Eden zone name>
  --block-gap 25     yalms: the fixed-point block rule        --no-png   skip flow.png
Outputs (folder naming: an existing NNN_* folder in --out wins, else NNN_<Eden zone name> with --eden, else
NNN_<LSB dir>):
  <zone id>_<Zone>/flow.json   shape documented in README.md
  <zone id>_<Zone>/flow.png    map: region outlines (grey), zone lines (black X + tag), block centroids colored
                               by id order (red -> violet), lines between consecutive blocks, first slot labelled
  FLOW-SUMMARY.md              one line per zone folder in --out that has a flow.json
"""
import argparse
import collections
import datetime
import glob
import json
import math
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # -I does not put the script dir on sys.path
import lsbfetch  # noqa: E402  (exits with a hint if PyYAML is missing)
import pngplot  # noqa: E402

OUT = os.path.abspath(os.environ.get("P75_FLOW_OUT") or "flow-out")  # output root, see --out
EDEN = os.environ.get("P75_EDEN") or None  # Eden checkout, only for zone folder names, see --eden
BLOCK_GAP = 25.0


def slot(eid):
    return int(eid) & 0xFFF


def centroid(poly):
    return [sum(p[i] for p in poly) / len(poly) for i in range(3)]


def placeholder(at):
    return abs(at[0]) < 1.01 and abs(at[2]) < 1.01


IRREGULAR = {"scripted", "lottery"}  # LSB template spawn types that never spawn on a timer by themselves


def regular_of(spawn, templates):
    """True if an LSB mob spawn appears on its own timer: its template's `attributes.spawn.type` (or the spawn's own
    `spawn.type`) has no scripted/lottery entry. Fished placeholders and scripted NMs are not regular."""
    t = (templates or {}).get(spawn.get("template")) or {}
    st = set((((t.get("attributes") or {}).get("spawn") or {}).get("type")) or [])
    st |= set(((spawn.get("spawn") or {}).get("type")) or [])
    return not (st & IRREGULAR)


def points(entries, regions, key_name, templates=None):
    """{slot: {"id", "name", "at": [x, y, z], "region": str|None}} for placed entries; plus unplaced slot list."""
    placed, unplaced = {}, []
    for k, v in (entries or {}).items():
        v = v or {}
        at, reg = v.get("at"), v.get("region")
        if reg and reg in regions:
            at = centroid(regions[reg])
        if not at or len(at) < 3 or (not reg and placeholder(at)):
            unplaced.append(slot(k))
            continue
        placed[slot(k)] = {"id": int(k), "regular": regular_of(v, templates) if templates is not None else True,
                           "name": str(v.get(key_name) or v.get("template") or v.get("script") or ""),
                           "at": [float(at[0]), float(at[1]), float(at[2])], "region": reg if reg in regions else None}
    return placed, sorted(unplaced)


def blocks_of(placed, gap):
    out = []
    for s in sorted(placed):
        p = placed[s]
        xz = (p["at"][0], p["at"][2])
        b = out[-1] if out else None
        same = b is not None and b["last"] == s - 1 and (
            (p["region"] is not None and p["region"] == b["region"]) or
            (p["region"] is None and b["region"] is None and math.dist(xz, b["_last_xz"]) < gap))
        if same:
            b["slots"].append(s)
            b["last"] = s
            b["_pts"].append(p["at"])
            b["_last_xz"] = xz
            b["names"][p["name"]] += 1
            b["regular"] = b["regular"] or p["regular"]
        else:
            out.append({"first": s, "last": s, "slots": [s], "region": p["region"], "_pts": [p["at"]],
                        "_last_xz": xz, "names": collections.Counter([p["name"]]), "regular": p["regular"]})
    for b in out:
        b["centroid"] = [round(sum(q[i] for q in b["_pts"]) / len(b["_pts"]), 3) for i in range(3)]
        b["names"] = dict(b["names"])
        del b["_pts"], b["_last_xz"]
    return out


def xz(b):
    return (b["centroid"][0], b["centroid"][2])


def route(blocks):
    ranks, steps = [], []
    for i in range(len(blocks) - 1):
        c, dn = xz(blocks[i]), math.dist(xz(blocks[i]), xz(blocks[i + 1]))
        if dn <= 1:  # same spot (a camp split by a region change): no information
            continue
        later = [math.dist(c, xz(b)) for b in blocks[i + 1:] if math.dist(c, xz(b)) > 1]
        ranks.append(1 + sum(1 for d in later if d < dn - 1e-6))
        steps.append(dn)
    n = len(ranks)
    if not n:
        return {"transitions": 0}
    return {"transitions": n, "nearest_pct": round(100 * sum(r == 1 for r in ranks) / n, 1),
            "top3_pct": round(100 * sum(r <= 3 for r in ranks) / n, 1), "median_rank": statistics.median(ranks),
            "step_median": round(statistics.median(steps), 1), "step_max": round(max(steps), 1), "ranks": ranks}


def entries_of(zone_yaml):
    out = []
    for tag, z in ((zone_yaml or {}).get("zonelines") or {}).items():
        f = (z or {}).get("from")
        if f and len(f) >= 3:
            out.append({"tag": str(tag), "to": str(z.get("to", "")), "at": [float(f[0]), float(f[1]), float(f[2])]})
    return out


def entry_test(blocks, entries):
    if not blocks or not entries:
        return None
    ex = [(e["at"][0], e["at"][2]) for e in entries]
    near = [min(math.dist(xz(b), p) for p in ex) for b in blocks]
    d0 = near[0]
    per_entry = []
    for e in entries:
        p = (e["at"][0], e["at"][2])
        k = min(range(len(blocks)), key=lambda i: math.dist(xz(blocks[i]), p))
        per_entry.append({"tag": e["tag"], "to": e["to"], "nearest_block_index": k,
                          "nearest_block_first_slot": blocks[k]["first"], "distance": round(math.dist(xz(blocks[k]), p), 1)})
    reg = next((i for i, b in enumerate(blocks) if b.get("regular")), None)
    nearest_entry = lambda i: min(entries, key=lambda e: math.dist(xz(blocks[i]), (e["at"][0], e["at"][2])))
    first_regular = None if reg is None else {
        "block_index": reg, "slot": blocks[reg]["first"], "names": blocks[reg]["names"],
        "centroid": blocks[reg]["centroid"], "entry_distance": round(near[reg], 1),
        "entry_rank": 1 + sum(1 for d in near if d < near[reg] - 1e-6),
        "nearest_entry": {k: nearest_entry(reg)[k] for k in ("tag", "to")}}
    return {"first_block_slot": blocks[0]["first"], "first_block_entry_distance": round(d0, 1),
            "first_block_entry_rank": 1 + sum(1 for d in near if d < d0 - 1e-6), "blocks": len(blocks),
            "first_regular": first_regular,
            "median_block_entry_distance": round(statistics.median(near), 1), "per_entry": per_entry}


def analyse(placed, unplaced, gap, entries):
    bl = blocks_of(placed, gap)
    return {"placed": len(placed), "unplaced": len(unplaced), "unplaced_slots": unplaced, "blocks": bl,
            "block_size_mean": round(len(placed) / len(bl), 2) if bl else 0, "route": route(bl),
            "entry_test": entry_test(bl, entries)}


def render(path, title, regions, entries, mob_blocks):
    pts = [q for poly in regions.values() for q in poly] + [e["at"] for e in entries] + \
          [b["centroid"] for b in mob_blocks]
    if not pts:
        return
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    z0, z1 = min(p[2] for p in pts), max(p[2] for p in pts)
    W = 1000
    sc = (W - 80) / max(x1 - x0, z1 - z0, 1)
    H = int((z1 - z0) * sc) + 80
    img = pngplot.Img(W, H)

    def P(x, z):
        return 40 + (x - x0) * sc, H - 40 - (z - z0) * sc  # z up (north)
    for poly in regions.values():
        for a, b in zip(poly, poly[1:] + poly[:1]):
            img.line(*P(a[0], a[2]), *P(b[0], b[2]), (200, 200, 200))
    n = max(len(mob_blocks) - 1, 1)
    for i in range(len(mob_blocks) - 1):
        img.line(*P(*xz(mob_blocks[i])), *P(*xz(mob_blocks[i + 1])), pngplot.hue(i / n), 2)
    for i, b in enumerate(mob_blocks):
        x, y = P(*xz(b))
        img.disc(x, y, 4, pngplot.hue(i / n))
        img.text(x + 6, y - 2, b["first"], (0, 0, 0))
    for e in entries:
        x, y = P(e["at"][0], e["at"][2])
        img.line(x - 6, y - 6, x + 6, y + 6, (0, 0, 0), 2)
        img.line(x - 6, y + 6, x + 6, y - 6, (0, 0, 0), 2)
        img.text(x + 8, y + 4, e["tag"], (0, 0, 0))
    img.text(10, 10, title, (0, 0, 0), 2)
    img.save(path)


_EDEN_ZONES = {}  # {zone id: name} from Eden's zone.yml, read once


def eden_zone_name(zid):
    """Zone name from <Eden>/data/records/zone.yml (None without --eden or if the zone is not listed). Eden's record
    files change some characters of the name (Abdhaljs_Isle-Purgonorgo -> Abdhaljs_IslePurgonorgo.yml), so the first
    spelling that has an npc or mob record file wins, as in the folder names of the original run."""
    if not EDEN:
        return None
    if not _EDEN_ZONES:
        with open(os.path.join(EDEN, "data", "records", "zone.yml"), encoding="utf-8") as fh:
            for k, v in (lsbfetch.yaml.safe_load(fh) or {}).items():
                _EDEN_ZONES[int(k)] = str(v["name"])
    name = _EDEN_ZONES.get(zid)
    if name is None:
        return None
    for cand in (name, name.replace("-", ""), name.replace("-", "_"), name.replace("'", "")):
        if os.path.exists(os.path.join(EDEN, "data", "records", "npc", cand + ".yml")) or \
           os.path.exists(os.path.join(EDEN, "data", "records", "mob", "group", cand + ".yml")):
            return cand
    return name


def zone_folder(zid, lsb_dir):
    hits = sorted(glob.glob(os.path.join(OUT, "%03d_*" % zid)))
    return hits[0] if hits else os.path.join(OUT, "%03d_%s" % (zid, eden_zone_name(zid) or lsb_dir))


def run_zone(zid, gap, png):
    f = lsbfetch.zone_files(zid)
    if f is None:
        return None
    regions = {k: v["poly"] for k, v in ((f["regions"] or {}).get("regions") or {}).items()
               if isinstance(v, dict) and v.get("poly")}
    entries = entries_of(f["zone"])
    mobs, mob_un = points(f["mobs"].get("spawns"), regions, "script", f["mobs"].get("templates") or {})
    npcs, npc_un = points(f["npcs"].get("npcs"), regions, "display_name")
    res = {"zone": zid, "lsb_dir": f["dir"], "lsb_commit": f["commit"], "generated": datetime.date.today().isoformat(),
           "block_gap": gap, "entries": entries,
           # primary test of the placement pattern: regular spawns only (own timer); scripted,
           # lottery and fished ids were placed by hand later and only add noise
           "mobs": analyse({k: v for k, v in mobs.items() if v["regular"]},
                           mob_un + sorted(k for k, v in mobs.items() if not v["regular"]), gap, entries),
           "mobs_irregular_slots": sorted(k for k, v in mobs.items() if not v["regular"]),
           "mobs_all": analyse(mobs, mob_un, gap, entries),
           "npcs": analyse(npcs, npc_un, gap, entries)}
    d = zone_folder(zid, f["dir"])
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "flow.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    if png:
        render(os.path.join(d, "flow.png"), "%d %s mob blocks (LSB %s)" % (zid, f["dir"], f["commit"][:8]),
               regions, entries, res["mobs"]["blocks"])
    return res


def summary():
    lines = ["# LSB id-flow summary", "",
             "Generated by lsb_flow.py (%s). Mob blocks only; NPC numbers are in each flow.json." %
             datetime.date.today().isoformat(), "",
             "| zone | LSB dir | placed mobs | blocks | mean size | next=nearest % | next in top3 % | median rank "
             "| first regular block slot | -> nearest entry (yalms) | entry | its entry rank / blocks |",
             "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for p in sorted(glob.glob(os.path.join(OUT, "*", "flow.json"))):
        r = json.load(open(p, encoding="utf-8"))
        m, rt, et = r["mobs"], r["mobs"]["route"], r["mobs"]["entry_test"] or {}
        fr = et.get("first_regular") or {}
        lines.append("| %s | %s | %d | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            os.path.basename(os.path.dirname(p)), r["lsb_dir"], m["placed"], len(m["blocks"]), m["block_size_mean"],
            rt.get("nearest_pct", "-"), rt.get("top3_pct", "-"), rt.get("median_rank", "-"),
            fr.get("slot", "-"), fr.get("entry_distance", "-"), (fr.get("nearest_entry") or {}).get("to", "-"),
            "%s / %s" % (fr.get("entry_rank", "-"), et.get("blocks", "-"))))
    with open(os.path.join(OUT, "FLOW-SUMMARY.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def main():
    global OUT, EDEN
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("zones", nargs="*", type=int)
    ap.add_argument("--zones-file", help="file with zone ids, one per line ('#' starts a comment)")
    ap.add_argument("--all", action="store_true", help="every zone that already has an NNN_* folder in --out")
    ap.add_argument("--block-gap", type=float, default=BLOCK_GAP)
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--out", default=OUT, help="output root (per-zone folders + FLOW-SUMMARY.md; env P75_FLOW_OUT; "
                                               "default %(default)s)")
    ap.add_argument("--lsb", default=lsbfetch.LOCAL, help="LandSandBoat checkout to read instead of downloading "
                                                          "(env P75_LSB)")
    ap.add_argument("--lsb-cache", default=lsbfetch.CACHE, help="download cache dir (env P75_LSB_CACHE; default "
                                                                "%(default)s)")
    ap.add_argument("--lsb-commit", default=lsbfetch.PIN, help="LSB commit to download (env P75_LSB_COMMIT; "
                                                               "default: the cache's PINNED file, else the tip of base)")
    ap.add_argument("--eden", default=EDEN, help="Eden checkout, only to name new zone folders NNN_<Eden zone name> "
                                                 "(env P75_EDEN)")
    a = ap.parse_args()
    OUT = os.path.abspath(a.out)
    EDEN = os.path.abspath(a.eden) if a.eden else None
    lsbfetch.set_cache(a.lsb_cache)
    lsbfetch.set_local(a.lsb)
    lsbfetch.set_pin(a.lsb_commit)
    zones = list(a.zones)
    if a.zones_file:
        with open(a.zones_file, encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.split("#", 1)[0].strip()
                zones += [int(t) for t in ln.replace(",", " ").split()]
    if a.all:
        zones = sorted(int(os.path.basename(p)[:3]) for p in glob.glob(os.path.join(OUT, "[0-9][0-9][0-9]_*")))
    failed = []
    for z in zones:
        try:
            r = run_zone(z, a.block_gap, not a.no_png)
        except Exception as e:  # one bad zone must not stop a batch (103 Valkurm Dunes: `region` given as a list)
            print("%3d ERROR %s: %s" % (z, type(e).__name__, e))
            failed.append(z)
            continue
        if r is None:
            print("%3d not in LSB" % z)
            continue
        m = r["mobs"]
        et = m["entry_test"] or {}
        fr = et.get("first_regular") or {}
        print("%3d %-26s mobs %4d blocks %3d route %s | first regular slot %s %s -> %s yalms from %s, rank %s/%s" % (
            z, r["lsb_dir"], m["placed"], len(m["blocks"]),
            {k: m["route"].get(k) for k in ("nearest_pct", "top3_pct", "median_rank")}, fr.get("slot"),
            "/".join(fr.get("names", {})), fr.get("entry_distance"), (fr.get("nearest_entry") or {}).get("to"),
            fr.get("entry_rank"), et.get("blocks")))
    summary()
    if failed:
        print("failed zones: %s" % " ".join(map(str, failed)))
        return 1


if __name__ == "__main__":
    sys.exit(main())
