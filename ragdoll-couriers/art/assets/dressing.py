"""Batch 7: set dressing. More traffic, billboards, power poles, street furniture and birds.
Same conventions as world.py: ground at z = 0, front faces +Y, `Paint` parts take a colour per instance."""

import math

from lib import Mesh


def _one(m: Mesh, kind: str, **meta):
    return [m.done()], {"kind": kind, **meta}


# ------------------------------------------------------------------ traffic


def bus():
    """City bus, 30 long. Paint is the livery."""
    paint, body = Mesh("Paint"), Mesh("Body")
    w, L, h = 8, 30, 9
    paint.box((w, L, h - 1.6), (0, 0, 1.6 + (h - 1.6) / 2), bevel=0.6, segments=2)
    body.box((w + 0.1, L - 4, 2.6), (0, -1, 6.2), "tintdark", bevel=0.2)  # window band
    body.box((w - 0.6, 0.2, 3.6), (0, L / 2 + 0.05, 5.6), "tintdark", bevel=0.1)  # windscreen
    body.box((5, 0.3, 1.0), (0, L / 2 + 0.1, 8.0), "black", bevel=0.05)  # route sign
    body.box((4.4, 0.35, 0.6), (0, L / 2 + 0.15, 8.0), "neonorange", bevel=0)
    for y in (9, -3):  # doors on the kerb side (+X)
        body.box((0.2, 3.4, 6), (w / 2 + 0.05, y, 4.4), "tint", bevel=0.05)
        body.box((0.25, 0.15, 6), (w / 2 + 0.1, y, 4.4), "charcoal", bevel=0)
    body.box((6, 8, 1), (0, -4, h + 0.5), "lightgrey", bevel=0.3)  # roof AC
    for sx in (-1, 1):
        body.cyl(0.5, 0.2, (sx * 2.8, L / 2 + 0.1, 2.6), "headlight", rot=(90, 0, 0), segments=12, bevel=0)
        body.box((1.0, 0.2, 0.6), (sx * 3, -L / 2 - 0.05, 2.8), "taillight", bevel=0.05)
        body.box((0.3, 0.8, 1.2), (sx * 4.3, L / 2 - 1, 6.6), "black", bevel=0.1)  # mirrors
    body.box((w + 0.3, 1, 1.2), (0, L / 2, 1.2), "charcoal", bevel=0.3)
    body.box((w + 0.3, 1, 1.2), (0, -L / 2, 1.2), "charcoal", bevel=0.3)
    for sx in (-1, 1):
        for y in (9.5, -9.5):
            body.tire(1.5, 1.0, (sx * 3.5, y, 1.5))
    return [paint.done(), body.done()], {"kind": "hazard"}


def taxi():
    """Taxi: the traffic hatchback shape with a roof sign and a checker band."""
    paint, body = Mesh("Paint"), Mesh("Body")
    paint.box((6.2, 11, 2.6), (0, 0, 2.2), bevel=0.6, segments=3)
    paint.box((5.6, 6.2, 2.4), (0, -1.0, 4.4), bevel=0.7, segments=3)
    body.box((5.0, 0.2, 1.9), (0, 2.05, 4.4), "glass", rot=(-35, 0, 0), bevel=0.05)
    body.box((5.0, 0.2, 1.8), (0, -4.05, 4.4), "glass", rot=(20, 0, 0), bevel=0.05)
    for sx in (-1, 1):
        body.box((0.2, 4.8, 1.6), (sx * 2.82, -0.9, 4.45), "glass", bevel=0.05)
        body.cyl(0.45, 0.2, (sx * 2.2, 5.48, 2.6), "headlight", rot=(90, 0, 0), segments=14, bevel=0.03)
        body.box((1.0, 0.2, 0.5), (sx * 2.2, -5.48, 2.8), "taillight", bevel=0.05)
        for k in range(10):  # checker band
            body.box((0.12, 1.0, 0.5), (sx * 3.12, -4.5 + k * 1.0, 2.3 + (k % 2) * 0.5), "black", bevel=0)
    body.box((2.4, 1.0, 0.8), (0, -0.8, 6.0), "yellow", bevel=0.2)  # roof sign
    body.box((2.2, 1.05, 0.4), (0, -0.8, 6.0), "black", bevel=0)
    body.box((6.4, 0.6, 0.8), (0, 5.5, 1.2), "charcoal", bevel=0.25)
    body.box((6.4, 0.6, 0.8), (0, -5.5, 1.2), "charcoal", bevel=0.25)
    for sx in (-1, 1):
        for y in (3.5, -3.5):
            body.tire(1.15, 0.9, (sx * 2.75, y, 1.15))
    return [paint.done(), body.done()], {"kind": "hazard"}


def van():
    """Box van, 16 long: a rival courier's (Paint is their colour)."""
    paint, body = Mesh("Paint"), Mesh("Body")
    paint.box((7, 11, 8), (0, -2.5, 5), bevel=0.4)  # box body
    paint.box((7, 5, 4.6), (0, 5.5, 3.3), bevel=0.6)  # cab
    body.box((6.4, 0.2, 2.4), (0, 8.05, 4.4), "glass", rot=(-15, 0, 0), bevel=0.05)
    for sx in (-1, 1):
        body.box((0.2, 2.6, 1.8), (sx * 3.52, 5.6, 4.4), "glass", bevel=0.05)
        body.cyl(0.45, 0.2, (sx * 2.5, 8.05, 2.4), "headlight", rot=(90, 0, 0), segments=12, bevel=0.03)
        body.box((0.8, 0.2, 0.8), (sx * 2.8, -8.05, 2.4), "taillight", bevel=0.05)
        body.box((0.3, 6, 3), (sx * 3.55, -2.5, 6), "white", bevel=0.1)  # side panel for a logo decal
        for y in (5, -5.5):
            body.tire(1.3, 0.9, (sx * 3.0, y, 1.3))
    body.box((7.2, 0.6, 1), (0, 8.2, 1.4), "charcoal", bevel=0.25)
    body.box((7.2, 0.6, 1), (0, -8.2, 1.4), "charcoal", bevel=0.25)
    body.box((6.6, 0.1, 6.8), (0, -8.05, 5), "lightgrey", bevel=0.05)  # roller door
    return [paint.done(), body.done()], {"kind": "hazard"}


# ------------------------------------------------------------------ roadside


def billboard():
    """Big roadside billboard. The +Y face of `Panel` is blank: put a Decal or SurfaceGui on it."""
    frame, panel = Mesh("Frame"), Mesh("Panel")
    for x in (-7, 7):
        frame.box((0.8, 0.8, 12), (x, -0.6, 6), "steel", bevel=0.1)
    frame.box((25, 1, 13), (0, -0.4, 16), "charcoal", bevel=0.3)
    panel.box((24, 0.3, 12), (0, 0.2, 16), "white", bevel=0)
    frame.box((24, 2.4, 0.3), (0, 1.0, 9.6), "steel", bevel=0)  # catwalk
    for x in (-8, 0, 8):
        frame.tube((x, -0.2, 22.6), (x, 2.4, 23.6), 0.12, "charcoal", segments=6)
        frame.cyl(0.6, 0.4, (x, 2.6, 23.4), "headlight", rot=(60, 0, 0), segments=10, bevel=0)
    return [frame.done(), panel.done()], {"kind": "prop", "note": "Panel's front: a decal slot for ads or crash-clip art"}


def power_pole():
    m = Mesh("Pole")
    m.cyl(0.55, 22, (0, 0, 11), "wood", segments=10, r2=0.4, bevel=0)
    m.box((7, 0.5, 0.5), (0, 0, 20.5), "wood", bevel=0.05)
    for x in (-3, 0, 3):
        m.cyl(0.25, 0.8, (x, 0, 21.2), "white", segments=8, bevel=0)  # insulators
    m.box((1.4, 1.2, 2.0), (0, 0.9, 16), "grey", bevel=0.1)  # transformer
    return _one(m, "prop", wires=[[-3, 21.6, 0], [0, 21.6, 0], [3, 21.6, 0]], note="wire attach points (Roblox space); wires are built per road in PowerLines")


def flower_bed():
    m = Mesh("FlowerBed")
    m.box((6, 3, 1.2), (0, 0, 0.6), "brick", bevel=0.1)
    m.box((5.4, 2.4, 0.3), (0, 0, 1.15), "darkbrown", bevel=0)
    colours = ("red", "yellow", "pink", "white", "purple", "orange")
    for k in range(12):
        x, y = -2.2 + (k % 6) * 0.88, -0.6 + (k // 6) * 1.2
        m.cyl(0.05, 0.6, (x, y, 1.55), "green", segments=4, bevel=0)
        m.sphere(0.32, (x, y, 1.9), colours[k % len(colours)], segments=8, rings=5)
    for k in range(3):
        m.sphere(0.5, (-2 + k * 2, 0, 1.4), "darkgreen", scale=(1, 0.7, 0.6), segments=8, rings=5)
    return _one(m, "prop")


def bus_stop():
    m = Mesh("BusStop")
    for x in (-4, 4):
        m.box((0.3, 0.3, 6), (x, -1.2, 3), "steel", bevel=0)
    m.box((9, 0.15, 4.6), (0, -1.3, 3.6), "glass", bevel=0)  # back panel
    m.box((10, 3.2, 0.3), (0, 0, 6.1), "charcoal", bevel=0.1)  # roof
    m.box((7, 1, 0.3), (0, -0.6, 1.6), "wood", bevel=0.05)  # bench
    m.box((7, 0.3, 1), (0, -1.0, 2.2), "wood", bevel=0.05)
    m.cyl(0.12, 8, (5.4, 0.6, 4), "steel", segments=6, bevel=0)  # sign pole
    m.cyl(0.9, 0.2, (5.4, 0.6, 7.6), "blue", rot=(90, 0, 0), segments=16, bevel=0)
    m.box((1.4, 0.25, 0.4), (5.4, 0.75, 7.6), "white", bevel=0)
    return _one(m, "prop")


def postbox():
    """A red pillar box: the courier city's favourite street furniture."""
    m = Mesh("Postbox")
    m.cyl(0.95, 0.3, (0, 0, 0.15), "black", segments=16, bevel=0.05)
    m.cyl(0.8, 4, (0, 0, 2.2), "red", segments=16, bevel=0.05)
    m.sphere(0.85, (0, 0, 4.2), "red", scale=(1, 1, 0.55), segments=16, rings=8)
    m.box((1.0, 0.2, 0.18), (0, 0.78, 3.3), "black", bevel=0)  # slot
    m.box((0.7, 0.15, 0.5), (0, 0.8, 2.4), "gold", bevel=0.02)  # plate
    return _one(m, "prop", physics=True)


def phone_box():
    m = Mesh("PhoneBox")
    m.box((3, 3, 8), (0, 0, 4), "red", bevel=0.15)
    m.box((3.3, 3.3, 0.6), (0, 0, 8.3), "red", bevel=0.2)
    m.cyl(2.0, 0.6, (0, 0, 8.8), "red", rot=(0, 0, 45), segments=4, bevel=0.1)
    for a in range(4):
        r = math.radians(a * 90)
        cx, cy = math.sin(r) * 1.52, math.cos(r) * 1.52
        m.box((2.2, 0.1, 5), (cx, cy, 4.5), "glass", rot=(0, 0, -a * 90), bevel=0)
        m.box((2.0, 0.12, 0.5), (cx * 1.01, cy * 1.01, 7.4), "black", rot=(0, 0, -a * 90), bevel=0)  # header
    return _one(m, "prop")


def bike_rack():
    m = Mesh("BikeRack")
    for k in range(5):
        x = -4 + k * 2
        m.tube((x, -0.6, 0), (x, -0.6, 2.4), 0.1, "steel", segments=6)
        m.tube((x, 0.6, 0), (x, 0.6, 2.4), 0.1, "steel", segments=6)
        m.tube((x, -0.6, 2.4), (x, 0.6, 2.4), 0.1, "steel", segments=6)
    for k, c in enumerate(("red", "blue")):  # two parked bikes
        x = -3 + k * 4
        m.tire(1.0, 0.15, (x, -1.6, 1.0), "rubber", "steel", segments=16)  # default axle along X: wheels upright
        m.tire(1.0, 0.15, (x, 1.6, 1.0), "rubber", "steel", segments=16)
        m.tube((x, -1.6, 1.0), (x, 0.2, 2.2), 0.08, c, segments=6)
        m.tube((x, 0.2, 2.2), (x, 1.6, 1.0), 0.08, c, segments=6)
        m.tube((x, 0.2, 2.2), (x, -0.8, 2.6), 0.08, c, segments=6)
    return _one(m, "prop", physics=True)


# ------------------------------------------------------------------ birds


def seagull():
    m = Mesh("Seagull")
    m.sphere(0.5, (0, 0, 0.9), "white", scale=(0.7, 1.4, 0.7), segments=10, rings=6)
    m.sphere(0.32, (0, 0.6, 1.3), "white", segments=10, rings=6)
    m.cyl(0.1, 0.35, (0, 0.95, 1.25), "yellow", rot=(-90, 0, 0), r2=0.02, segments=6, bevel=0)
    for sx in (-1, 1):
        m.sphere(0.35, (sx * 0.38, -0.1, 1.0), "grey", scale=(0.3, 1.4, 0.5), segments=8, rings=5)  # folded wings
        m.tube((sx * 0.15, 0, 0.6), (sx * 0.15, 0.05, 0), 0.05, "orange", segments=4)
    m.sphere(0.06, (0.18, 0.82, 1.38), "black", segments=6, rings=4)
    m.sphere(0.06, (-0.18, 0.82, 1.38), "black", segments=6, rings=4)
    return _one(m, "prop", note="scatters when you crash near it (animate in code)")


def pigeon():
    m = Mesh("Pigeon")
    m.sphere(0.4, (0, 0, 0.6), "grey", scale=(0.8, 1.2, 0.85), segments=10, rings=6)
    m.sphere(0.25, (0, 0.45, 0.95), "charcoal", segments=10, rings=6)
    m.cyl(0.07, 0.2, (0, 0.72, 0.92), "black", rot=(-90, 0, 0), r2=0.02, segments=6, bevel=0)
    m.sphere(0.18, (0, 0.3, 0.75), "teal", scale=(1.2, 0.6, 0.8), segments=8, rings=5)  # iridescent neck
    for sx in (-1, 1):
        m.tube((sx * 0.12, 0, 0.35), (sx * 0.12, 0.05, 0), 0.04, "pink", segments=4)
    return _one(m, "prop", note="scatters when you crash near it (animate in code)")


ASSETS = {
    "Traffic_Bus": bus,
    "Traffic_Taxi": taxi,
    "Traffic_Van": van,
    "Street_Billboard": billboard,
    "Street_PowerPole": power_pole,
    "Street_FlowerBed": flower_bed,
    "Street_BusStop": bus_stop,
    "Street_Postbox": postbox,
    "Street_PhoneBox": phone_box,
    "Street_BikeRack": bike_rack,
    "Bird_Seagull": seagull,
    "Bird_Pigeon": pigeon,
}
