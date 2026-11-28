"""The city master plan. Pure Python (no Blender), so tests run anywhere: `python3 map/test_plan.py`.

The map is a grid of 40-stud cells, i (east, +X) and j (north, Blender +Y = Roblox -Z), each -25..25,
about 2,000 x 2,000 studs. The hub sits in the middle with a district on each side:

            Mountain (NE)
    Old Town (north)
  Docks (west)  HUB  Suburbs (east)
    Building Site (south)

Outputs one list of placements: {"asset", "x", "y", "rot", "paint"?, "district"} in Blender studs
(rot = degrees counter-clockwise about up), plus addresses, the road graph and district rectangles.
"""

import json
import os
import random

CELL = 40
HALF = 25  # cells from the centre to the edge
EXPORT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "export")

# Inclusive cell rectangles (i0, j0, i1, j1). Later entries win where they overlap.
DISTRICTS = {
    "Outskirts": ((-22, -HALF, HALF, HALF), "8fc96b"),  # west of i = -22 is sea
    "Hub": ((-5, -5, 5, 5), "d9d4c7"),
    "Suburbs": ((6, -9, 24, 9), "8fd07a"),
    "OldTown": ((-9, 6, 9, 24), "c9b79c"),
    "Docks": ((-22, -9, -6, 9), "a9b3bd"),
    "Site": ((-9, -24, 9, -6), "d8bf8f"),
    "Mountain": ((10, 10, 24, 24), "9a9f8f"),
}
SEA_I = -23  # cells with i <= this are sea (docks quay faces it)

N, E, S, W = "N", "E", "S", "W"
DIRS = {N: (0, 1), E: (1, 0), S: (0, -1), W: (-1, 0)}
CCW = {N: W, W: S, S: E, E: N}  # where each side ends up after a 90 degree counter-clockwise turn
FACING_ROT = {N: 0, W: 90, S: 180, E: 270}  # turns an asset's front (+Y) toward that side

TILES = {  # base tile: its open sides with rot 0
    "Road_Straight": {N, S},
    "Road_Corner": {N, E},
    "Road_T": {N, S, E},
    "Road_Cross": {N, E, S, W},
}


def rotate(sides: set, quarter_turns: int) -> set:
    for _ in range(quarter_turns % 4):
        sides = {CCW[s] for s in sides}
    return sides


def tile_for(open_sides: set) -> tuple[str, int]:
    """Which road tile and rotation (degrees) connects exactly these sides."""
    if len(open_sides) == 1:  # dead end: a straight that stops at the pavement
        open_sides = open_sides | {CCW[CCW[next(iter(open_sides))]]}
    for name, base in TILES.items():
        for k in range(4):
            if rotate(base, k) == open_sides:
                return name, k * 90
    raise ValueError(f"no tile for {open_sides}")


def district_of(i: int, j: int) -> str:
    found = "Outskirts"
    for name, ((i0, j0, i1, j1), _) in DISTRICTS.items():
        if i0 <= i <= i1 and j0 <= j <= j1:
            found = name
    return found


def roads() -> set:
    cells = set()

    def h(j, i0, i1):  # east-west street
        cells.update((i, j) for i in range(min(i0, i1), max(i0, i1) + 1))

    def v(i, j0, j1):  # north-south street
        cells.update((i, j) for j in range(min(j0, j1), max(j0, j1) + 1))

    # Hub ring and the four avenues out of it
    h(5, -5, 5), h(-5, -5, 5), v(5, -5, 5), v(-5, -5, 5)
    h(0, 5, 24), h(0, -22, -5), v(0, 5, 24), v(0, -24, -5)
    # Suburbs: long residential streets, cross streets, an edge road
    h(4, 5, 24), h(-4, 5, 24), h(9, 10, 24), h(-9, 10, 24)
    for i in (10, 15, 20, 24):
        v(i, -9, 9)
    # Old Town: a tight grid
    v(4, 5, 22), v(-4, 5, 22), v(8, 10, 22), v(-8, 10, 22)
    for j in (10, 14, 18, 22):
        h(j, -8, 8)
    # Docks: quay road along the water, a spine, cross streets
    h(4, -22, -5), h(-4, -22, -5), h(9, -22, -14), h(-9, -22, -14)
    v(-22, -9, 9), v(-14, -9, 9)
    # Building Site
    v(4, -22, -5), v(-4, -22, -5), v(8, -22, -10), v(-8, -22, -10)
    for j in (-10, -16, -22):
        h(j, -8, 8)
    # Mountain approach (the switchbacks come with the terrain, batch 4/5)
    v(20, 9, 14)
    # Outer loop through the outskirts, so every district links to its neighbours
    h(18, -22, -8), v(-22, 9, 18)  # Docks <-> Old Town
    v(-22, -16, -9), h(-16, -22, -8)  # Docks <-> Site
    v(24, -22, -9), h(-22, 8, 24)  # Suburbs <-> Site
    h(22, 8, 14), v(14, 14, 22), h(14, 14, 20)  # Old Town <-> Mountain foot
    return cells


def open_sides(cell, road_cells) -> set:
    i, j = cell
    return {d for d, (di, dj) in DIRS.items() if (i + di, j + dj) in road_cells}


def _sizes() -> dict:
    """Footprints from the exported asset metadata: Roblox size [x, y, z] -> Blender (width, depth)."""
    out = {}
    for f in os.listdir(EXPORT):
        if f.endswith(".json"):
            s = json.load(open(os.path.join(EXPORT, f)))["size_studs"]
            out[f[:-5]] = (s[0], s[2])
    return out


HOUSE_PAINT = ["fff1d6", "ffd6d6", "d6ecff", "e3ffd6", "fff3b0", "ffe0c2", "e8dcff", "f4f4f8", "cfe8e0"]
SHOP_PAINT = ["f6c26b", "8fc1e3", "e98b7d", "b5d99c", "f4f4f8", "d4a5c9"]
CONTAINER_PAINT = ["e8443a", "3a7bf0", "43b85c", "ff9a2e", "1fb5a8", "8b5cf6", "ffd23f"]
CAR_PAINT = ["e8443a", "3a7bf0", "ffd23f", "f4f4f8", "43b85c", "3a3d46", "ff8fc7"]


def plan(seed: int = 7) -> dict:
    rnd = random.Random(seed)
    road_cells = roads()
    sizes = _sizes()
    items, addresses = [], []

    def place(asset, x, y, rot=0, district=None, paint=None, **extra):
        item = {"asset": asset, "x": round(x, 2), "y": round(y, 2), "rot": rot % 360, "district": district or district_of(round(x / CELL), round(y / CELL))}
        if paint:
            item["paint"] = paint
        item.update(extra)
        items.append(item)
        return item

    # ---------------------------------------------------------------- road tiles + street furniture
    for cell in sorted(road_cells):
        i, j = cell
        x, y = i * CELL, j * CELL
        sides = open_sides(cell, road_cells)
        district = district_of(i, j)
        name, rot = tile_for(sides)
        if name == "Road_Straight" and district == "OldTown":
            name = "Road_Cobble"
        place(name, x, y, rot, district)
        straight = name in ("Road_Straight", "Road_Cobble")
        along_ns = N in sides and S in sides
        # Pavement spots either side of a straight: 17.5 studs out, the middle of the 5-stud pavement.
        side_a = (x + 17.5, y) if along_ns else (x, y + 17.5)
        side_b = (x - 17.5, y) if along_ns else (x, y - 17.5)
        face_a = 90 if along_ns else 180  # props face the road
        face_b = 270 if along_ns else 0
        if straight:
            if (i + j) % 2 == 0:
                lx, ly = side_a if (i + j) % 4 == 0 else side_b
                lamp_rot = (face_a if (i + j) % 4 == 0 else face_b) + 180  # lamp arm reaches over the road
                place("Street_Lamp", lx, ly, lamp_rot, district)
            if district == "Suburbs" and (i + j) % 2 == 1:
                place("Street_Tree", *(side_b if (i * 3 + j) % 2 else side_a), rnd.choice((0, 90, 180, 270)), district)
                if rnd.random() < 0.15:
                    place("Street_Hydrant", *side_a, face_a, district)
            elif district == "OldTown" and (i + j) % 3 == 1:
                place("Street_Bench", *side_b, face_b, district)
                place("Street_Bin", *side_a, face_a, district)
            elif district == "Hub" and (i + j) % 2 == 1:
                place("Street_Tree", *side_b, 0, district)
            elif district == "Outskirts" and rnd.random() < 0.35:
                place("Mountain_Guardrail" if rnd.random() < 0.3 else "Street_Bush", *side_a, face_a + 90, district)
            # Hazards on the road itself
            if district == "Suburbs" and along_ns is False and i % 3 == 0 and j in (4, -4):
                place("SpeedBump", x, y, 0 if along_ns else 90, district)
            if district == "Site" and (i, j) in ((4, -13), (-4, -19), (0, -13)):
                place("Ramp", x, y, 0 if along_ns else 90, district)
            if i == SEA_I + 1 and district == "Docks" and j % 2 == 0:  # mooring bollards on the quay edge
                place("Docks_Bollard", x - 17.5, y, 0, district)
            if district == "Docks" and (i, j) == (-14, 2):
                place("Ramp", x, y, 0, district)
        elif name in ("Road_T", "Road_Cross") and district in ("Hub", "Suburbs", "OldTown") and (i + j) % 2 == 0:
            place("Street_TrafficLight", x + 17.5, y + 17.5, 225, district)

    # ---------------------------------------------------------------- plots
    def frontage(i, j):
        """Sides of a non-road cell that touch a road, in a stable order."""
        return [d for d in (S, N, E, W) if (i + DIRS[d][0], j + DIRS[d][1]) in road_cells]

    def building(asset, i, j, side, district, paint=None, setback=6.0, address=True):
        dx, dy = DIRS[side]
        depth = sizes.get(asset, (20, 20))[1]
        off = CELL / 2 - setback - depth / 2
        x, y = i * CELL + dx * off, j * CELL + dy * off
        place(asset, x, y, FACING_ROT[side], district, paint)
        if address:
            ax, ay = i * CELL + dx * (CELL / 2 + 2.5), j * CELL + dy * (CELL / 2 + 2.5)  # on the pavement out front
            addresses.append({"district": district, "x": round(ax, 2), "y": round(ay, 2), "building": asset})
        return x, y

    hub_special = set()
    for i in range(-HALF, HALF + 1):
        for j in range(-HALF, HALF + 1):
            if (i, j) in road_cells:
                continue
            x, y = i * CELL, j * CELL
            district = district_of(i, j)
            sides = frontage(i, j)
            if i <= SEA_I:
                continue
            if district == "Hub":
                hub_special.add((i, j))
                continue
            if district == "Suburbs":
                if sides:
                    side = sides[0]
                    asset = rnd.choices(["House_A", "House_B", "House_C"], (4, 3, 3))[0]
                    hx, hy = building(asset, i, j, side, district, rnd.choice(HOUSE_PAINT))
                    dx, dy = DIRS[side]
                    px, py = -dy, dx  # mailbox beside the path, at the front of the yard
                    place("Street_Mailbox", x + dx * 17 + px * 8, y + dy * 17 + py * 8, FACING_ROT[side], district)
                    for s in (-1, 1):  # side fences
                        place("Street_Fence", x + px * s * 19.5 + dx * 12, y + py * s * 19.5 + dy * 12, FACING_ROT[side], district)
                    if rnd.random() < 0.6:
                        place("Street_Tree", x - dx * 14 + px * rnd.uniform(-10, 10), y - dy * 14 + py * rnd.uniform(-10, 10), rnd.randrange(360), district)
                    if rnd.random() < 0.25:
                        place("Traffic_Car", x + dx * 12 + px * 13, y + dy * 12 + py * 13, FACING_ROT[side], district, rnd.choice(CAR_PAINT), parked=True)
                else:
                    for _ in range(2):
                        place(rnd.choice(["Street_Tree", "Street_Bush"]), x + rnd.uniform(-14, 14), y + rnd.uniform(-14, 14), rnd.randrange(360), district)
            elif district == "OldTown":
                if sides:
                    corner = len(sides) > 1
                    asset = "OldTown_Shop" if corner or rnd.random() < 0.35 else "OldTown_Townhouse"
                    building(asset, i, j, sides[0], district, rnd.choice(SHOP_PAINT) if asset == "OldTown_Shop" else None, setback=1.5)
                    if not corner and asset == "OldTown_Townhouse":  # second townhouse shares the plot: they are narrow
                        dx, dy = DIRS[sides[0]]
                        px, py = -dy, dx
                        bx, by = items[-1]["x"], items[-1]["y"]
                        items[-1]["x"], items[-1]["y"] = round(bx + px * 7, 2), round(by + py * 7, 2)
                        place("OldTown_Townhouse", bx - px * 7, by - py * 7, FACING_ROT[sides[0]], district)
                        addresses.append({"district": district, "x": round(addresses[-1]["x"] - px * 14, 2), "y": round(addresses[-1]["y"] - py * 14, 2), "building": "OldTown_Townhouse"})
                else:  # inner courtyards become little market squares
                    place("OldTown_MarketStall", x - 8, y, rnd.choice((0, 180)), district)
                    place("OldTown_MarketStall", x + 8, y, rnd.choice((0, 180)), district)
                    place("Street_Bench", x, y + 12, 180, district)
                    place("Street_Tree", x, y - 12, 0, district)
            elif district == "Docks":
                if sides and (i + j) % 2 == 0:
                    building("Docks_Warehouse", i, j, sides[0], district, rnd.choice(["c9ccd4", "8fc1e3", "f4f4f8"]), setback=0)
                else:
                    stacks = 1 if sides else 2
                    for k in range(stacks):
                        height = rnd.choices((1, 2, 3), (5, 3, 1))[0]
                        for level in range(height):
                            place("Docks_Container", x - 12 + k * 10, y, 0, district, rnd.choice(CONTAINER_PAINT), z=level * 8.5)
                    for _ in range(rnd.randint(1, 3)):
                        place(rnd.choice(["Docks_Barrel", "Docks_Crate"]), x + rnd.uniform(-16, 16), y + rnd.uniform(12, 17) * rnd.choice((-1, 1)), rnd.randrange(360), district)
            elif district == "Site":
                if sides:
                    asset = rnd.choice(["Site_Portacabin", "Site_Scaffold", "Site_Pipes", "Site_DirtPile"])
                    building(asset, i, j, sides[0], district, "ffd23f" if asset == "Site_Portacabin" else None, setback=4, address=asset == "Site_Portacabin")
                    dx, dy = DIRS[sides[0]]
                    px, py = -dy, dx
                    for k in (-1, 1):
                        place("Site_Cone", x + dx * 17 + px * k * 12, y + dy * 17 + py * k * 12, 0, district)
                    place("Site_Barrier", x + dx * 18.5, y + dy * 18.5, FACING_ROT[sides[0]] + 90, district)
                elif (i * 7 + j * 3) % 11 == 0:
                    place("Site_TowerCrane", x, y, rnd.choice((0, 90, 180, 270)), district)
                else:
                    place("Site_DirtPile", x, y, rnd.randrange(360), district)
            elif district == "Mountain":
                if sides and rnd.random() < 0.5:
                    building("Mountain_Cabin", i, j, sides[0], district)
                for _ in range(rnd.randint(1, 3)):
                    place(rnd.choice(["Mountain_Pine", "Mountain_Pine", "Mountain_RockSmall", "Mountain_RockLarge"]), x + rnd.uniform(-15, 15), y + rnd.uniform(-15, 15), rnd.randrange(360), district)
            else:  # Outskirts: woodland, thicker away from the roads
                count = rnd.choices((0, 1, 2, 3), (2, 3, 3, 2 if not sides else 0))[0]
                for _ in range(count):
                    asset = rnd.choices(["Mountain_Pine", "Street_Tree", "Street_Bush", "Mountain_RockSmall"], (4, 3, 2, 1))[0]
                    place(asset, x + rnd.uniform(-16, 16), y + rnd.uniform(-16, 16), rnd.randrange(360), district)

    # ---------------------------------------------------------------- hub (hand-placed)
    place("Hub_Depot", 0, 120, 180, "Hub", "ff9a2e")
    spawn = {"x": 0.0, "y": 60.0, "rot": 180}
    place("Hub_JobBoard", -60, 40, 270, "Hub")
    place("Hub_Plinth", 70, 40, 0, "Hub")
    place("Hub_Leaderboard", -40, -120, 0, "Hub")
    place("Hub_Leaderboard", 0, -120, 0, "Hub")
    place("Hub_Leaderboard", 40, -120, 0, "Hub")
    for x in range(-150, 151, 50):
        for y in (-170, 170):
            if abs(x) > 20:
                place("Street_Tree", x, y, 0, "Hub")
    for x, y in ((-120, 0), (120, 0), (-120, -60), (120, -60), (-120, 60), (120, 60)):
        place("Street_Bench", x, y, 90 if x < 0 else 270, "Hub")
        place("Street_Lamp", x, y + 15, 90 if x < 0 else 270, "Hub")
    for x in (-25, 25):
        place("Street_Bin", x, 70, 180, "Hub")

    return {
        "cell": CELL,
        "half": HALF,
        "items": items,
        "addresses": addresses,
        "spawn": spawn,
        "roads": sorted(road_cells),
        "sea": {"i_max": SEA_I},
        "districts": {k: {"rect": [r[0] * CELL - CELL / 2, r[1] * CELL - CELL / 2, r[2] * CELL + CELL / 2, r[3] * CELL + CELL / 2], "colour": c} for k, (r, c) in DISTRICTS.items()},
        "hub_cells": sorted(hub_special),
    }
