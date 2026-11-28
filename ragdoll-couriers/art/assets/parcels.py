"""Parcels: one MeshPart each, centred on the origin, sized in studs.
Tiers follow the plan: easy, fragile, chaotic, co-op, legendary, event."""

import math

from lib import Mesh


def _one(m: Mesh, tier: str):
    return [m.done()], {"tier": tier}


def pillow():
    m = Mesh("Parcel")
    m.box((2.2, 1.6, 0.9), (0, 0, 0), "white", bevel=0.42, segments=5)  # puffy rounded slab
    m.box((2.24, 0.06, 0.12), (0, 0, 0), "skyblue", bevel=0.02)  # piping
    return _one(m, "easy")


def teddy():
    m = Mesh("Parcel")
    m.sphere(0.6, (0, 0, -0.35), "brown", scale=(1, 0.9, 1.05))
    m.sphere(0.32, (0, 0.42, -0.35), "tan", scale=(1, 0.5, 1.1))  # belly
    m.sphere(0.48, (0, 0.05, 0.55), "brown")
    m.sphere(0.22, (0, 0.42, 0.45), "tan", scale=(1, 0.8, 0.8))  # muzzle
    m.sphere(0.07, (0, 0.6, 0.5), "black", segments=8, rings=6)
    for sx in (-1, 1):
        m.sphere(0.17, (sx * 0.38, 0.0, 0.95), "brown", scale=(1, 0.6, 1))  # ears
        m.sphere(0.07, (sx * 0.17, 0.42, 0.68), "black", segments=8, rings=6)  # eyes
        m.sphere(0.22, (sx * 0.62, 0.15, -0.15), "brown", scale=(0.9, 0.9, 1.5), rot=(0, sx * 25, 0))  # arms
        m.sphere(0.25, (sx * 0.35, 0.3, -0.85), "brown", scale=(1, 1.4, 0.8))  # legs
    return _one(m, "easy")


def post():
    m = Mesh("Parcel")
    m.box((1.8, 1.4, 1.2), (0, 0, 0), "cardboard", bevel=0.06)
    m.box((1.84, 0.34, 1.24), (0, 0, 0), "tape", bevel=0.02)
    m.box((0.34, 1.44, 1.26), (0, 0, 0), "tape", bevel=0.02)
    m.box((0.7, 0.04, 0.45), (0.45, 0.71, 0.15), "white", bevel=0.02)  # address label
    for i in range(3):
        m.box((0.5, 0.02, 0.04), (0.45, 0.735, 0.27 - i * 0.1), "charcoal", bevel=0)
    m.box((0.3, 0.02, 0.3), (-0.55, 0.71, -0.25), "red", bevel=0.02)  # "fragile" sticker
    return _one(m, "easy")


def tv():
    m = Mesh("Parcel")
    m.box((2.6, 0.22, 1.5), (0, 0, 0.12), "black", bevel=0.06)
    m.box((2.4, 0.05, 1.3), (0, 0.11, 0.12), "screen", bevel=0.01)
    m.box((0.8, 0.02, 0.4), (-0.55, 0.14, 0.4), "neonblue", bevel=0.01)  # a bit of on-screen glare
    m.cyl(0.08, 0.4, (0, -0.02, -0.75), "charcoal", segments=12)
    m.box((1.1, 0.6, 0.08), (0, -0.02, -0.92), "charcoal", bevel=0.04)
    m.sphere(0.04, (1.15, 0.12, -0.55), "neongreen", segments=6, rings=4)
    return _one(m, "fragile")


def vase():
    m = Mesh("Parcel")
    prof = [(0, -1.1), (0.45, -1.1), (0.55, -0.9), (0.62, -0.4), (0.58, 0.1), (0.4, 0.55), (0.28, 0.8), (0.32, 1.0), (0.38, 1.1), (0.32, 1.1), (0.24, 0.85), (0, 0.85)]
    m.lathe(prof, (0, 0, 0), "blue", segments=28)
    for z in (-0.5, 0.2):
        m.lathe([(0, z - 0.06), (0.63 if z < 0 else 0.53, z - 0.06), (0.63 if z < 0 else 0.53, z + 0.06), (0, z + 0.06)], (0, 0, 0), "white", segments=28)  # glazed bands
    return _one(m, "fragile")


def laptop():
    m = Mesh("Parcel")
    m.box((1.8, 1.25, 0.1), (0, 0, -0.5), "steel", bevel=0.04)
    m.box((1.5, 0.6, 0.02), (0, 0.15, -0.44), "charcoal", bevel=0.01)  # keyboard
    m.box((0.5, 0.32, 0.02), (0, -0.38, -0.44), "grey", bevel=0.01)  # trackpad
    m.box((1.8, 0.08, 1.15), (0, -0.85, 0.05), "steel", rot=(-20, 0, 0), bevel=0.04)
    m.box((1.6, 0.02, 0.95), (0, -0.8, 0.07), "screen", rot=(-20, 0, 0), bevel=0.01)
    m.box((0.3, 0.02, 0.2), (0, -0.78, 0.1), "neonblue", rot=(-20, 0, 0), bevel=0.01)
    return _one(m, "fragile")


def fishtank():
    m = Mesh("Parcel")
    w, d, h = 2.4, 1.4, 1.6
    for sx in (-1, 1):
        for sy in (-1, 1):
            m.box((0.12, 0.12, h), (sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), 0), "black", bevel=0.03)
    for z in (-h / 2 + 0.06, h / 2 - 0.06):
        m.box((w, d, 0.12), (0, 0, z), "black", bevel=0.03)
    m.box((w - 0.16, d - 0.16, h * 0.75), (0, 0, -0.12), "water", bevel=0.02)
    m.box((w - 0.18, d - 0.18, 0.18), (0, 0, -h / 2 + 0.2), "sand", bevel=0.03)  # gravel
    for i, (x, y, c) in enumerate(((-0.5, 0.1, "orange"), (0.4, -0.2, "yellow"), (0.1, 0.25, "orange"))):
        z = -0.2 + i * 0.2
        m.sphere(0.16, (x, y, z), c, scale=(1.4, 0.6, 0.9), segments=10, rings=6)
        m.cyl(0.12, 0.05, (x - 0.24, y, z), c, rot=(0, 90, 0), r2=0.01, segments=6, bevel=0)  # tail
    for x in (-0.85, 0.8):
        for k in range(3):
            m.sphere(0.1, (x + k * 0.05, 0.3, -0.45 + k * 0.2), "green", scale=(0.6, 0.6, 1.8), segments=8, rings=5)  # weed
    m.box((0.3, 0.3, 0.3), (0.9, -0.35, -0.5), "stone", rot=(0, 0, 20), bevel=0.1)
    return _one(m, "chaotic")


def cake():
    m = Mesh("Parcel")
    tiers = ((0.95, -0.7, 0.55, "icing"), (0.7, -0.15, 0.5, "pink"), (0.48, 0.35, 0.45, "icing"))
    for r, z, h, c in tiers:
        m.cyl(r, h, (0, 0, z), c, segments=32, bevel=0.06)
        for k in range(10):
            a = k / 10 * math.tau
            m.sphere(0.09, (math.cos(a) * r, math.sin(a) * r, z + h / 2 - 0.05), "icing" if c == "pink" else "pink", scale=(1, 1, 1.6), segments=8, rings=5)
    m.cyl(1.15, 0.08, (0, 0, -1.0), "white", segments=32, bevel=0.03)  # board
    m.cyl(0.05, 0.4, (0, 0, 0.78), "skyblue", segments=8, bevel=0)
    m.sphere(0.07, (0, 0, 1.03), "neonorange", scale=(1, 1, 1.6), segments=8, rings=5)  # flame
    for k in range(5):
        a = k / 5 * math.tau
        m.sphere(0.08, (math.cos(a) * 0.3, math.sin(a) * 0.3, 0.6), "red", segments=8, rings=5)  # cherries
    return _one(m, "chaotic")


def piano():
    m = Mesh("Parcel")
    m.box((3.6, 1.2, 2.6), (0, -0.2, 0.1), "black", bevel=0.08)
    m.box((3.7, 1.3, 0.12), (0, -0.2, 1.42), "black", bevel=0.05)  # lid
    m.box((3.3, 0.6, 0.25), (0, 0.6, -0.15), "black", bevel=0.05)  # key bed
    m.box((3.1, 0.45, 0.06), (0, 0.66, 0.0), "white", bevel=0.01)
    for i in range(21):
        if i % 7 in (2, 6):
            continue
        m.box((0.07, 0.25, 0.08), (-1.45 + i * 0.145, 0.56, 0.06), "black", bevel=0)
    for sx in (-1, 1):
        m.box((0.2, 0.25, 1.3), (sx * 1.6, 0.75, -0.6), "black", bevel=0.05)  # legs
        m.box((0.3, 0.12, 0.3), (sx * 0.3, 0.6, -1.0), "gold", rot=(30, 0, 0), bevel=0.04)  # pedals
    m.box((1.4, 0.06, 0.7), (0, 0.42, 0.75), "cream", rot=(-12, 0, 0), bevel=0.02)  # sheet music
    return _one(m, "chaotic")


def sofa():
    m = Mesh("Parcel")
    m.box((4.2, 1.8, 0.6), (0, 0, -0.55), "coral", bevel=0.18)
    for x in (-1.0, 1.0):
        m.box((1.95, 1.4, 0.4), (x, 0.15, -0.08), "coral", bevel=0.17)  # seat cushions
    m.box((4.2, 0.5, 1.4), (0, -0.65, 0.2), "coral", bevel=0.2)  # back
    for sx in (-1, 1):
        m.box((0.45, 1.8, 0.95), (sx * 1.9, 0, -0.1), "coral", bevel=0.2)  # arms
        for sy in (-1, 1):
            m.cyl(0.08, 0.3, (sx * 1.8, sy * 0.7, -0.95), "darkbrown", segments=8, bevel=0.02)
    m.box((0.8, 0.3, 0.7), (-1.2, -0.3, 0.3), "yellow", rot=(-15, 0, 10), bevel=0.15)  # throw cushion
    return _one(m, "coop")


def fridge():
    m = Mesh("Parcel")
    m.box((1.8, 1.8, 3.6), (0, 0, 0), "white", bevel=0.18)
    m.box((1.84, 0.05, 0.06), (0, 0.9, 0.55), "lightgrey", bevel=0)  # door gap
    for z, hgt in ((1.2, 0.6), (-0.3, 1.2)):
        m.box((0.1, 0.12, hgt), (0.7, 0.95, z), "chrome", bevel=0.04)  # handles
    for x, z, c in ((-0.4, 1.3, "red"), (-0.1, 1.1, "yellow"), (-0.5, 0.0, "blue"), (0.1, -0.3, "green")):
        m.box((0.22, 0.05, 0.22), (x, 0.92, z), c, bevel=0.04)  # magnets
    m.box((0.5, 0.03, 0.6), (-0.3, 0.92, -0.55), "white", rot=(0, 5, 0), bevel=0.01)  # drawing
    return _one(m, "coop")


def hottub():
    m = Mesh("Parcel")
    w, h = 4.0, 1.6
    for sx in (-1, 1):
        m.box((0.4, w, h), (sx * (w / 2 - 0.2), 0, 0), "wood", bevel=0.08)
        m.box((w, 0.4, h), (0, sx * (w / 2 - 0.2), 0), "wood", bevel=0.08)
        for k in range(-3, 4):  # plank grooves
            m.box((0.04, 0.06, h * 0.96), (sx * (w / 2 + 0.005), k * 0.5, 0), "darkbrown", bevel=0)
            m.box((0.06, 0.04, h * 0.96), (k * 0.5, sx * (w / 2 + 0.005), 0), "darkbrown", bevel=0)
    for sx in (-1, 1):
        m.box((0.5, w + 0.1, 0.12), (sx * (w / 2 - 0.2), 0, h / 2), "darkbrown", bevel=0.05)
        m.box((w + 0.1, 0.5, 0.12), (0, sx * (w / 2 - 0.2), h / 2), "darkbrown", bevel=0.05)
    m.box((w - 0.7, w - 0.7, 0.2), (0, 0, -h / 2 + 0.1), "white", bevel=0.05)
    m.box((w - 0.75, w - 0.75, 0.9), (0, 0, -0.1), "water", bevel=0.03)
    m.sphere(0.35, (0.8, 0.8, 0.4), "yellow", scale=(1.1, 1, 0.9))  # rubber duck
    m.sphere(0.2, (0.95, 0.95, 0.75), "yellow")
    m.cyl(0.1, 0.2, (1.05, 1.08, 0.72), "orange", rot=(-60, 0, 45), r2=0.02, segments=8, bevel=0)
    return _one(m, "coop")


def goldstatue():
    m = Mesh("Parcel")
    m.box((1.2, 1.2, 0.5), (0, 0, -1.05), "darkbrown", bevel=0.08)
    m.box((1.0, 1.0, 0.15), (0, 0, -0.73), "gold", bevel=0.04)
    m.sphere(0.32, (0, 0, -0.35), "gold", scale=(1, 0.8, 1.2))  # hips
    m.sphere(0.42, (0, 0, 0.2), "gold", scale=(1, 0.75, 1.1))  # chest
    m.sphere(0.3, (0, 0, 0.82), "gold")  # head
    for sx in (-1, 1):
        m.tube((sx * 0.2, 0, -0.45), (sx * 0.22, 0, -0.75), 0.13, "gold")  # legs
        m.tube((sx * 0.4, 0, 0.4), (sx * 0.55, 0, 1.15), 0.1, "gold")  # arms up: victory pose
        m.sphere(0.13, (sx * 0.56, 0, 1.2), "gold")
    m.box((0.6, 0.05, 0.18), (0, 0.62, -1.05), "gold", bevel=0.02)  # plaque
    return _one(m, "legendary")


def alienegg():
    m = Mesh("Parcel")
    m.lathe([(0, -0.8), (0.4, -0.75), (0.6, -0.45), (0.62, 0.0), (0.52, 0.4), (0.3, 0.7), (0, 0.8)], (0, 0, 0.1), "alien", segments=28)
    for k in range(9):
        a = k * 2.4
        z = -0.5 + (k % 5) * 0.25
        rad = 0.6 if abs(z) < 0.4 else 0.45
        m.sphere(0.1, (math.cos(a) * rad, math.sin(a) * rad, z + 0.1), "purple", scale=(1, 1, 0.4), rot=(0, 90, math.degrees(a)), segments=10, rings=6)
    m.cyl(0.55, 0.2, (0, 0, -0.72), "charcoal", segments=24, r2=0.45, bevel=0.03)  # nest
    for k in range(6):
        a = k / 6 * math.tau
        m.box((0.08, 0.3, 0.12), (math.cos(a) * 0.5, math.sin(a) * 0.5, -0.6), "neongreen", rot=(0, 0, math.degrees(a)), bevel=0.02)
    return _one(m, "legendary")


def chicken():
    m = Mesh("Parcel")
    m.sphere(0.5, (0, -0.05, 0), "white", scale=(0.9, 1.25, 0.95))
    m.sphere(0.32, (0, 0.45, 0.48), "white")
    m.cyl(0.11, 0.25, (0, 0.78, 0.46), "orange", rot=(-90, 0, 0), r2=0.02, segments=8, bevel=0)  # beak
    m.sphere(0.08, (0, 0.68, 0.32), "comb", scale=(0.6, 0.6, 1.3), segments=8, rings=5)  # wattle
    for k in range(3):
        m.sphere(0.09, (0, 0.38 + k * 0.1, 0.78 - abs(k - 1) * 0.04), "comb", segments=8, rings=5)
    for sx in (-1, 1):
        m.sphere(0.05, (sx * 0.2, 0.65, 0.55), "black", segments=8, rings=5)
        m.sphere(0.3, (sx * 0.42, -0.05, 0.05), "white", scale=(0.4, 1.0, 0.75))  # wings
        m.tube((sx * 0.18, 0, -0.4), (sx * 0.2, 0.05, -0.65), 0.04, "orange")
        m.box((0.22, 0.3, 0.04), (sx * 0.2, 0.12, -0.66), "orange", bevel=0.01)
    for k in range(3):
        m.sphere(0.13, (0, -0.65, 0.25 + k * 0.12), "white", scale=(0.5, 0.8, 1.2), rot=(30, 0, 0), segments=10, rings=6)  # tail
    return _one(m, "legendary")


def pizza():
    m = Mesh("Parcel")
    for i in range(3):
        z = -0.24 + i * 0.25
        m.box((2.0, 2.0, 0.22), (0.03 * (i - 1), -0.03 * (i - 1), z), "white", rot=(0, 0, (i - 1) * 4), bevel=0.03)
    top = 0.26 + 0.11  # top face of the top box
    m.cyl(0.55, 0.02, (0.03, -0.03, top + 0.01), "red", segments=24, bevel=0)  # logo
    m.cyl(0.4, 0.02, (0.03, -0.03, top + 0.025), "pizza", segments=24, bevel=0)
    for k in range(5):
        a = k / 5 * math.tau
        m.cyl(0.08, 0.02, (0.03 + math.cos(a) * 0.22, -0.03 + math.sin(a) * 0.22, top + 0.04), "red", segments=10, bevel=0)  # pepperoni
    return _one(m, "event")


def present():
    m = Mesh("Parcel")
    m.box((1.6, 1.6, 1.4), (0, 0, -0.1), "red", bevel=0.05)
    m.box((1.7, 1.7, 0.3), (0, 0, 0.6), "red", bevel=0.06)  # lid
    m.box((0.3, 1.74, 1.66), (0, 0, 0.05), "gold", bevel=0.02)
    m.box((1.74, 0.3, 1.66), (0, 0, 0.05), "gold", bevel=0.02)
    for sx in (-1, 1):
        m.sphere(0.32, (sx * 0.3, 0, 0.92), "gold", scale=(1.3, 0.45, 0.8), rot=(0, sx * 20, 0))  # bow loops
    m.sphere(0.14, (0, 0, 0.85), "gold")
    return _one(m, "event")


def pumpkin():
    m = Mesh("Parcel")
    for k in range(8):
        a = k / 8 * math.tau
        m.sphere(0.6, (math.cos(a) * 0.35, math.sin(a) * 0.35, 0), "pumpkin", scale=(0.9, 0.9, 1.0), rot=(0, 0, math.degrees(a)), segments=18, rings=12)
    m.cyl(0.12, 0.45, (0.05, 0, 0.7), "darkgreen", rot=(0, 15, 0), segments=8, r2=0.08, bevel=0.03)
    m.sphere(0.25, (0.3, 0.2, 0.6), "green", scale=(1.2, 0.8, 0.2), rot=(0, 0, 30), segments=10, rings=5)  # leaf
    return _one(m, "event")


ASSETS = {
    "Parcel_Pillow": pillow,
    "Parcel_Teddy": teddy,
    "Parcel_Post": post,
    "Parcel_TV": tv,
    "Parcel_Vase": vase,
    "Parcel_Laptop": laptop,
    "Parcel_FishTank": fishtank,
    "Parcel_Cake": cake,
    "Parcel_Piano": piano,
    "Parcel_Sofa": sofa,
    "Parcel_Fridge": fridge,
    "Parcel_HotTub": hottub,
    "Parcel_GoldStatue": goldstatue,
    "Parcel_AlienEgg": alienegg,
    "Parcel_Chicken": chicken,
    "Parcel_Pizza": pizza,
    "Parcel_Present": present,
    "Parcel_Pumpkin": pumpkin,
}
