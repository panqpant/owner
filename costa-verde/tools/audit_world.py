"""Audit build/world.json: is the road network connected, is built-up land used, are there roads over
water without bridges, buildings on roads, and do district street patterns match the real data?
Usage: python tools/audit_world.py  -> prints a report and writes tools/data/audit.md. Exit code 1 on a failed check."""
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, "tools")
from road_stats import KEYS, stats  # noqa: E402

W = json.load(open("build/world.json"))
subprocess.run(["lune", "run", "tools/audit-exact.luau"], check=True, capture_output=True)
EXACT = json.load(open("build/audit_exact.json"))  # exact-resolution checks using the game's terrain code
TARGET = json.load(open("tools/data/road_stats.json"))["roles"]
hm = W["heightmap"]
n, cell = hm["n"], hm["cell"]
water = np.array(hm["water"], float).reshape(n, n) > -9000
built = np.array(hm["built"], bool).reshape(n, n)
ROADS = [r for r in W["roads"] if r["kind"] != "runway"]
lines, fails = [], []


def say(s=""):
    print(s)
    lines.append(s)


def check(name, ok, detail):
    say(f"- [{'PASS' if ok else 'FAIL'}] {name}: {detail}")
    if not ok:
        fails.append(name)


def key(x, z):
    return (round(x * 2), round(z * 2))  # half-stud grid


# 1. Connectivity (union-find over shared vertices)
parent = {}


def find(a):
    while parent.setdefault(a, a) != a:
        parent[a] = parent[parent[a]]
        a = parent[a]
    return a


deg = Counter()
for r in ROADS:
    a, b = key(r["ax"], r["az"]), key(r["bx"], r["bz"])
    if a == b:
        continue
    parent[find(a)] = find(b)
    deg[a] += 1
    deg[b] += 1
comp_len = Counter()
for r in ROADS:
    comp_len[find(key(r["ax"], r["az"]))] += math.dist((r["ax"], r["az"]), (r["bx"], r["bz"]))
total = sum(comp_len.values())
main = comp_len.most_common(1)[0][1]
say("## Road network")
say(f"total road length {total / 2400:.0f} km in {len(comp_len)} pieces")
check("connected network", main / total > 0.97, f"{100 * main / total:.1f}% of all road length is one connected network (target > 97%)")
small = [l for c, l in comp_len.items() if l != main]
say(f"  disconnected pieces: {len(small)}, total {sum(small) / 2400:.1f} km, largest {max(small, default=0) / 2400:.2f} km")

# 2. Dead ends by road kind (vertices of degree 1)
kind_at = defaultdict(set)
for r in ROADS:
    kind_at[key(r["ax"], r["az"])].add(r["kind"])
    kind_at[key(r["bx"], r["bz"])].add(r["kind"])
ends = [v for v, d in deg.items() if d == 1]
by_kind = Counter(next(iter(kind_at[v])) for v in ends)
junctions = sum(1 for d in deg.values() if d != 2)
say(f"dead ends by kind: {dict(by_kind)}")
major_ends = sum(by_kind[k] for k in ("freeway", "boulevard", "arterial", "state"))
ends_all = EXACT["inland_ends"]  # every loose major-road end (exact check)
bad_ends = [e for e in ends_all if e["district"] != "keytown"]  # the overseas highway ends in Key Marisol's streets
check("major roads don't just stop", not bad_ends, f"{len(ends_all)} loose major-road ends, {len(bad_ends)} outside Key Marisol: {[(e['kind'], e['district'], round(e['x']), round(e['z'])) for e in bad_ends][:8]}")
rural_ends = by_kind["county"]
county_j = sum(1 for v, d in deg.items() if d != 2 and "county" in kind_at[v])
say(f"rural county-road dead ends: {rural_ends} of {county_j} county junctions/ends ({100 * rural_ends / max(county_j, 1):.0f}%; real rural networks: 34%)")
SURFACE = {"street", "collector", "arterial", "boulevard", "county", "drive"}
# a freeway's own end may meet surface roads (real freeways terminate at junctions); mid-span (the same
# freeway on both sides of the point) may not
fw_rid = Counter()
for r in ROADS:
    if r["kind"] == "freeway":
        fw_rid[(key(r["ax"], r["az"]), r.get("rid"))] += 1
        fw_rid[(key(r["bx"], r["bz"]), r.get("rid"))] += 1
through_pts = {v for (v, rid), n in fw_rid.items() if n >= 2}
at_grade = sum(1 for v in through_pts if kind_at[v] & SURFACE)
check("freeways are grade-separated", at_grade == 0, f"{at_grade} places where a surface road meets a freeway mid-span at grade (should only connect via ramps)")
say(f"interchange ramps: {sum(1 for r in ROADS if r['kind'] == 'ramp')} segments")
city_ends = by_kind["street"] + by_kind["collector"]
city_j = sum(1 for v, d in deg.items() if d != 2 and kind_at[v] & {"street", "collector"})
check("city dead ends like real cities", city_ends / max(city_j, 1) < 0.30, f"{100 * city_ends / max(city_j, 1):.0f}% of city street junctions are dead ends (real US: 12-27%, mostly cul-de-sacs)")

# 3. Unused space: built-up land near a road / a building
def raster(points, radius):
    m = np.zeros((n, n), bool)
    r = int(math.ceil(radius / cell))
    for x, z in points:
        i, j = int(x / cell), int(z / cell)
        m[max(0, j - r):j + r + 1, max(0, i - r):i + r + 1] = True
    return m


road_pts = []
for r in ROADS:
    L = math.dist((r["ax"], r["az"]), (r["bx"], r["bz"]))
    for t in np.linspace(0, 1, max(2, int(L / cell) + 1)):
        road_pts.append((r["ax"] + (r["bx"] - r["ax"]) * t, r["az"] + (r["bz"] - r["az"]) * t))
near_road = raster(road_pts, 150)
near_bldg = raster([(b["x"], b["z"]) for b in W["buildings"]], 130)
say("\n## Land use")
cov_r = (built & near_road).sum() / built.sum()
cov_b = (built & near_bldg).sum() / built.sum()
check("built-up land reached by roads", cov_r > 0.92, f"{100 * cov_r:.1f}% of built-up land is within 150 studs of a road")
check("built-up land has buildings", cov_b > 0.80, f"{100 * cov_b:.1f}% of built-up land has a building within 130 studs")

# 4. Roads over water without a bridge
ub = EXACT["unbridged_studs"] or {}
ub_len = sum(ub.values())
say("\n## Water")
check("no roads driving through water", ub_len < 0.001 * total, f"{ub_len / 2400:.2f} km of road over water without a bridge (exact terrain); by kind (studs) { {k: round(v) for k, v in ub.items()} }")

# 5. Buildings on roads / overlapping
seg_grid = defaultdict(list)
for r in ROADS:
    for gx in range(int(min(r["ax"], r["bx"]) // 128) - 1, int(max(r["ax"], r["bx"]) // 128) + 2):
        for gz in range(int(min(r["az"], r["bz"]) // 128) - 1, int(max(r["az"], r["bz"]) // 128) + 2):
            seg_grid[(gx, gz)].append(r)


def on_road(b):
    x, z = b["x"], b["z"]
    rad = min(b["w"], b["d"]) / 2
    for r in seg_grid[(int(x // 128), int(z // 128))]:
        dx, dz = r["bx"] - r["ax"], r["bz"] - r["az"]
        L2 = dx * dx + dz * dz or 1e-9
        t = max(0, min(1, ((x - r["ax"]) * dx + (z - r["az"]) * dz) / L2))
        if math.dist((x, z), (r["ax"] + dx * t, r["az"] + dz * t)) < rad + r["width"] / 2 - 2:
            return True
    return False


B = W["buildings"]
bad = sum(on_road(b) for b in B)
say("\n## Buildings")
check("buildings not on roads", bad / len(B) < 0.01, f"{bad} of {len(B)} buildings ({100 * bad / len(B):.2f}%) overlap a road")
bg = defaultdict(list)
for b in B:
    bg[(int(b["x"] // 128), int(b["z"] // 128))].append(b)
ov = 0
for b in B:
    for i in (-1, 0, 1):
        for j in (-1, 0, 1):
            for o in bg[(int(b["x"] // 128) + i, int(b["z"] // 128) + j)]:
                if o is not b and math.dist((b["x"], b["z"]), (o["x"], o["z"])) < (min(b["w"], b["d"]) + min(o["w"], o["d"])) / 2 - 2:
                    ov += 1
check("buildings not overlapping", ov / 2 / len(B) < 0.01, f"{ov // 2} overlapping pairs")
say(f"buildings by district: {dict(Counter(b['district'] for b in B).most_common())}")

# 6. Street patterns per district vs real US networks
say("\n## Street patterns vs real data (2.4 km windows at district centres)")
STYLE = {d["id"]: None for d in W["districts"]}
style_of = {"downtown": "tower", "midtown": "midrise", "calle": "stucco", "docks": "warehouse", "northshore": "house",
            "westside": "house", "palmgrove": "house", "university": "campus", "gulftown": "stucco"}
for d in W["districts"]:
    role = style_of.get(d["id"])
    if not role:
        continue
    half = 3000
    local = [{"kind": r["kind"] if r["kind"] in ("street", "collector") else "arterial",
              "pts": [(r["ax"] - d["x"], r["az"] - d["z"]), (r["bx"] - d["x"], r["bz"] - d["z"])]}
             for r in ROADS if abs((r["ax"] + r["bx"]) / 2 - d["x"]) < half and abs((r["az"] + r["bz"]) / 2 - d["z"]) < half
             and r["kind"] in ("street", "collector", "arterial", "boulevard")]
    s = stats(local, half, clip_frac=0.4)
    t = TARGET[role]
    say(f"  {d['id']:10s} ({role:9s}) " + "  ".join(f"{k[:8]} {s[k]:.2f}/{t[k]:.2f}" for k in KEYS))

# 6a. Building uses vs the real Florida mix (metro, general-purpose styles), and markers
say("\n## Building uses")
RATES = json.load(open("tools/data/building_rates.json"))["business"]
metro_uses = Counter(b.get("use") for b in B if b["style"] in ("midrise", "stucco", "deco") and b["district"] not in ("keytown",))
tot = sum(metro_uses.values())
real_tot = sum(r["urban_per_100k"] for r in RATES.values() if r["group"] not in ("Industry & logistics", "Utilities"))
off = []
for name, r in sorted(RATES.items(), key=lambda kv: -kv[1]["urban_per_100k"])[:12]:
    if r["group"] in ("Industry & logistics", "Utilities"):
        continue
    real_share = r["urban_per_100k"] / real_tot
    map_share = metro_uses[name] / max(tot, 1)
    if not 0.5 < map_share / real_share < 2:
        off.append(f"{name} {100 * map_share:.1f}% vs real {100 * real_share:.1f}%")
check("building uses match the real mix", not off and tot > 0, f"top uses within 2x of real Florida shares{': ' + '; '.join(off) if off else ''}")
missing_use = sum(1 for b in B if not b.get("use"))
check("every building has a use", missing_use == 0, f"{missing_use} without a use")
mk = Counter(b["marker"] for b in B if b.get("marker"))
say(f"map markers: {dict(mk)}")

# 6b. Landmarks: all placed, on the right ground, not cut by roads or buildings, reachable
say("\n## Landmarks")
LM = W.get("landmarks", [])
check("all 200 landmarks placed", len(LM) == 200, f"{len(LM)} of 200 placed")
sea_ok = {"offshore", "shore", "islet", "bridge"}  # piers and marinas touch water by design; islets are smaller than the audit grid


def inside(l, x, z, shrink=0):
    return abs(x - l["x"]) < l["w"] / 2 - shrink and abs(z - l["z"]) < l["d"] / 2 - shrink


wet_lm = [l["name"] for l in LM if l["site"] not in sea_ok and water[min(n - 1, int(l["z"] / cell)), min(n - 1, int(l["x"] / cell))]]
check("landmarks on land (except offshore ones)", not wet_lm, f"{len(wet_lm)} on water: {wet_lm[:5]}")
cut = []
for l in LM:
    for r in seg_grid[(int(l["x"] // 128), int(l["z"] // 128))]:
        if l["site"] != "bridge" and r["kind"] != "access" and inside(l, (r["ax"] + r["bx"]) / 2, (r["az"] + r["bz"]) / 2, 10):
            cut.append(l["name"])
            break
check("no road through a landmark", not cut, f"{len(cut)} landmarks with a road through them: {cut[:5]}")
on_lm = sum(1 for b in B for l in LM if abs(b["x"] - l["x"]) < 900 and inside(l, b["x"], b["z"], 5))
check("no ordinary building inside a landmark", on_lm == 0, f"{on_lm} buildings inside landmark footprints")
unreached = []
for l in LM:
    if l["site"] in ("offshore", "islet", "bridge"):
        continue
    reach = max(l["w"], l["d"]) / 2 + 200
    if not any(math.dist((l["x"], l["z"]), ((r["ax"] + r["bx"]) / 2, (r["az"] + r["bz"]) / 2)) < reach
               for r in ROADS if abs(r["ax"] - l["x"]) < reach and abs(r["az"] - l["z"]) < reach):
        unreached.append(l["name"])
check("landmarks reachable by road (boat/air for islets and offshore)", not unreached, f"{len(unreached)} with no road nearby: {unreached[:5]}")
say(f"landmark sites: {dict(Counter(l['site'] for l in LM))}")

# 7. Transit
say("\n## Transit")
st_far = 0
for st in W["stations"]:
    if not any(abs(r["ax"] - st["x"]) < 150 and abs(r["az"] - st["z"]) < 150 for r in seg_grid[(int(st["x"] // 128), int(st["z"] // 128))]):
        st_far += 1
check("stations reachable from a road", st_far == 0, f"{st_far} of {len(W['stations'])} stations have no road within ~150 studs")
say(f"lines: {dict(Counter(t['line'] for t in W['tracks']))}")

say(f"\n{len(fails)} failed checks: {fails}" if fails else "\nall checks passed")
open("tools/data/audit.md", "w").write("# World audit\n\n" + "\n".join(lines) + "\n")
sys.exit(1 if fails else 0)
