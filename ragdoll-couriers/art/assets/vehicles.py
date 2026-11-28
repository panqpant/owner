"""Vehicles. Blender frame: +Y front, +Z up, origin = the invisible physics body centre.
Ground is at z = -1.8 for every vehicle, matching the kill test's ride height.

Parts per vehicle:
  Paint  - panels that take the skin colour (in Roblox: drop the texture, set Color/Material)
  Body   - everything else that doesn't move (textured)
  wheels - one part each, centred on the hub so code can spin them
"""

from lib import Mesh

GROUND = -1.8


def _wheel(name, r, w, y, x=0.0, tyre="rubber", hub="chrome"):
    return Mesh(name).tire(r, w, (0, 0, 0), tyre, hub).done((x, y, GROUND + r))


def _meta(seat, anchor, wheels, rays, capacity=1, size_class=1, extra=None):
    """Positions in Roblox vehicle space (x right, y up, -z forward)."""
    rb = lambda v: [round(v[0], 3), round(v[2], 3), round(-v[1], 3)]
    m = {
        "seat": rb(seat),
        "parcelAnchors": [rb(a) for a in anchor],
        "wheels": {n: {"centre": rb(c), "radius": r} for n, (c, r) in wheels.items()},
        "rayPoints": [rb(p) for p in rays],
        "capacity": capacity,
        "sizeClass": size_class,
        "rideHeight": 2.2,
        "groundY": GROUND,
    }
    m.update(extra or {})
    return m


def _cargo_box(m: Mesh, centre, size, colour="yellow", trim="red", wall=0.18):
    """Open-top delivery box with a stripe and corner caps."""
    x, y, z = centre
    w, d, h = size
    m.box((w, d, wall), (x, y, z - h / 2 + wall / 2), colour, bevel=0.06)
    for sx in (-1, 1):
        m.box((wall, d, h), (x + sx * (w / 2 - wall / 2), y, z), colour, bevel=0.06)
        m.box((wall + 0.04, d * 0.98, 0.22), (x + sx * (w / 2 - wall / 2), y, z + h * 0.15), trim, bevel=0.03)
    for sy in (-1, 1):
        m.box((w, wall, h), (x, y + sy * (d / 2 - wall / 2), z), colour, bevel=0.06)
        m.box((w * 0.98, wall + 0.04, 0.22), (x, y + sy * (d / 2 - wall / 2), z + h * 0.15), trim, bevel=0.03)
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box((0.26, 0.26, h + 0.08), (x + sx * (w / 2 - 0.08), y + sy * (d / 2 - 0.08), z + 0.04), "charcoal", bevel=0.08)


def scooter(rocket=False):
    paint, body = Mesh("Paint"), Mesh("Body")
    r = 0.85
    fy, ry = 2.35, -2.25
    # Floorboard, leg shield and the round rear cowl that hides the engine.
    paint.box((1.4, 1.9, 0.32), (0, 0.75, -0.95), bevel=0.12)
    paint.box((1.5, 0.34, 2.1), (0, 1.85, 0.0), rot=(-14, 0, 0), bevel=0.14)
    paint.sphere(1, (0, -0.75, -0.35), scale=(0.82, 1.65, 0.62), segments=24, rings=14)
    paint.box((0.9, 0.9, 0.55), (0, 2.1, 1.25), rot=(-14, 0, 0), bevel=0.2)  # headset cover
    # Front fender: three segments hugging the wheel.
    for i, a in enumerate((-35, 0, 35)):
        import math

        t = math.radians(a)
        paint.box((0.62, 0.7, 0.12), (0, fy + math.sin(t) * (r + 0.18), GROUND + r + math.cos(t) * (r + 0.18)), rot=(-a, 0, 0), bevel=0.05)

    body.box((1.0, 1.55, 0.36), (0, -0.35, 0.42), "black", bevel=0.16)  # seat
    body.box((1.04, 1.6, 0.12), (0, -0.35, 0.22), "charcoal", bevel=0.05)
    body.tube((0, fy, GROUND + r), (0, 2.08, 1.1), 0.12, "chrome")  # fork + steering column
    body.tube((-1.15, 2.05, 1.55), (1.15, 2.05, 1.55), 0.08, "charcoal")  # handlebars
    for sx in (-1, 1):
        body.cyl(0.13, 0.5, (sx * 1.05, 2.05, 1.55), "rubber", rot=(0, 90, 0), segments=12)
        body.tube((sx * 0.55, 2.0, 1.55), (sx * 0.75, 1.9, 2.15), 0.04, "chrome")  # mirror stalk
        body.sphere(0.16, (sx * 0.78, 1.9, 2.2), "chrome", scale=(1.2, 0.5, 0.9))
    body.cyl(0.26, 0.18, (0, 2.32, 0.6), "chrome", rot=(76, 0, 0))  # headlight rim
    body.cyl(0.21, 0.2, (0, 2.36, 0.62), "headlight", rot=(76, 0, 0), bevel=0.02)
    body.box((0.5, 0.2, 0.18), (0, -2.5, -0.05), "taillight", bevel=0.05)
    body.box((0.8, 0.08, 0.5), (0, -2.55, -0.5), "white", bevel=0.03)  # number plate
    # Rear rack and the cargo box.
    for sx in (-1, 1):
        body.tube((sx * 0.6, -1.1, 0.05), (sx * 0.6, -2.4, 0.3), 0.06, "charcoal")
        body.tube((sx * 0.35, ry, GROUND + r), (sx * 0.55, -1.5, -0.2), 0.08, "chrome")  # rear swingarm
    body.box((1.4, 1.6, 0.12), (0, -1.75, 0.35), "charcoal", bevel=0.03)
    _cargo_box(body, (0, -1.75, 1.3), (2.6, 2.4, 1.8))
    if rocket:
        for sx in (-1, 1):
            body.cyl(0.36, 2.2, (sx * 1.0, -0.9, -0.2), "steel", rot=(90, 0, 0), bevel=0.08)
            body.cyl(0.36, 0.8, (sx * 1.0, 0.55, -0.2), "red", rot=(-90, 0, 0), r2=0.02, bevel=0.03)  # nose cone
            body.cyl(0.4, 0.5, (sx * 1.0, -2.2, -0.2), "charcoal", rot=(90, 0, 0), r2=0.28)  # nozzle
            body.cyl(0.24, 0.1, (sx * 1.0, -2.47, -0.2), "neonorange", rot=(90, 0, 0), bevel=0)
            body.box((0.08, 0.7, 0.6), (sx * 1.0, -1.7, 0.25), "red", rot=(-20, 0, 0), bevel=0.03)  # fins
            body.box((0.6, 0.7, 0.08), (sx * 1.35, -1.7, -0.2), "red", rot=(0, 0, 0), bevel=0.03)
    else:
        body.tube((0.55, -0.4, -1.05), (0.6, -2.3, -0.75), 0.13, "chrome")  # exhaust
        body.cyl(0.17, 0.35, (0.6, -2.45, -0.72), "charcoal", rot=(80, 0, 0))

    objs = [paint.done(), body.done(), _wheel("FrontWheel", r, 0.62, fy), _wheel("RearWheel", r, 0.66, ry)]
    meta = _meta(
        seat=(0, -0.35, 0.6),
        anchor=[(0, -1.75, 1.3)],
        wheels={"FrontWheel": ((0, fy, GROUND + r), r), "RearWheel": ((0, ry, GROUND + r), r)},
        rays=[(-0.8, 2.3, -0.4), (0.8, 2.3, -0.4), (-0.8, -2.3, -0.4), (0.8, -2.3, -0.4)],
        extra={"boxInnerSize": [2.24, 1.62, 2.04]},
    )
    return objs, meta


def ebike():
    paint, body = Mesh("Paint"), Mesh("Body")
    r = 1.05
    fy, ry = 2.15, -1.95
    bb = (0, 0.05, -0.55)  # bottom bracket
    seat_top = (0, -0.55, 0.95)
    head_top, head_bot = (0, 1.55, 1.05), (0, 1.72, 0.35)
    front_hub, rear_hub = (0, fy, GROUND + r), (0, ry, GROUND + r)
    for a, b in ((bb, head_bot), (seat_top, head_top), (bb, seat_top), (head_top, head_bot)):
        paint.tube(a, b, 0.16, "white")
    for sx in (-1, 1):
        paint.tube((sx * 0.18, rear_hub[1], rear_hub[2]), (sx * 0.1, bb[1], bb[2]), 0.09, "white")  # chainstays
        paint.tube((sx * 0.18, rear_hub[1], rear_hub[2]), (sx * 0.1, -0.5, 0.85), 0.09, "white")  # seatstays
        body.tube((sx * 0.18, front_hub[1], front_hub[2]), (sx * 0.12, 1.72, 0.35), 0.08, "chrome")  # fork
    body.box((0.42, 1.5, 0.42), (0, 0.85, -0.12), "charcoal", rot=(-27, 0, 0), bevel=0.12)  # battery on the down tube
    body.box((0.1, 0.3, 0.12), (0.22, 0.6, 0.0), "neongreen", rot=(-27, 0, 0), bevel=0.03)  # charge LEDs
    body.cyl(0.35, 0.3, bb, "charcoal", rot=(0, 90, 0))  # motor
    body.cyl(0.55, 0.06, (0.3, bb[1], bb[2]), "steel", rot=(0, 90, 0), bevel=0.01)  # chainring
    for sx in (-1, 1):
        body.tube((sx * 0.3, bb[1], bb[2]), (sx * 0.45, bb[1] + 0.35 * (1 if sx > 0 else -1), bb[2] - 0.35), 0.05, "charcoal")  # cranks
        body.box((0.45, 0.25, 0.08), (sx * 0.6, bb[1] + 0.35 * (1 if sx > 0 else -1), bb[2] - 0.35), "black", bevel=0.03)  # pedals
    body.tube(head_top, (0, 1.45, 1.55), 0.09, "charcoal")  # stem
    body.tube((-1.05, 1.4, 1.6), (1.05, 1.4, 1.6), 0.07, "charcoal")
    for sx in (-1, 1):
        body.cyl(0.11, 0.45, (sx * 0.95, 1.4, 1.6), "rubber", rot=(0, 90, 0), segments=12)
    body.tube(seat_top, (0, -0.62, 1.3), 0.08, "chrome")  # seatpost
    body.box((0.55, 1.05, 0.25), (0, -0.55, 1.42), "black", bevel=0.11)  # saddle
    body.cyl(0.2, 0.22, (0, 1.85, 0.95), "headlight", rot=(80, 0, 0), bevel=0.04)
    body.box((0.3, 0.12, 0.15), (0, -2.65, 0.32), "taillight", bevel=0.04)
    # Mudguards
    for y, z in ((fy, GROUND + r * 2 + 0.12), (ry, GROUND + r * 2 + 0.12)):
        paint.box((0.38, 1.3, 0.08), (0, y, z), bevel=0.03)
    # Rear rack + box
    for sx in (-1, 1):
        body.tube((sx * 0.5, ry, GROUND + r), (sx * 0.55, -1.95, 0.4), 0.05, "charcoal")
    body.box((1.3, 1.7, 0.1), (0, -1.95, 0.42), "charcoal", bevel=0.02)
    _cargo_box(body, (0, -1.95, 1.27), (2.3, 2.2, 1.6), "skyblue", "white")
    objs = [paint.done(), body.done(), _wheel("FrontWheel", r, 0.3, fy, hub="steel"), _wheel("RearWheel", r, 0.36, ry, hub="charcoal")]
    meta = _meta(
        seat=(0, -0.55, 1.6),
        anchor=[(0, -1.95, 1.3)],
        wheels={"FrontWheel": (front_hub, r), "RearWheel": (rear_hub, r)},
        rays=[(-0.6, 2.1, -0.4), (0.6, 2.1, -0.4), (-0.6, -1.9, -0.4), (0.6, -1.9, -0.4)],
        extra={"boxInnerSize": [1.94, 1.46, 1.84]},
    )
    return objs, meta


def cargobike():
    """Long-john: the big wooden box sits low in front of the rider."""
    paint, body = Mesh("Paint"), Mesh("Body")
    rf, rr = 0.75, 1.0
    fy, ry = 3.6, -2.2
    front_hub, rear_hub = (0, fy, GROUND + rf), (0, ry, GROUND + rr)
    # Frame: long low spine under the box, then up to the rider.
    paint.box((0.32, 4.0, 0.3), (0, 1.3, -1.05), bevel=0.1)
    paint.tube((0, -0.5, -1.0), (0, -0.85, 0.85), 0.17)  # seat tube
    paint.tube((0, -0.2, -0.95), (0, 0.15, 1.0), 0.15)  # to handlebar post
    paint.tube((0, -0.85, 0.85), (0, 0.15, 1.0), 0.14)
    for sx in (-1, 1):
        paint.tube((sx * 0.2, rear_hub[1], rear_hub[2]), (sx * 0.12, -0.5, -1.0), 0.09)
        paint.tube((sx * 0.2, rear_hub[1], rear_hub[2]), (sx * 0.1, -0.8, 0.75), 0.09)
        body.tube((sx * 0.15, front_hub[1], front_hub[2]), (sx * 0.1, 3.35, -0.2), 0.08, "chrome")
    body.tube((0, 3.35, -0.2), (0, 3.25, 0.25), 0.1, "chrome")  # head tube by the front wheel
    body.tube((0, 0.15, 1.0), (0, 3.25, 0.2), 0.04, "steel")  # steering linkage rod
    body.tube((0, 0.15, 1.0), (0, 0.3, 1.6), 0.09, "charcoal")
    body.tube((-1.1, 0.3, 1.65), (1.1, 0.3, 1.65), 0.07, "charcoal")
    for sx in (-1, 1):
        body.cyl(0.11, 0.45, (sx * 1.0, 0.3, 1.65), "rubber", rot=(0, 90, 0), segments=12)
    body.tube((0, -0.85, 0.85), (0, -0.95, 1.25), 0.08, "chrome")
    body.box((0.6, 1.1, 0.26), (0, -0.95, 1.38), "black", bevel=0.12)
    body.cyl(0.38, 0.3, (0, -0.5, -1.0), "charcoal", rot=(0, 90, 0))
    for sx in (-1, 1):
        body.box((0.45, 0.25, 0.08), (sx * 0.55, -0.5 + 0.3 * sx, -1.3), "black", bevel=0.03)
    # Wooden box: planks with dark gaps.
    bx, by, bz = 0, 1.75, -0.3
    w, d, h = 2.8, 2.6, 1.6
    body.box((w, d, 0.2), (bx, by, bz - h / 2 + 0.1), "wood", bevel=0.04)
    for i in range(3):
        z = bz - h / 2 + 0.25 + i * 0.5
        for sx in (-1, 1):
            body.box((0.16, d, 0.44), (bx + sx * (w / 2 - 0.08), by, z + 0.22), "wood", bevel=0.05)
        for sy in (-1, 1):
            body.box((w, 0.16, 0.44), (bx, by + sy * (d / 2 - 0.08), z + 0.22), "wood", bevel=0.05)
    for sx in (-1, 1):
        for sy in (-1, 1):
            body.box((0.2, 0.2, h + 0.1), (bx + sx * (w / 2 - 0.05), by + sy * (d / 2 - 0.05), bz + 0.05), "darkbrown", bevel=0.05)
    body.cyl(0.2, 0.2, (0, by + d / 2 + 0.05, bz + 0.3), "headlight", rot=(90, 0, 0), bevel=0.04)
    body.box((0.35, 0.12, 0.15), (0, -2.95, 0.15), "taillight", bevel=0.04)
    paint.box((0.4, 1.4, 0.08), (0, ry, GROUND + rr * 2 + 0.12), bevel=0.03)
    objs = [paint.done(), body.done(), _wheel("FrontWheel", rf, 0.3, fy), _wheel("RearWheel", rr, 0.36, ry)]
    meta = _meta(
        seat=(0, -0.95, 1.55),
        anchor=[(-0.6, 1.75, -0.2), (0.6, 1.75, -0.2)],
        wheels={"FrontWheel": (front_hub, rf), "RearWheel": (rear_hub, rr)},
        rays=[(-0.9, 3.5, -0.6), (0.9, 3.5, -0.6), (-0.9, -2.1, -0.6), (0.9, -2.1, -0.6)],
        capacity=2,
        size_class=2,
        extra={"boxInnerSize": [2.48, 1.4, 2.28]},
    )
    return objs, meta


def van():
    """Cab-over delivery truck with an open, railed cargo bed so parcels can fly out."""
    paint, body = Mesh("Paint"), Mesh("Body")
    r = 1.15
    fy, ry = 3.9, -3.6
    hz = GROUND + r
    # Chassis and bed
    body.box((5.4, 12.6, 0.6), (0, -0.2, -0.25), "charcoal", bevel=0.1)
    paint.box((6.2, 7.4, 0.4), (0, -2.6, 0.25), bevel=0.12)  # bed floor
    for sx in (-1, 1):
        paint.box((0.25, 7.4, 1.3), (sx * 2.98, -2.6, 1.05), bevel=0.08)  # bed sides
        for y in (-5.9, -4.3, -2.6, -0.9):
            body.box((0.3, 0.3, 2.2), (sx * 2.98, y, 1.5), "steel", bevel=0.08)  # rail posts
        body.tube((sx * 2.98, -6.2, 2.6), (sx * 2.98, 1.0, 2.6), 0.12, "steel")
    paint.box((6.2, 0.25, 1.3), (0, -6.18, 1.05), bevel=0.08)  # tailgate
    body.box((6.4, 0.5, 0.5), (0, -6.45, -0.25), "charcoal", bevel=0.15)  # rear bumper
    for sx in (-1, 1):
        body.box((0.7, 0.12, 0.4), (sx * 2.5, -6.32, 0.9), "taillight", bevel=0.06)
    # Cab
    paint.box((6.2, 4.6, 3.4), (0, 3.65, 1.75), bevel=0.5, segments=3)
    paint.box((6.0, 4.2, 0.4), (0, 3.6, 3.6), bevel=0.2)  # roof
    body.box((5.4, 0.2, 1.7), (0, 5.95, 2.25), "glass", rot=(-8, 0, 0), bevel=0.06)  # windscreen
    for sx in (-1, 1):
        body.box((0.15, 2.2, 1.4), (sx * 3.1, 4.3, 2.35), "glass", bevel=0.05)  # side windows
        body.box((0.12, 0.6, 0.12), (sx * 3.12, 2.6, 1.35), "chrome", bevel=0.04)  # door handles
        body.tube((sx * 3.1, 5.4, 2.6), (sx * 3.6, 5.6, 2.6), 0.05, "charcoal")
        body.box((0.15, 0.5, 0.8), (sx * 3.65, 5.6, 2.4), "charcoal", bevel=0.06)  # mirrors
        body.cyl(0.42, 0.15, (sx * 2.2, 5.98, 0.85), "chrome", rot=(90, 0, 0))
        body.cyl(0.34, 0.17, (sx * 2.2, 6.0, 0.85), "headlight", rot=(90, 0, 0))
        body.box((0.5, 0.12, 0.25), (sx * 2.55, 5.98, 1.45), "orange", bevel=0.05)  # indicators
    body.box((3.0, 0.15, 0.9), (0, 5.98, 0.8), "charcoal", bevel=0.06)  # grille
    for i in range(4):
        body.box((2.8, 0.18, 0.08), (0, 6.0, 0.48 + i * 0.22), "steel", bevel=0.02)
    body.box((6.4, 0.6, 0.55), (0, 6.15, -0.1), "charcoal", bevel=0.18)  # front bumper
    body.box((1.6, 0.1, 0.45), (0, 6.47, -0.1), "white", bevel=0.04)  # plate
    body.box((3.5, 0.9, 0.5), (0, 3.4, 3.95), "orange", bevel=0.15)  # roof beacon bar
    # Wheel arches
    for y in (fy, ry):
        for sx in (-1, 1):
            body.box((0.4, 2.8, 0.35), (sx * 3.0, y, hz + r + 0.25), "black", bevel=0.1)
    wheels, objs = {}, []
    for name, y in (("FrontLeft", fy), ("FrontRight", fy), ("RearLeft", ry), ("RearRight", ry)):
        x = -2.55 if "Left" in name else 2.55
        objs.append(_wheel(name, r, 0.9, y, x=x))
        wheels[name] = ((x, y, hz), r)
    objs = [paint.done(), body.done()] + objs
    meta = _meta(
        seat=(-1.4, 3.6, 1.2),
        anchor=[(-1.5, -1.3, 1.4), (1.5, -1.3, 1.4), (-1.5, -4.2, 1.4), (1.5, -4.2, 1.4)],
        wheels=wheels,
        rays=[(-2.5, 3.9, -0.6), (2.5, 3.9, -0.6), (-2.5, -3.6, -0.6), (2.5, -3.6, -0.6)],
        capacity=4,
        size_class=3,
        extra={"boxInnerSize": [5.7, 2.5, 7.2]},
    )
    return objs, meta


ASSETS = {
    "Vehicle_Scooter": scooter,
    "Vehicle_EBike": ebike,
    "Vehicle_CargoBike": cargobike,
    "Vehicle_Van": van,
    "Vehicle_RocketScooter": lambda: scooter(rocket=True),
}
