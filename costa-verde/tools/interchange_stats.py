"""Measure the real mix of freeway interchange types from Census TIGER/Line ramps (public domain).
Usage: python tools/interchange_stats.py -> tools/data/interchange_stats.json
Ramps (MTFCC S1630) are clustered into interchanges and classified by geometry:
  system   - two freeways (S1100) meet at the cluster
  clover   - 4+ loop ramps (a loop turns ~270 degrees)
  parclo   - 1-3 loop ramps
  spui     - no loops and the ramps meet the crossing road at one point
  diamond  - no loops otherwise
Check against the published national figure: diamonds ~61% of 25,000+ US interchanges
(Professional Geographer 74(1), 2021)."""
import json
import math
import urllib.parse
import urllib.request
from collections import defaultdict

BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/{layer}/query"
REGIONS = {  # name: (south, west, north, east), urban flag
    "miami": ((25.65, -80.45, 25.95, -80.15), True),
    "broward": ((26.0, -80.35, 26.3, -80.1), True),
    "tampa": ((27.85, -82.6, 28.15, -82.3), True),
    "orlando": ((28.35, -81.55, 28.65, -81.25), True),
    "jacksonville": ((30.15, -81.8, 30.45, -81.5), True),
    "rural_i75": ((26.4, -82.0, 27.3, -81.7), False),
    "rural_i10": ((30.2, -84.0, 30.6, -82.8), False),
}


def query(layer, where, box):
    s, w, n, e = box
    params = {"where": where, "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope", "inSR": 4326,
              "outSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": "MTFCC,NAME", "returnGeometry": "true",
              "f": "json", "resultRecordCount": 20000}
    with urllib.request.urlopen(BASE.format(layer=layer) + "?" + urllib.parse.urlencode(params), timeout=180) as r:
        return json.load(r).get("features", [])


def to_m(lat0):
    kx, kz = 111320 * math.cos(math.radians(lat0)), 110574
    return lambda p: (p[0] * kx, p[1] * kz)


def turning(path):
    total = 0.0
    for a, b, c in zip(path, path[1:], path[2:]):
        h1 = math.atan2(b[1] - a[1], b[0] - a[0])
        h2 = math.atan2(c[1] - b[1], c[0] - b[0])
        d = (h2 - h1 + math.pi) % (2 * math.pi) - math.pi
        total += d
    return abs(math.degrees(total))


def classify(region, box):
    proj = to_m((box[0] + box[2]) / 2)
    ramps = [[proj(p) for p in path] for f in query(8, "MTFCC='S1630'", box) for path in f["geometry"]["paths"]]
    fwys = [([proj(p) for p in path], f["attributes"].get("NAME") or "") for f in query(2, "MTFCC='S1100'", box)
            for path in f["geometry"]["paths"]]
    # merge ramp pieces into chains (pieces sharing endpoints), then cluster chains within 150 m
    def k(p):
        return (round(p[0]), round(p[1]))
    ends = defaultdict(list)
    for i, r in enumerate(ramps):
        ends[k(r[0])].append(i)
        ends[k(r[-1])].append(i)
    parent = list(range(len(ramps)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for lst in ends.values():
        for i in lst[1:]:
            parent[find(i)] = find(lst[0])
    cell = defaultdict(list)
    for i, r in enumerate(ramps):
        for p in r[:: max(1, len(r) // 4)]:
            cell[(int(p[0] // 150), int(p[1] // 150))].append(i)
    for (cx, cz), lst in list(cell.items()):
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                for j in cell.get((cx + dx, cz + dz), []):
                    if lst:
                        parent[find(j)] = find(lst[0])
    clusters = defaultdict(list)
    for i in range(len(ramps)):
        clusters[find(i)].append(i)
    counts = defaultdict(int)
    for members in clusters.values():
        pts = [p for i in members for p in ramps[i]]
        cx, cz = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
        # system interchange: two freeway segments actually cross near the ramps at a real angle
        # (names are unreliable, and the two carriageways of one freeway run parallel)
        near = [(a, b) for path, _ in fwys for a, b in zip(path, path[1:])
                if math.dist(a, (cx, cz)) < 600]
        system = False
        for i in range(len(near)):
            (a1, b1) = near[i]
            for j in range(i + 1, len(near)):
                (a2, b2) = near[j]
                d1 = (b1[0] - a1[0], b1[1] - a1[1])
                d2 = (b2[0] - a2[0], b2[1] - a2[1])
                den = d1[0] * d2[1] - d1[1] * d2[0]
                n1, n2 = math.hypot(*d1), math.hypot(*d2)
                if n1 < 1e-6 or n2 < 1e-6 or abs(den) / (n1 * n2) < math.sin(math.radians(30)):
                    continue
                t = ((a2[0] - a1[0]) * d2[1] - (a2[1] - a1[1]) * d2[0]) / den
                u = ((a2[0] - a1[0]) * d1[1] - (a2[1] - a1[1]) * d1[0]) / den
                if 0 <= t <= 1 and 0 <= u <= 1:
                    system = True
                    break
            if system:
                break
        loops = sum(1 for i in members if turning(ramps[i]) > 200)
        if len(members) < 2:
            continue  # stray ramp piece, not an interchange
        if system:
            kind = "system"
        elif loops >= 4:
            kind = "clover"
        elif loops >= 1:
            kind = "parclo"
        else:
            # SPUI: ramp ends away from the freeway converge on one point
            far = [max((r[0], r[-1]), key=lambda p: min(math.dist(p, q) for path, _ in fwys for q in path[:: max(1, len(path) // 30)]))
                   for r in (ramps[i] for i in members)]
            spread = max(math.dist(a, b) for a in far for b in far) if len(far) > 1 else 0
            kind = "spui" if len(members) >= 4 and spread < 90 else "diamond"
        counts[kind] += 1
    return dict(counts)


if __name__ == "__main__":
    out = {}
    for name, (box, urban) in REGIONS.items():
        c = classify(name, box)
        out[name] = {"urban": urban, "counts": c}
        tot = sum(c.values()) or 1
        print(f"{name:13s} {'urban' if urban else 'rural'} n={tot:4d} " + "  ".join(f"{k} {100 * v / tot:.0f}%" for k, v in sorted(c.items())))
    for flag in (True, False):
        agg = defaultdict(int)
        for v in out.values():
            if v.get("urban") == flag:
                for k, n in v["counts"].items():
                    agg[k] += n
        tot = sum(agg.values()) or 1
        out["urban_mix" if flag else "rural_mix"] = {k: v / tot for k, v in agg.items()}
        print(("URBAN" if flag else "RURAL") + " mix: " + "  ".join(f"{k} {100 * v / tot:.0f}%" for k, v in sorted(agg.items())))
    json.dump(out, open("tools/data/interchange_stats.json", "w"), indent=1)
