"""Free-form roads that leave the grid: the mountain switchbacks, the lake causeway and the roundabout.
Pure Python like plan.py. Each road is a centreline sampled every STEP studs with a height per sample;
the terrain then cuts and fills itself to meet it (terrain.py), and build_map.py turns it into a mesh.

Blender studs: x east, y north, z up.
"""

import math

STEP = 4.0
MAX_GRADE = 0.16  # 16%: steep enough to feel like a mountain, gentle enough for a scooter
ROAD_W = 30.0


def catmull_rom(ctrl, step=STEP, closed=False):
    """Centripetal Catmull-Rom through the control points, resampled at roughly `step` spacing."""
    pts = list(ctrl)
    if closed:
        pts = [pts[-1]] + pts + [pts[0], pts[1]]
    else:
        pts = [tuple(2 * a - b for a, b in zip(pts[0], pts[1]))] + pts + [tuple(2 * a - b for a, b in zip(pts[-1], pts[-2]))]

    def lerp(a, b, t):
        return tuple(x + (y - x) * t for x, y in zip(a, b))

    def dist(a, b):
        return max(math.dist(a[:2], b[:2]) ** 0.5, 1e-6)

    dense = []
    for k in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[k - 1], pts[k], pts[k + 1], pts[k + 2]
        t0 = 0.0
        t1 = t0 + dist(p0, p1)
        t2 = t1 + dist(p1, p2)
        t3 = t2 + dist(p2, p3)
        n = max(2, int(math.dist(p1[:2], p2[:2]) / 1.0))
        for s in range(n):
            t = t1 + (t2 - t1) * s / n
            a1 = lerp(p0, p1, (t - t0) / (t1 - t0))
            a2 = lerp(p1, p2, (t - t1) / (t2 - t1))
            a3 = lerp(p2, p3, (t - t2) / (t3 - t2))
            b1 = lerp(a1, a2, (t - t0) / (t2 - t0))
            b2 = lerp(a2, a3, (t - t1) / (t3 - t1))
            dense.append(lerp(b1, b2, (t - t1) / (t2 - t1)))
    if not closed:
        dense.append(tuple(ctrl[-1]))
    # Resample evenly by arc length.
    out, acc = [dense[0]], 0.0
    for a, b in zip(dense, dense[1:]):
        acc += math.dist(a[:2], b[:2])
        if acc >= step:
            out.append(b)
            acc = 0.0
    if not closed and out[-1] != dense[-1]:
        out[-1] = dense[-1]
    return out


def grade_limit(zs, step=STEP, grade=MAX_GRADE, start=None, end=None):
    """Smooth a height profile and keep every slope under `grade`. Pins the ends if given."""
    window = 12
    smooth = [sum(zs[max(0, k - window) : k + window + 1]) / len(zs[max(0, k - window) : k + window + 1]) for k in range(len(zs))]
    if start is not None:
        smooth[0] = start
    if end is not None:
        smooth[-1] = end
    rise = grade * step
    for _ in range(3):  # forward and backward until both limits hold
        for k in range(1, len(smooth)):
            smooth[k] = min(max(smooth[k], smooth[k - 1] - rise), smooth[k - 1] + rise)
        if end is not None:
            smooth[-1] = end
        for k in range(len(smooth) - 2, -1, -1):
            smooth[k] = min(max(smooth[k], smooth[k + 1] - rise), smooth[k + 1] + rise)
        if start is not None:
            smooth[0] = start
    return smooth


def make_roads(ground) -> list[dict]:
    """`ground(x, y)` is the batch-4 terrain height (city flat, hills free). Returns the road list."""
    roads = []

    # Mountain: leaves the valley road heading east, then four hairpins up the south-east flank
    # to a summit car park just below the peak.
    ctrl = [
        (860, 560), (960, 572), (1090, 600), (1175, 625), (1205, 665), (1180, 705),  # leg 1, hairpin 1
        (1100, 712), (1060, 735), (1040, 772), (1065, 805),  # leg 2, hairpin 2 (kept away from the peak's steep side)
        (1140, 818), (1190, 845), (1212, 885), (1185, 922),  # leg 3, hairpin 3
        (1120, 930), (1075, 955), (1055, 990), (1078, 1022),  # leg 4, hairpin 4
        (1150, 1035), (1200, 1065), (1190, 1105), (1130, 1112),  # leg 5 to the summit car park
    ]
    pts = catmull_rom([(x, y, 0.0) for x, y in ctrl])
    zs = grade_limit([ground(x, y) for x, y, _ in pts], start=0.0)
    roads.append({"name": "Mountain", "width": ROAD_W - 6, "edge": "rails", "points": [(x, y, round(z, 2)) for (x, y, _), z in zip(pts, zs)],
                  "shelter": (0.33, 0.42)})  # avalanche shelter over part of leg 2 (fraction of length)

    # Lake causeway: from the suburbs' southern street, a gentle S across the lake on a low bridge.
    ctrl = [(640, -420), (630, -470), (622, -540), (650, -620), (660, -700), (645, -770), (640, -826)]
    pts = catmull_rom([(x, y, 0.0) for x, y in ctrl])
    n = len(pts)
    zs = []
    for k, (x, y, _) in enumerate(pts):
        u = min(k, n - 1 - k) * STEP  # distance from the nearer end
        zs.append(min(6.0, max(0.0, (u - 30) * 0.1)))  # 10% ramps up to a deck 6 studs above street level
    roads.append({"name": "Causeway", "width": ROAD_W, "edge": "pavement", "points": [(x, y, z) for (x, y, _), z in zip(pts, zs)]})

    # Roundabout where the causeway meets the southern loop road.
    cx, cy, r = 640.0, -880.0, 38.0
    ring = [(cx + r * math.cos(a), cy + r * math.sin(a), 0.0) for a in (k * math.tau / 96 for k in range(96))]
    entries = (math.pi, 0.0, math.pi / 2)  # west, east, north
    gap = math.asin((ROAD_W / 2 + 5) / (r + 11))  # the ring's pavement opens where each approach joins
    roads.append({"name": "Roundabout", "width": 22.0, "edge": "pavement", "points": ring, "closed": True, "island": (cx, cy, r - 11), "gaps": [(a, gap) for a in entries]})
    for name, a, b in (("RoundaboutW", (580, -880), (cx - r - 3, cy)), ("RoundaboutE", (700, -880), (cx + r + 3, cy)), ("RoundaboutN", (640, -826), (cx, cy + r + 3))):
        # Approaches run their asphalt into the ring (no gap at the join); pavement stops at the ring's edge.
        pts = [(a[0] + (b[0] - a[0]) * t / 4, a[1] + (b[1] - a[1]) * t / 4, 0.0) for t in range(5)]
        roads.append({"name": name, "width": ROAD_W, "edge": "pavement", "points": pts, "joins": (cx, cy, r + 16), "lines": False})
    return roads


class RoadIndex:
    """Nearest-centreline lookups for the terrain, bucketed so each query only checks nearby samples."""

    BUCKET = 40.0

    def __init__(self, roads):
        self.samples = []  # (x, y, z, half_width, road_index)
        self.buckets = {}
        for ri, road in enumerate(roads):
            for x, y, z in road["points"]:
                self.samples.append((x, y, z, road["width"] / 2, ri))
        for k, (x, y, *_r) in enumerate(self.samples):
            self.buckets.setdefault((int(x // self.BUCKET), int(y // self.BUCKET)), []).append(k)

    def nearest_index(self, x, y, reach=2):
        """Index of the closest sample within `reach` buckets, and its distance (None, 1e9 if none)."""
        bx, by = int(x // self.BUCKET), int(y // self.BUCKET)
        best, best_d = None, 1e18
        for i in range(bx - reach, bx + reach + 1):
            for j in range(by - reach, by + reach + 1):
                for k in self.buckets.get((i, j), ()):
                    s = self.samples[k]
                    d = (s[0] - x) ** 2 + (s[1] - y) ** 2
                    if d < best_d:
                        best, best_d = k, d
        return best, math.sqrt(best_d) if best is not None else 1e9

    def near(self, x, y, reach=2, block=25):
        """The closest sample of each stretch of road (per `block` samples) within `reach` buckets."""
        bx, by = int(x // self.BUCKET), int(y // self.BUCKET)
        best = {}
        for i in range(bx - reach, bx + reach + 1):
            for j in range(by - reach, by + reach + 1):
                for k in self.buckets.get((i, j), ()):
                    s = self.samples[k]
                    d = (s[0] - x) ** 2 + (s[1] - y) ** 2
                    key = (s[4], k // block)
                    if key not in best or d < best[key][1]:
                        best[key] = (k, d)
        return [(k, math.sqrt(d)) for k, d in best.values()]

    def nearest(self, x, y, reach=2):
        k, d = self.nearest_index(x, y, reach)
        return (self.samples[k] if k is not None else None), d
