"""Fetch real US road networks (Census TIGER/Line via TIGERweb, public domain) as street-pattern templates.
Usage: python tools/fetch_roads.py -> tools/data/roads/<name>.json
Training data only: tools/road_stats.py measures these networks and the generator is tuned to match
the statistics. No real street layout is placed in the game."""
import json
import math
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

STUD_PER_M = 2.4  # compresses real distances ~1.5x (GTA-style), keeps street widths sensible
BASE = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Transportation/MapServer/{layer}/query"
LAYERS = {8: "local", 6: "secondary", 2: "primary"}
# MTFCC road class -> our kind
CLASS = {"S1100": "arterial", "S1200": "arterial", "S1400": "street", "S1500": "track", "S1640": "street",
         "S1710": None, "S1720": None, "S1730": "alley", "S1740": "drive", "S1750": None, "S1780": "drive",
         "S1820": None, "S1830": None, "S1630": None}

# name, lat, lon, km box, role (matched to district styles)
TEMPLATES = [
    ("downtown_bayfront", 25.772, -80.193, 3.0, "tower"),
    ("downtown_riverfront", 27.950, -82.458, 3.0, "tower"),
    ("downtown_river_grid", 26.120, -80.143, 3.0, "midrise"),
    ("bay_old_town", 27.773, -82.640, 3.0, "midrise"),
    ("barrier_island_city", 25.800, -80.130, 5.0, "deco"),
    ("old_cuban_quarter", 25.766, -80.226, 3.0, "stucco"),
    ("gulf_old_town", 26.140, -81.795, 3.5, "stucco"),
    ("canal_suburb", 26.630, -81.975, 4.5, "house"),
    ("curvy_suburb", 26.100, -80.395, 4.5, "house"),
    ("cul_de_sac_suburb", 25.680, -80.380, 4.5, "house"),
    ("winding_suburb", 27.290, -80.350, 4.5, "house"),
    ("industrial_park", 25.810, -80.335, 3.5, "warehouse"),
    ("college_town", 29.645, -82.345, 3.5, "campus"),
    ("farm_town", 26.420, -81.420, 3.0, "shack"),
    ("sugar_town", 26.685, -80.667, 3.0, "shack"),
    ("county_roads_a", 27.500, -81.700, 16.0, "rural"),
    ("county_roads_b", 26.900, -81.200, 16.0, "rural"),
]


def query(layer, w, s, e, n):
    params = {
        "geometry": f"{w},{s},{e},{n}", "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
        "spatialRel": "esriSpatialRelIntersects", "outFields": "MTFCC", "returnGeometry": "true", "f": "json",
        "resultRecordCount": 20000,
    }
    with urllib.request.urlopen(BASE.format(layer=layer) + "?" + urllib.parse.urlencode(params), timeout=120) as r:
        return json.load(r).get("features", [])


def simplify(pts, tol):
    """Douglas-Peucker."""
    if len(pts) < 3:
        return pts
    (ax, az), (bx, bz) = pts[0], pts[-1]
    dx, dz = bx - ax, bz - az
    L = math.hypot(dx, dz) or 1e-9
    best, idx = 0, 0
    for i in range(1, len(pts) - 1):
        d = abs(dx * (az - pts[i][1]) - dz * (ax - pts[i][0])) / L
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [pts[0], pts[-1]]
    return simplify(pts[: idx + 1], tol)[:-1] + simplify(pts[idx:], tol)


def fetch(t):
    name, lat, lon, km, role = t
    dlat = km / 2 / 110.574
    dlon = km / 2 / (111.320 * math.cos(math.radians(lat)))
    box = (lon - dlon, lat - dlat, lon + dlon, lat + dlat)
    mx = 111320 * math.cos(math.radians(lat)) * STUD_PER_M
    mz = 110574 * STUD_PER_M
    roads, seen = [], set()
    layers = [8, 6] if role != "rural" else [8, 6, 2]
    for layer in layers:
        for f in query(layer, *box):
            kind = CLASS.get(f["attributes"].get("MTFCC"), "street")
            if role == "rural" and kind == "street":
                kind = "county"
            if kind is None:
                continue
            for path in f["geometry"]["paths"]:
                pts = [(round((p[0] - lon) * mx, 1), round(-(p[1] - lat) * mz, 1)) for p in path]
                key = (pts[0], pts[-1])
                if key in seen:
                    continue
                seen.add(key)
                pts = simplify(pts, 0.5)  # near-lossless: keeps junction vertices for tools/road_stats.py
                roads.append((kind, pts))
    with open(f"tools/data/roads/{name}.json", "w") as fh:
        json.dump({"name": name, "role": role, "half": km * 1000 * STUD_PER_M / 2,
                   "roads": [{"kind": k, "pts": p} for k, p in roads]}, fh)
    return name, role, len(roads), sum(len(p) for _, p in roads)


os.makedirs("tools/data/roads", exist_ok=True)
with ThreadPoolExecutor(4) as ex:
    for name, role, n, pts in ex.map(fetch, TEMPLATES):
        print(f"{name:22s} {role:9s} {n:6d} roads {pts:7d} points")
