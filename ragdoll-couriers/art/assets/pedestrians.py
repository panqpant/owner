"""Pedestrians: chunky blocky locals in the courier's style. Each is six MeshParts (Torso, Head, LArm,
RArm, LLeg, RLeg) so the game can swing the limbs while they walk and ragdoll them when a rider clips
them. Arms and legs hang from the top of their box and the head sits on the bottom of its box: the game
finds each joint from the part's bounds. Feet at z = 0, facing +Y, colours baked in (eight outfits)."""

from lib import Mesh

# shirt, trousers, shoes, skin, hair colour, hair style, extras, scale
PEOPLE = {
    "Ped_Shopper": ("pink", "navy", "white", "skin", "darkbrown", "long", ("bags",), 1.0),
    "Ped_Business": ("white", "charcoal", "black", "tan", "black", "short", ("tie", "briefcase"), 1.0),
    "Ped_Elder": ("tan", "brown", "darkbrown", "skin", "lightgrey", "flatcap", ("cane",), 0.95),
    "Ped_Kid": ("yellow", "blue", "red", "brown", "black", "short", ("backpack",), 0.72),
    "Ped_Jogger": ("lime", "charcoal", "white", "brown", "darkbrown", "headband", ("shorts",), 1.0),
    "Ped_Tourist": ("skyblue", "tan", "brown", "skin", "orange", "sunhat", ("camera", "shorts"), 1.0),
    "Ped_Worker": ("neonorange", "navy", "darkbrown", "tan", "brown", "hardhat", ("hivis",), 1.05),
    "Ped_Student": ("purple", "blue", "white", "skin", "brown", "short", ("headphones", "backpack"), 0.95),
}


def person(shirt, trousers, shoes, skin, hair, style, extras, s):
    def S(v):
        return tuple(x * s for x in v)

    def box(m, size, loc, colour, bevel=0.12):
        # body blocks stay over lib's 0.1 chamfer cut-off at any scale (the kid too): on people that size,
        # chamfer corners catch the light as little dark triangles
        m.box(S(size), S(loc), colour, bevel=max(bevel * s, 0.11) if bevel >= 0.12 else bevel * s)

    legs_colour = trousers
    torso, head = Mesh("Torso"), Mesh("Head")
    larm, rarm, lleg, rleg = Mesh("LArm"), Mesh("RArm"), Mesh("LLeg"), Mesh("RLeg")

    # legs: 1 x 1 x 2 from the hips (z 2) down; shorts show skin below the knee
    for m, x in ((lleg, -0.5), (rleg, 0.5)):
        if "shorts" in extras:
            box(m, (0.98, 0.98, 0.9), (x, 0, 1.55), legs_colour)
            box(m, (0.86, 0.86, 1.0), (x, 0, 0.6), skin)
        else:
            box(m, (0.98, 0.98, 1.85), (x, 0, 1.08), legs_colour)
        box(m, (1.0, 1.2, 0.35), (x, 0.1, 0.18), shoes)

    # torso: 2 x 1 x 2 from the hips (z 2) up
    box(torso, (2, 1, 2), (0, 0, 3), shirt, bevel=0.15)
    if "tie" in extras:
        box(torso, (0.3, 0.06, 1.3), (0, 0.52, 3.3), "red", bevel=0.02)
    if "hivis" in extras:
        for z in (2.7, 3.5):
            box(torso, (2.04, 1.04, 0.22), (0, 0, z), "lightgrey", bevel=0.02)
    if "backpack" in extras:
        box(torso, (1.5, 0.7, 1.5), (0, -0.85, 3.1), "red" if shirt != "red" else "navy", bevel=0.2)
    if "camera" in extras:
        box(torso, (0.7, 0.4, 0.5), (0.2, 0.7, 3.4), "black", bevel=0.05)
        torso.cyl(0.18, 0.3, S((0.2, 0.95, 3.4)), "glass", rot=(90, 0, 0), segments=10, bevel=0)

    # arms: 1 x 1 x 2 from the shoulders (z 4) down, sleeve then hand
    for m, x in ((larm, -1.5), (rarm, 1.5)):
        box(m, (0.96, 0.96, 1.35), (x, 0, 3.32), shirt)
        box(m, (0.86, 0.86, 0.62), (x, 0, 2.32), skin)
    if "briefcase" in extras:
        box(rarm, (0.3, 1.3, 0.95), (1.5, 0, 1.55), "darkbrown", bevel=0.06)
    if "bags" in extras:
        for m, x, c in ((larm, -1.5, "white"), (rarm, 1.5, "orange")):
            box(m, (0.4, 1.0, 1.1), (x, 0, 1.45), c, bevel=0.06)
    if "cane" in extras:
        rarm.cyl(0.1 * s, 2.0 * s, S((1.5, 0.35, 1.05)), "darkbrown", segments=6, bevel=0)

    # head: 1.2 cube on the neck (z 4), face to +Y
    box(head, (1.2, 1.15, 1.15), (0, 0, 4.6), skin, bevel=0.25)
    for sx in (-1, 1):
        head.sphere(0.1 * s, S((sx * 0.25, 0.58, 4.72)), "black", segments=6, rings=4)
    box(head, (0.4, 0.05, 0.09), (0, 0.58, 4.38), "darkbrown", bevel=0.02)
    if style in ("short", "long", "headband"):
        box(head, (1.28, 1.24, 0.35), (0, -0.02, 5.18), hair, bevel=0.12)
        box(head, (1.28, 0.35, 0.95), (0, -0.46, 4.85), hair, bevel=0.1)
    if style == "long":
        box(head, (1.3, 0.4, 1.0), (0, -0.48, 4.55), hair, bevel=0.12)  # stops at the neck: the head joint is the bottom of its bounds
    if style == "headband":
        box(head, (1.26, 1.2, 0.2), (0, 0, 4.98), "red", bevel=0.05)
    if "headphones" in extras:
        for sx in (-1, 1):
            box(head, (0.2, 0.45, 0.45), (sx * 0.72, 0, 4.7), "charcoal", bevel=0.08)
        box(head, (1.45, 0.15, 0.15), (0, 0, 5.4), "charcoal", bevel=0.03)
    if style == "flatcap":
        box(head, (1.3, 1.3, 0.15), (0, -0.25, 4.98), hair, bevel=0.05)  # grey sides peek out
        box(head, (1.3, 1.35, 0.35), (0, 0, 5.3), "brown", bevel=0.12)
        box(head, (1.0, 0.45, 0.1), (0, 0.8, 5.17), "brown", bevel=0.04)
    if style == "sunhat":
        head.cyl(1.05 * s, 0.1 * s, S((0, 0, 5.2)), "tan", segments=14, bevel=0)
        head.cyl(0.62 * s, 0.45 * s, S((0, 0, 5.45)), "tan", segments=14, bevel=0.05)
    if style == "hardhat":
        head.cyl(0.72 * s, 0.45 * s, S((0, 0, 5.35)), "yellow", segments=14, r2=0.6 * s, bevel=0.08)
        box(head, (1.0, 0.5, 0.08), (0, 0.65, 5.15), "yellow", bevel=0.03)

    objs = [m.done() for m in (torso, head, larm, rarm, lleg, rleg)]
    return objs, {"kind": "pedestrian", "note": "limbs swing from the top of their bounds; head from the bottom"}


ASSETS = {name: (lambda spec=spec: person(*spec)) for name, spec in PEOPLE.items()}
