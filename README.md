LSB commit pinned 40e075fe98bf

Eden client version 30181205\_0

Missing Lv75 zones Valkurm\_Dunes (103) and Qufim\_Island (126)

## Retail monster re-placements by date

| date | zones (notes wording) | in 2007 client? | matching zones in this folder |
|---|---|---|---|
| 2003-12-15 | placement + level, lv50-70 areas: Ro'Maeve, Cape Teriggan, King Ranperre's Tomb, Boyahda Tree, Dragon's Aery, Den of Rancor, Kuftal Tunnel, Gustav Tunnel, Ru'Aun Gardens, Ve'Lugannon Palace, Shrine of Ru'Avitau, Qulun Dome, Monastic Cavern, Castle Oztroja | yes | - |
| 2007-06-05 | placement + level: Promyvion Holla / Dem / Mea / Vahzl | yes | - |
| 2009-11-09, 2010-03-22 | distribution: Xarcabard (S) | no (WotG, out of scope) | - |
| 2010-06-21 | distribution + level: Bibiki Bay, Uleguerand Range, Promyvion Holla / Dem / Mea / Vahzl, Lufaise Meadows, Misareaux Coast, Phomiuna Aqueducts, Sacrarium, Riverne B01 / A01 | no | 4, 5, 16, 18, 20, 22, 24, 25, 27, 28, 29, 30 |
| 2010-09-08 | level and/or placement: Mount Zhayolm, Aydeewa Subterrane, Caedarva Mire, Arrapago Reef | no | 54, 61, 68, 79 |
| 2010-12-06 | distribution + level: (S) zones only | no (WotG) | - |
| 2011-05-10 | "Revamped Monster Placement" (SE forum thread dev1012, zone list not in our notes). Supplemental 2011-05-09: placement adjusted in Inner Horutoto, Toraimarai, Garlaige, Fei'Yin; detection changed in Bostaunieux, Toraimarai, King Ranperre's Tomb, Dangruf Wadi, Ordelle's Caves, Outer Horutoto, Gusgen Mines, Crawlers' Nest, Maze of Shakhrami, Garlaige, Fei'Yin (Ranguemont, Zeruhn, Inner Horutoto, Eldieme taken off that list 2011-05-12) | no | 166, 167, 169, 172, 190, 191, 192, 193, 194, 195, 196, 197, 198, 200, 204 |
| 2011-09-19 | level + placement (dev1022): Boyahda Tree, Korroloka Tunnel, Kuftal Tunnel, Shrine of Ru'Avitau, Gustav Tunnel, Labyrinth of Onzozo | no | 153, 173, 174, 178, 212, 213 |

Source: bg version update notes
Level check (Eden `data/records/mob/group`, highest maxLevel of placed mobs, 2026-10-18): the 2011-05 dungeon wave is NOT a >75 wave (Dangruf 30, Inner Horutoto 28, Fei'Yin 70, Ranguemont 60, Zeruhn 6; single >75 NMs only in Bostaunieux, Gusgen, Garlaige). The 2011-09 wave is: Kuftal 52 placed mobs >75 (up to 97), Gustav 109 (up to 82), Onzozo 4.

## How the maps were made

Each PNG in this repo is the `flow.png` of one zone, drawn by `tools/lsb_flow.py`. It shows how Square Enix laid out
mob ids on the map: which camp gets which block of consecutive ids, in which direction the blocks walk, and where a
zone's numbering starts. The point is to lay an older client's roster (names by id, no positions) onto the same walk.
This section records the steps, so the folder can be rebuilt from public data only.

### Quick start: rebuild one map
```
git clone https://github.com/p75xi/mob-placement-paths
cd mob-placement-paths
pip install pyyaml
python tools/lsb_flow.py 2 --lsb-commit 40e075fe98bf641f3d2d5111f63621ae96b1dd69
```
Run it from the repo root (on Windows `py` works in place of `python`). It downloads the needed LandSandBoat files
into `./lsb-cache` (about 3 MB for one zone) and writes the map to `./flow-out/002_carpenters_landing/flow.png`, next to
`flow.json`. Both folders are git-ignored. The rest of this section explains each step and the options.

### What you need
- Python 3 and PyYAML (`pip install pyyaml`). Everything else is the standard library; the PNGs are drawn by the
  pure-Python `tools/pngplot.py`.
- Internet access to GitHub, **or** a local checkout of [LandSandBoat](https://github.com/LandSandBoat/server) (LSB).
  No client files, no game server, no database.

Nothing in `tools/` has a fixed path. Inputs and outputs are chosen by option or environment variable:

| What | Option | Environment variable | Default |
|---|---|---|---|
| Output folder | `--out DIR` | `P75_FLOW_OUT` | `./flow-out` |
| LSB checkout to read (skips the download) | `--lsb DIR` | `P75_LSB` | none: download |
| Download cache | `--lsb-cache DIR` | `P75_LSB_CACHE` | `./lsb-cache` |
| LSB commit to download | `--lsb-commit SHA` | `P75_LSB_COMMIT` | the cache's `PINNED` file, else the tip of branch `base` |
| Eden checkout (optional, folder names only, see step 4) | `--eden DIR` | `P75_EDEN` | none |

### 1. Pick the LSB commit
LSB carries retail entity ids with per-id spawn points and region polygons, which is the data the whole analysis
rests on. The maps here use commit **`40e075fe98bf641f3d2d5111f63621ae96b1dd69`** (merge of #11815, 2026-10-18); pass
it as `--lsb-commit` to get the same input. Without a pin the tool downloads the current tip of `base` once and
remembers it in `<cache>/PINNED`, so later runs stay on that commit; `tools/lsbfetch.py --repin` moves it.

### 2. Pick the zones
`tools/zones.txt` lists the 133 candidate zone ids (comments start with `#`). It was made once from the zone list of an
EdenXI server: every zone whose type is not Battlefield, Instanced, None, Limbus or Dynamis, minus zones 0, 3, 43-47,
58-59, 70, 71, 131, 189, 199, 214, 219 and 220-228, which were excluded by hand. The file is the result; nothing needs
Eden to use it. To do one zone, just give its id.

### 3. Run the analysis
```
pip install pyyaml
python tools/lsb_flow.py --zones-file tools/zones.txt --out flow-out --lsb-commit 40e075fe98bf641f3d2d5111f63621ae96b1dd69
python tools/lsb_flow.py 2 191 --out flow-out        # or only some zones
```
The first run downloads the LSB file tree once (one API call, plus one for the tip of `base` when no commit is pinned)
and then, per zone, its `data/zones/<dir>/{mobs,npcs,regions,zone}.yaml` into the cache. To find which LSB folder
belongs to a zone id it also reads the `npcs.yaml` of other folders until it finds the id (kept in the cache's
`zones.json`). With a local checkout, `--lsb <checkout>` reads `<checkout>/data/zones` directly and downloads and
caches nothing. A zone that raises an error is reported as `ERROR ...`, the run goes on, and the exit code is 1 at the
end.

What `lsb_flow.py` does for each zone:
1. **Spawn point of an id** = the LSB `at` (x, y, z), or the centroid of its LSB `region` polygon. An `at` within 1.01
   of 0/1 on x and z is the `[1,1,1]` placeholder (fished or scripted mobs) and counts as unplaced.
2. **Regular spawns only** are the primary analysis: a mob whose LSB template (or spawn) has spawn type `scripted` or
   `lottery` is left out (fished placeholders, scripted/pop NMs, lottery NMs). `mobs_all` repeats it with every placed mob.
3. **Block** = a run of consecutive ids that share one LSB region, or (fixed points) whose points are each within
   25 yalms of the previous id's point (`--block-gap`). A block is one camp.
4. **Route**: for each block, the rank of the next block among all later blocks by centroid distance (1 = the nearest
   remaining one). `nearest_pct`, `top3_pct` and `median_rank` summarise it. Distances are 2D (x, z); y is height.
5. **Entry test**: the zone lines of LSB's `zone.yaml` are the entrances; for the first block it records the distance
   to the nearest entrance and its rank among all blocks ordered by distance to their nearest entrance.
6. NPCs that have an `at` are analysed the same way, separately (NPC ids are another sequence in the same id space).

### 4. Read the output
Per zone, in `<out>/<id>_<name>/`:

- `flow.png`: region outlines (grey), zone lines (black X + tag), block centroids coloured by id order (red to
  violet), lines joining consecutive blocks, the first slot of each block as a label.
- `flow.json`: `zone`, `lsb_dir`, `lsb_commit`, `generated`, `block_gap`, `entries` (zone lines), and `mobs`
  (regular spawns), `mobs_irregular_slots`, `mobs_all`, `npcs`. Each analysis holds `placed`, `unplaced`,
  `unplaced_slots` (slot = id & 0xFFF), `blocks` (`first`, `last`, `slots`, `region`, `centroid`, `names`),
  `block_size_mean`, `route` (`transitions`, `nearest_pct`, `top3_pct`, `median_rank`, `step_median`, `step_max`,
  `ranks`) and `entry_test` (`first_block_slot`, `first_block_entry_distance`, `first_block_entry_rank`, `blocks`,
  `median_block_entry_distance`, `first_regular`, `per_entry`).
- Also `<out>/FLOW-SUMMARY.md`: one row per zone folder that has a `flow.json`.

Folder naming: an existing `NNN_*` folder in `--out` is reused; otherwise `NNN_<LSB dir name>` (for example
`002_carpenters_landing`). The PNGs in this repo use Eden's zone spelling (`002_Carpenters_Landing.png`); with
`--eden <Eden checkout>` the zone name is read from its `data/records/zone.yml` instead. That option only affects
folder names. Eden is not public, so it is optional.

### 5. Choose the zones for this folder
Each zone's `flow.png` was copied here as `<id>_<Zone>.png`. Of the 133 zones, 100 were kept:

- **31 have no regular mob spawns** (towns and similar), so there is no walk to draw: 1, 14, 26, 32, 48, 50, 53, 152
  and 230-252. All have 0 regular mobs except 1 (Phanauet Channel, 2).
- **2 failed with an error**: 103 (Valkurm Dunes) and 126 (Qufim Island), listed at the top of this file. For 103 the
  cause is that a spawn's `region` is a list instead of a single name, which `points()` does not handle (the run now
  reports it and continues). 126 was not re-run. Neither was investigated further.

### 6. Date the retail re-placements (done by hand)
The table above lists, by date, the retail updates that re-placed monsters, to know which zones' ids changed after a
given client build. That is a manual lookup, not a script: read the Update History at
<https://www.bg-wiki.com/ffxi/Category:Update_History> and the per-update pages it links
(`https://www.bg-wiki.com/ffxi/<Month>_<Year>_Version_Update_Notes`), search them for monster placement and level
changes, and match the zone names to zone ids.

### Files in `tools/`
| file | what |
|---|---|
| `lsb_flow.py` | the analysis and the maps (steps 3-4) |
| `lsbfetch.py` | reads LSB data from a checkout or a pinned, cached download; also runs on its own (`python tools/lsbfetch.py [--repin] [--all \| <zone id> ...]`) |
| `pngplot.py` | tiny pure-Python PNG canvas (lines, discs, a 3x5 bitmap font) |
| `zones.txt` | the 133 zone ids of step 2 |

### Checked
On 2026-11-13, zones 2 (Carpenters Landing) and 191 (Dangruf Wadi) were re-run from `tools/` against LSB
`40e075fe98bf`: both `flow.png` files are byte-identical to the PNGs in this repo, and both `flow.json` files match the
originals apart from the `generated` date. Zone 2 was also run from an empty cache with downloads only (about 2.7 MB,
18 s) with the same result. The local-checkout mode (`--lsb`) was tested only with a stand-in checkout made from cached
files, because no full LSB checkout was at hand. The full 133-zone run from `tools/` was not repeated.

### Limits
- The route and entry rank are computed over the whole zone in 2D, so multi-floor or multi-map zones (Castle Oztroja,
  Promyvion, Uggalepih) need a per-floor split first. It is not automated.
- Mapping a client roster onto the walk, and assigning client maps in multi-map zones, are not done here.
- The numbers describe retail as LSB records it at the pinned commit, not any particular client build.
