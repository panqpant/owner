"""Checks the city plan: python3 map/test_plan.py"""

import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import CELL, DIRS, HALF, N, E, S, W, open_sides, plan, roads, rotate, tile_for  # noqa: E402

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
    for di, dj in DIRS.values():
        n = (i + di, j + dj)
        if n in cells and n not in seen:
            seen.add(n)
            queue.append(n)
assert seen == cells, f"{len(cells - seen)} road cells are cut off, e.g. {sorted(cells - seen)[:5]}"

p = plan()
items = p["items"]
limit = (HALF + 0.5) * CELL
for it in items:
    assert -limit <= it["x"] <= limit and -limit <= it["y"] <= limit, it

# No building sits on a road cell, and no two buildings share a spot.
buildings = [it for it in items if it["asset"].startswith(("House", "OldTown_Shop", "OldTown_Town", "Docks_Ware", "Site_Porta", "Site_Skeleton", "Downtown_", "Mountain_Cabin", "Hub_Depot"))]
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
    assert cell in cells, f"address off the road: {a}"

districts = {a["district"] for a in p["addresses"]}
assert {"Suburbs", "OldTown", "Docks", "Downtown"} <= districts, districts

counts = {}
for it in items:
    counts[it["asset"]] = counts.get(it["asset"], 0) + 1
print(f"plan ok: {len(cells)} road tiles, {len(items)} placements, {len(p['addresses'])} addresses")
print(", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1])))
