"""Checks the city plan: python3 map/test_plan.py"""

import math
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import CELL, DIRS, HALF, LINKS, N, E, S, W, open_sides, plan, roads, rotate, tile_for  # noqa: E402

# Tile picking: every connection pattern gets a tile whose rotated open sides match exactly.
assert rotate({N, E}, 1) == {W, N}
assert tile_for({N, S}) == ("Road_Straight", 0)
assert tile_for({E, W}) == ("Road_Straight", 90)
assert tile_for({N, E}) == ("Road_Corner", 0)
assert tile_for({S, E}) == ("Road_Corner", 270)
assert tile_for({N, S, W}) == ("Road_T", 180)
assert tile_for({N}) == ("Road_Straight", 0)  # dead end
for k in range(4):
    for base in ({N, S}, {N, E}, {N, S, E}, {N, E, S, W}):
        name, rot = tile_for(rotate(base, k))
        from plan import TILES

        assert rotate(TILES[name], rot // 90) == rotate(base, k)

# Every road connects to every other road.
cells = roads()
start = next(iter(cells))
seen, queue = {start}, deque([start])
while queue:
    i, j = queue.popleft()
    linked = [b for a, b in LINKS if a == (i, j)] + [a for a, b in LINKS if b == (i, j)]
    for n in [(i + di, j + dj) for di, dj in DIRS.values()] + linked:
        if n in cells and n not in seen:
            seen.add(n)
            queue.append(n)
assert seen == cells, f"{len(cells - seen)} road cells are cut off, e.g. {sorted(cells - seen)[:5]}"

p = plan()
items = p["items"]
limit = 1400  # inside the terrain (EXTENT 1500): the mountain road climbs past the city grid
for it in items:
    assert -limit <= it["x"] <= limit and -limit <= it["y"] <= limit, it

# No building sits on a road cell, and no two buildings share a spot.
buildings = [it for it in items if it["asset"].startswith(("House", "OldTown_Shop", "OldTown_Town", "Docks_Ware", "Docks_Fish", "Site_Porta", "Site_Skeleton", "Downtown_", "Mountain_Cabin", "Hub_Depot", "Hub_Garage", "Hub_VIP", "Suburbs_School", "OldTown_Church", "OldTown_Clock"))]
for b in buildings:
    cell = (round(b["x"] / CELL), round(b["y"] / CELL))
    assert cell not in cells, f"{b['asset']} on a road at {cell}"
spots = [(round(b["x"]), round(b["y"])) for b in buildings]
assert len(spots) == len(set(spots)), "two buildings overlap"

# Building footprints never overlap (touching terraces are fine: 1 stud of slack for awnings and sills).
from plan import _sizes  # noqa: E402

sizes = _sizes()
rects = []
for b in buildings:
    w, d = sizes[b["asset"]]
    if b["rot"] % 180:
        w, d = d, w
    rects.append((b["x"] - w / 2, b["y"] - d / 2, b["x"] + w / 2, b["y"] + d / 2, b["asset"]))
for k, r in enumerate(rects):
    for q in rects[k + 1 :]:
        ox = min(r[2], q[2]) - max(r[0], q[0])
        oy = min(r[3], q[3]) - max(r[1], q[1])
        assert ox <= 1.0 or oy <= 1.0, f"{r[4]} overlaps {q[4]} near ({r[0]:.0f}, {r[1]:.0f}) by {ox:.1f} x {oy:.1f}"

# Each address is on a road cell's pavement, so a rider can reach it.
for a in p["addresses"]:
    cell = (round(a["x"] / CELL), round(a["y"] / CELL))
    on_free = p["terrain"].free.nearest(a["x"], a["y"])[1] < 20
    on_free = on_free or math.dist((a["x"], a["y"]), p["summit"][:2]) < 40  # the summit car park
    assert cell in cells or on_free, f"address off the road: {a}"

districts = {a["district"] for a in p["addresses"]}
assert {"Suburbs", "OldTown", "Docks", "Downtown"} <= districts, districts

# Terrain: the city is flat, the landscape is not, and nothing is left underwater.
t = p["terrain"]
from terrain import FLAT, WATER  # noqa: E402

for cell in list(cells)[::7]:
    assert abs(t.height(cell[0] * CELL, cell[1] * CELL) - FLAT) < 0.01, f"road cell {cell} is not flat"
for it in items:
    if not it["asset"].startswith("Road") and it["asset"] != "Docks_QuayWall" and not it.get("onroad") and not it.get("afloat"):
        assert t.height(it["x"], it["y"]) >= WATER + 1, f"{it['asset']} is underwater"
peak = max(t.height(x, y) for x in range(600, 1100, 25) for y in range(600, 1100, 25))
assert peak > 200, f"mountain too low: {peak}"
assert t.height(-1200, 0) < WATER and t.height(680, -620) < WATER, "sea or lake is missing"

# Free roads: graded, joined to the grid, and the bridge actually clears the lake.
import math  # noqa: E402

free = {r["name"]: r for r in p["free_roads"]}
mountain = free["Mountain"]["points"]
for a, b in zip(mountain, mountain[1:]):
    assert abs(b[2] - a[2]) <= 0.161 * max(math.dist(a[:2], b[:2]), 1e-6) + 1e-6, "mountain road too steep"
assert mountain[-1][2] > 100, f"mountain road only reaches {mountain[-1][2]}"
for x, y, z in mountain[::25]:
    assert abs(t.height(x, y) - (z - 1.6)) < 1.0, f"ground doesn't sit just under the mountain road at {(x, y)}"
causeway = free["Causeway"]["points"]
assert any(t.water_floor(x, y) < WATER and z > WATER + 6 for x, y, z in causeway), "causeway never bridges the lake"
for road, cell in (("Mountain", (21, 14)), ("Causeway", (16, -10))):
    x, y, _ = free[road]["points"][0]
    assert math.dist((x, y), (cell[0] * CELL + (20 if road == "Mountain" else 0), cell[1] * CELL - (20 if road == "Causeway" else 0))) < 1, f"{road} doesn't meet its stub"

# Where a free road meets a grid stub it must arrive square-on, or the join shows a wedge.
for road, end in (("Mountain", 0), ("Mountain", -1), ("Causeway", 0), ("Causeway", -1)):
    pts = free[road]["points"]
    a, b = (pts[0], pts[1]) if end == 0 else (pts[-2], pts[-1])
    dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
    assert min(dx, dy) < 0.01 * max(dx, dy), f"{road} meets the grid at an angle ({dx:.2f}, {dy:.2f})"

# Batch 6: every landmark made it onto the map, where it should be.
names = {it["asset"] for it in items}
for asset in ("Hub_Fountain", "Hub_Garage", "Hub_VIPGarage", "Suburbs_School", "Suburbs_Playground", "OldTown_ClockTower", "OldTown_Church",
              "OldTown_Canal", "OldTown_Footbridge", "Docks_Lighthouse", "Docks_GantryCrane", "Docks_CargoShip", "Docks_FishMarket", "Site_Hoist",
              "Mountain_Lodge", "Mountain_Waterfall", "House_D", "House_E"):
    assert asset in names, f"{asset} was never placed"
for name, cell in p["landmarks"].items():
    assert cell is not None, f"no plot found for {name}"
canal = next(it for it in items if it["asset"] == "OldTown_Canal")
assert t.height(canal["x"], canal["y"]) < -6, "the ground isn't cut away under the canal"
ship = next(it for it in items if it["asset"] == "Docks_CargoShip")
assert t.height(ship["x"], ship["y"]) < -8, "the ship isn't in deep water"
for it in items:
    if it["asset"] == "Docks_GantryCrane":
        assert (round(it["x"] / CELL), round(it["y"] / CELL)) in cells, "gantry crane isn't over the quay road"

# The harbour wall runs the whole length of the docks quay, junctions included.
quay = {round(it["y"] / CELL) for it in items if it["asset"] == "Docks_QuayWall"}
docks_quay = {j for i, j in cells if i == -22 and -9 <= j <= 9}
assert docks_quay <= quay, f"harbour wall missing at quay cells {sorted(docks_quay - quay)}"

counts = {}
for it in items:
    counts[it["asset"]] = counts.get(it["asset"], 0) + 1
print(f"plan ok: {len(cells)} road tiles, {len(items)} placements, {len(p['addresses'])} addresses")
print(", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
