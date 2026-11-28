"""Terrain height and ground colour for the city. Pure Python like plan.py; tests in test_plan.py.

Blender studs (x east, y north, z up). The city stays flat at FLAT so roads and buildings sit on it;
the land rises into hills, a backdrop ring and a mountain away from them, and drops into the sea
(west) and a lake (south-east). Water surface is at WATER.
"""

import math

from plan import CELL, DISTRICTS, SEA_I

FLAT = -0.1  # just under road tiles (asphalt top is 0), so they never z-fight with the ground
WATER = -3.0
EXTENT = 1500  # terrain covers -EXTENT..EXTENT; the playable city is about +-1020
COAST_X = (SEA_I + 0.5) * CELL  # -900: the docks quay edge
DOCKS_Y = (-9.5 * CELL, 9.5 * CELL)  # quay wall here; beaches north and south of it
PEAK = (870.0, 840.0, 290.0)  # x, y, height
LAKE = (680.0, -620.0, 175.0, 125.0)  # centre x, y, radius x, radius y
HUB_PARKS = ((-130, -120), (130, -120), (-140, 10), (140, 10))  # same as the groves in plan.py
FLAT_DISTRICTS = ("Hub", "Suburbs", "OldTown", "Docks", "Downtown")


def _hash(ix: int, iy: int, seed: int) -> float:
    h = (ix * 374761393 + iy * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 0xFFFF


def noise(x: float, y: float, seed: int = 0) -> float:
    """Smooth value noise in 0..1."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = x - ix, y - iy
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(ix, iy, seed), _hash(ix + 1, iy, seed)
    c, d = _hash(ix, iy + 1, seed), _hash(ix + 1, iy + 1, seed)
    return (a + (b - a) * sx) + ((c + (d - c) * sx) - (a + (b - a) * sx)) * sy


def fbm(x: float, y: float, seed: int = 0, octaves: int = 4) -> float:
    total, amp, freq, norm = 0.0, 1.0, 1.0, 0.0
    for o in range(octaves):
        total += noise(x * freq, y * freq, seed + o * 17) * amp
        norm += amp
        amp *= 0.5
        freq *= 2.0
    return total / norm


def smoothstep(e0: float, e1: float, v: float) -> float:
    t = min(1.0, max(0.0, (v - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


class Terrain:
    def __init__(self, p: dict):
        self.roads = {tuple(c) for c in p["roads"]}
        self.flat_rects = [p["districts"][d]["rect"] for d in FLAT_DISTRICTS]
        # Buildings out in the hills (mountain cabins) get a flat pad.
        self.pads = [(it["x"], it["y"]) for it in p["items"] if it["asset"] == "Mountain_Cabin"]

    # ------------------------------------------------------------ how flat must the ground be here?
    def _road_distance(self, x: float, y: float, reach: int = 4) -> float:
        ci, cj = round(x / CELL), round(y / CELL)
        best = 1e9
        for i in range(ci - reach, ci + reach + 1):
            for j in range(cj - reach, cj + reach + 1):
                if (i, j) in self.roads:
                    dx = max(abs(x - i * CELL) - CELL / 2, 0)
                    dy = max(abs(y - j * CELL) - CELL / 2, 0)
                    best = min(best, math.hypot(dx, dy))
        return best

    def flatness(self, x: float, y: float) -> float:
        """1 = must be flat (city), 0 = free to be landscape."""
        m = 1 - smoothstep(20, 110, self._road_distance(x, y))
        for x0, y0, x1, y1 in self.flat_rects:
            dx = max(x0 - x, 0, x - x1)
            dy = max(y0 - y, 0, y - y1)
            m = max(m, 1 - smoothstep(0, 90, math.hypot(dx, dy)))
        for px, py in self.pads:
            m = max(m, 1 - smoothstep(25, 70, math.hypot(x - px, y - py)))
        return m

    # ------------------------------------------------------------ landscape before flattening
    @staticmethod
    def land(x: float, y: float) -> float:
        hills = (fbm(x / 260, y / 260, 3) - 0.35) * 90
        hills = max(hills, 0) + fbm(x / 70, y / 70, 9) * 8
        px, py, ph = PEAK
        r = math.hypot(x - px, y - py)
        ridge = 0.75 + 0.5 * fbm(x / 90, y / 90, 21)
        mountain = ph * max(0.0, 1 - r / 430) ** 1.6 * ridge
        edge = (abs(x) ** 8 + abs(y) ** 8) ** 0.125  # a rounded square: no crease along the diagonals
        backdrop = smoothstep(1040, 1380, edge) * (110 + fbm(x / 180, y / 180, 5) * 110)
        return hills + mountain + backdrop

    @staticmethod
    def water_floor(x: float, y: float) -> float:
        """Height of the sea or lake bed here, or +inf if this is dry land."""
        floor = math.inf
        if DOCKS_Y[0] <= y <= DOCKS_Y[1]:
            if x < COAST_X:  # quay wall: deep water right against it
                floor = -12 - min((COAST_X - x) * 0.04, 30)
        else:
            # Beach: starts just west of the coast road and slopes into the sea; the waterline wanders.
            top = COAST_X - 5 - fbm(y / 150, 0.5, 31) * 40
            if x < top:
                floor = max(FLAT - (top - x) * 0.12, -40)
        d = Terrain.lake_distance(x, y)
        if d < 1.25:  # sloping bank, then a flat-ish bed
            bed = WATER + 2.5 - (1.25 - d) * 30 if d > 0.75 else -12.5 - (0.75 - d) * 5
            floor = min(floor, bed)
        return floor

    @staticmethod
    def lake_distance(x: float, y: float) -> float:
        """1.0 is roughly the lake's edge; the outline wobbles."""
        lx, ly, rx, ry = LAKE
        return math.hypot((x - lx) / rx, (y - ly) / ry) * (0.85 + 0.3 * fbm(x / 60, y / 60, 41))

    def height(self, x: float, y: float) -> float:
        m = self.flatness(x, y)
        land = self.land(x, y) * smoothstep(1.2, 2.0, self.lake_distance(x, y))  # hills ease down to the shore
        h = FLAT * m + land * (1 - m)
        if x < COAST_X - 300:  # open sea: no backdrop hills to the west
            h = min(h, -20.0)
        return min(h, self.water_floor(x, y))

    # ------------------------------------------------------------ ground colour (palette names)
    def colour(self, x: float, y: float, h: float, steepness: float, district: str) -> str:
        if h < WATER + 0.5:
            return "sand" if h > WATER - 4 else "stone"
        if h > 200 and math.hypot(x - PEAK[0], y - PEAK[1]) < 260:
            return "white"  # snow cap on the mountain only
        if steepness > 0.55 and h > 15:
            return "stone" if (int(x / 30) + int(y / 30)) % 3 else "grey"
        if h < WATER + 3.5 and self.water_floor(x, y) != math.inf:
            return "sand"
        patch = fbm(x / 90, y / 90, 55) > 0.6  # soft worn patches, not a pattern
        if district == "Hub":
            if any(math.hypot(x - px, y - py) < 40 for px, py in HUB_PARKS):
                return "grass"
            return "concrete" if patch else "lightgrey"
        if district == "Downtown" or district == "Docks":
            return "stone" if patch else "concrete"
        if district == "OldTown":
            return "sand" if patch else "tan"
        if district == "Suburbs":
            return "grass"
        n = fbm(x / 120, y / 120, 77)
        return "darkgreen" if n > 0.62 else ("lime" if n < 0.32 else "grass")
