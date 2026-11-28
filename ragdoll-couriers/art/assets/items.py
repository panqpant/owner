"""Batch 9: small models for the store and UI icons, plus the banana peel the troll product drops in-game.
Same conventions as world.py: base at z = 0, front faces +Y."""

import math

from lib import Mesh


def _one(m: Mesh, kind: str, **meta):
    return [m.done()], {"kind": kind, **meta}


def banana_peel():
    """Troll product: dropped behind you, ragdolls the next rider. About 2 studs across."""
    m = Mesh("BananaPeel")
    m.sphere(0.45, (0, 0, 0.25), "yellow", scale=(1.3, 1.0, 0.55), segments=12, rings=8)
    for k in range(4):  # floppy peel arms splayed out
        a = k * math.pi / 2 + 0.4
        m.sphere(0.35, (math.cos(a) * 0.85, math.sin(a) * 0.85, 0.12), "yellow", scale=(2.0, 0.7, 0.3), rot=(0, 0, math.degrees(a)), segments=10, rings=6)
        m.sphere(0.12, (math.cos(a) * 1.45, math.sin(a) * 1.45, 0.12), "darkbrown", segments=6, rings=4)  # brown tips
    m.cyl(0.12, 0.4, (0, 0, 0.6), "darkbrown", segments=6, r2=0.08, bevel=0)  # stalk
    return _one(m, "item", note="ragdolls the next rider to touch it")


def coin_pile(count=9):
    m = Mesh("Coins")
    rows = [(0, 0)] + [(math.cos(k * 1.26) * 1.3, math.sin(k * 1.26) * 1.3) for k in range(5)] + [(math.cos(k * 1.05 + 0.3) * 2.5, math.sin(k * 1.05 + 0.3) * 2.5) for k in range(6)]
    for k in range(min(count, len(rows))):
        x, y = rows[k]
        stack = 1 + (count - k) // 4
        for s in range(stack):
            z = 0.13 + s * 0.27 + k * 0.035  # each coin a hair higher than the last: overlapping faces never share a height
            m.cyl(1.0, 0.25, (x, y, z), "gold", segments=20, bevel=0.06)
            m.cyl(0.7, 0.27, (x, y, z), "yellow", segments=20, bevel=0)
    return _one(m, "icon")


def mystery_crate():
    m = Mesh("Crate")
    s = 4
    m.box((s, s, s), (0, 0, s / 2), "purple", bevel=0.25)
    for z in (0.35, s - 0.35):  # gold bands
        m.box((s + 0.1, s + 0.1, 0.5), (0, 0, z), "gold", bevel=0.1)
    for x in (-s / 2 + 0.35, s / 2 - 0.35):
        for y in (-s / 2 + 0.35, s / 2 - 0.35):
            m.box((0.5, 0.5, s + 0.1), (x, y, s / 2), "gold", bevel=0.1)
    # question mark on the front: a smooth hook, a stem and a dot
    hook = [(math.cos(a) * 0.7, s / 2 + 0.12, 2.8 + math.sin(a) * 0.7) for a in (math.pi * 1.05 - k * math.pi * 1.55 / 16 for k in range(17))]
    m.sweep(hook + [(0, s / 2 + 0.12, 1.55)], 0.22, "white", segments=10)
    m.sphere(0.3, (0, s / 2 + 0.12, 0.95), "white", segments=12, rings=8)
    return _one(m, "icon")


def starter_pack():
    m = Mesh("StarterPack")
    m.box((4, 3, 2.6), (0, 0, 1.3), "orange", bevel=0.2)
    m.box((4.2, 3.2, 0.6), (0, 0, 2.7), "orange", bevel=0.2)
    m.box((0.6, 3.25, 3.1), (0, 0, 1.55), "white", bevel=0.05)
    for sx in (-1, 1):
        m.sphere(0.6, (sx * 0.6, 0, 3.4), "white", scale=(1.4, 0.5, 0.9), rot=(0, sx * 25, 0), segments=10, rings=6)
    for k in range(5):  # coins spilling out
        m.cyl(0.6, 0.2, (-2.6 + k * 0.4, 1.8 - k * 0.2, 0.1 + k * 0.12), "gold", rot=(0, 20 - k * 8, 0), segments=16, bevel=0.04)
    return _one(m, "icon")


def spring():
    m = Mesh("Spring")
    turns, r = 6, 1.0
    step = 0.12  # fine enough that the coil reads as one wire
    pts = [(math.cos(t) * r, math.sin(t) * r, 0.4 + t / (2 * math.pi) * 0.65) for t in (k * step for k in range(int(turns * 2 * math.pi / step) + 1))]
    m.sweep(pts, 0.16, "chrome", segments=8)
    m.cyl(1.3, 0.4, (0, 0, 0.2), "charcoal", segments=20, bevel=0.1)
    m.cyl(1.3, 0.4, (0, 0, pts[-1][2] + 0.25), "charcoal", segments=20, bevel=0.1)
    return _one(m, "icon")


def bubble_wrap():
    m = Mesh("BubbleWrap")
    m.box((5, 3.6, 0.1), (0, 0, 0.6), "glass", rot=(-12, 0, 0), bevel=0)
    for i in range(7):
        for j in range(5):
            x, y = -2.1 + i * 0.7 + (0.35 if j % 2 else 0), -1.4 + j * 0.7
            m.sphere(0.28, (x, y * math.cos(math.radians(12)), 0.65 + y * math.sin(math.radians(12))), "skyblue", scale=(1, 1, 0.7), segments=10, rings=6)
    return _one(m, "icon")


def engine():
    m = Mesh("Engine")
    m.box((3, 2.2, 1.8), (0, 0, 1.2), "charcoal", bevel=0.2)
    for x in (-0.9, 0, 0.9):  # cylinders
        m.cyl(0.45, 1.2, (x, 0, 2.6), "steel", segments=12, bevel=0.08)
        m.cyl(0.55, 0.25, (x, 0, 3.3), "chrome", segments=12, bevel=0.05)
    m.cyl(0.8, 0.5, (1.8, 0, 1.2), "red", rot=(0, 90, 0), segments=16, bevel=0.1)  # pulley
    m.tube((-1.5, 0.8, 1.8), (-2.4, 1.6, 2.6), 0.18, "chrome", segments=8)  # exhaust
    return _one(m, "icon")


def brake_disc():
    m = Mesh("Brake")
    m.cyl(2, 0.3, (0, 0, 2.2), "steel", rot=(90, 0, 0), segments=32, bevel=0.05)
    m.cyl(0.8, 0.4, (0, 0, 2.2), "charcoal", rot=(90, 0, 0), segments=20, bevel=0.05)
    for k in range(8):
        a = k / 8 * math.tau
        m.cyl(0.15, 0.4, (math.cos(a) * 1.4, 0, 2.2 + math.sin(a) * 1.4), "charcoal", rot=(90, 0, 0), segments=8, bevel=0)
    m.box((1.0, 1.0, 1.6), (1.7, 0, 3.0), "red", rot=(0, -35, 0), bevel=0.2)  # caliper
    return _one(m, "icon")


def crown():
    m = Mesh("Crown")
    m.cyl(1.6, 1.0, (0, 0, 0.5), "gold", segments=24, bevel=0.1)
    for k in range(5):
        a = k / 5 * math.tau
        m.cyl(0.45, 1.6, (math.cos(a) * 1.35, math.sin(a) * 1.35, 1.6), "gold", segments=4, r2=0.05, bevel=0)
        m.sphere(0.25, (math.cos(a) * 1.35, math.sin(a) * 1.35, 2.45), "red" if k % 2 else "blue", segments=8, rings=5)
    return _one(m, "icon")


def shield():
    m = Mesh("Shield")
    outline = [(0, 2.4), (1.8, 1.8), (1.7, -0.4), (0, -2.2), (-1.7, -0.4), (-1.8, 1.8)]
    m.prism([(x, 0.3 * 0 + y) for x, y in outline], 0.5, "green", thickness=0.5)
    m.prism([(x * 0.8, y * 0.8 + 0.1) for x, y in outline], 0.6, "white", thickness=0.1)
    m.box((0.9, 0.9, 0.9), (0, 0.3, 1.1), "cardboard", rot=(0, 0, 45), bevel=0.1)  # parcel on the shield
    objs, meta = _one(m, "icon")
    objs[0].rotation_euler = (math.radians(-70), 0, 0)  # stand the shield up, face toward the front (+Y)
    return objs, meta


def hourglass():
    m = Mesh("Hourglass")
    for z in (0.15, 4.15):
        m.cyl(1.4, 0.3, (0, 0, z), "wood", segments=20, bevel=0.08)
    for k in range(3):
        a = k / 3 * math.tau
        m.tube((math.cos(a) * 1.2, math.sin(a) * 1.2, 0.3), (math.cos(a) * 1.2, math.sin(a) * 1.2, 4.0), 0.1, "wood", segments=6)
    m.lathe([(0.05, 0.3), (0.9, 0.5), (0.9, 1.0), (0.12, 2.15), (0.9, 3.3), (0.9, 3.8), (0.05, 4.0)], colour="glass", segments=20)
    m.lathe([(0.0, 0.32), (0.85, 0.5), (0.8, 0.95), (0.0, 1.3)], colour="gold", segments=20)  # sand
    return _one(m, "icon")


def route_pin():
    m = Mesh("Pin")
    m.sphere(1.2, (0, 0, 3.2), "red", segments=20, rings=12)
    m.cyl(1.0, 2.2, (0, 0, 1.6), "red", segments=20, r2=0.05, rot=(180, 0, 0), bevel=0)
    m.sphere(0.45, (0, 0, 3.3), "white", segments=12, rings=8)
    m.cyl(1.6, 0.1, (0, 0, 0.05), "neongreen", segments=24, bevel=0)  # glowing route line ring
    return _one(m, "icon")


ASSETS = {
    "Item_BananaPeel": banana_peel,
    "Item_CoinsSmall": lambda: coin_pile(3),
    "Item_CoinsMedium": lambda: coin_pile(6),
    "Item_CoinsLarge": lambda: coin_pile(9),
    "Item_CoinsHuge": lambda: coin_pile(12),
    "Item_Crate": mystery_crate,
    "Item_StarterPack": starter_pack,
    "Item_Spring": spring,
    "Item_BubbleWrap": bubble_wrap,
    "Item_Engine": engine,
    "Item_Brake": brake_disc,
    "Item_Crown": crown,
    "Item_Shield": shield,
    "Item_Hourglass": hourglass,
    "Item_RoutePin": route_pin,
}
