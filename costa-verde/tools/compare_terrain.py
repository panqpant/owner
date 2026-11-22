"""Side-by-side hillshades: real USGS regions (top) vs generated Costa Verde terrain of the same type (bottom).
Usage: python tools/compare_terrain.py  (needs build/heightmap.json and build/dem/ from the other tools)"""
import json
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from terrain_stats import REGIONS, KM, hillshade, fetch

CFG = open("src/shared/Gen/Config.luau").read()
VERT = float(re.search(r"Config.VERT = ([\d.]+)", CFG).group(1))
SPM = float(re.search(r"Config.STUD_PER_M = ([\d.]+)", CFG).group(1))
hm = json.load(open("build/heightmap.json"))
n, cell = hm["n"], hm["cell"]
h = np.array(hm["h"], float).reshape(n, n)
w = np.array(hm["water"], float).reshape(n, n)
surf = np.where(w > -9000, np.maximum(h, w), h) / VERT
lt = np.array(hm["ltype"]).reshape(n, n)
px_m = cell / SPM
VIEW_KM = 5.0
win = int(VIEW_KM * 1000 / px_m)  # same ground size for both
T = 256
picks = ["ridge_lakes", "sinkhole_lakes", "flat_cattle", "pine_flatwoods", "sawgrass", "big_cypress"]
sheet = Image.new("RGB", (len(picks) * T, 2 * (T + 20)), (20, 20, 22))
d = ImageDraw.Draw(sheet)
font = ImageFont.truetype("DejaVuSans.ttf", 13)
used = []
for i, name in enumerate(picks):
    lat, lon, biome = next((r[1], r[2], r[3]) for r in REGIONS if r[0] == name)
    real = fetch(name, lat, lon)
    c = int(256 * VIEW_KM / KM)
    o = (256 - c) // 2
    sheet.paste(hillshade(real[o:o + c, o:o + c], KM * 1000 / 256).resize((T, T), Image.BILINEAR), (i * T, 0))
    d.text((i * T + 4, T + 3), f"REAL {name} (5 km)", fill=(230, 230, 230), font=font)
    best, bxy = -1, (0, 0)
    for y in range(0, n - win, win // 4):
        for x in range(0, n - win, win // 4):
            if any(b == biome and abs(x - ux) < win and abs(y - uy) < win for ux, uy, b in used):
                continue
            f = (lt[y:y + win, x:x + win] == biome).mean()
            if f > best:
                best, bxy = f, (x, y)
    used.append((*bxy, biome))
    x, y = bxy
    tile = surf[y:y + win, x:x + win]
    img = hillshade(tile, px_m).resize((T, T), Image.BILINEAR)
    sheet.paste(img, (i * T, T + 20))
    d.text((i * T + 4, 2 * T + 23), f"OURS {biome} ({np.percentile(tile, 98) - np.percentile(tile, 2):.0f} m relief)", fill=(255, 220, 120), font=font)
sheet = sheet.crop((0, 0, sheet.width, 2 * T + 40))
sheet.save("screenshots/terrain_compare.png")
print("wrote screenshots/terrain_compare.png")
