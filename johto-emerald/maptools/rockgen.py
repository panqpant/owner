"""Procedural boulder sprites in Emerald's rock palette (General palette 3), lit from the top-left."""
import math, random

# palette 3 indices, light -> dark
HI, LIGHT, MID, DARK, DARKER, OUTLINE = 2, 3, 4, 5, 14, 8   # grey ramp, plum-brown shadow, near-black outline

def boulder(w, h, seed, bumps=5):
    """Return h x w grid of palette indices (0 = transparent)."""
    rnd = random.Random(seed)
    cx, cy = w / 2 - 0.5, h / 2 + 0.5
    rx, ry = w / 2 - 1.2, h / 2 - 1.0
    # lumpy outline: radius modulated by a few low-frequency bumps
    phases = [(rnd.uniform(0, 2 * math.pi), rnd.uniform(0.02, 0.06), k) for k in range(2, 2 + bumps)]
    def inside(x, y):
        dx, dy = (x - cx) / rx, (y - cy) / ry
        a = math.atan2(dy, dx); r = math.hypot(dx, dy)
        lim = 1 + sum(amp * math.sin(k * a + ph) for ph, amp, k in phases)
        # flatter bottom so rocks sit in the water
        if dy > 0.55: lim = min(lim, 0.55 / max(dy, 1e-6) * r + 0.0) if False else lim * (1 - 0.25 * (dy - 0.55))
        return r <= lim
    mask = [[inside(x, y) for x in range(w)] for y in range(h)]
    # a crack/ridge line for texture
    ridge = rnd.uniform(0.2, 0.6)
    out = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if not mask[y][x]: continue
            edge = any(not (0 <= x + dx < w and 0 <= y + dy < h and mask[y + dy][x + dx])
                       for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
            if edge: out[y][x] = OUTLINE; continue
            nx, ny = (x - cx) / rx, (y - cy) / ry
            nz = math.sqrt(max(0.0, 1 - min(1.0, nx * nx + ny * ny)))
            light = (-0.6 * nx - 0.7 * ny + 0.6 * nz) + rnd.uniform(-0.12, 0.12)
            if abs((nx - ny * 0.4) - ridge + 0.5) < 0.06 and nz > 0.3: light -= 0.5
            if ny > 0.62: light -= 0.9          # wet, shadowed waterline
            out[y][x] = HI if light > 1.05 else LIGHT if light > 0.5 else MID if light > 0.1 else DARK if light > -0.35 else DARKER
    return out

def sprites():
    return {
        'rockL': boulder(32, 32, 11, 6),
        'rockL2': boulder(32, 32, 23, 6),
        'rockS1': boulder(16, 16, 5, 4),
        'rockS2': boulder(16, 16, 7, 4),
        'rockS3': boulder(16, 14, 9, 4) + [[0] * 16] * 2,
    }
