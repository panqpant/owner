"""Learn terrain character from real USGS 3DEP elevation (public domain).
Usage: python tools/terrain_stats.py [--compare build/world.json]
-> tools/data/terrain_stats.json (per-region RMS height per wavelength band, relief, slopes)
-> screenshots/terrain_real.png (hillshades of the training regions)
The generator's per-octave amplitudes in Config.TERRAIN_BANDS are fitted from these numbers."""
import json
import math
import os
import sys
import time
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFont

URL = ("https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
       "?bbox={w},{s},{e},{n}&bboxSR=4326&imageSR=4326&size=256,256&format=tiff&pixelType=F32&noData=-9999&f=image")
KM = 12.0  # box size per region
# name, lat, lon, biome it trains
REGIONS = [
    ("ridge_lakes", 27.75, -81.55, "farm"),
    ("rolling_hills", 28.85, -82.10, "farm"),
    ("sinkhole_lakes", 28.05, -81.75, "farm"),
    ("citrus_ridge", 28.45, -81.75, "farm"),
    ("flat_cattle", 27.35, -81.15, "scrub"),
    ("river_valley", 27.40, -82.30, "scrub"),
    ("pine_flatwoods", 26.90, -81.60, "scrub"),
    ("coastal_plain", 27.20, -80.50, "coast"),
    ("gulf_coast", 26.60, -81.80, "coast"),
    ("sugar_flats", 26.65, -80.65, "wetland"),
    ("big_cypress", 26.10, -81.20, "wetland"),
    ("sawgrass", 25.85, -80.75, "wetland"),
]
BANDS_M = [150, 300, 600, 1200, 2400, 4800]  # wavelengths (m), octave bands


def fetch(name, lat, lon):
    os.makedirs("build/dem", exist_ok=True)
    path = f"build/dem/{name}.npy"
    if os.path.exists(path):
        return np.load(path)
    dlat = KM / 2 / 110.574
    dlon = KM / 2 / (111.320 * math.cos(math.radians(lat)))
    url = URL.format(w=lon - dlon, s=lat - dlat, e=lon + dlon, n=lat + dlat)
    for attempt in range(5):
        try:
            urllib.request.urlretrieve(url, "build/dem/tmp.tif")
            a = np.array(Image.open("build/dem/tmp.tif"), dtype=np.float64)
            break
        except Exception:
            time.sleep(4 * (attempt + 1))
    else:
        raise RuntimeError(f"could not fetch {name}")
    a[a < -1000] = np.nan
    a = np.where(np.isnan(a), np.nanmin(a), a)
    np.save(path, a)
    return a


def band_rms(h, px_m):
    """RMS height (m) in octave wavelength bands, from the detrended, windowed spectrum."""
    n = h.shape[0]
    y, x = np.mgrid[0:n, 0:n]
    A = np.c_[x.ravel(), y.ravel(), np.ones(n * n)]
    coef, *_ = np.linalg.lstsq(A, h.ravel(), rcond=None)
    d = h - (A @ coef).reshape(n, n)
    win = np.outer(np.hanning(n), np.hanning(n))
    F = np.fft.fft2(d * win) / np.sqrt((win ** 2).sum())
    P = np.abs(F) ** 2 / (n * n)
    fy, fx = np.meshgrid(np.fft.fftfreq(n, px_m), np.fft.fftfreq(n, px_m), indexing="ij")
    f = np.hypot(fx, fy)
    out = {}
    for lam in BANDS_M:
        sel = (f >= 1 / (lam * math.sqrt(2))) & (f < math.sqrt(2) / lam)
        out[str(lam)] = float(np.sqrt(P[sel].sum()))
    return out, d


def stats(h, px_m):
    bands, d = band_rms(h, px_m)
    gy, gx = np.gradient(h, px_m)
    slope = np.hypot(gx, gy)
    return {
        "mean_m": float(h.mean()), "relief_m": float(np.percentile(h, 98) - np.percentile(h, 2)),
        "std_detrended_m": float(d.std()), "slope_p50": float(np.median(slope)), "slope_p95": float(np.percentile(slope, 95)),
        "bands_rms_m": bands,
    }


def hillshade(h, px_m):
    gy, gx = np.gradient(h, px_m)
    az, alt = math.radians(315), math.radians(35)
    shade = np.sin(alt) + np.cos(alt) * (gx * math.sin(az) - gy * math.cos(az)) / np.sqrt(1 + gx ** 2 + gy ** 2) * 8
    lo, hi = np.percentile(h, 2), np.percentile(h, 98)
    t = np.clip((h - lo) / (hi - lo + 1e-6), 0, 1)
    base = np.stack([60 + 150 * t, 110 + 90 * t, 60 + 60 * t], -1)
    return Image.fromarray(np.clip(base * np.clip(shade, 0.3, 1.4)[..., None], 0, 255).astype(np.uint8))


if __name__ == "__main__":
    px_m = KM * 1000 / 256
    result, tiles = {}, []
    for name, lat, lon, biome in REGIONS:
        h = fetch(name, lat, lon)
        s = stats(h, px_m)
        s["biome"] = biome
        result[name] = s
        tiles.append((name, h))
        print(f"{name:15s} {biome:8s} relief {s['relief_m']:6.1f} m  slope95 {s['slope_p95']:.3f}  bands " +
              " ".join(f"{v:5.2f}" for v in s["bands_rms_m"].values()))
    # per-biome average band amplitudes = training target
    target = {}
    for biome in {r[3] for r in REGIONS}:
        rows = [result[r[0]]["bands_rms_m"] for r in REGIONS if r[3] == biome]
        target[biome] = {lam: float(np.mean([row[lam] for row in rows])) for lam in rows[0]}
    os.makedirs("tools/data", exist_ok=True)
    json.dump({"regions": result, "biome_bands_rms_m": target, "bands_m": BANDS_M, "box_km": KM},
              open("tools/data/terrain_stats.json", "w"), indent=1)
    T = 256
    sheet = Image.new("RGB", (6 * T, 2 * (T + 20)), (20, 20, 22))
    dr = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 13)
    except OSError:
        font = ImageFont.load_default()
    for i, (name, h) in enumerate(tiles):
        x, y = (i % 6) * T, (i // 6) * (T + 20)
        sheet.paste(hillshade(h, px_m), (x, y))
        dr.text((x + 4, y + T + 3), f"{name} ({result[name]['relief_m']:.0f} m relief)", fill=(230, 230, 230), font=font)
    sheet.save("screenshots/terrain_real.png")
    print("per-biome target (RMS m per band):", json.dumps(target, indent=None))
