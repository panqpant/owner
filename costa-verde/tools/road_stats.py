"""Measure street-network statistics (same code for real TIGER data and our generated streets).
Usage: python tools/road_stats.py            -> tools/data/road_stats.json (per-role targets)
       python tools/road_stats.py file.json  -> stats for one generated network
Units: studs (1 m = 2.4 studs, see fetch_roads.py)."""
import glob
import json
import math
import sys
from collections import defaultdict

import numpy as np

SKIP = {"drive", "track", "alley"}  # minor ways don't define the street pattern


def graph(roads):
    """Vertex graph from polylines; vertices merged on a 1-stud grid. A street ending on the middle of
    another road (simplification removed the shared vertex) is split into a real junction."""
    adj = defaultdict(set)
    for r in roads:
        if r["kind"] in SKIP:
            continue
        pts = [(round(x), round(z)) for x, z in r["pts"]]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                adj[a].add(b)
                adj[b].add(a)
    CELL = 64
    grid = defaultdict(set)
    for a in adj:
        for b in adj[a]:
            if a < b:
                for gx in range(min(a[0], b[0]) // CELL, max(a[0], b[0]) // CELL + 1):
                    for gz in range(min(a[1], b[1]) // CELL, max(a[1], b[1]) // CELL + 1):
                        grid[(gx, gz)].add((a, b))
    for v in [v for v in adj if len(adj[v]) == 1]:
        for a, b in list(grid[(v[0] // CELL, v[1] // CELL)]):
            if v in (a, b) or b not in adj[a]:
                continue
            dx, dz = b[0] - a[0], b[1] - a[1]
            L2 = dx * dx + dz * dz
            t = ((v[0] - a[0]) * dx + (v[1] - a[1]) * dz) / L2
            if 0 < t < 1 and math.dist(v, (a[0] + dx * t, a[1] + dz * t)) < 2.5:
                adj[a].discard(b); adj[b].discard(a)
                adj[a].add(v); adj[v].add(a); adj[b].add(v); adj[v].add(b)
                for g in grid.values():
                    if (a, b) in g:
                        g.discard((a, b))
                break
    return adj


def stats(roads, half, clip_frac=0.8):
    clip = half * clip_frac
    adj = graph(roads)  # full network, so the measuring window doesn't create fake dead ends

    def inside(v):
        return max(abs(v[0]), abs(v[1])) <= clip

    area_km2 = (2 * clip / 2400) ** 2  # studs -> km
    total = sum(math.dist(a, b) for a in adj for b in adj[a] if inside(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))) / 2
    junction = {v for v in adj if len(adj[v]) != 2 and inside(v)}
    deg = [len(adj[v]) for v in junction]
    # edges between junctions: walk degree-2 chains
    seen, lengths, straight = set(), [], []
    for s in junction:
        for nb in adj[s]:
            if (s, nb) in seen:
                continue
            path = [s, nb]
            while len(adj[path[-1]]) == 2:
                nxt = next(iter(adj[path[-1]] - {path[-2]}), None)
                if nxt is None or nxt == path[0]:
                    break
                path.append(nxt)
            seen.add((path[-1], path[-2]))
            seen.add((s, nb))
            L = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
            if L > 5:
                lengths.append(L)
                straight.append(math.dist(path[0], path[-1]) / L)
    # orientation order (Boeing 2019): 1 = perfect grid, 0 = uniform
    hist = np.zeros(36)
    for a in adj:
        if not inside(a):
            continue
        for b in adj[a]:
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
            hist[int(ang // 5) % 36] += math.dist(a, b)
    p = hist / max(hist.sum(), 1e-9)
    H = -sum(x * math.log(x) for x in p if x > 0)
    hmax, hgrid = math.log(36), math.log(4)
    order = 1 - ((H - hgrid) / (hmax - hgrid)) ** 2 if H > hgrid else 1.0
    n = max(len(deg), 1)
    return {
        "density_km_per_km2": total / 2400 / max(area_km2, 1e-9),
        "block_median": float(np.median(lengths)) if lengths else 0,
        "block_p75": float(np.percentile(lengths, 75)) if lengths else 0,
        "straightness": float(np.mean(straight)) if straight else 1,
        "dead_end_frac": sum(d == 1 for d in deg) / n,
        "t_frac": sum(d == 3 for d in deg) / n,
        "cross_frac": sum(d >= 4 for d in deg) / n,
        "orientation_order": float(order),
        "junctions_per_km2": len(junction) / max(area_km2, 1e-9),
    }


KEYS = ["density_km_per_km2", "block_median", "straightness", "dead_end_frac", "t_frac", "cross_frac", "orientation_order"]

if __name__ == "__main__":
    if len(sys.argv) > 1:
        d = json.load(open(sys.argv[1]))
        print(json.dumps(stats(d["roads"], d["half"]), indent=1))
        sys.exit()
    per, roles = {}, defaultdict(list)
    for f in sorted(glob.glob("tools/data/roads/*.json")):
        d = json.load(open(f))
        s = stats(d["roads"], d["half"])
        per[d["name"]] = s | {"role": d["role"]}
        roles[d["role"]].append(s)
        print(f"{d['name']:22s} {d['role']:9s} " + " ".join(f"{k[:10]}={s[k]:.2f}" for k in KEYS))
    target = {r: {k: float(np.mean([s[k] for s in rows])) for k in rows[0]} for r, rows in roles.items()}
    json.dump({"templates": per, "roles": target}, open("tools/data/road_stats.json", "w"), indent=1)
    print("\nper-role targets:")
    for r, t in target.items():
        print(f"  {r:9s} " + " ".join(f"{k[:10]}={t[k]:.2f}" for k in KEYS))
