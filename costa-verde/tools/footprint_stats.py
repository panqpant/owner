"""Real building footprints -> size and shape statistics per district style.

Source: FEMA / ORNL "USA Structures" (public domain, outlines traced from satellite and aerial imagery).
For each street-network template region (tools/fetch_roads.py) it downloads the footprints in a box at the
centre, then measures, per building: area, long and short side of the minimum rotated rectangle, how much
of that rectangle the outline fills (1.0 = a plain box; L, T, U shapes are lower), corner count, angle to
the nearest street, distance to the street centreline (setback), gap to the nearest neighbour, and height.
Nothing is copied: only the distributions go into tools/data/footprint_stats.json, which the generator
is tuned against (tools/audit_world.py checks generated buildings against the same numbers).

Usage (from costa-verde/): python3 tools/footprint_stats.py [--refresh]
"""
import json
import math
import os
import sys
import urllib.parse
import urllib.request

from shapely import STRtree
from shapely.geometry import LineString, Polygon

sys.path.insert(0, os.path.dirname(__file__))
from fetch_roads import STUD_PER_M, TEMPLATES  # same regions and projection as the road training

URL = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/ArcGIS/rest/services/USA_Structures_View/FeatureServer/0/query"
HERE = os.path.dirname(__file__)
RAW = os.path.join(HERE, "data", "footprints")  # gitignored raw downloads
OUT = os.path.join(HERE, "data", "footprint_stats.json")
BOX_KM = {"rural": 4.0}  # sample box per region; towns 1.2 km
CAP = 6000


def fetch(name, lat, lon, km):
    path = os.path.join(RAW, name + ".json")
    if os.path.exists(path) and "--refresh" not in sys.argv:
        return json.load(open(path))
    dlat, dlon = km / 2 / 110.574, km / 2 / (111.320 * math.cos(math.radians(lat)))
    feats, offset = [], 0
    while len(feats) < CAP:
        params = {
            "geometry": f"{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}", "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "outSR": 4326, "spatialRel": "esriSpatialRelIntersects",
            "outFields": "OCC_CLS,PRIM_OCC,HEIGHT,OUTBLDG", "returnGeometry": "true", "f": "json",
            "resultOffset": offset, "resultRecordCount": 2000,
        }
        with urllib.request.urlopen(URL + "?" + urllib.parse.urlencode(params), timeout=180) as r:
            page = json.load(r)
        got = page.get("features", [])
        feats += got
        offset += len(got)
        if not got or not page.get("exceededTransferLimit"):
            break
    os.makedirs(RAW, exist_ok=True)
    json.dump(feats, open(path, "w"))
    return feats


def mrr(poly):
    """Long side, short side and long-side direction (radians) of the minimum rotated rectangle."""
    c = list(poly.minimum_rotated_rectangle.exterior.coords)
    a = math.dist(c[0], c[1])
    b = math.dist(c[1], c[2])
    if a >= b:
        return a, b, math.atan2(c[1][1] - c[0][1], c[1][0] - c[0][0])
    return b, a, math.atan2(c[2][1] - c[1][1], c[2][0] - c[1][0])


def pct(v, qs=(10, 25, 50, 75, 90)):
    v = sorted(v)
    if not v:
        return {}
    return {f"p{q}": round(v[min(len(v) - 1, int(q / 100 * len(v)))], 2) for q in qs}


def measure(name, lat, lon, role, km):
    mx = 111320 * math.cos(math.radians(lat))
    mz = 110574
    roads = json.load(open(os.path.join(HERE, "data", "roads", name + ".json")))["roads"]
    # road centrelines in metres (road cache is in studs)
    lines = [LineString([(x / STUD_PER_M, z / STUD_PER_M) for x, z in r["pts"]]) for r in roads if len(r["pts"]) > 1]
    rtree = STRtree(lines)
    polys, info = [], []
    for f in fetch(name, lat, lon, km):
        rings = f.get("geometry", {}).get("rings")
        if not rings:
            continue
        p = Polygon([((x - lon) * mx, -(y - lat) * mz) for x, y in rings[0]])
        if not p.is_valid or p.area < 20:
            continue
        polys.append(p)
        a = f["attributes"]
        info.append((a.get("OCC_CLS") or "Unknown", a.get("HEIGHT"), a.get("OUTBLDG")))
    ptree = STRtree(polys)
    rows = []
    for i, p in enumerate(polys):
        L, S, ang = mrr(p)
        simple = p.simplify(0.4)
        corners = len(simple.exterior.coords) - 1
        near = lines[rtree.nearest(p)]
        setback = p.distance(near)
        # angle between the building's long side and the street there (0 = parallel, 90 = end-on)
        s0 = near.interpolate(near.project(p.centroid))
        s1 = near.interpolate(min(near.length, near.project(p.centroid) + 2))
        s2 = near.interpolate(max(0, near.project(p.centroid) - 2))
        street = math.atan2(s1.y - s2.y, s1.x - s2.x)
        rel = abs(math.degrees(ang - street)) % 180
        rel = min(rel, 180 - rel)
        gap = None
        for j in ptree.query(p.buffer(60)):
            if j != i:
                d = p.distance(polys[j])
                gap = d if gap is None else min(gap, d)
        occ, h, out = info[i]
        rows.append({
            "occ": occ, "out": out == "Y" or out == 1, "area": p.area, "long": L, "short": S, "aspect": L / max(S, 0.1),
            "fill": p.area / max(L * S, 1), "corners": corners, "angle": rel, "setback": setback, "gap": gap,
            "h": h if isinstance(h, (int, float)) and h > 0 else None, "street_dist": s0.distance(p.centroid),
        })
    area_box = (km * 1000) ** 2
    return rows, area_box


def summarise(rows, area_box):
    main = [r for r in rows if not r["out"]]

    def stats(sel):
        return {
            "n": len(sel),
            "area_m2": pct([r["area"] for r in sel]),
            "long_m": pct([r["long"] for r in sel]),
            "short_m": pct([r["short"] for r in sel]),
            "aspect": pct([r["aspect"] for r in sel]),
            "fill": pct([r["fill"] for r in sel]),
            "corners": pct([r["corners"] for r in sel]),
            "plain_box_share": round(sum(1 for r in sel if r["fill"] > 0.97 and r["corners"] <= 4) / max(1, len(sel)), 3),
            "parallel_share": round(sum(1 for r in sel if r["angle"] < 20) / max(1, len(sel)), 3),
            "endon_share": round(sum(1 for r in sel if r["angle"] > 70) / max(1, len(sel)), 3),
            "setback_m": pct([r["setback"] for r in sel]),
            "gap_m": pct([r["gap"] for r in sel if r["gap"] is not None]),
            "height_m": pct([r["h"] for r in sel if r["h"]]),
        }

    out = {"all": stats(main), "coverage": round(sum(r["area"] for r in main) / area_box, 3),
           "per_km2": round(len(main) / (area_box / 1e6)), "outbuilding_share": round(1 - len(main) / max(1, len(rows)), 3)}
    for occ in sorted({r["occ"] for r in main}):
        sel = [r for r in main if r["occ"] == occ]
        if len(sel) >= 30:
            out[occ] = stats(sel)
    return out


def main():
    result = {"source": "FEMA/ORNL USA Structures (public domain), via services2.arcgis.com", "stud_per_m": STUD_PER_M, "regions": {}}
    by_role = {}
    for name, lat, lon, _km, role in TEMPLATES:
        km = BOX_KM.get(role, 1.2)
        try:
            rows, box = measure(name, lat, lon, role, km)
        except Exception as e:  # one region failing shouldn't lose the rest
            print(f"{name}: failed ({e})")
            continue
        s = summarise(rows, box)
        result["regions"][name] = {"role": role, **s}
        by_role.setdefault(role, ([], 0))
        by_role[role] = (by_role[role][0] + rows, by_role[role][1] + box)
        a = s["all"]
        print(f"{name:22s} {role:9s} n={a['n']:5d} area p50={a['area_m2'].get('p50')} long={a['long_m'].get('p50')} "
              f"short={a['short_m'].get('p50')} fill={a['fill'].get('p50')} box={a['plain_box_share']} "
              f"setback={a['setback_m'].get('p50')} gap={a['gap_m'].get('p50')} h={a['height_m'].get('p50')} cov={s['coverage']}")
    result["styles"] = {role: summarise(rows, box) for role, (rows, box) in by_role.items()}
    json.dump(result, open(OUT, "w"), indent=1)
    print("wrote", OUT)
    write_luau(result["styles"])


def write_luau(styles):
    """Quantile tables in studs for the generator (src/shared/Gen/FootprintData.luau)."""
    k, k2 = STUD_PER_M, STUD_PER_M ** 2
    q = ("p10", "p25", "p50", "p75", "p90")
    lines = ["-- Generated by tools/footprint_stats.py from FEMA/ORNL USA Structures footprints (public domain):",
             "-- real building size distributions per district style, in studs. Do not edit.",
             "-- area/aspect/setback/gap are quantiles at 10/25/50/75/90%; box = share of plain rectangles,",
             "-- endon = share of buildings whose long side runs away from the street (of those clearly aligned).",
             "return {"]
    for role, st in sorted(styles.items()):
        a = st["all"]
        if a["n"] < 30:
            continue
        def row(key, scale):
            return "{ " + ", ".join(f"{a[key][x] * scale:.1f}" for x in q) + " }"
        endon = a["endon_share"] / max(0.01, a["endon_share"] + a["parallel_share"])
        lines.append(f"\t{role} = {{ area = {row('area_m2', k2)}, aspect = {row('aspect', 1)}, setback = {row('setback_m', k)},"
                     f" gap = {row('gap_m', k)}, box = {a['plain_box_share']:.2f}, endon = {endon:.2f} }},")
    lines.append("}")
    path = os.path.join(HERE, "..", "src", "shared", "Gen", "FootprintData.luau")
    open(path, "w").write("\n".join(lines) + "\n")
    print("wrote", path)


if __name__ == "__main__":
    main()
