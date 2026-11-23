"""Top-down map of build/world.json -> screenshots/map.png. Usage: python tools/render_map.py"""
import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

world = json.load(open("build/world.json"))
hm = world["heightmap"]
n, size = hm["n"], world["size"]
PX = int(sys.argv[2]) if len(sys.argv) > 2 else 3072
k = PX / size

# Colours sampled by eye from the USGS reference set.
BIOME = {"beach": (214, 200, 160), "mangrove": (40, 70, 40), "wetland": (120, 112, 70), "hammock": (50, 80, 40),
         "farm": (95, 120, 60), "scrub": (90, 110, 65)}
MAT = {"Grass": (110, 135, 60), "LeafyGrass": (70, 100, 45), "Ground": (110, 90, 60), "Mud": (70, 75, 55), "Sand": (214, 200, 160)}
h = np.array(hm["h"], dtype=float).reshape(n, n)
wl = np.array(hm["water"], dtype=float).reshape(n, n)
rgb = np.zeros((n, n, 3), dtype=float)
for idx, (bi, m) in enumerate(zip(hm["biome"], hm["material"])):
    c = MAT[m] if bi in ("farm", "wetland") and m in MAT else BIOME.get(bi, (90, 110, 65))
    if hm["built"][idx] and bi != "beach":
        c = (176, 172, 162)  # built-up ground (light, so streets read)
    rgb[idx // n, idx % n] = c
biome = np.array(hm["biome"]).reshape(n, n)
depth = np.clip((wl - h) / 40, 0, 1)[..., None]
sea = np.array([95, 200, 200]) * (1 - depth) + np.array([20, 55, 105]) * depth  # turquoise shelf -> deep blue
bay = np.array([70, 120, 105]) * (1 - depth) + np.array([40, 95, 100]) * depth  # seagrass bay
lake = np.array([25, 45, 50])
marsh = np.array([55, 70, 60])
water = wl > -9000
rgb = np.where(water[..., None] & (biome == "bay")[..., None], bay, np.where(water[..., None] & (biome == "lake")[..., None], lake, np.where(water[..., None] & np.isin(biome, ["marsh", "wetland", "hammock"])[..., None], marsh, np.where(water[..., None], sea, rgb))))
img = Image.fromarray(rgb.clip(0, 255).astype(np.uint8)).resize((PX, PX), Image.BILINEAR)
S_PX = PX
d = ImageDraw.Draw(img)

for p in world["parks"]:
    x, z, w = p["x"] * k, p["z"] * k, p["w"] * k / 2
    d.rectangle([x - w, z - w, x + w, z + w], fill={"lake": (25, 45, 50), "golf": (110, 160, 80), "park": (60, 110, 50)}[p["kind"]])
# Road hierarchy: draw minor first, majors on top; freeways get a casing.
ORDER = ["drive", "access", "county", "street", "collector", "runway", "state", "arterial", "boulevard", "ramp", "freeway"]
COL = {"street": (70, 70, 76), "collector": (55, 55, 62), "arterial": (235, 200, 120), "boulevard": (245, 170, 90),
       "state": (225, 190, 110), "ramp": (230, 150, 90), "freeway": (230, 120, 60), "runway": (150, 150, 150), "county": (150, 135, 105), "drive": (165, 150, 120), "access": (205, 120, 190)}
def road_width(r):
    return max(1, int(r["width"] * k * (2.2 if r["kind"] in ("freeway", "boulevard", "arterial", "state", "ramp") else 1.6)))


for kind in ORDER:
    group = [r for r in world["roads"] if r["kind"] == kind]
    if kind == "freeway":  # casing first for the whole freeway, then the fill, so segments don't hatch
        for r in group:
            d.line([r["ax"] * k, r["az"] * k, r["bx"] * k, r["bz"] * k], fill=(60, 40, 30), width=road_width(r) + 3)
    for r in group:
        d.line([r["ax"] * k, r["az"] * k, r["bx"] * k, r["bz"] * k], fill=(205, 205, 210) if r["bridge"] else COL[kind], width=road_width(r))
STYLE = {"tower": (205, 215, 230), "midrise": (190, 190, 180), "deco": (250, 190, 200), "stucco": (240, 220, 170), "warehouse": (170, 150, 130),
         "house": (235, 235, 225), "campus": (200, 120, 100), "shack": (150, 120, 90), "farmhouse": (240, 240, 230),
         "barn": (170, 40, 35), "silo": (200, 200, 205), "store": (90, 140, 200), "gas": (230, 200, 40), "church": (255, 255, 255),
         "diner": (230, 90, 140), "trailer": (200, 200, 190)}
for b in world["buildings"]:
    x, z = b["x"], b["z"]
    c, sn = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
    base = STYLE.get(b["style"], (200, 200, 200))
    for p in sorted(b.get("parts", []), key=lambda p: p["base"] + p["h"]):  # taller parts drawn on top, darker
        pts = p["pts"]
        poly = [((x + c * pts[i] - sn * pts[i + 1]) * k, (z + sn * pts[i] + c * pts[i + 1]) * k) for i in range(0, len(pts), 2)]
        shade = 1 - min(0.35, (p["base"] + p["h"]) / 1500)
        fill = tuple(int(v * shade) for v in base) if p["roof"] not in ("canopy",) else (210, 210, 215)
        d.polygon(poly, fill=fill, outline=tuple(int(v * 0.6) for v in base))

for t in world["tracks"]:
    pts = [t["ax"] * k, t["az"] * k, t["bx"] * k, t["bz"] * k]
    if t["kind"] == "metro":
        d.line(pts, fill=(150, 60, 200), width=5)
    else:
        d.line(pts, fill=(30, 30, 30), width=5)
        d.line(pts, fill=(220, 220, 220), width=2)
for st in world["stations"]:
    x, z = st["x"] * k, st["z"] * k
    d.ellipse([x - 7, z - 7, x + 7, z + 7], fill=(255, 255, 255), outline=(150, 60, 200), width=3)
for p in world["pois"]:
    x, z = p["x"] * k, p["z"] * k
    star = [(x + (10 if i % 2 == 0 else 4) * math.cos(math.pi / 5 * i - math.pi / 2), z + (10 if i % 2 == 0 else 4) * math.sin(math.pi / 5 * i - math.pi / 2)) for i in range(10)]
    d.polygon(star, fill=(255, 215, 0), outline=(0, 0, 0))
try:
    small = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
except OSError:
    small = ImageFont.load_default()
for st in world["settlements"]:
    d.text((st["x"] * k, st["z"] * k - 18), st["name"], fill=(255, 250, 220), font=small, anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
try:
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", 26)
except OSError:
    font = ImageFont.load_default()
for dist in world["districts"]:
    x, z = dist["x"] * k, dist["z"] * k
    d.text((x, z), dist["name"], fill=(255, 255, 255), font=font, anchor="mm", stroke_width=3, stroke_fill=(0, 0, 0))
# Landmarks: footprints with names (readable when zoomed); playable markers as lettered circles.
lm_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 12)
SURFACE = {"lot": (120, 120, 125), "field": (90, 160, 80), "stands": (225, 120, 200), "runway": (60, 60, 65), "deck": (170, 130, 90),
           "tank": (230, 230, 235), "water": (60, 170, 220), "panel": (40, 60, 120), "wall": (60, 60, 60), "pit": (175, 150, 110)}
for l in world.get("landmarks", []):
    x, z, w2, d2 = l["x"] * k, l["z"] * k, l["w"] * k / 2, l["d"] * k / 2
    if l.get("parts"):  # site plan: surfaces in their own colours, buildings in landmark magenta
        for p in sorted(l["parts"], key=lambda p: p["base"] + p["h"]):
            pts = p["pts"]
            poly = [((l["x"] + pts[i]) * k, (l["z"] + pts[i + 1]) * k) for i in range(0, len(pts), 2)]
            d.polygon(poly, fill=SURFACE.get(p["roof"], (205, 60, 180)), outline=(90, 0, 80) if p["roof"] not in SURFACE else None)
    else:
        d.rectangle([x - w2, z - d2, x + w2, z + d2], fill=(205, 60, 180), outline=(90, 0, 80), width=2)
    d.text((x, z - d2 - 8), l["name"], fill=(255, 230, 250), font=lm_font, anchor="mm", stroke_width=2, stroke_fill=(60, 0, 50))
MARK = {"gun_store": ("G", (200, 30, 30)), "mod_shop": ("M", (240, 140, 20)), "car_dealer": ("C", (40, 120, 220)),
        "boat_dealer": ("B", (20, 160, 200)), "clothing": ("S", (180, 80, 220)), "barber": ("H", (120, 80, 40)),
        "tattoo": ("T", (40, 40, 40)), "convenience": ("$", (30, 150, 60)), "gas": ("F", (230, 200, 20)),
        "liquor": ("L", (150, 40, 90)), "bank": ("K", (20, 90, 40)), "jewelry": ("J", (220, 180, 60)),
        "pawn": ("P", (100, 100, 100)), "food": ("E", (230, 90, 60)), "bar": ("D", (110, 40, 160)),
        "gym": ("Y", (60, 60, 160)), "cinema": ("V", (90, 90, 200)), "arcade": ("A", (200, 60, 120)),
        "bowling": ("W", (100, 160, 160)), "hospital": ("+", (220, 40, 40)), "fire": ("R", (230, 60, 0)),
        "police": ("*", (20, 50, 160))}
mk_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
for b in world["buildings"]:
    if b.get("marker") in MARK:
        ch, col = MARK[b["marker"]]
        x, z = b["x"] * k, b["z"] * k
        d.ellipse([x - 8, z - 8, x + 8, z + 8], fill=col, outline=(255, 255, 255), width=2)
        d.text((x, z), ch, fill=(255, 255, 255), font=mk_font, anchor="mm")
lx, ly = 24, S_PX - 30 - 18 * len(MARK)
d.rectangle([lx - 8, ly - 8, lx + 260, S_PX - 16], fill=(20, 24, 30))
for i, (name, (ch, col)) in enumerate(MARK.items()):
    y = ly + 18 * i
    d.ellipse([lx, y, lx + 14, y + 14], fill=col, outline=(255, 255, 255))
    d.text((lx + 7, y + 7), ch, fill=(255, 255, 255), font=mk_font, anchor="mm")
    d.text((lx + 22, y), name.replace("_", " "), fill=(230, 230, 230), font=mk_font)
d.rectangle([lx + 150, ly, lx + 164, ly + 14], fill=(205, 60, 180), outline=(90, 0, 80))
d.text((lx + 170, ly), "landmark", fill=(230, 230, 230), font=mk_font)

d.text((24, 24), f"COSTA VERDE  ~{size * 0.28 / 1000:.1f} x {size * 0.28 / 1000:.1f} km   * = easter egg   o = station", fill=(255, 255, 255), font=font, stroke_width=3, stroke_fill=(0, 0, 0))

out = sys.argv[1] if len(sys.argv) > 1 else "screenshots/map.png"
img.save(out)
print("wrote", out)
