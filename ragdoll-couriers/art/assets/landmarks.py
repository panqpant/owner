"""Batch 6: a landmark (or two) for every district, plus more house variety.
Same conventions as world.py: ground at z = 0, front faces +Y, `Paint` parts take a colour per instance."""

import math

from assets.world import _door, _gable, _window
from lib import Mesh


def _one(m: Mesh, kind: str, **meta):
    return [m.done()], {"kind": kind, **meta}


# ------------------------------------------------------------------ hub


def fountain():
    """Three-tier fountain with a golden parcel on top. About 26 studs across: something to crash into."""
    m = Mesh("Fountain")
    m.cyl(13, 1.2, (0, 0, 0.6), "stone", segments=40, bevel=0.2)  # basin rim
    m.cyl(12, 1.0, (0, 0, 0.9), "water", segments=40, bevel=0)
    m.cyl(1.6, 6, (0, 0, 3), "stone", segments=16, bevel=0.1)
    m.cyl(6.5, 0.9, (0, 0, 5.6), "stone", segments=32, bevel=0.2)  # middle bowl
    m.cyl(5.8, 0.6, (0, 0, 5.9), "water", segments=32, bevel=0)
    m.cyl(1.1, 3.5, (0, 0, 7.6), "stone", segments=12, bevel=0.1)
    m.cyl(3.2, 0.7, (0, 0, 9.5), "stone", segments=24, bevel=0.15)  # top bowl
    m.cyl(2.7, 0.5, (0, 0, 9.7), "water", segments=24, bevel=0)
    m.box((2.2, 2.2, 2.2), (0, 0, 11.4), "gold", rot=(0, 0, 45), bevel=0.2)  # the golden parcel
    m.box((2.3, 0.6, 2.3), (0, 0, 11.4), "yellow", rot=(0, 0, 45), bevel=0.05)
    for k in range(8):  # spouts arcing into the basin
        a = k / 8 * math.tau
        m.tube((math.cos(a) * 6.2, math.sin(a) * 6.2, 5.8), (math.cos(a) * 9.5, math.sin(a) * 9.5, 1.2), 0.25, "skyblue", segments=6)
    return _one(m, "landmark", note="water parts: set Transparency ~0.3 in Studio for a glassy look")


def _garage(vip: bool):
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 40, 24, 14
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.3)
    body.box((w + 1, d + 1, 1), (0, 0, h + 0.5), "gold" if vip else "white", bevel=0.3)
    for x in (-12, 0, 12):  # three open bays
        body.box((10.5, 0.6, 9), (x, d / 2 + 0.05, 4.5), "charcoal", bevel=0.1)
        body.box((9.6, 0.65, 8.4), (x, d / 2 + 0.1, 4.2), "black", bevel=0)
        body.box((10.5, 0.8, 0.6), (x, d / 2 + 0.2, 9.2), "neonblue" if not vip else "gold", bevel=0.1)
    body.box((26, 0.8, 3.4), (0, d / 2 + 0.3, 11.6), "navy" if not vip else "black", bevel=0.2)  # sign board
    if vip:
        for x in range(-18, 19, 6):  # red carpet and rope posts
            body.cyl(0.25, 2.6, (x, d / 2 + 5, 1.3), "gold", segments=10, bevel=0.05)
            body.sphere(0.4, (x, d / 2 + 5, 2.8), "gold", segments=10, rings=6)
        body.tube((-18, d / 2 + 5, 2.2), (18, d / 2 + 5, 2.2), 0.15, "red", segments=6)
        body.box((10, 8, 0.1), (0, d / 2 + 4, 0.05), "red", bevel=0)
        body.cyl(0.25, 4, (0, 0, h + 3), "gold", segments=8, bevel=0)
        body.box((3, 0.2, 2), (1.5, 0, h + 4), "magenta", bevel=0.05)  # VIP flag
    else:
        for x in (-12, 0, 12):
            body.box((8, 0.2, 0.6), (x, d / 2 + 6, 0.05), "white", bevel=0)  # bay lines
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 2, d + 8]}


def garage():
    return _garage(False)


def vip_garage():
    return _garage(True)


# ------------------------------------------------------------------ suburbs


def house_d():
    """Cottage with dormers and a round window."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 16, 12, 7
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.15)
    body.box((w + 0.4, d + 0.4, 0.8), (0, 0, 0.4), "stone", bevel=0.1)
    _gable(body, w, d, h, 6.5, "darkgreen", "cream")
    for x in (-4, 4):  # dormers
        body.box((3.6, 3.4, 3.2), (x, d / 2 - 1.8, h + 2.6), "cream", bevel=0.15)
        body.box((4.4, 3.8, 0.4), (x, d / 2 - 1.6, h + 4.4), "darkgreen", rot=(-10, 0, 0), bevel=0.1)
        _window(body, x, d / 2 - 0.1, h + 2.4, w=2.0, h=1.8)
    _door(body, 0, d / 2, colour="red", w=3.0, h=5.6)
    for x in (-5, 5):
        _window(body, x, d / 2, 3.6, w=2.6, h=2.4)
    for x in (-4, 4):
        _window(body, x, -d / 2, 3.6, w=2.6, h=2.4, face="-Y")
    body.cyl(1.2, 0.3, (0, -d / 2 - 0.1, h + 3), "white", rot=(90, 0, 0), segments=16, bevel=0)
    body.cyl(0.9, 0.35, (0, -d / 2 - 0.12, h + 3), "glass", rot=(90, 0, 0), segments=16, bevel=0)
    body.box((1.8, 1.8, 5), (-5, -2, h + 5), "brick", bevel=0.08)
    return [paint.done(), body.done()], {"kind": "building"}


def house_e():
    """Modern flat-roofed house: two offset boxes, big glass, a carport."""
    paint, body = Mesh("Paint"), Mesh("Body")
    paint.box((18, 12, 6.5), (-2, 0, 3.25), bevel=0.1)
    paint.box((12, 11, 6), (2.5, -0.5, 9.5), bevel=0.1)
    body.box((18.6, 12.6, 0.5), (-2, 0, 6.75), "charcoal", bevel=0.05)
    body.box((12.6, 11.6, 0.5), (2.5, -0.5, 12.75), "charcoal", bevel=0.05)
    body.box((8, 0.3, 4.6), (-5, 6.05, 3.2), "tint", bevel=0.03)  # big ground-floor glass
    body.box((9, 0.3, 3.6), (2.5, 5.1, 9.6), "tint", bevel=0.03)
    _door(body, 4, 6, colour="wood", w=2.8, h=5.2)
    body.box((8, 7, 0.4), (11, 2.5, 5.2), "charcoal", bevel=0.05)  # carport roof
    for x, y in ((14.6, 5.6), (14.6, -0.6)):
        body.box((0.4, 0.4, 5), (x, y, 2.6), "steel", bevel=0)
    body.box((8, 9, 0.1), (11, 3, 0.05), "concrete", bevel=0)
    return [paint.done(), body.done()], {"kind": "building"}


def school():
    """Two-storey school with a clock, flag and a fenced yard in front."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 36, 16, 15
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.2)
    body.box((w + 1, d + 1, 1.2), (0, 0, h + 0.6), "white", bevel=0.2)
    body.box((10, d + 2, 4), (0, 0, h + 2.4), "brick", bevel=0.2)  # clock gable
    body.cyl(1.8, 0.4, (0, d / 2 + 1.1, h + 2.5), "white", rot=(90, 0, 0), segments=24, bevel=0)
    body.box((0.25, 0.1, 1.3), (0, d / 2 + 1.35, h + 2.9), "black", bevel=0)
    body.box((1.0, 0.1, 0.25), (0.45, d / 2 + 1.35, h + 2.5), "black", bevel=0)
    _door(body, 0, d / 2, colour="blue", w=5, h=6)
    for z in (4.2, 11):
        for x in (-14, -9, 9, 14):
            _window(body, x, d / 2, z, w=3.2, h=3.0)
        for x in (-14, -9, -4, 4, 9, 14):
            _window(body, x, -d / 2, z, w=3.2, h=3.0, face="-Y")
        if z > 5:
            for x in (-4, 4):
                _window(body, x, d / 2, z, w=3.2, h=3.0)
    body.cyl(0.2, 16, (14, d / 2 + 9, 8), "steel", segments=8, bevel=0)  # flag pole
    body.box((0.1, 4, 2.4), (14, d / 2 + 11, 14.6), "red", bevel=0)
    for x in range(-18, 19, 4):  # low yard fence
        body.box((0.3, 0.3, 2.4), (x, d / 2 + 14, 1.2), "green", bevel=0)
    body.box((36, 0.2, 0.3), (0, d / 2 + 14, 2.1), "green", bevel=0)
    body.box((30, 12, 0.1), (0, d / 2 + 7.5, 0.05), "asphalt", bevel=0)  # playground tarmac
    for k in range(4):  # hopscotch
        body.box((1.6, 1.6, 0.04), (-8, d / 2 + 4 + k * 1.8, 0.12), "yellow", bevel=0)
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 2, d + 16]}


def playground():
    m = Mesh("Playground")
    m.box((26, 20, 0.15), (0, 0, 0.075), "sand", bevel=0)
    # swings
    for x in (-10, -4):
        m.tube((x, -6, 0), (x + 1, -6, 7), 0.15, "red", segments=6)
        m.tube((x, -1, 0), (x + 1, -1, 7), 0.15, "red", segments=6)
    m.tube((-9, -6, 7), (-3, -6, 7), 0.15, "red", segments=6)
    m.tube((-9, -1, 7), (-3, -1, 7), 0.15, "red", segments=6)
    for x in (-8, -5):
        m.tube((x, -3.5, 7), (x, -3.5, 2.6), 0.04, "steel", segments=4)
        m.box((1.4, 0.6, 0.2), (x, -3.5, 2.5), "yellow", bevel=0.05)
    # slide tower
    for x, y in ((4, -2), (8, -2), (4, 2), (8, 2)):
        m.box((0.4, 0.4, 6), (x, y, 3), "blue", bevel=0.05)
    m.box((4.8, 4.8, 0.4), (6, 0, 5), "wood", bevel=0.1)
    m.cyl(3.4, 2, (6, 0, 7.2), "red", rot=(0, 0, 45), segments=4, r2=0.2, bevel=0.1)  # roof
    m.box((2.4, 9, 0.3), (6, 6.5, 2.6), "yellow", rot=(-32, 0, 0), bevel=0.1)  # slide
    for k in range(6):  # ladder
        m.box((2, 0.2, 0.2), (6, -2.6 - k * 0.2, 0.6 + k * 0.8), "steel", bevel=0)
    # roundabout and sandbox
    m.cyl(2.6, 0.4, (-6, 6, 0.6), "green", segments=24, bevel=0.1)
    m.cyl(0.3, 1.6, (-6, 6, 1.4), "steel", segments=8, bevel=0)
    m.box((6, 6, 0.6), (8, -7, 0.3), "wood", bevel=0.1)
    m.box((5.4, 5.4, 0.62), (8, -7, 0.32), "sand", bevel=0)
    return _one(m, "prop", note="a place to ragdoll into on purpose")


# ------------------------------------------------------------------ old town


def clock_tower():
    m = Mesh("ClockTower")
    m.box((9, 9, 3), (0, 0, 1.5), "stone", bevel=0.2)
    m.box((7, 7, 30), (0, 0, 18), "brick", bevel=0.1)
    for z in (10, 20):
        m.box((7.6, 7.6, 0.8), (0, 0, z), "stone", bevel=0.1)
    m.box((8.4, 8.4, 7), (0, 0, 36.5), "stone", bevel=0.2)
    for a in range(4):  # a clock on every face
        r = math.radians(a * 90)
        cx, cy = math.sin(r) * 4.25, math.cos(r) * 4.25
        m.cyl(2.6, 0.3, (cx, cy, 36.5), "white", rot=(90, 0, -a * 90), segments=28, bevel=0)
        m.cyl(2.75, 0.25, (cx * 0.99, cy * 0.99, 36.5), "gold", rot=(90, 0, -a * 90), segments=28, bevel=0)
        m.box((0.3, 0.2, 1.8), (cx * 1.03, cy * 1.03, 37.2), "black", rot=(0, 0, -a * 90), bevel=0)
        m.box((1.4, 0.2, 0.3), (cx * 1.03 + math.cos(r) * 0.6, cy * 1.03 - math.sin(r) * 0.6, 36.5), "black", rot=(0, 0, -a * 90), bevel=0)
        m.box((2, 0.4, 4), (cx * 0.98, cy * 0.98, 27), "charcoal", rot=(0, 0, -a * 90), bevel=0.1)  # belfry openings
    m.cyl(6, 9, (0, 0, 44.5), "darkgreen", rot=(0, 0, 45), segments=4, r2=0.3, bevel=0.1)  # copper spire
    m.sphere(0.6, (0, 0, 49.3), "gold", segments=10, rings=6)
    _door(m, 0, 4.5, colour="darkbrown", w=2.8, h=5.4)
    return _one(m, "landmark")


def church():
    m = Mesh("Church")
    w, d, h = 16, 26, 13  # 26 deep plus the tower: fits a 40-stud plot
    m.box((w, d, h), (0, -4, h / 2), "stone", bevel=0.15)
    a = math.atan2(7, w / 2)
    for s in (1, -1):
        m.box(((w / 2 + 1) / math.cos(a), d + 1.5, 0.7), (s * (w / 4 + 0.25), -4, h + 3.3), "charcoal", rot=(0, s * math.degrees(a), 0), bevel=0.15)
    for yface in (-4 - d / 2 + 0.4, -4 + d / 2 - 0.4):  # gable triangles at both ends, ridge along Y
        for s in (1, -1):
            m.wedge((0.8, w / 2, 7), (s * w / 4, yface, h + 3.5), "stone", rot=(0, 0, -90 if s > 0 else 90))
    m.box((8, 8, 30), (0, d / 2 - 4 + 4, 15), "stone", bevel=0.15)  # bell tower over the door
    m.cyl(5.6, 12, (0, d / 2, 36), "charcoal", rot=(0, 0, 45), segments=4, r2=0.2, bevel=0.1)  # steeple
    m.tube((0, d / 2, 42), (0, d / 2, 46), 0.2, "gold", segments=6)
    m.tube((-1.2, d / 2, 44.8), (1.2, d / 2, 44.8), 0.2, "gold", segments=6)
    m.cyl(2.6, 0.4, (0, d / 2 + 4.05, 21), "white", rot=(90, 0, 0), segments=28, bevel=0)  # rose window
    m.cyl(2.2, 0.45, (0, d / 2 + 4.08, 21), "purple", rot=(90, 0, 0), segments=28, bevel=0)
    _door(m, 0, d / 2 + 4, colour="darkbrown", w=3.6, h=7)
    for y in (-13, -7, -1, 5):
        for s in (1, -1):
            m.box((0.4, 2.4, 6), (s * w / 2, y, 7), "tintdark", bevel=0.05)  # tall windows
            m.cyl(1.2, 0.4, (s * w / 2, y, 10), "tintdark", rot=(0, 90, 0), segments=12, bevel=0)
    return _one(m, "landmark")


def canal():
    """Old canal basin, 34 x 14 studs, water 2.4 below street level. The terrain is cut away under it
    (terrain.py `cuts`), and its walls hide where the 10-stud ground grid slopes back up."""
    m = Mesh("Canal")
    L = 34
    m.box((L, 14, 0.6), (0, 0, -4.3), "stone", bevel=0)  # bed
    m.box((L - 2, 12.6, 0.4), (0, 0, -2.6), "water", bevel=0)
    for s in (1, -1):
        m.box((L, 1.2, 4.6), (0, s * 7.1, -2.3), "stone", bevel=0.1)  # side walls
        m.box((1.2, 14, 4.6), (s * (L / 2 - 0.6), 0, -2.3), "stone", bevel=0.1)  # end walls
        m.box((L + 3.6, 1.8, 0.4), (0, s * 7.3, 0.2), "concrete", bevel=0.1)  # coping all round
        m.box((1.8, 12.8, 0.4), (s * (L / 2 + 0.9), 0, 0.2), "concrete", bevel=0.1)  # fits between the side copings: no overlap
        for x in range(-15, 16, 6):
            m.cyl(0.25, 2.4, (x, s * 7.9, 1.6), "charcoal", segments=8, bevel=0)  # railing posts
        m.box((L, 0.18, 0.18), (0, s * 7.9, 2.7), "charcoal", bevel=0)
    return _one(m, "prop", note="needs the terrain cut under it: plan.py adds one wherever it places a canal")


def footbridge():
    """Arched stone footbridge for the canal."""
    m = Mesh("Footbridge")
    arch = [(t * 9.5, 2.4 * (1 - t * t) + 0.6) for t in (k / 12 - 1 for k in range(25))]  # smooth arch, 19 long
    m.strip([(2.5, y, z) for y, z in arch], [(-2.5, y, z) for y, z in arch], "stone", thickness=0.9)  # deck
    for s in (1, -1):  # parapets follow the same curve
        m.strip([(s * 2.6, y, z + 1.1) for y, z in arch], [(s * 2.1, y, z + 1.1) for y, z in arch], "stone", thickness=1.1)
    m.box((4, 1.2, 3), (0, 0, -1.2), "stone", bevel=0.1)  # keystone pier
    return _one(m, "prop")


# ------------------------------------------------------------------ docks


def lighthouse():
    m = Mesh("Lighthouse")
    m.rock(9, (0, 0, -2), "stone", scale=(1.3, 1.2, 0.6), seed=71, lumpiness=0.15)  # islet
    m.cyl(5, 1.5, (0, 0, 3), "concrete", segments=24, bevel=0.2)
    for k in range(6):
        m.cyl(4.2 - k * 0.32, 4.5, (0, 0, 6 + k * 4.5), "red" if k % 2 == 0 else "white", segments=24, r2=4.2 - (k + 1) * 0.32, bevel=0)
    m.cyl(3.2, 0.6, (0, 0, 33.3), "charcoal", segments=24, bevel=0.1)  # gallery
    for k in range(12):
        a = k / 12 * math.tau
        m.tube((math.cos(a) * 3.1, math.sin(a) * 3.1, 33.6), (math.cos(a) * 3.1, math.sin(a) * 3.1, 34.8), 0.08, "charcoal", segments=4)
    m.cyl(2.0, 3, (0, 0, 35.2), "headlight", segments=16, bevel=0)  # lantern
    m.cyl(2.4, 1.6, (0, 0, 37.5), "red", segments=16, r2=0.3, bevel=0.1)
    _door(m, 0, 3.9, colour="navy", w=2.0, h=3.6)
    return _one(m, "landmark", light=[0, 35.2, 0], note="put a rotating SpotLight in the lantern")


def gantry_crane():
    """Container crane straddling the quay road; the boom reaches out over the water (-X when placed)."""
    m = Mesh("Gantry")
    span, h = 38, 34
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box((1.6, 1.6, h), (sx * span / 2, sy * 6, h / 2), "red", bevel=0.1)
        m.box((2, 14, 1.6), (sx * span / 2, 0, h), "red", bevel=0.1)
        m.box((2.4, 15, 1.2), (sx * span / 2, 0, 0.6), "charcoal", bevel=0.1)  # rail bogies
        m.tube((sx * span / 2, -6, 4), (sx * span / 2, 6, h - 4), 0.35, "red", segments=6)  # bracing
    for sy in (-1, 1):
        m.box((span + 2, 1.4, 1.6), (0, sy * 6, h), "red", bevel=0.1)
    m.box((70, 4, 2.4), (-span / 2 - 14, 0, h + 3), "red", bevel=0.2)  # boom out over the water
    m.box((8, 4.5, 4.5), (span / 2 + 2, 0, h + 3), "concrete", bevel=0.2)  # counterweight
    m.box((5, 5, 4), (-span / 2 + 6, 0, h + 6.2), "white", bevel=0.3)  # cab
    m.box((4.6, 0.2, 2.4), (-span / 2 + 6, 2.55, h + 6.4), "glass", bevel=0.05)
    m.box((4, 6, 1.4), (-span / 2 - 30, 0, h + 1.2), "charcoal", bevel=0.1)  # trolley
    m.tube((-span / 2 - 30, 0, h + 0.5), (-span / 2 - 30, 0, h - 14), 0.12, "black", segments=6)
    m.box((10, 3, 1.2), (-span / 2 - 30, 0, h - 14.6), "yellow", bevel=0.1)  # spreader
    for x in (-span / 2 - 50, -span / 2 - 20, span / 2 - 5):
        m.tube((x, 0, h + 4.2), (0, 0, h + 14), 0.25, "red", segments=6)  # stays
    m.box((2, 2, 12), (0, 0, h + 8), "red", bevel=0.1)
    return _one(m, "landmark", note="legs straddle a 30-stud road plus pavements")


def cargo_ship():
    """Container ship moored at the quay. Waterline at z = 0 (place it at sea level)."""
    hull, deck = Mesh("Hull"), Mesh("Cargo")
    L, B = 130, 24
    hull.box((B, L - 20, 12), (0, 0, -1), "navy", bevel=0.8, segments=2)
    hull.cyl(B / 2, 12, (0, L / 2 - 10, -1), "navy", segments=24, bevel=0.5)  # rounded bow
    hull.box((B, 12, 12), (0, -L / 2 + 16, -1), "navy", bevel=0.8)
    hull.box((B + 0.2, L - 8, 1.6), (0, 2, -4.6), "red", bevel=0.2)  # boot top at the waterline
    hull.box((B - 1, L - 18, 0.6), (0, 0, 5.2), "charcoal", bevel=0.1)  # deck
    hull.box((B - 2, 14, 16), (0, -L / 2 + 18, 13), "white", bevel=0.6)  # bridge tower
    hull.box((B - 1.5, 0.3, 2.4), (0, -L / 2 + 25.1, 18), "tintdark", bevel=0.05)
    hull.box((B + 4, 5, 1.2), (0, -L / 2 + 22, 20), "white", bevel=0.3)  # bridge wings
    hull.cyl(2.4, 8, (0, -L / 2 + 14, 25), "red", segments=16, bevel=0.2)  # funnel
    hull.cyl(2.5, 1.5, (0, -L / 2 + 14, 28.5), "black", segments=16, bevel=0.1)
    colours = ("red", "blue", "green", "orange", "teal", "yellow", "purple")
    for row in range(8):  # container stacks
        for col in range(3):
            for level in range(1 + (row + col) % 3):
                c = colours[(row * 3 + col + level) % len(colours)]
                deck.box((7.6, 10, 4.2), ((col - 1) * 7.8, -L / 2 + 34 + row * 11, 7.6 + level * 4.3), c, bevel=0.15)
    return [hull.done(), deck.done()], {"kind": "landmark", "note": "z = 0 is the waterline: place at sea level"}


def fish_market():
    m = Mesh("FishMarket")
    w, d = 30, 20
    for sx in (-1, 0, 1):
        for sy in (-1, 1):
            m.box((0.8, 0.8, 9), (sx * (w / 2 - 1), sy * (d / 2 - 1), 4.5), "white", bevel=0.1)
    for s in (1, -1):  # pitched canopy
        m.box((w + 2, d / 2 + 2, 0.5), (0, s * d / 4, 10.4), "teal", rot=(-s * 14, 0, 0), bevel=0.15)
    m.box((24, 0.6, 2.6), (0, d / 2, 12.4), "navy", bevel=0.2)  # sign board
    m.box((24, 0.65, 0.5), (0, d / 2, 11.4), "yellow", bevel=0.1)
    for x in (-9, 0, 9):  # stalls with ice and fish
        m.box((7, 4, 3), (x, 2, 1.5), "white", bevel=0.2)
        m.box((6.6, 3.6, 0.4), (x, 2, 3.1), "lightgrey", bevel=0.05)
        for k in range(5):
            m.sphere(0.5, (x - 2.4 + k * 1.2, 2 + (k % 2) * 0.6 - 0.3, 3.5), "skyblue" if k % 2 else "pink", scale=(1.8, 0.6, 0.5), segments=8, rings=5)
    for k in range(6):  # crates of catch
        m.box((2.4, 1.8, 1.2), (-12 + k * 4.6, -6, 0.6 + (k % 2) * 1.2), "wood", bevel=0.05)
    m.box((w, d, 0.15), (0, 0, 0.075), "stone", bevel=0)
    return _one(m, "building")


# ------------------------------------------------------------------ downtown


def hoist():
    """Construction lift beside the skeleton tower: a mast and a cage the game moves up and down."""
    mast, cage = Mesh("Mast"), Mesh("Cage")
    H = 54
    for sx in (-1, 1):
        for sy in (-1, 1):
            mast.tube((sx * 1.2, sy * 1.2, 0), (sx * 1.2, sy * 1.2, H), 0.15, "yellow", segments=6)
    for z in range(0, H, 3):
        mast.tube((-1.2, -1.2, z), (1.2, 1.2, z + 3), 0.08, "yellow", segments=4)
    mast.box((5, 5, 1), (0, 0, 0.5), "concrete", bevel=0.1)
    mast.box((3, 3, 2), (0, 0, H + 1), "charcoal", bevel=0.1)
    cage.box((5, 5, 0.4), (0, 4.2, 1.2), "steel", bevel=0.05)
    for sx in (-1, 1):
        cage.box((0.15, 5, 3), (sx * 2.4, 4.2, 2.9), "orange", bevel=0)
    cage.box((5, 0.15, 3), (0, 6.6, 2.9), "orange", bevel=0)
    cage.box((5, 5, 0.3), (0, 4.2, 4.6), "steel", bevel=0.05)
    return [mast.done(), cage.done()], {"kind": "hazard", "note": "move `Cage` up and down (Roblox Y, 0 to 50 studs); ride it up the skeleton"}


# ------------------------------------------------------------------ mountain


def lodge():
    """Summit lodge: chalet with a big viewing window and a balcony."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 26, 18, 9
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.2)
    body.box((w + 0.6, d + 0.6, 1.2), (0, 0, 0.6), "stone", bevel=0.15)
    _gable(body, w, d, h, 8, "darkbrown", "wood", overhang=2.0)
    body.box((14, 0.4, 5.5), (0, d / 2 + 0.05, 5), "tint", bevel=0.05)  # big view window
    for x in range(-6, 7, 3):
        body.box((0.3, 0.5, 5.5), (x, d / 2 + 0.1, 5), "wood", bevel=0)
    body.box((w + 2, 5, 0.5), (0, d / 2 + 2.5, 1.4), "wood", bevel=0.1)  # deck
    for x in range(-13, 14, 3):
        body.box((0.3, 0.3, 2.4), (x, d / 2 + 4.8, 2.8), "wood", bevel=0)
    body.box((w + 2, 0.3, 0.3), (0, d / 2 + 4.8, 4), "wood", bevel=0)
    _door(body, -10, d / 2, colour="red", w=2.8, h=5.4)
    body.box((3, 3, 9), (8, -4, h + 6), "stone", bevel=0.15)  # chimney
    body.box((10, 0.4, 1.2), (0, d / 2 + 0.25, h - 0.6), "navy", bevel=0.1)  # sign on the wall above the view window
    for k in range(6):  # skis by the door
        body.box((0.25, 0.1, 5), (-14 + k * 0.5, d / 2 + 0.4, 2.8), ("red", "blue", "yellow")[k % 3], rot=(0, 8, 0), bevel=0)
    return [paint.done(), body.done()], {"kind": "building"}


def waterfall():
    """A rock face with a falling ribbon of water and a pool. Base at z = 0, cliff top 36 up."""
    rock, water = Mesh("Rocks"), Mesh("Water")
    rock.rock(14, (0, -6, 12), "stone", scale=(1.4, 0.8, 1.5), seed=81, lumpiness=0.18)
    rock.rock(9, (-12, -2, 6), "grey", scale=(1.1, 0.9, 1.0), seed=82, lumpiness=0.2)
    rock.rock(9, (12, -2, 6), "stone", scale=(1.1, 0.9, 1.0), seed=83, lumpiness=0.2)
    rock.rock(6, (0, 4, 30), "grey", scale=(1.6, 0.8, 0.6), seed=84, lumpiness=0.15)
    water.box((5, 10, 0.8), (0, 2, 32.5), "water", bevel=0.2)  # stream over the lip
    for k in range(11):  # the fall, out in front of the rock face, widening as it drops
        z = 31 - k * 3
        water.box((6 + k * 0.25, 1.6, 3.3), (0, 9.5 + k * 0.2, z), "water", bevel=0.2)
    water.cyl(11, 0.6, (0, 13, 0.3), "water", segments=28, bevel=0)  # pool
    for k in range(6):  # foam where it lands
        water.sphere(1.3, (-3 + k * 1.2, 12 + (k % 2) * 1.5, 0.9), "white", scale=(1, 1, 0.5), segments=10, rings=6)
    for k in range(7):
        a = k / 7 * math.tau
        rock.rock(1.6, (math.cos(a) * 11.5, 12 + math.sin(a) * 11.5, 0.6), "stone", seed=90 + k, lumpiness=0.2, subdivisions=1)
    return [rock.done(sharp=5), water.done()], {"kind": "landmark", "note": "Water: Transparency ~0.3; add a ParticleEmitter for spray at the pool"}


ASSETS = {
    "Hub_Fountain": fountain,
    "Hub_Garage": garage,
    "Hub_VIPGarage": vip_garage,
    "House_D": house_d,
    "House_E": house_e,
    "Suburbs_School": school,
    "Suburbs_Playground": playground,
    "OldTown_ClockTower": clock_tower,
    "OldTown_Church": church,
    "OldTown_Canal": canal,
    "OldTown_Footbridge": footbridge,
    "Docks_Lighthouse": lighthouse,
    "Docks_GantryCrane": gantry_crane,
    "Docks_CargoShip": cargo_ship,
    "Docks_FishMarket": fish_market,
    "Site_Hoist": hoist,
    "Mountain_Lodge": lodge,
    "Mountain_Waterfall": waterfall,
}
