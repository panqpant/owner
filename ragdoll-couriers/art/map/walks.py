"""Pedestrian walks: paths along the pavements of straight streets that weave past thin things (lamp
posts, tree trunks, hydrants) and stop short of solid ones (benches, bins, bus stops, quay walls).
Walkers pace a walk end to end and turn round. Every path point is checked clear of every prop.

python map/walks.py   writes src/shared/Walks.luau (the client reads it; ServerStorage is server-only).
"""

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plan import CELL, _sizes, plan  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "src", "shared", "Walks.luau")

PAVE_IN, PAVE_OUT = 15.0, 20.0  # pavement band, studs out from the road's centre line
FOOT = 1.0  # feet stay on the pavement: centre at least this far inside either edge
BODY = 0.85  # torso half-width for clearance (arms may brush a pole for a moment; nobody sees that)
DEPTH = 0.8  # body half-depth along the walk
KERB = 0.4  # pavement top above the road
STEP = 0.5
MIN_LEN = 16
SHIFT = 3.0  # studs to ease sideways round a pole
THIN = {"Street_Lamp": 0.6, "Street_Tree": 0.7, "Street_Hydrant": 0.7, "Street_PowerPole": 0.6}
DENSITY = {"OldTown": 3, "Downtown": 3, "Hub": 3, "Suburbs": 1.5, "Docks": 1}  # relative walkers per stud
SKIP = ("Road_", "Terrain", "Wires", "PowerLines", "SpeedBump", "Ramp")


def obstacles(items, sizes):
    """Axis-aligned ground rects (x0, y0, x1, y1) for everything that stands in the street scene."""
    out = []
    for it in items:
        a = it["asset"]
        if a.startswith(SKIP) or a not in sizes:
            continue
        if a in THIN:
            r = THIN[a]
            w = d = 2 * r
        else:
            w, d = sizes[a]
            rot = it["rot"] % 360
            if rot % 90:
                w = d = math.hypot(w, d)  # any angle: the circumscribed square
            elif rot % 180:
                w, d = d, w
        out.append((it["x"] - w / 2, it["y"] - d / 2, it["x"] + w / 2, it["y"] + d / 2, a))
    return out


def runs(items):
    """Straight-street cells grouped into runs along the street: (along_ns, fixed index, first, last)."""
    straight = {}
    for it in items:
        if it["asset"] in ("Road_Straight", "Road_Cobble"):
            straight[(round(it["x"] / CELL), round(it["y"] / CELL))] = (it["rot"] % 180 == 0, it["district"])
    out = []
    for (i, j), (ns, dist) in sorted(straight.items()):
        prev = (i, j - 1) if ns else (i - 1, j)
        if straight.get(prev, (None,))[0] == ns:
            continue  # not the start of a run
        k = 0
        while straight.get((i, j + k + 1) if ns else (i + k + 1, j), (None,))[0] == ns:
            k += 1
        out.append((ns, i if ns else j, j if ns else i, (j if ns else i) + k, dist))
    return out


def walks(p=None):
    p = p or plan()
    items = p["items"]
    obs = obstacles(items, _sizes())
    result = []
    for ns, fixed, first, last, district in runs(items):
        if district not in DENSITY:
            continue
        a0, a1 = first * CELL - CELL / 2 + 1, last * CELL + CELL / 2 - 1  # a stud short of the junctions either end
        for side in (1, -1):
            centre = fixed * CELL

            def world(t, lat):  # (along, lateral-out-from-road-centre) -> plan x, y
                off = centre + side * lat
                return (off, t) if ns else (t, off)

            band = [o for o in obs if _hits(o, ns, centre, side)]
            ts = [a0 + k * STEP for k in range(int((a1 - a0) / STEP) + 1)]
            want = [_free_lateral(t, band, ns, centre, side) for t in ts]
            # ease round poles: each point takes the biggest nearby sideways shift, fading over SHIFT studs
            lat = []
            reach = int(SHIFT / STEP)
            for k, t in enumerate(ts):
                best = 17.5
                for q in range(max(0, k - reach), min(len(ts), k + reach + 1)):
                    w = want[q]
                    if w is None or w == 17.5:
                        continue
                    fade = 1 - abs(ts[q] - t) / SHIFT
                    if fade > 0 and abs(17.5 + (w - 17.5) * fade - 17.5) > abs(best - 17.5):
                        best = 17.5 + (w - 17.5) * fade
                lat.append(None if want[k] is None else best)
            # keep only points that really are clear, then split into runs of clear points
            seg = []
            for t, l in zip(ts, lat):
                if l is not None and _clear(world(t, l), ns, band) and PAVE_IN + FOOT - 1e-6 <= l <= PAVE_OUT - FOOT + 1e-6:
                    seg.append((t, l))
                    continue
                _emit(seg, world, district, result)
                seg = []
            _emit(seg, world, district, result)
    return result


def _hits(o, ns, centre, side):
    lo, hi = (o[0], o[2]) if ns else (o[1], o[3])
    b0, b1 = sorted((centre + side * (PAVE_IN - 1), centre + side * (PAVE_OUT + 1)))
    return hi > b0 and lo < b1


def _free_lateral(t, band, ns, centre, side):
    """The clear lateral nearest the pavement's middle at along-position t, or None if blocked."""
    blocks = []
    for o in band:
        a_lo, a_hi = (o[1], o[3]) if ns else (o[0], o[2])
        if a_hi + DEPTH <= t or a_lo - DEPTH >= t:
            continue
        l_lo, l_hi = sorted((((o[0] if ns else o[1]) - centre) * side, ((o[2] if ns else o[3]) - centre) * side))
        blocks.append((l_lo - BODY, l_hi + BODY))
    candidates = [k / 10 for k in range(int((PAVE_IN + FOOT) * 10), int((PAVE_OUT - FOOT) * 10) + 1)]
    free = [c for c in candidates if not any(b0 < c < b1 for b0, b1 in blocks)]
    return min(free, key=lambda c: abs(c - 17.5)) if free else None


def _clear(pt, ns, band):
    x, y = pt
    hx, hy = (BODY, DEPTH) if ns else (DEPTH, BODY)
    return all(not (x + hx > o[0] and x - hx < o[2] and y + hy > o[1] and y - hy < o[3]) for o in band)


def _emit(seg, world, district, result):
    if len(seg) < 2 or seg[-1][0] - seg[0][0] < MIN_LEN:
        return
    pts = [seg[0]]
    for k in range(1, len(seg) - 1):
        if seg[k][1] != seg[k - 1][1] or seg[k][1] != seg[k + 1][1]:
            pts.append(seg[k])  # keep the bends, drop points mid-straight
    pts.append(seg[-1])
    # plan (x, y) -> Roblox (x, height, z = -y)
    result.append({"d": district, "p": [[round(x, 2), KERB, round(-y, 2)] for x, y in (world(t, l) for t, l in pts)]})


def write(result):
    with open(OUT, "w") as f:
        f.write("-- Generated by art/map/walks.py. Pedestrian walks: pavement paths in Roblox studs (city origin).\n")
        f.write("-- d = district, p = points (x, y, z); walkers pace a walk end to end.\n")
        f.write(f"return {{ density = {json.dumps(DENSITY).replace(':', ' =').replace('\"', '')}, walks = game:GetService(\"HttpService\"):JSONDecode([==[")
        f.write(json.dumps(result, separators=(",", ":")))
        f.write("]==]) }\n")
    print("wrote", OUT, len(result), "walks,", round(sum(_length(w) for w in result)), "studs")


def _length(w):
    return sum(math.dist(a, b) for a, b in zip(w["p"], w["p"][1:]))


if __name__ == "__main__":
    write(walks())
