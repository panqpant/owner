"""Download the CC0 (public-domain) photo-scanned materials used by the realistic renders, from ambientCG.
Files go to assets/cc0/<id>/ (gitignored; re-run this to restore them).
Usage (from costa-verde/): python3 tools/fetch_cc0.py"""
import io
import os
import urllib.request
import zipfile

MATERIALS = ["Plaster001", "Asphalt031", "RoofingTiles013A", "Concrete034", "Grass004", "Gravel043", "Ground037",
             "Bark014", "Leaf001", "WoodSiding011"]

for mid in MATERIALS:
    out = f"assets/cc0/{mid}"
    if os.path.isdir(out) and os.listdir(out):
        continue
    url = f"https://ambientcg.com/get?file={mid}_1K-JPG.zip"
    req = urllib.request.Request(url, headers={"User-Agent": "costa-verde-asset-fetch"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            if n.lower().endswith((".jpg", ".png")) and "/" not in n:  # flat names only (zip-slip safe)
                open(os.path.join(out, n), "wb").write(z.read(n))
    print(mid, sorted(os.listdir(out)))
