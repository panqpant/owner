"""Fit Config.TERRAIN.cal so generated terrain matches the real elevation statistics.
Loop: export heightmap (Lune) -> measure RMS per wavelength band in pure-biome windows, exactly as
tools/terrain_stats.py measures real DEMs -> scale each band toward the target -> write Config.
Usage: python tools/train_terrain.py [iterations]"""
import json
import re
import subprocess
import sys

import numpy as np

sys.path.insert(0, "tools")
from terrain_stats import band_rms  # noqa: E402

CFG = "src/shared/Gen/Config.luau"
GROUPS = {"farm": {"farm"}, "scrub": {"scrub"}, "wetland": {"wetland"}}
WIN = 128
FIT_BANDS = 5  # the 4.8 km band is longer than a window; it follows band 5


def read_cal():
    src = open(CFG).read()
    return {g: [float(x) for x in re.search(rf"\t\t{g} = \{{ ([^}}]*) \}}", src[src.index("cal = {"):]).group(1).split(",")]
            for g in ("coast", "farm", "scrub", "wetland")}


def write_cal(cal):
    s = open(CFG).read()
    i = s.index("cal = {")
    head, tail = s[:i], s[i:]
    for g, row in cal.items():
        tail = re.sub(rf"(\t\t{g} = )\{{ [^}}]* \}}", lambda m: m.group(1) + "{ " + ", ".join(f"{c:.3f}" for c in row) + " }", tail, count=1)
    open(CFG, "w").write(head + tail)


def measure():
    subprocess.run(["lune", "run", "tools/export-heightmap.luau"], check=True)
    hm = json.load(open("build/heightmap.json"))
    n, cell = hm["n"], hm["cell"]
    vert = float(re.search(r"Config.VERT = ([\d.]+)", open(CFG).read()).group(1))
    spm = float(re.search(r"Config.STUD_PER_M = ([\d.]+)", open(CFG).read()).group(1))
    h = np.array(hm["h"], float).reshape(n, n)
    w = np.array(hm["water"], float).reshape(n, n)
    surf = np.where(w > -9000, np.maximum(h, w), h) / vert  # metres, like a DEM (water surface on lakes)
    biome = np.array(hm["ltype"]).reshape(n, n)
    px_m = cell / spm
    out = {}
    for g, names in GROUPS.items():
        mask = np.isin(biome, list(names))
        rows = []
        for y in range(0, n - WIN, WIN // 2):
            for x in range(0, n - WIN, WIN // 2):
                if mask[y:y + WIN, x:x + WIN].mean() > 0.8:
                    rows.append(band_rms(surf[y:y + WIN, x:x + WIN], px_m)[0])
        if rows:
            out[g] = {k: float(np.mean([r[k] for r in rows])) for k in rows[0]} | {"windows": len(rows)}
    return out


if __name__ == "__main__":
    target = json.load(open("tools/data/terrain_stats.json"))["biome_bands_rms_m"]
    keys = [str(b) for b in json.load(open("tools/data/terrain_stats.json"))["bands_m"]]
    iters = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    log = []
    for it in range(iters + 1):
        m = measure()
        cal = read_cal()
        err = []
        print(f"iter {it}: cal = " + str({g: [round(c, 2) for c in row] for g, row in cal.items()}))
        for g, row in m.items():
            ratio = [target[g][k] / max(row[k], 1e-4) for k in keys[:FIT_BANDS]]
            err += [abs(np.log(r)) for r in ratio]
            print(f"  {g:8s} ({row['windows']:3d} windows) measured/target per band: " +
                  "  ".join(f"{row[k]:.2f}/{target[g][k]:.2f}" for k in keys[:FIT_BANDS]))
        log.append({"iter": it, "cal": cal, "mean_log_error": float(np.mean(err)), "measured": m})
        print(f"  mean |log error| = {np.mean(err):.3f}")
        if it == iters:
            break
        new = {g: list(row) for g, row in cal.items()}
        for g in m:
            for i, k in enumerate(keys[:FIT_BANDS]):
                new[g][i] = float(np.clip(cal[g][i] * np.clip(target[g][k] / max(m[g][k], 1e-4), 0.33, 3), 0.1, 10))
            new[g][FIT_BANDS] = new[g][FIT_BANDS - 1]
        write_cal(new)
    json.dump(log, open("tools/data/terrain_training_log.json", "w"), indent=1)
