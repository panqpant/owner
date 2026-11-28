"""World kit. Ground is z = 0 and buildings face +Y (the street side).
Road tiles are 40 x 40 studs: a 30-stud road (the kill test's width) with 5-stud pavements.
Houses and cars have a separate `Paint` part so the same mesh can come in many colours."""

import math

from lib import Mesh

TILE, ROAD = 40, 30
EDGE = (TILE - ROAD) / 2
KERB = 0.4


def _one(m: Mesh, kind: str, **meta):
    return [m.done()], {"kind": kind, **meta}


# ------------------------------------------------------------------ roads


def _tile(open_sides: set[str], surface="asphalt", dashes=False, crossings=False):
    """open_sides is any of N(+Y) S(-Y) E(+X) W(-X). Closed sides get pavement."""
    m = Mesh("Tile")
    stones = surface == "cobble"

    def ground(size, loc):
        if not stones:
            m.box((size[0], size[1], 1), (loc[0], loc[1], -0.5), "asphalt", bevel=0)
            return
        nx, ny = max(1, round(size[0] / 3.3)), max(1, round(size[1] / 3.3))
        sx, sy = size[0] / nx, size[1] / ny
        m.box((size[0], size[1], 0.8), (loc[0], loc[1], -0.6), "charcoal", bevel=0)  # grout
        for i in range(nx):
            for j in range(ny):
                x = loc[0] - size[0] / 2 + sx * (i + 0.5)
                y = loc[1] - size[1] / 2 + sy * (j + 0.5)
                h = 0.32 + ((i * 7 + j * 13) % 5) * 0.03
                m.box((sx * 0.86, sy * 0.86, h), (x, y, -0.2 + h / 2 - 0.16), "stone" if (i + j) % 3 else "concrete", bevel=0.12, segments=1)

    def pavement(size, loc):
        m.box((size[0], size[1], 1 + KERB), (loc[0], loc[1], (KERB - 1) / 2), "concrete", bevel=0.08, segments=1)

    ground((ROAD, ROAD), (0, 0))
    half = ROAD / 2 + EDGE / 2
    for side, (dx, dy) in {"N": (0, 1), "S": (0, -1), "E": (1, 0), "W": (-1, 0)}.items():
        size = (ROAD, EDGE) if dx == 0 else (EDGE, ROAD)
        loc = (dx * half, dy * half)
        if side in open_sides:
            ground(size, loc)
            if crossings:
                for k in range(-6, 7, 2):
                    off = k * 1.15
                    m.box((1.4, EDGE - 1, 0.04) if dx == 0 else (EDGE - 1, 1.4, 0.04), (loc[0] + (off if dx == 0 else 0), loc[1] + (off if dy == 0 else 0), 0.02), "white", bevel=0)
        else:
            pavement(size, loc)
    for cx in (-1, 1):
        for cy in (-1, 1):
            pavement((EDGE, EDGE), (cx * half, cy * half))
    if dashes:
        for y in range(-16, 17, 8):
            m.box((0.5, 4, 0.04), (0, y, 0.02), "white", bevel=0)
        for sx in (-1, 1):
            m.box((0.3, TILE, 0.04), (sx * (ROAD / 2 - 1), 0, 0.02), "yellow", bevel=0)
    if not stones and "E" not in open_sides:  # drain grates on the kerb line
        m.box((1.6, 0.8, 0.05), (ROAD / 2 - 0.9, 6, 0.03), "charcoal", bevel=0.02)
    return [m.done()], {"kind": "roadTile", "tile": TILE, "road": ROAD, "open": sorted(open_sides)}


def road_straight():
    return _tile({"N", "S"}, dashes=True)


def road_corner():
    return _tile({"N", "E"})


def road_t():
    return _tile({"N", "S", "E"}, crossings=True)


def road_cross():
    return _tile({"N", "S", "E", "W"}, crossings=True)


def road_cobble():
    return _tile({"N", "S"}, surface="cobble")


def speed_bump():
    m = Mesh("SpeedBump")
    for i in range(6):
        m.cyl(1.3, ROAD / 6, (-ROAD / 2 + ROAD / 12 + i * ROAD / 6, 0, -0.5), "yellow" if i % 2 else "black", rot=(0, 90, 0), segments=20, bevel=0.1)
    return _one(m, "hazard", note="half buried: top is 0.8 studs above the road")


def ramp():
    m = Mesh("Ramp")
    m.wedge((18, 26, 7), (0, 0, 3.5), "orange", rot=(0, 0, 180))  # rises toward +Y, the way you ride it
    for sx in (-1, 1):
        m.wedge((0.6, 26.2, 7.2), (sx * 9.1, 0, 3.6), "black", rot=(0, 0, 180))
        for k in range(4):
            m.box((0.66, 1.5, 0.6), (sx * 9.1, -10 + k * 6, 0.8 + k * 1.6), "yellow", bevel=0.02)
    for k in range(3):
        m.box((14, 0.5, 0.08), (0, -6 + k * 6, 2.2 + k * 1.62), "white", rot=(-15, 0, 0), bevel=0)
    return _one(m, "hazard")


# ------------------------------------------------------------------ building helpers


def _window(m: Mesh, x, y, z, w=2.6, h=3.0, frame="white", face="+Y"):
    if face in ("+Y", "-Y"):
        s = 1 if face == "+Y" else -1
        m.box((w + 0.5, 0.3, h + 0.5), (x, y + s * 0.05, z), frame, bevel=0.06)
        m.box((w, 0.34, h), (x, y + s * 0.07, z), "glass", bevel=0.03)
        m.box((w + 0.9, 0.7, 0.3), (x, y + s * 0.3, z - h / 2 - 0.3), frame, bevel=0.06)  # sill
        m.box((0.18, 0.38, h), (x, y + s * 0.09, z), frame, bevel=0)  # mullion
    else:
        s = 1 if face == "+X" else -1
        m.box((0.3, w + 0.5, h + 0.5), (x + s * 0.05, y, z), frame, bevel=0.06)
        m.box((0.34, w, h), (x + s * 0.07, y, z), "glass", bevel=0.03)


def _gable(m: Mesh, w, d, wall_h, rise, colour="red", gable_colour="cream", overhang=1.0):
    a = math.atan2(rise, d / 2)
    run = d / 2 + overhang
    length = run / math.cos(a)
    for s in (1, -1):
        m.box((w + 2 * overhang, length, 0.6), (0, s * run / 2, wall_h + rise - run / 2 * math.tan(a)), colour, rot=(-s * math.degrees(a), 0, 0), bevel=0.15)
    for sx in (-1, 1):  # gable triangles
        for s in (1, -1):
            m.wedge((0.6, d / 2, rise), (sx * (w / 2 - 0.3), s * d / 4, wall_h + rise / 2), gable_colour, rot=(0, 0, 0 if s > 0 else 180))
    m.box((w + 2 * overhang + 0.2, 0.7, 0.7), (0, 0, wall_h + rise + 0.05), "darkbrown", bevel=0.2)  # ridge cap


def _door(m: Mesh, x, y, colour="wood", w=3.2, h=6.0):
    m.box((w + 0.6, 0.4, h + 0.3), (x, y + 0.05, h / 2), "white", bevel=0.08)
    m.box((w, 0.45, h), (x, y + 0.1, h / 2), colour, bevel=0.06)
    m.sphere(0.2, (x + w * 0.32, y + 0.4, h * 0.48), "gold", segments=10, rings=6)
    m.box((w + 1.2, 1.6, 0.3), (x, y + 0.9, 0.15), "concrete", bevel=0.06)  # step


def house_a():
    """Suburban gabled house."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 18, 14, 10
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.15)
    body.box((w + 0.4, d + 0.4, 1.0), (0, 0, 0.5), "stone", bevel=0.1)  # plinth
    _gable(body, w, d, h, 5.5, "red", "cream")
    _door(body, -3.5, d / 2)
    _window(body, 4.5, d / 2, 5.0)
    for y in (-3, 3):
        for sx in (-1, 1):
            _window(body, sx * w / 2, y, 5.0, w=2.6, face="+X" if sx > 0 else "-X")
    for x in (-4.5, 4.5):
        _window(body, x, -d / 2, 5.0, face="-Y")
    body.box((2.2, 2.2, 7), (5, -2.5, h + 4.5), "brick", bevel=0.08)  # chimney
    body.box((2.8, 2.8, 0.5), (5, -2.5, h + 8.1), "charcoal", bevel=0.08)
    # Porch roof over the door
    body.box((6, 3, 0.4), (-3.5, d / 2 + 1.5, 7.2), "red", rot=(-12, 0, 0), bevel=0.1)
    for sx in (-1, 1):
        body.cyl(0.22, 7, (-3.5 + sx * 2.6, d / 2 + 2.7, 3.5), "white", segments=10, bevel=0.05)
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 2, d + 4]}


def house_b():
    """Two storeys with a hipped roof."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 15, 14, 17
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.15)
    body.box((w + 0.4, d + 0.4, 1.0), (0, 0, 0.5), "stone", bevel=0.1)
    body.box((w + 0.6, d + 0.6, 0.6), (0, 0, 8.6), "white", bevel=0.1)  # floor band
    body.cyl(math.hypot(w, d) / 2 + 1.2, 6, (0, 0, h + 3), "charcoal", rot=(0, 0, 45), segments=4, r2=0.6, bevel=0.2)
    _door(body, 0, d / 2, colour="navy")
    for x in (-4.5, 4.5):
        _window(body, x, d / 2, 4.5)
        _window(body, x, d / 2, 12.5)
    _window(body, 0, d / 2, 12.5, w=2.0)
    for sx in (-1, 1):
        for z in (4.5, 12.5):
            _window(body, sx * w / 2, 0, z, face="+X" if sx > 0 else "-X")
    for x in (-4.5, 4.5):
        for z in (4.5, 12.5):
            _window(body, x, -d / 2, z, face="-Y")
    body.box((1.6, 0.3, 1.2), (-5.5, d / 2 + 0.2, 7.0), "white", bevel=0.05)  # house number plate
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 3, d + 4]}


def house_c():
    """Bungalow with a garage."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 24, 13, 8
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.15)
    body.box((w + 0.4, d + 0.4, 0.8), (0, 0, 0.4), "stone", bevel=0.1)
    _gable(body, w, d, h, 4, "brown", "cream")
    body.box((9, 0.4, 6.5), (6.5, d / 2 + 0.05, 3.25), "white", bevel=0.1)  # garage door frame
    body.box((8.2, 0.45, 6.0), (6.5, d / 2 + 0.1, 3.0), "lightgrey", bevel=0.05)
    for k in range(6):
        body.box((8.2, 0.5, 0.12), (6.5, d / 2 + 0.12, 0.6 + k * 1.0), "grey", bevel=0)
    _door(body, -2.5, d / 2, colour="green")
    _window(body, -8, d / 2, 4.2, w=4.0, h=2.8)
    body.box((10, 5, 0.12), (6.5, d / 2 + 2.6, 0.06), "concrete", bevel=0)  # driveway
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 2, d + 6]}


def townhouse():
    """Old Town: tall narrow brick house."""
    m = Mesh("Building")
    w, d, h = 12, 12, 26
    m.box((w, d, h), (0, 0, h / 2), "brick", bevel=0.1)
    m.box((w + 0.8, d + 0.8, 1.0), (0, 0, h + 0.5), "stone", bevel=0.2)  # cornice
    m.box((w + 0.4, d + 0.4, 0.5), (0, 0, 8.5), "stone", bevel=0.1)
    m.cyl(math.hypot(w, d) / 2 + 0.6, 5, (0, 0, h + 3.5), "charcoal", rot=(0, 0, 45), segments=4, r2=0.4, bevel=0.15)
    _door(m, -2.5, d / 2, colour="red", h=6.5)
    _window(m, 3, d / 2, 4.2, w=2.4, frame="stone")
    for z in (12, 17.5, 23):
        for x in (-3, 3):
            _window(m, x, d / 2, z, w=2.4, h=3.4, frame="stone")
            m.box((2.4, 0.9, 0.6), (x, d / 2 + 0.6, z - 2.3), "darkgreen", bevel=0.05)  # flower box
            for k in (-0.8, 0, 0.8):
                m.sphere(0.35, (x + k, d / 2 + 0.6, z - 1.9), "pink" if k else "red", segments=8, rings=5)
    for z in (4.2, 12, 17.5, 23):
        for x in (-3, 3):
            _window(m, x, -d / 2, z, w=2.4, h=3.4, frame="stone", face="-Y")
    m.box((1.4, 1.4, 4), (3, -3, h + 4), "brick", bevel=0.06)
    return _one(m, "building", footprint=[w + 1, d + 2])


def shop():
    """Old Town shop front with a striped awning and a blank sign board for a SurfaceGui."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 16, 12, 14
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.12)
    body.box((w + 0.6, d + 0.6, 0.8), (0, 0, h + 0.4), "white", bevel=0.15)
    body.box((w - 2, 0.5, 6.2), (-1.5, d / 2 + 0.05, 3.8), "white", bevel=0.08)  # shop window frame
    body.box((w - 6.5, 0.55, 5.4), (-3.2, d / 2 + 0.08, 3.8), "glass", bevel=0.04)
    _door(body, 4.5, d / 2, colour="glass", w=3.0, h=6.2)
    for i in range(8):  # awning stripes
        x = -w / 2 + 1 + i * (w - 2) / 8 + (w - 2) / 16
        body.box(((w - 2) / 8, 3.4, 0.25), (x, d / 2 + 1.6, 7.8), "red" if i % 2 else "white", rot=(-22, 0, 0), bevel=0.03)
    for i in range(8):
        x = -w / 2 + 1 + i * (w - 2) / 8 + (w - 2) / 16
        body.box(((w - 2) / 8, 0.15, 0.6), (x, d / 2 + 3.15, 6.9), "red" if i % 2 else "white", bevel=0.02)
    body.box((w - 3, 0.5, 2.4), (0, d / 2 + 0.2, 9.8), "navy", bevel=0.1)  # sign board (put a SurfaceGui on +Z face)
    for x in (-4.5, 0, 4.5):
        _window(body, x, d / 2, 12.1, w=2.2, h=1.6)
        _window(body, x, -d / 2, 12.1, w=2.2, h=1.6, face="-Y")
        _window(body, x, -d / 2, 4.5, w=2.2, h=2.4, face="-Y")
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 1, d + 4]}


def market_stall():
    m = Mesh("Stall")
    m.box((8, 3.5, 0.4), (0, 0, 3.2), "wood", bevel=0.08)
    m.box((7.6, 3.1, 3.0), (0, 0, 1.5), "darkbrown", bevel=0.08)
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.cyl(0.18, 7.5, (sx * 3.8, sy * 1.6, 3.75), "white", segments=8, bevel=0.03)
    for i in range(6):
        m.box((8.6 / 6, 4.6, 0.2), (-4.3 + 8.6 / 12 + i * 8.6 / 6, 0, 7.6), "green" if i % 2 else "white", rot=(-8, 0, 0), bevel=0.03)
    for i, c in enumerate(("red", "orange", "lime", "yellow")):
        x = -2.7 + i * 1.8
        m.box((1.6, 1.4, 0.6), (x, 0.6, 3.7), "wood", bevel=0.05)
        for k in range(5):
            m.sphere(0.3, (x - 0.5 + (k % 3) * 0.5, 0.35 + (k // 3) * 0.5, 4.15 + (k // 3) * 0.1), c, segments=10, rings=6)
    return _one(m, "prop")


# ------------------------------------------------------------------ docks


def container():
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 8, 20, 8.5
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.15)
    for k in range(-9, 10):
        for sx in (-1, 1):
            paint.box((0.3, 0.5, h - 1.2), (sx * w / 2, k, h / 2), bevel=0.05)  # corrugation
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (0.4, h - 0.4):
                body.box((0.9, 0.9, 0.8), (sx * (w / 2 - 0.3), sy * (d / 2 - 0.3), z), "charcoal", bevel=0.1)  # corner castings
    for sx in (-1, 1):  # door end (+Y): bars and handles
        body.cyl(0.12, h - 1.5, (sx * 1.2, d / 2 + 0.15, h / 2), "steel", segments=8, bevel=0)
        body.cyl(0.12, h - 1.5, (sx * 3.0, d / 2 + 0.15, h / 2), "steel", segments=8, bevel=0)
    body.box((0.15, 0.1, h - 1), (0, d / 2 + 0.05, h / 2), "charcoal", bevel=0)
    return [paint.done(), body.done()], {"kind": "prop", "stackable": True}


def forklift():
    """Docks hazard: drives back and forth. Front (+Y) carries the forks."""
    m = Mesh("Forklift")
    m.box((4.2, 5.5, 2.2), (0, -0.4, 2.0), "yellow", bevel=0.3)
    m.box((4.0, 1.6, 2.6), (0, -2.8, 2.6), "charcoal", bevel=0.4)  # counterweight
    m.box((1.8, 1.6, 0.8), (0, -0.6, 3.5), "black", bevel=0.25)  # seat
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.tube((sx * 1.8, sy * 1.5 - 0.3, 3.1), (sx * 1.8, sy * 1.5 - 0.3, 8.0), 0.13, "charcoal")
        m.box((0.35, 0.35, 8.5), (sx * 1.2, 2.6, 4.6), "charcoal", bevel=0.06)  # mast
        m.box((0.45, 4.2, 0.25), (sx * 0.9, 4.7, 0.9), "steel", bevel=0.05)  # forks
        m.box((0.45, 0.3, 2.0), (sx * 0.9, 2.75, 1.8), "steel", bevel=0.05)
    m.box((4.0, 3.6, 0.3), (0, -0.3, 8.1), "yellow", bevel=0.1)  # overhead guard
    m.box((3, 0.3, 0.6), (0, 2.75, 2.2), "charcoal", bevel=0.05)
    m.tube((0, 0.8, 3.2), (0, 0.3, 4.4), 0.08, "black")
    m.cyl(0.6, 0.12, (0, 0.25, 4.45), "black", rot=(60, 0, 0), segments=16, bevel=0.03)  # steering wheel
    m.cyl(0.35, 0.5, (0, -0.3, 8.5), "neonorange", segments=12, bevel=0.1)  # beacon
    for sx in (-1, 1):
        m.tire(1.2, 0.9, (sx * 2.1, 1.4, 1.2), "rubber", "yellow")
        m.tire(0.9, 0.8, (sx * 2.0, -2.4, 0.9), "rubber", "yellow")
    return _one(m, "hazard")


def warehouse():
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 40, 30, 16
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.2)
    for x in range(-18, 19, 2):
        paint.box((0.4, 0.3, h - 0.6), (x, d / 2 + 0.1, h / 2), bevel=0.05)
    a = math.atan2(4, d / 2)
    for s in (1, -1):
        body.box((w + 1.5, (d / 2 + 1) / math.cos(a), 0.5), (0, s * (d / 4 + 0.5), h + 2 - 0.5), "steel", rot=(-s * math.degrees(a), 0, 0), bevel=0.1)
    for sx in (-1, 1):
        for s in (1, -1):
            body.wedge((0.5, d / 2, 4), (sx * (w / 2 - 0.25), s * d / 4, h + 2), "steel", rot=(0, 0, 0 if s > 0 else 180))
    for x in (-11, 11):
        body.box((11, 0.5, 11), (x, d / 2 + 0.05, 5.5), "charcoal", bevel=0.1)  # roller doors
        for k in range(11):
            body.box((10.4, 0.6, 0.12), (x, d / 2 + 0.1, 0.5 + k), "grey", bevel=0)
        body.box((11.6, 0.6, 0.8), (x, d / 2 + 0.2, 11.4), "yellow", bevel=0.05)
    body.box((10, 0.4, 2.6), (0, d / 2 + 0.2, 13.5), "white", bevel=0.1)  # sign board
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 2, d + 2]}


def bollard():
    m = Mesh("Bollard")
    m.cyl(0.8, 2.2, (0, 0, 1.1), "charcoal", segments=16, bevel=0.1)
    m.cyl(1.1, 0.5, (0, 0, 2.3), "charcoal", segments=16, bevel=0.15)
    m.cyl(0.82, 0.3, (0, 0, 1.6), "yellow", segments=16, bevel=0.03)
    return _one(m, "prop")


def barrel():
    m = Mesh("Barrel")
    m.cyl(1.2, 3.4, (0, 0, 1.7), "blue", segments=20, bevel=0.15)
    for z in (0.6, 1.7, 2.8):
        m.cyl(1.25, 0.18, (0, 0, z), "navy", segments=20, bevel=0.03)
    m.cyl(0.25, 0.1, (0.5, 0.3, 3.42), "charcoal", segments=10, bevel=0)
    return _one(m, "prop", physics=True)


def crate():
    m = Mesh("Crate")
    s = 3
    m.box((s, s, s), (0, 0, s / 2), "wood", bevel=0.06)
    for face in range(4):
        rot = (0, 0, face * 90)
        r = math.radians(face * 90)
        cx, cy = math.sin(r) * (s / 2 + 0.06), math.cos(r) * (s / 2 + 0.06)
        for z in (0.3, s - 0.3):
            m.box((s, 0.14, 0.45), (cx, cy, z), "darkbrown", rot=rot, bevel=0.04)
        m.box(((s - 0.9) * 1.38, 0.14, 0.4), (cx, cy, s / 2), "darkbrown", rot=(0, 45 if face % 2 else -45, face * 90), bevel=0.04)  # brace fits inside the frame
    return _one(m, "prop", physics=True, note="the kill test's smashable crates")


# ------------------------------------------------------------------ building site


def tower_crane():
    """Building site crane. The jib points +Y; hang WreckingBall from `hook`."""
    m = Mesh("Crane")
    H, J, C = 60, 40, 14
    m.box((8, 8, 2), (0, 0, 1), "concrete", bevel=0.2)
    s = 2.2
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.tube((sx * s, sy * s, 2), (sx * s, sy * s, H), 0.22, "yellow")
    for z in range(2, H, 4):  # lattice braces
        for k in range(4):
            a, b = [(-s, -s), (s, -s), (s, s), (-s, s)][k], [(s, -s), (s, s), (-s, s), (-s, -s)][k]
            m.tube((a[0], a[1], z), (b[0], b[1], z + 4), 0.1, "yellow", segments=6)
    m.box((5.6, 5.6, 0.6), (0, 0, H + 0.3), "yellow", bevel=0.1)
    m.box((4, 4, 3.5), (2.4, 3.2, H - 2.2), "white", bevel=0.25)  # cab
    m.box((3.6, 0.2, 2.2), (2.4, 5.25, H - 2), "glass", bevel=0.05)
    for sx in (-1, 1):  # jib and counter-jib
        m.tube((sx * 1.2, 0, H + 1), (sx * 0.4, J, H + 1), 0.18, "yellow")
        m.tube((sx * 1.2, 0, H + 1), (sx * 1.2, -C, H + 1), 0.18, "yellow")
    m.tube((0, 0, H + 4), (0, J, H + 1.4), 0.15, "yellow")
    m.tube((0, 0, H + 4), (0, -C, H + 1.4), 0.15, "yellow")
    m.tube((0, 0, H + 0.6), (0, 0, H + 6.5), 0.4, "yellow")
    for y in range(4, J, 6):
        m.tube((-1.1 + y * 0.02, y, H + 1), (0, y + 3, H + 1 + 3 * (1 - (y + 3) / J) * 0.8 + 0.5), 0.08, "yellow", segments=6)
    m.box((4, 6, 3.5), (0, -C + 3, H - 0.8), "concrete", bevel=0.15)  # counterweight
    m.box((2, 1.5, 1.2), (0, J * 0.7, H + 0.1), "charcoal", bevel=0.1)  # trolley
    m.tube((0, J * 0.7, H - 0.5), (0, J * 0.7, H - 18), 0.06, "black", segments=6)
    return _one(m, "prop", hook=[0, 60 - 18, -40 * 0.7], note="hook in Roblox space relative to the base centre")


def wrecking_ball():
    m = Mesh("WreckingBall")
    m.sphere(3, (0, 0, 0), "charcoal", segments=24, rings=16)
    m.cyl(0.8, 1.2, (0, 0, 3.1), "steel", segments=12, bevel=0.15)
    for k in range(6):
        m.cyl(0.45, 0.2, (0, 0, 4.0 + k * 0.85), "steel", rot=(90 if k % 2 else 0, 0, 0), segments=12, bevel=0.05)  # chain links
    return _one(m, "hazard", pivot="top of the chain; swing it from the crane hook")


def cone():
    m = Mesh("Cone")
    m.box((2.2, 2.2, 0.3), (0, 0, 0.15), "black", bevel=0.1)
    m.cyl(0.95, 3.0, (0, 0, 1.8), "orange", segments=20, r2=0.18, bevel=0.03)
    for z, r in ((1.3, 0.78), (2.2, 0.53)):
        m.cyl(r + 0.02, 0.35, (0, 0, z), "white", segments=20, r2=r - 0.06, bevel=0)
    return _one(m, "prop", physics=True)


def jersey_barrier():
    m = Mesh("Barrier")
    m.box((1.8, 10, 0.9), (0, 0, 0.45), "concrete", bevel=0.1)
    m.box((1.2, 10, 1.2), (0, 0, 1.4), "concrete", bevel=0.1)
    m.box((0.7, 10, 1.4), (0, 0, 2.6), "concrete", bevel=0.15)
    for k in range(-2, 3):
        m.box((0.75, 1.0, 0.6), (0, k * 2, 2.6), "red" if k % 2 else "white", bevel=0.05)
    return _one(m, "prop")


def scaffold():
    m = Mesh("Scaffold")
    w, d, h = 12, 4, 15
    for x in (-w / 2, 0, w / 2):
        for y in (-d / 2, d / 2):
            m.tube((x, y, 0), (x, y, h), 0.15, "steel", segments=8)
    for z in (5, 10, 15):
        for y in (-d / 2, d / 2):
            m.tube((-w / 2, y, z), (w / 2, y, z), 0.13, "steel", segments=8)
        m.box((w, d, 0.3), (0, 0, z - 0.2), "wood", bevel=0.04)
        m.box((w, 0.2, 0.9), (0, d / 2 + 0.1, z + 0.4), "orange", bevel=0.03)  # toe boards
    for x in (-w / 4, w / 4):
        m.tube((x - w / 4, d / 2, 0.5), (x + w / 4, d / 2, 5), 0.1, "steel", segments=6)
    return _one(m, "prop")


def portacabin():
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 20, 8, 8
    paint.box((w, d, h), (0, 0, h / 2 + 0.6), bevel=0.25)
    body.box((w + 0.4, d + 0.4, 0.6), (0, 0, h + 0.9), "white", bevel=0.15)
    for x in (-6, 6):
        body.box((2, 2, 0.6), (x, 0, 0.3), "concrete", bevel=0.1)
    _door(body, -7.5, d / 2, colour="grey", w=2.8)
    for x in (-1.5, 5):
        _window(body, x, d / 2, 5, w=3.6, h=2.4)
    return [paint.done(), body.done()], {"kind": "building"}


def pipe_stack():
    m = Mesh("Pipes")
    for row, (n, z) in enumerate(((4, 0.9), (3, 2.45), (2, 4.0))):
        for k in range(n):
            x = (k - (n - 1) / 2) * 1.85
            m.lathe([(0.7, -6), (0.9, -6), (0.9, 6), (0.7, 6), (0.7, -6)], (x, 0, z), "orange" if (k + row) % 2 else "steel", rot=(90, 0, 0), segments=18)
    for y in (-4, 4):
        m.box((8.5, 0.6, 0.4), (0, y, 0.2), "wood", bevel=0.05)
    return _one(m, "prop")


def dirt_pile():
    m = Mesh("Dirt")
    m.rock(5, (0, 0, 0.4), "tan", scale=(1.3, 1.1, 0.55), seed=3, lumpiness=0.12)
    m.rock(2.5, (3, 2, 1.8), "brown", scale=(1, 1, 0.6), seed=4)
    return [m.done(sharp=5)], {"kind": "prop", "note": "doubles as a small jump"}


# ------------------------------------------------------------------ mountain


def rock_large():
    m = Mesh("Rock")
    m.rock(8, (0, 0, 5), "stone", scale=(1.2, 1, 0.8), seed=11)
    m.rock(4.5, (6, 4, 2.5), "grey", seed=12)
    m.rock(3, (-7, -3, 1.5), "stone", seed=13)
    return [m.done(sharp=5)], {"kind": "prop"}


def rock_small():
    m = Mesh("Rock")
    m.rock(2.2, (0, 0, 1.2), "grey", scale=(1.2, 1, 0.8), seed=21)
    m.rock(1.2, (1.8, 1, 0.6), "stone", seed=22)
    return [m.done(sharp=5)], {"kind": "prop"}


def boulder():
    m = Mesh("Boulder")
    m.rock(3, (0, 0, 0), "stone", seed=31, lumpiness=0.08, subdivisions=3)
    return [m.done(sharp=5)], {"kind": "hazard", "note": "rolls down the mountain road; use a Ball collision"}


def guardrail():
    m = Mesh("Guardrail")
    for y in (-4.5, 0, 4.5):
        m.box((0.4, 0.4, 3.0), (0, y, 1.5), "steel", bevel=0.05)
    m.box((0.35, 10, 1.1), (0.3, 0, 2.3), "chrome", bevel=0.1)
    for y in (-4.6, 4.6):
        m.box((0.4, 0.6, 1.1), (0.3, y, 2.3), "red", bevel=0.05)  # reflectors
    return _one(m, "prop", note="10 studs long; break it to fly off the cliff")


def cabin():
    m = Mesh("Cabin")
    w, d, h = 16, 12, 8
    for k in range(int(h / 1.0)):
        z = 0.5 + k * 1.0
        for sx in (-1, 1):
            m.cyl(0.55, d + 1.2, (sx * w / 2, 0, z), "wood", rot=(90, 0, 0), segments=10, bevel=0.1)
        for sy in (-1, 1):
            m.cyl(0.55, w + 1.2, (0, sy * d / 2, z + 0.5), "wood" if k % 2 else "brown", rot=(0, 90, 0), segments=10, bevel=0.1)
    m.box((w, d, h), (0, 0, h / 2), "darkbrown", bevel=0)  # inner wall
    _gable(m, w + 1, d + 1, h + 0.5, 5, "darkgreen", "wood")
    _door(m, -3, d / 2 + 0.6, colour="darkbrown")
    _window(m, 3.5, d / 2 + 0.6, 4.5, w=3, h=2.6, frame="wood")
    m.box((2, 2, 6), (5, -2, h + 5), "stone", bevel=0.2)
    return _one(m, "building", note="mountain road delivery address")


def pine():
    m = Mesh("Pine")
    m.cyl(0.6, 4, (0, 0, 2), "darkbrown", segments=10, bevel=0.1)
    for i, (r, z) in enumerate(((4.2, 5.0), (3.4, 8.0), (2.4, 10.8))):
        m.cyl(r, 5, (0, 0, z), "darkgreen" if i % 2 else "green", segments=9, r2=0.2, bevel=0.15)
    return [m.done(sharp=20)], {"kind": "prop"}


# ------------------------------------------------------------------ street props


def tree_round():
    m = Mesh("Tree")
    m.cyl(0.7, 7, (0, 0, 3.5), "brown", segments=10, r2=0.5, bevel=0.1)
    m.tube((0, 0, 5), (1.6, 0.5, 7.5), 0.3, "brown", segments=8)
    m.rock(4, (0, 0, 10), "green", scale=(1, 1, 0.9), seed=41, lumpiness=0.12)
    m.rock(2.8, (2.4, 1.0, 8.4), "darkgreen", seed=42, lumpiness=0.12)
    m.rock(2.6, (-2.2, -1.2, 8.8), "lime", seed=43, lumpiness=0.12)
    return [m.done(sharp=5)], {"kind": "prop"}


def bush():
    m = Mesh("Bush")
    for k, (x, y, r, c) in enumerate(((0, 0, 1.8, "green"), (1.6, 0.4, 1.3, "darkgreen"), (-1.4, -0.3, 1.4, "lime"))):
        m.rock(r, (x, y, r * 0.7), c, seed=50 + k, lumpiness=0.12, subdivisions=1)
    return [m.done(sharp=5)], {"kind": "prop"}


def lamp_post():
    m = Mesh("Lamp")
    m.cyl(0.6, 0.6, (0, 0, 0.3), "charcoal", segments=12, bevel=0.1)
    m.cyl(0.28, 12, (0, 0, 6), "charcoal", segments=12, r2=0.2, bevel=0)
    m.tube((0, 0, 11.8), (0, 2.2, 12.3), 0.15, "charcoal", segments=8)
    m.cyl(0.8, 0.6, (0, 2.6, 12.1), "charcoal", segments=12, r2=0.5, bevel=0.1)
    m.cyl(0.55, 0.15, (0, 2.6, 11.75), "headlight", segments=12, bevel=0)
    return _one(m, "prop", light=[0, 11.6, -2.6], note="put a PointLight/SpotLight at `light` (Roblox space)")


def bench():
    m = Mesh("Bench")
    for k in range(3):
        m.box((6, 0.5, 0.2), (0, -0.6 + k * 0.6, 1.6), "wood", bevel=0.05)
    for k in range(2):
        m.box((6, 0.2, 0.5), (0, -1.0, 2.3 + k * 0.7), "wood", rot=(-12, 0, 0), bevel=0.05)
    for sx in (-1, 1):
        m.box((0.25, 1.8, 0.25), (sx * 2.6, -0.1, 1.4), "charcoal", bevel=0.05)
        m.box((0.25, 0.25, 1.4), (sx * 2.6, 0.6, 0.7), "charcoal", bevel=0.05)
        m.box((0.25, 0.25, 3.2), (sx * 2.6, -0.95, 1.6), "charcoal", rot=(-12, 0, 0), bevel=0.05)
    return _one(m, "prop")


def fence():
    m = Mesh("Fence")
    for k in range(9):
        y = -4.4 + k * 1.1
        m.box((0.2, 0.8, 3.2), (0, y, 1.6), "white", bevel=0.05)
        for s in (1, -1):  # pointed top
            m.wedge((0.2, 0.4, 0.4), (0, y + s * 0.2, 3.4), "white", rot=(0, 0, 0 if s > 0 else 180), bevel=0)
    for z in (1.0, 2.4):
        m.box((0.18, 10, 0.4), (-0.18, 0, z), "white", bevel=0.04)
    return _one(m, "prop", note="10 studs long")


def hydrant():
    m = Mesh("Hydrant")
    m.cyl(0.7, 0.3, (0, 0, 0.15), "red", segments=14, bevel=0.05)
    m.cyl(0.55, 2.2, (0, 0, 1.4), "red", segments=14, bevel=0.05)
    m.sphere(0.6, (0, 0, 2.5), "red", scale=(1, 1, 0.7), segments=14, rings=8)
    m.cyl(0.2, 0.4, (0, 0, 3.0), "yellow", segments=6, bevel=0.03)
    for a in (0, 90, 270):
        r = math.radians(a)
        m.cyl(0.28, 0.6, (math.sin(r) * 0.7, math.cos(r) * 0.7, 1.9), "yellow", rot=(90, 0, -a), segments=10, bevel=0.04)
    return _one(m, "prop", physics=True)


def traffic_light():
    m = Mesh("TrafficLight")
    m.cyl(0.3, 10, (0, 0, 5), "charcoal", segments=10, bevel=0)
    m.box((1.4, 1.2, 3.8), (0, 0.4, 9), "black", bevel=0.2)
    for i, c in enumerate(("taillight", "yellow", "neongreen")):
        m.cyl(0.42, 0.2, (0, 1.05, 10.2 - i * 1.2), c, rot=(90, 0, 0), segments=14, bevel=0)
        m.box((1.0, 0.5, 0.12), (0, 1.25, 10.6 - i * 1.2), "black", rot=(20, 0, 0), bevel=0.02)  # visors
    return _one(m, "prop")


def mailbox():
    m = Mesh("Mailbox")
    m.box((0.4, 0.4, 3.4), (0, 0, 1.7), "wood", bevel=0.05)
    m.box((1.2, 2.0, 0.8), (0, 0.2, 3.6), "navy", bevel=0.05)
    m.cyl(0.6, 1.96, (0, 0.2, 4.0), "navy", rot=(90, 0, 0), segments=16, bevel=0.03)
    m.box((0.1, 0.2, 1.0), (0.65, 0.7, 4.3), "red", bevel=0.02)  # flag up: a parcel is waiting
    m.box((0.1, 0.6, 0.3), (0.65, 0.95, 4.75), "red", bevel=0.02)
    return _one(m, "prop", note="marks delivery addresses")


def bin_():
    m = Mesh("Bin")
    m.box((2.2, 2.2, 3.4), (0, 0, 1.7), "green", bevel=0.2)
    m.box((2.4, 2.5, 0.3), (0, -0.1, 3.5), "darkgreen", rot=(-6, 0, 0), bevel=0.1)
    for sx in (-1, 1):
        m.cyl(0.35, 0.3, (sx * 0.9, -1.2, 0.35), "black", rot=(0, 90, 0), segments=12, bevel=0.05)
    return _one(m, "prop", physics=True)


def street_sign():
    m = Mesh("Sign")
    m.cyl(0.15, 8, (0, 0, 4), "steel", segments=8, bevel=0)
    for k, (c, a) in enumerate((("green", 0), ("blue", 90))):
        m.box((4.5, 0.15, 1.0), (1.8 if a == 0 else 0, 0 if a == 0 else 1.8, 7.3 - k * 1.2), c, rot=(0, 0, a), bevel=0.06)
    return _one(m, "prop", note="put SurfaceGuis on the two boards for district names")


# ------------------------------------------------------------------ moving things


def dog():
    """Suburbs hazard: dashes across the road."""
    m = Mesh("Dog")
    m.sphere(1, (0, 0, 2.0), "tan", scale=(0.9, 1.6, 0.9))
    m.sphere(0.85, (0, 1.7, 2.9), "tan")
    m.sphere(0.45, (0, 2.45, 2.7), "cream", scale=(1, 1.1, 0.8))  # snout
    m.sphere(0.18, (0, 2.95, 2.85), "black", segments=8, rings=5)
    for sx in (-1, 1):
        m.sphere(0.12, (sx * 0.35, 2.4, 3.2), "black", segments=8, rings=5)
        m.sphere(0.4, (sx * 0.65, 1.5, 3.3), "brown", scale=(0.5, 0.8, 1.4), rot=(0, sx * 20, 0))  # ears
        for y in (0.9, -0.9):
            m.cyl(0.28, 1.6, (sx * 0.5, y, 0.8), "tan", segments=10, bevel=0.1)
            m.sphere(0.32, (sx * 0.5, y + 0.15, 0.1), "cream", scale=(1, 1.3, 0.6), segments=10, rings=6)
    m.tube((0, -1.5, 2.4), (0, -2.4, 3.4), 0.18, "tan", segments=8)  # tail up
    m.box((1.2, 0.3, 0.3), (0, 1.15, 2.6), "red", rot=(30, 0, 0), bevel=0.08)  # collar
    m.sphere(0.15, (0, 1.4, 2.25), "gold", segments=8, rings=5)
    return _one(m, "hazard")


def car_hatch():
    """Traffic car. Recolour `Paint` per car for variety."""
    paint, body = Mesh("Paint"), Mesh("Body")
    paint.box((6.2, 11, 2.6), (0, 0, 2.2), bevel=0.6, segments=3)
    paint.box((5.6, 6.2, 2.4), (0, -1.0, 4.4), bevel=0.7, segments=3)
    body.box((5.0, 0.2, 1.9), (0, 2.05, 4.4), "glass", rot=(-35, 0, 0), bevel=0.05)
    body.box((5.0, 0.2, 1.8), (0, -4.05, 4.4), "glass", rot=(20, 0, 0), bevel=0.05)
    for sx in (-1, 1):
        body.box((0.2, 4.8, 1.6), (sx * 2.82, -0.9, 4.45), "glass", bevel=0.05)
        body.cyl(0.45, 0.2, (sx * 2.2, 5.48, 2.6), "headlight", rot=(90, 0, 0), segments=14, bevel=0.03)
        body.box((1.0, 0.2, 0.5), (sx * 2.2, -5.48, 2.8), "taillight", bevel=0.05)
        body.box((0.6, 0.4, 0.4), (sx * 3.15, 1.6, 3.6), "charcoal", bevel=0.1)  # mirrors
    body.box((6.4, 0.6, 0.8), (0, 5.5, 1.2), "charcoal", bevel=0.25)
    body.box((6.4, 0.6, 0.8), (0, -5.5, 1.2), "charcoal", bevel=0.25)
    body.box((1.8, 0.1, 0.6), (0, 5.82, 1.2), "white", bevel=0.03)
    for sx in (-1, 1):
        for y in (3.5, -3.5):
            body.tire(1.15, 0.9, (sx * 2.75, y, 1.15))
    return [paint.done(), body.done()], {"kind": "hazard"}


# ------------------------------------------------------------------ hub


def depot():
    """The courier depot: start point, garage and job board area."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, d, h = 50, 24, 16
    paint.box((w, d, h), (0, 0, h / 2), bevel=0.3)
    body.box((w + 1, d + 1, 1.2), (0, 0, h + 0.6), "white", bevel=0.3)
    for x in (-15, 0, 15):
        body.box((11, 0.6, 10), (x, d / 2 + 0.05, 5), "white", bevel=0.15)  # roller door frames
        body.box((10, 0.65, 9.4), (x, d / 2 + 0.1, 4.7), "lightgrey", bevel=0.05)
        for k in range(9):
            body.box((9.6, 0.7, 0.12), (x, d / 2 + 0.12, 0.6 + k * 1.0), "grey", bevel=0)
        for sx in (-1, 1):
            body.box((0.6, 4, 0.08), (x + sx * 5, d / 2 + 2.2, 0.04), "yellow", bevel=0)  # bay lines
    body.box((30, 0.8, 4.4), (0, d / 2 + 0.3, 13), "navy", bevel=0.3)  # sign board for "RAGDOLL COURIERS"
    body.box((31, 0.7, 0.6), (0, d / 2 + 0.3, 15.4), "yellow", bevel=0.1)
    body.box((4.4, 4.4, 4.4), (-20, d / 2 - 1, h + 3.4), "cardboard", rot=(0, 0, 12), bevel=0.2)  # rooftop mascot parcel
    body.box((4.5, 0.9, 4.5), (-20, d / 2 - 1, h + 3.4), "tape", rot=(0, 0, 12), bevel=0.05)
    for x in (10, 18):
        body.cyl(1.3, 2.4, (x, -4, h + 2.2), "steel", segments=14, bevel=0.1)  # roof vents
        body.cyl(1.7, 0.5, (x, -4, h + 3.6), "steel", segments=14, bevel=0.1)
    for sx in (-1, 1):
        _window(body, sx * 23, d / 2, 12.5, w=2.4, h=2.4)
    body.box((w + 6, 6, 0.6), (0, d / 2 + 3, 0.3), "concrete", bevel=0.1)  # forecourt kerb
    return [paint.done(), body.done()], {"kind": "building", "footprint": [w + 6, d + 8]}


def job_board():
    m = Mesh("JobBoard")
    for sx in (-1, 1):
        m.box((0.7, 0.7, 9), (sx * 5, 0, 4.5), "wood", bevel=0.1)
    m.box((10.5, 0.6, 6), (0, 0, 5.5), "darkbrown", bevel=0.15)
    m.box((9.6, 0.65, 5.2), (0, 0.02, 5.5), "cardboard", bevel=0.05)  # cork
    colours = ("white", "yellow", "skyblue", "pink", "lime", "white", "cream", "coral")
    for k, c in enumerate(colours):
        x, z = -3.6 + (k % 4) * 2.4, 6.7 - (k // 4) * 2.4
        m.box((1.8, 0.1, 1.9), (x, 0.38, z), c, rot=(0, (k * 37 % 11) - 5, 0), bevel=0.02)
        m.sphere(0.13, (x, 0.45, z + 0.75), "red", segments=8, rings=5)  # pin
    m.box((11.6, 2.6, 0.4), (0, 0.4, 9.2), "red", rot=(-14, 0, 0), bevel=0.12)  # little roof
    m.box((4, 0.4, 1.0), (0, 0.4, 8.3), "yellow", bevel=0.1)  # "JOBS" plate
    return _one(m, "prop", note="ProximityPrompt on the cork face opens the Jobs screen")


def display_plinth():
    m = Mesh("Plinth")
    m.cyl(9, 1.0, (0, 0, 0.5), "charcoal", segments=40, bevel=0.2)
    m.cyl(8.2, 0.3, (0, 0, 1.15), "lightgrey", segments=40, bevel=0.05)
    m.cyl(9.05, 0.25, (0, 0, 0.75), "neonblue", segments=40, bevel=0)
    return _one(m, "prop", note="garage turntable: spin the vehicle on top")


def leaderboard():
    m = Mesh("Leaderboard")
    for sx in (-1, 1):
        m.box((1, 1, 16), (sx * 7, 0, 8), "charcoal", bevel=0.15)
    m.box((15.5, 1.2, 11), (0, 0, 10), "navy", bevel=0.3)
    m.box((14, 1.25, 9.6), (0, 0.01, 10), "black", bevel=0.05)  # screen: SurfaceGui on the +Z face
    m.box((16, 1.6, 1.6), (0, 0, 16.1), "gold", bevel=0.4)
    m.sphere(1.0, (0, 0, 17.6), "gold", scale=(1, 1, 0.8), segments=16, rings=10)
    return _one(m, "prop")


def address_marker():
    m = Mesh("Marker")
    m.cyl(12, 0.12, (0, 0, 0.06), "neongreen", segments=48, bevel=0)
    m.cyl(10.8, 0.14, (0, 0, 0.07), "green", segments=48, bevel=0)
    m.box((1.8, 1.8, 1.8), (0, 0, 9), "cardboard", rot=(0, 0, 45), bevel=0.15)  # floating parcel icon
    m.box((1.9, 0.5, 1.9), (0, 0, 9), "tape", rot=(0, 0, 45), bevel=0.03)
    m.cyl(1.0, 1.4, (0, 0, 6.6), "neongreen", segments=4, r2=0.05, rot=(180, 0, 45), bevel=0)  # arrow tip
    return _one(m, "prop", note="spin + bob the parcel icon in code")


ASSETS = {
    "Road_Straight": road_straight,
    "Road_Corner": road_corner,
    "Road_T": road_t,
    "Road_Cross": road_cross,
    "Road_Cobble": road_cobble,
    "SpeedBump": speed_bump,
    "Ramp": ramp,
    "House_A": house_a,
    "House_B": house_b,
    "House_C": house_c,
    "OldTown_Townhouse": townhouse,
    "OldTown_Shop": shop,
    "OldTown_MarketStall": market_stall,
    "Docks_Container": container,
    "Docks_Forklift": forklift,
    "Docks_Warehouse": warehouse,
    "Docks_Bollard": bollard,
    "Docks_Barrel": barrel,
    "Docks_Crate": crate,
    "Site_TowerCrane": tower_crane,
    "Site_WreckingBall": wrecking_ball,
    "Site_Cone": cone,
    "Site_Barrier": jersey_barrier,
    "Site_Scaffold": scaffold,
    "Site_Portacabin": portacabin,
    "Site_Pipes": pipe_stack,
    "Site_DirtPile": dirt_pile,
    "Mountain_RockLarge": rock_large,
    "Mountain_RockSmall": rock_small,
    "Mountain_Boulder": boulder,
    "Mountain_Guardrail": guardrail,
    "Mountain_Cabin": cabin,
    "Mountain_Pine": pine,
    "Street_Tree": tree_round,
    "Street_Bush": bush,
    "Street_Lamp": lamp_post,
    "Street_Bench": bench,
    "Street_Fence": fence,
    "Street_Hydrant": hydrant,
    "Street_TrafficLight": traffic_light,
    "Street_Mailbox": mailbox,
    "Street_Bin": bin_,
    "Street_Sign": street_sign,
    "Traffic_Dog": dog,
    "Traffic_Car": car_hatch,
    "Hub_Depot": depot,
    "Hub_JobBoard": job_board,
    "Hub_Plinth": display_plinth,
    "Hub_Leaderboard": leaderboard,
    "Hub_AddressMarker": address_marker,
}
