"""Fully modelled buildings and streets for a small area, built in Blender from the generated world
(no textures needed: windows, frames, sills, shutters, balconies, shopfronts, awnings, doors, garage doors,
porches, real hip / gable roofs with eaves, parapets, cornices, rooftop units, pools, driveways, sidewalks,
curbs, lane markings and street lights are all geometry). Each building is one object with a material per
surface, so it exports to Roblox as MeshParts (`--export` writes assets/roblox/buildings/<id>.fbx).

Run after `lune run tools/export-world.luau` and `lune run tools/export-terrain.luau`.
Usage (from costa-verde/): python tools/blender/detail_town.py [--export]"""
import json
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402
from render_terrain import build as build_terrain, lin  # noqa: E402
from render_world import camera, render, reset, sky  # noqa: E402
import realism  # noqa: E402

AREA = "oldtown"
W = json.load(open("build/world.json"))
T = json.load(open(f"build/terrain_{AREA}.json"))
X0, Z0, SPAN = T["x0"], T["z0"], T["nx"] * T["res"]
CX, CZ = X0 + SPAN / 2, Z0 + SPAN / 2
R = 380  # detailed zone half-size (studs); greybox beyond

# surface -> (roughness, metallic, fixed colour or None = per-face colour)
SURF = {
    "wall": (0.88, 0, None), "trim": (0.7, 0, (246, 244, 236)), "glass": (0.04, 0.6, (40, 58, 70)),
    "frame": (0.5, 0, None), "roof_tile": (0.75, 0, None), "roof_flat": (0.95, 0, (176, 172, 164)),
    "metal": (0.4, 0.7, (178, 180, 182)), "awning": (0.8, 0, None), "door": (0.6, 0, None), "concrete": (0.9, 0, (198, 194, 186)),
    "asphalt": (0.92, 0, (52, 52, 55)), "paint": (0.7, 0, None), "pool": (0.05, 0, (60, 170, 210)), "wood": (0.8, 0, (150, 118, 84)),
    "pole": (0.5, 0.6, (90, 92, 94)), "lamp": (0.3, 0, (255, 244, 214)), "solar": (0.08, 0.3, (22, 30, 52)), "neon": (0.3, 0, (255, 40, 50)), "shopglass": (0.02, 0, (30, 36, 40)), "mirror": (0.02, 1.0, (220, 224, 226)), "floor": (0.35, 0, None), "fabric": (0.85, 0, None),
}
PASTEL = [(242, 200, 168), (196, 226, 206), (246, 228, 160), (240, 170, 150), (180, 212, 230), (244, 236, 214), (236, 236, 230)]
HOUSE_COL = [(246, 240, 224), (236, 226, 200), (214, 222, 200), (206, 220, 230), (240, 214, 190), (250, 250, 246)]
SHUTTER = [(40, 110, 100), (60, 80, 130), (150, 90, 60), (90, 120, 70), (250, 250, 246)]
AWNING = [(180, 50, 50), (30, 110, 120), (40, 70, 140), (200, 150, 40), (60, 120, 70)]
TILE = [(186, 96, 64), (172, 112, 82), (160, 84, 58)]


def faded(c, k=0.38, dark=0.9):
    g = sum(c) / 3
    return tuple(int((v + (g - v) * k) * dark) for v in c)


PASTEL = [faded(c) for c in PASTEL]
HOUSE_COL = [faded(c, 0.3, 0.88) for c in HOUSE_COL]
TILE = [faded(c, 0.25, 0.85) for c in TILE]
SHINGLE = [(92, 90, 88), (112, 98, 86), (130, 126, 118)]


def ground(x, z):
    i = min(T["nx"] - 1, max(0, int((x - X0) / T["res"])))
    j = min(T["nz"] - 1, max(0, int((z - Z0) / T["res"])))
    return T["h"][j * T["nx"] + i]


class Model:
    """Faces per surface in world space (Blender axes), one object per model."""

    def __init__(self, name, tf):
        self.name, self.tf = name, tf  # tf: local (x, y, z) -> blender (x, y, z)
        self.v, self.f, self.c, self.s = [], [], [], []

    def face(self, surf, pts, col=None):
        n = len(self.v)
        self.v += [self.tf(*p) for p in pts]
        self.f.append(tuple(range(n, n + len(pts))))
        self.c.append(col or SURF[surf][2] or (200, 200, 200))
        self.s.append(surf)

    def box(self, surf, c, u, w, h, d, col=None):
        """Box centred at local c=(x, y, z), width w along horizontal unit u=(ux, uz), height h, depth d along u's normal."""
        ux, uz = u
        nx, nz = -uz, ux
        pts = []
        for i in (-1, 1):
            for j in (-1, 1):
                for k in (-1, 1):
                    pts.append((c[0] + ux * w / 2 * i + nx * d / 2 * k, c[1] + h / 2 * j, c[2] + uz * w / 2 * i + nz * d / 2 * k))
        for q in [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]:
            self.face(surf, [pts[i] for i in q], col)

    def prism(self, surf, poly, y0, y1, col=None, top=True):
        n = len(poly)
        for i in range(n):
            (ax, az), (bx, bz) = poly[i], poly[(i + 1) % n]
            self.face(surf, [(ax, y0, az), (bx, y0, bz), (bx, y1, bz), (ax, y1, az)], col)
        if top:
            self.face(surf, [(x, y1, z) for x, z in poly][::-1], col)

    def finish(self):
        me = bpy.data.meshes.new(self.name)
        me.from_pydata(self.v, [], self.f)
        me.update()
        ca = me.color_attributes.new("col", "FLOAT_COLOR", "CORNER")
        surfs = sorted(set(self.s))
        for m in surfs:
            me.materials.append(material(m))
        for poly, col, s in zip(me.polygons, self.c, self.s):
            poly.material_index = surfs.index(s)
            lc = lin(col)
            for li in poly.loop_indices:
                ca.data[li].color = (*lc, 1)
        me.validate()
        o = bpy.data.objects.new(self.name, me)
        bpy.context.collection.objects.link(o)
        return o


MATS = {}
SIGNS = []  # (transform, z, width, rng): shop names added as 3D text by realism.signs


def material(surf):
    if surf in MATS:
        return MATS[surf]
    m = bpy.data.materials.new(surf)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    a = nt.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "col"
    nt.links.new(a.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value, b.inputs["Metallic"].default_value = SURF[surf][0], SURF[surf][1]
    if surf == "neon":
        b.inputs["Emission Color"].default_value = (1, 0.08, 0.1, 1)
        b.inputs["Emission Strength"].default_value = 8
    if surf == "lamp":
        b.inputs["Emission Color"].default_value = (1, 0.9, 0.7, 1)
        b.inputs["Emission Strength"].default_value = 2
    MATS[surf] = m
    return m


def poly_area(poly):
    return sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) / 2


def edges(poly):
    """(a, b, unit along, outward normal, length) per edge."""
    sign = 1 if poly_area(poly) > 0 else -1
    out = []
    for i in range(len(poly)):
        a, b = poly[i], poly[(i + 1) % len(poly)]
        L = math.dist(a, b)
        if L < 3:
            continue
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        n = (u[1] * sign, -u[0] * sign)
        out.append((a, b, u, n, L))
    return out


STYLE = {  # floor height, bay width, window w x h, sill height above floor
    "house": (12, 13, 5, 6, 3.5), "stucco": (13, 10, 4.5, 7, 3.5), "shack": (12, 11, 4, 6, 3.5), "deco": (12, 9, 4, 7, 3),
    "midrise": (12, 10, 6, 7, 3), "campus": (14, 9, 4, 8, 3), "warehouse": (28, 20, 8, 4, 18), "tower": (12, 8, 7, 9, 1.5),
}


def window(m, e, along, y, w, h, frame_col, rng, shutters=None):
    a, _, u, n, _ = e
    x, z = a[0] + u[0] * along, a[1] + u[1] * along
    off = lambda d: (x + n[0] * d, z + n[1] * d)  # noqa: E731
    gx, gz = off(0.15)
    m.box("glass", (gx, y + h / 2, gz), u, w, h, 0.3)
    fx, fz = off(0.35)
    for dy, hh in ((0, 0.6), (h, 0.6)):  # head and sill of the frame
        m.box("frame", (fx, y + dy, fz), u, w + 1.2, hh, 0.7, frame_col)
    for s in (-1, 1):
        m.box("frame", (fx + u[0] * (w / 2 + 0.3) * s, y + h / 2, fz + u[1] * (w / 2 + 0.3) * s), u, 0.6, h, 0.7, frame_col)
    m.box("frame", (fx, y + h / 2, fz), u, 0.35, h, 0.5, frame_col)  # mullion
    sx, sz = off(0.8)
    m.box("trim", (sx, y - 0.6, sz), u, w + 2, 0.6, 1.6)  # sill
    if shutters:
        for s in (-1, 1):
            m.box("door", (fx + u[0] * (w / 2 + 1.9) * s + n[0] * 0.8, y + h / 2, fz + u[1] * (w / 2 + 1.9) * s + n[1] * 0.8), u, 2.4, h + 0.6, 0.4, shutters)


def flat_roof(m, poly, y, rng, wall_col, big=False):
    m.face("roof_flat", [(x, y + 0.2, z) for x, z in poly][::-1])
    for e in edges(poly):  # parapet + cornice
        a, b, u, n, L = e
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        m.box("wall", (mx - n[0] * 0.4, y + 1.4, mz - n[1] * 0.4), u, L, 2.8, 0.8, wall_col)
        m.box("trim", (mx + n[0] * 0.3, y - 0.4, mz + n[1] * 0.3), u, L + 1.2, 1.0, 1.4)
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    def spot(margin=4):
        for _ in range(8):
            x, z = rng.uniform(min(xs) + margin, max(xs) - margin), rng.uniform(min(zs) + margin, max(zs) - margin)
            if inside(poly, x, z):
                return x, z
        return None
    for _ in range(rng.randint(1, 4 if big else 2)):  # AC units
        p = spot()
        if p:
            m.box("metal", (p[0], y + 1.6, p[1]), (1, 0), 4, 3, 3)
            m.box("pole", (p[0], y + 3.15, p[1]), (1, 0), 3, 0.1, 2.4)  # fan grille
    for _ in range(rng.randint(2, 5)):  # vent stacks
        p = spot(2)
        if p:
            m.box("metal", (p[0], y + 1.2, p[1]), (1, 0), 0.6, 2.4, 0.6, (120, 120, 118))
    if rng.random() < 0.5:  # satellite dish on a stub mast
        p = spot(3)
        if p:
            m.box("pole", (p[0], y + 1.5, p[1]), (1, 0), 0.25, 3, 0.25)
            m.box("trim", (p[0], y + 3.2, p[1] + 0.4), (0.7, 0.7), 2.4, 2.4, 0.3)
    if rng.random() < 0.4:  # roof hatch
        p = spot(3)
        if p:
            m.box("metal", (p[0], y + 0.6, p[1]), (1, 0), 3, 1.2, 3, (140, 140, 136))
    if big and rng.random() < 0.7:  # HVAC duct run
        p = spot(6)
        if p:
            m.box("metal", (p[0], y + 1.2, p[1]), (1, 0), max(6, (max(xs) - min(xs)) * 0.4), 1.6, 1.6)
    if rng.random() < 0.3:  # water heater / tank
        p = spot(3)
        if p:
            m.box("metal", (p[0], y + 1.8, p[1]), (1, 0), 2.2, 3.6, 2.2, (200, 200, 196))


def inside(poly, x, z):
    c = False
    for i in range(len(poly)):
        (ax, az), (bx, bz) = poly[i], poly[i - 1]
        if (az > z) != (bz > z) and x < (bx - ax) * (z - az) / (bz - az) + ax:
            c = not c
    return c


def pitched_roof(m, poly, y, kind, tile_col, wall_col, rng=None):
    """Hip or gable roof with 2.5-stud eaves over a rectangular part."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, z0, z1 = min(xs) - 2.5, max(xs) + 2.5, min(zs) - 2.5, max(zs) + 2.5
    along_x = (x1 - x0) >= (z1 - z0)
    W = (z1 - z0) if along_x else (x1 - x0)
    rh = min(W * 0.33, 14)
    inset = W / 2 if kind == "hip" else 0
    if along_x:
        zm = (z0 + z1) / 2
        r0, r1 = (x0 + inset, y + rh, zm), (x1 - inset, y + rh, zm)
        e = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        m.face("roof_tile", [e[0], r0, r1, e[1]], tile_col)
        m.face("roof_tile", [e[2], r1, r0, e[3]], tile_col)
        ends = [(e[3], r0, e[0]), (e[1], r1, e[2])]
    else:
        xm = (x0 + x1) / 2
        r0, r1 = (xm, y + rh, z0 + inset), (xm, y + rh, z1 - inset)
        e = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)]
        m.face("roof_tile", [e[1], r0, r1, e[2]], tile_col)
        m.face("roof_tile", [e[3], r1, r0, e[0]], tile_col)
        ends = [(e[0], r0, e[1]), (e[2], r1, e[3])]
    if rng and rng.random() < 0.3:  # rooftop solar on the first slope: inset panel array lifted off the tiles
        a, b, c, d = (e[0], r0, r1, e[1]) if along_x else (e[1], r0, r1, e[2])
        def lerp(p, q, t):
            return tuple(p[i] + (q[i] - p[i]) * t for i in range(3))
        p0, p1 = lerp(a, d, 0.2), lerp(a, d, 0.8)
        q0, q1 = lerp(b, c, 0.2), lerp(b, c, 0.8)
        lo0, lo1, hi0, hi1 = lerp(p0, q0, 0.2), lerp(p1, q1, 0.2), lerp(p0, q0, 0.7), lerp(p1, q1, 0.7)
        lift = lambda p: (p[0], p[1] + 0.35, p[2])  # noqa: E731
        m.face("solar", [lift(lo0), lift(lo1), lift(hi1), lift(hi0)][::-1] if along_x else [lift(lo0), lift(lo1), lift(hi1), lift(hi0)])
    if rng:  # plumbing vent pipes through the roof
        for _ in range(rng.randint(1, 3)):
            x, z = rng.uniform(x0 + 4, x1 - 4), rng.uniform(z0 + 4, z1 - 4)
            m.box("metal", (x, y + rh * 0.55, z), (1, 0), 0.4, rh * 0.5 + 2, 0.4, (90, 90, 90))
    for tri in ends:  # hip ends are roof; gable ends are wall
        m.face("roof_tile" if kind == "hip" else "wall", list(tri), tile_col if kind == "hip" else wall_col)
    for a, b in zip(e, e[1:] + e[:1]):  # fascia boards along the eaves
        mx, mz = (a[0] + b[0]) / 2, (a[2] + b[2]) / 2
        L = math.dist((a[0], a[2]), (b[0], b[2]))
        m.box("trim", (mx, y - 0.4, mz), ((b[0] - a[0]) / L, (b[2] - a[2]) / L), L, 0.9, 0.5)


INTERIOR_KIND = {"Barber shop": "salon", "Beauty salon": "salon", "Nail salon": "salon", "Full-service restaurant": "food", "Fast food": "food",
                 "Coffee shop / snack bar": "food", "Bar / nightclub": "food", "Clothing store": "clothing", "Thrift / used goods": "clothing",
                 "Shoe store": "clothing", "Jewelry store": "jewelry", "Fitness centre / gym": "gym"}
OFFICE = ("office", "agency", "Doctor", "Dentist", "care", "Veterinarian", "Law", "Real estate", "Insurance", "school", "Bank", "Credit")
SIGN_TEXT = {"Barber shop": "BARBER", "Beauty salon": "SALON", "Full-service restaurant": "RESTAURANT", "Fast food": "BURGERS",
             "Coffee shop / snack bar": "CAFE", "Clothing store": "BOUTIQUE", "Thrift / used goods": "THRIFT", "Jewelry store": "JEWELRY",
             "Doctor's office": "FAMILY MEDICINE", "Real estate office": "REALTY", "Insurance agency": "INSURANCE", "Law office": "LAW OFFICE",
             "Pharmacy": "PHARMACY", "Convenience store": "FOOD MART", "Sporting goods (incl. gun shops)": "SPORTS", "Fitness centre / gym": "FITNESS",
             "Veterinarian": "ANIMAL CLINIC", "Urgent care / outpatient centre": "URGENT CARE", "Tire shop": "TIRES", "Child day care": "DAY CARE",
             "Auto repair (general)": "AUTO REPAIR", "Body / paint shop": "BODY SHOP", "Used car dealer": "AUTO SALES"}


def interior_kind(use):
    if use in INTERIOR_KIND:
        return INTERIOR_KIND[use]
    return "office" if any(k in (use or "") for k in OFFICE) else "retail"


def interior(m, poly, kind, rng, ceil):
    """Furnish a shop's ground floor so it reads through the glass. Local frame: street at min z."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, z0, z1 = min(xs) + 1.5, max(xs) - 1.5, min(zs) + 1.5, max(zs) - 1.5
    ok = lambda x, z: inside(poly, x, z) and x0 < x < x1 and z0 < z < z1  # noqa: E731
    U = (1, 0)
    floor_col = {"salon": (230, 230, 226), "food": (150, 110, 80), "office": (120, 120, 126), "clothing": (190, 170, 140),
                 "jewelry": (40, 40, 44), "gym": (50, 50, 54), "retail": (210, 210, 204)}[kind]
    m.face("floor", [(x, 0.4, z) for x, z in poly][::-1], floor_col)
    m.face("trim", [(x, ceil - 0.3, z) for x, z in poly], (236, 234, 228))  # ceiling, facing down
    for gx in range(int(x0) + 3, int(x1) - 1, 8):  # ceiling light panels
        for gz in range(int(z0) + 3, int(z1) - 1, 8):
            if ok(gx, gz):
                m.box("lamp", (gx, ceil - 0.45, gz), U, 3, 0.15, 1.2)
    depth = z1 - z0
    if kind == "salon":
        for k, x in enumerate(range(int(x0) + 3, int(x1) - 2, 6)):
            z = z0 + 3.5
            if ok(x, z + 4):
                m.box("pole", (x, 1.0, z + 4), U, 1.0, 1.6, 1.0)  # chair base
                m.box("fabric", (x, 2.4, z + 4), U, 2.6, 1.0, 2.6, (30, 30, 32))  # seat
                m.box("fabric", (x, 4.0, z + 5.2), U, 2.6, 3.0, 0.6, (30, 30, 32))  # back
                m.box("mirror", (x, 5.5, z1 - 0.3), U, 4, 5, 0.2)  # mirror on the back wall
                m.box("wood", (x, 3.4, z1 - 1.2), U, 4.5, 0.4, 1.6)  # station shelf
        m.box("wood", (x1 - 5, 2.0, z0 + 3), U, 6, 4, 2, (240, 240, 236))  # reception
    elif kind == "food":
        m.box("wood", ((x0 + x1) / 2, 2.2, z1 - 2), U, (x1 - x0) * 0.7, 4.4, 2.2)  # counter
        m.box("door", ((x0 + x1) / 2, 7.5, z1 - 0.3), U, (x1 - x0) * 0.5, 2.5, 0.2, (25, 25, 25))  # menu board
        for x in range(int(x0) + 3, int(x1) - 2, 7):
            for z in (z0 + 4, z0 + 4 + min(8, depth * 0.35)):
                if ok(x, z):
                    m.box("wood", (x, 3.5, z), U, 3.2, 0.3, 3.2, (120, 80, 50))  # table
                    m.box("pole", (x, 1.7, z), U, 0.4, 3.4, 0.4)
                    for dx, dz in ((-2.3, 0), (2.3, 0)):
                        m.box("fabric", (x + dx, 2.0, z + dz), U, 1.6, 0.4, 1.6, rng.choice([(140, 40, 30), (40, 40, 40), (200, 170, 60)]))
                        m.box("fabric", (x + dx * 1.3, 3.5, z + dz), U, 0.3, 3.0, 1.6, (40, 40, 40))
                    m.box("lamp", (x, ceil - 3, z), U, 0.8, 0.8, 0.8)  # pendant light
    elif kind == "office":
        for x in range(int(x0) + 4, int(x1) - 3, 9):
            for z in (z0 + 6, z0 + 6 + min(9, depth * 0.4)):
                if ok(x, z):
                    m.box("wood", (x, 3.3, z), U, 5, 0.3, 2.6, (200, 196, 186))  # desk
                    m.box("pole", (x - 2.2, 1.6, z), U, 0.3, 3.2, 2.4)
                    m.box("pole", (x + 2.2, 1.6, z), U, 0.3, 3.2, 2.4)
                    m.box("door", (x, 4.6, z + 0.6), U, 2.0, 1.4, 0.15, (20, 20, 22))  # monitor
                    m.box("fabric", (x, 2.3, z - 2.0), U, 1.8, 2.6, 1.8, (30, 30, 34))  # chair
        for x in range(int(x0) + 2, int(x1) - 1, 3):  # filing cabinets / shelving along the back
            if ok(x, z1 - 1):
                m.box("metal", (x, 2.6, z1 - 1), U, 2.6, 5.2, 1.6, (170, 172, 170))
        m.box("fabric", (x0 + 3, 1.8, z0 + 2.5), U, 5, 1.6, 2, (60, 90, 120))  # waiting bench by the window
    elif kind == "clothing":
        for x in range(int(x0) + 4, int(x1) - 3, 7):
            z = z0 + 6
            if ok(x, z):
                m.box("pole", (x, 5.2, z), U, 5, 0.2, 0.2)  # rail
                for k in range(9):  # garments
                    m.box("fabric", (x - 2.2 + k * 0.55, 3.6, z), U, 0.35, 3.0, 2.0,
                          rng.choice([(200, 60, 60), (40, 60, 110), (230, 230, 220), (30, 30, 30), (90, 130, 90), (210, 170, 120)]))
        for x in range(int(x0) + 2, int(x1) - 1, 4):  # wall shelves with folded stacks
            if ok(x, z1 - 1):
                for lvl in (2, 4, 6):
                    m.box("wood", (x, lvl, z1 - 1), U, 3.6, 0.2, 1.6)
                    m.box("fabric", (x, lvl + 0.5, z1 - 1), U, 3.0, 0.8, 1.2, rng.choice([(170, 50, 50), (50, 70, 120), (220, 220, 210)]))
        for k in range(2):  # mannequins in the window
            x = x0 + 4 + k * 6
            if ok(x, z0 + 2.5):
                m.box("trim", (x, 3.4, z0 + 2.5), U, 1.0, 6.4, 0.8, (236, 228, 214))
                m.box("fabric", (x, 4.2, z0 + 2.5), U, 1.6, 2.6, 1.2, rng.choice([(180, 40, 60), (30, 30, 30)]))
    elif kind == "jewelry":
        for x in range(int(x0) + 4, int(x1) - 3, 7):
            for z in (z0 + 5, z1 - 3):
                if ok(x, z):
                    m.box("wood", (x, 1.8, z), U, 5, 3.6, 2, (30, 30, 34))
                    m.box("shopglass", (x, 4.4, z), U, 5, 1.6, 2)  # glass case
                    m.box("lamp", (x, 3.75, z), U, 4.6, 0.1, 1.6)
    elif kind == "gym":
        for x in range(int(x0) + 4, int(x1) - 3, 6):
            if ok(x, z0 + 5):
                m.box("pole", (x, 2.4, z0 + 5), U, 2.2, 4.8, 5, (40, 40, 44))  # treadmill
        m.box("mirror", ((x0 + x1) / 2, 5.5, z1 - 0.3), U, x1 - x0 - 2, 6, 0.2)
        m.box("pole", ((x0 + x1) / 2, 4, z1 - 3), U, 6, 8, 1, (60, 60, 64))  # rack
    else:  # retail: shelf gondolas parallel to the street, stocked, checkout by the door
        for z in [z0 + 7 + k * 6 for k in range(int((depth - 8) // 6))]:
            for x in range(int(x0) + 4, int(x1) - 3, 8):
                if ok(x, z):
                    m.box("metal", (x, 2.8, z), U, 6.5, 5.6, 1.8, (220, 220, 216))
                    for lvl in (1.2, 2.6, 4.0, 5.4):
                        for side in (-1, 1):
                            for k in range(4):
                                m.box("fabric", (x - 2.4 + k * 1.6, lvl + 0.5, z + side * 1.0), U, 1.2, 0.9, 0.3,
                                      rng.choice([(200, 50, 40), (40, 90, 160), (240, 200, 60), (60, 140, 80), (240, 240, 230), (150, 60, 140)]))
        m.box("wood", (x1 - 5, 2.0, z0 + 3.5), U, 6, 4, 2.2, (230, 230, 226))  # checkout


HOLLOW = ("house", "stucco", "shack", "deco", "midrise", "campus")  # styles built as real walls with openings and furnished floors


def skin(m, e, y0_, y1_, openings, wall_col, ext=0.9):
    """Wall of one edge between y0_ and y1_ built from panels around openings [(centre, width, bottom, top)], 0.9 thick
    outward from the wall line; ends run past the corners so neighbouring walls close up."""
    a, _, u, n, L = e
    cuts = sorted({y0_, y1_} | {max(y0_, min(y1_, v)) for c_, w_, bt, tp in openings for v in (bt, tp)})
    for ya, yb_ in zip(cuts, cuts[1:]):
        if yb_ - ya < 0.05:
            continue
        gaps = sorted((c_ - w_ / 2, c_ + w_ / 2) for c_, w_, bt, tp in openings if bt <= ya + 0.01 and tp >= yb_ - 0.01)
        x = -ext
        for g0, g1 in gaps + [(L + ext, L + ext)]:
            if g0 > x + 0.05:
                mid = (x + g0) / 2
                m.box("wall", (a[0] + u[0] * mid + n[0] * 0.45, (ya + yb_) / 2, a[1] + u[1] * mid + n[1] * 0.45), u, g0 - x, yb_ - ya, 0.9, wall_col)
            x = max(x, g1)


FURN = [(150, 120, 90), (90, 100, 120), (200, 190, 170), (60, 70, 80), (170, 80, 60), (110, 130, 100)]


def furnish(m, poly, yb, height, kind, rng):
    """One floor of a home or office: floor, ceiling light, furniture along the walls and in the middle."""
    xs, zs = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, z0, z1 = min(xs) + 1.5, max(xs) - 1.5, min(zs) + 1.5, max(zs) - 1.5
    if x1 - x0 < 6 or z1 - z0 < 6:
        return
    ok = lambda x, z: inside(poly, x, z) and x0 < x < x1 and z0 < z < z1  # noqa: E731
    U = (1, 0)
    m.face("floor", [(x, yb + 0.35, z) for x, z in poly][::-1], rng.choice([(150, 110, 80), (200, 196, 186), (120, 96, 72), (210, 206, 196)]))
    m.face("trim", [(x, yb + height - 0.2, z) for x, z in poly], (238, 236, 230))  # ceiling
    for gx in range(int(x0) + 4, int(x1) - 2, 12):
        for gz in range(int(z0) + 4, int(z1) - 2, 12):
            if ok(gx, gz):
                m.box("lamp", (gx, yb + height - 0.45, gz), U, 1.4, 0.2, 1.4)  # ceiling light
    y = yb + 0.35
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    if kind == "office":
        for x in range(int(x0) + 3, int(x1) - 2, 8):
            for z in range(int(z0) + 3, int(z1) - 2, 7):
                if ok(x, z):
                    m.box("wood", (x, y + 2.9, z), U, 4.6, 0.3, 2.4, (200, 196, 186))
                    m.box("door", (x, y + 4.2, z + 0.6), U, 1.8, 1.3, 0.15, (20, 20, 22))
                    m.box("fabric", (x, y + 2.0, z - 1.8), U, 1.7, 2.4, 1.7, (30, 30, 34))
        return
    # living area: sofa facing a TV unit, coffee table, rug
    if ok(cx - 4, z0 + 2):
        col = rng.choice(FURN)
        m.box("fabric", (cx - 4, y + 1.2, z0 + 2.2), U, 7, 2.4, 2.6, col)  # sofa seat
        m.box("fabric", (cx - 4, y + 2.6, z0 + 1.3), U, 7, 2.8, 0.8, col)  # back
        m.box("fabric", (cx - 4, y + 0.05, z0 + 5.5), U, 8, 0.1, 5, rng.choice(FURN))  # rug
        m.box("wood", (cx - 4, y + 1.0, z0 + 5.5), U, 3.5, 0.3, 2, (110, 80, 60))  # coffee table
        if ok(cx - 4, z0 + 9):
            m.box("wood", (cx - 4, y + 1.2, z0 + 9.2), U, 6, 2.4, 1.4, (60, 50, 44))  # TV unit
            m.box("door", (cx - 4, y + 4.0, z0 + 9.3), U, 5, 3, 0.2, (15, 15, 17))  # TV
    # dining table with chairs
    if ok(cx + 5, cz):
        m.box("wood", (cx + 5, y + 2.6, cz), U, 5, 0.3, 3, (140, 100, 70))
        for dx in (-1.6, 1.6):
            for dz in (-2.3, 2.3):
                m.box("wood", (cx + 5 + dx, y + 1.5, cz + dz), U, 1.4, 0.3, 1.4, (120, 90, 64))
                m.box("wood", (cx + 5 + dx, y + 2.6, cz + dz * 1.25), U, 1.4, 2.2, 0.25, (120, 90, 64))
    # kitchen run along the back wall with upper cabinets and a fridge
    for x in range(int(x0) + 1, int(min(x1, x0 + 14)), 3):
        if ok(x + 1.5, z1 - 1.2):
            m.box("wood", (x + 1.5, y + 1.6, z1 - 1.2), U, 3, 3.2, 2.2, (236, 234, 228))
            m.box("metal", (x + 1.5, y + 3.25, z1 - 1.2), U, 3, 0.15, 2.3, (60, 60, 64))  # counter top
            m.box("wood", (x + 1.5, y + 6.4, z1 - 0.8), U, 3, 2.4, 1.4, (236, 234, 228))
    if ok(x0 + 16, z1 - 1.4):
        m.box("metal", (x0 + 16, y + 3.6, z1 - 1.4), U, 3, 7.2, 2.6, (210, 212, 214))  # fridge
    # bed with nightstands and a wardrobe in the far corner
    bx, bz = x1 - 5, cz + 2
    if ok(bx, bz) and ok(bx, bz + 5):
        m.box("wood", (bx, y + 0.9, bz), U, 5.6, 1.8, 7, (120, 96, 72))
        m.box("fabric", (bx, y + 2.0, bz), U, 5.4, 0.6, 6.8, (236, 236, 230))  # mattress
        m.box("fabric", (bx, y + 2.4, bz + 3.0), U, 4.8, 0.5, 1.2, (250, 250, 246))  # pillows
        m.box("fabric", (bx, y + 2.35, bz - 1.0), U, 5.6, 0.25, 4.4, rng.choice(FURN))  # duvet
        m.box("wood", (bx, y + 3.4, bz + 3.6), U, 5.8, 3.4, 0.4, (100, 80, 60))  # headboard
        for side in (-1, 1):
            m.box("wood", (bx + side * 3.6, y + 1.1, bz + 3), U, 1.4, 2.2, 1.4, (100, 80, 60))
    if ok(x1 - 1.4, z0 + 4):
        m.box("wood", (x1 - 1.4, y + 3.8, z0 + 4), U, 2.2, 7.6, 4.5, (200, 190, 170))  # wardrobe
    for _ in range(rng.randint(1, 3)):  # plants and a floor lamp
        px, pz = rng.uniform(x0 + 1, x1 - 1), rng.uniform(z0 + 1, z1 - 1)
        if ok(px, pz):
            m.box("door", (px, y + 0.8, pz), U, 1.2, 1.6, 1.2, (150, 90, 60))
            m.box("fabric", (px, y + 2.6, pz), U, 2.0, 2.4, 2.0, (60, 110, 50))
    if ok(x0 + 2, z0 + 2):
        m.box("pole", (x0 + 2, y + 3, z0 + 2), U, 0.2, 6, 0.2)
        m.box("lamp", (x0 + 2, y + 6.2, z0 + 2), U, 1.2, 0.8, 1.2)


def building(idx, b):
    rng = random.Random(idx)
    c, s = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
    gy = b["y"]
    tf = lambda x, y, z: (b["x"] + c * x - s * z, -(b["z"] + s * x + c * z), gy + y)  # noqa: E731
    m = Model(f"b{idx}", tf)
    style = b["style"]
    fh, bay, ww, wh, sill = STYLE.get(style, STYLE["stucco"])
    wall_col = rng.choice(HOUSE_COL if style == "house" else PASTEL)
    frame_col = (250, 250, 246) if style != "tower" else (190, 196, 200)
    shut = rng.choice(SHUTTER) if rng.random() < 0.55 else None
    tile_col = rng.choice(TILE) if rng.random() < 0.6 else rng.choice(SHINGLE)
    parts = b.get("parts", [])
    main_h = max((p["h"] for p in parts), default=12)
    for pi, p in enumerate(parts):
        poly = [(p["pts"][i], p["pts"][i + 1]) for i in range(0, len(p["pts"]), 2)]
        y0, h = p["base"], p["h"]
        porch = style == "house" and p["roof"] == "flat" and h < main_h * 0.7
        if porch:  # open porch: floor, posts, roof slab
            m.prism("concrete", poly, -0.5, 0.6)
            for x, z in poly:
                m.box("trim", (x * 0.9, h / 2, z * 0.9), (1, 0), 1.2, h, 1.2)
            m.prism("trim", poly, h, h + 1.0)
            continue
        if p["roof"] == "canopy":  # gas station canopy on columns
            m.prism("trim", poly, y0 + h - 1.5, y0 + h)
            for x, z in poly:
                m.box("pole", (x * 0.8, (y0 + h) / 2, z * 0.8), (1, 0), 1.5, y0 + h, 1.5)
            continue
        shop_part = style in ("stucco", "shack") and pi == 0 and y0 == 0 and h >= 11 and any(e[3][1] < -0.7 for e in edges(poly))
        CEIL = 10.0
        hollow = style in HOLLOW
        if shop_part:  # ground floor is a real room open to the street through glass
            interior(m, poly, interior_kind(b.get("use")), rng, CEIL)
        if not hollow:
            m.prism("wall", poly, y0 - 3, y0 + h, wall_col, top=False)
        else:  # walls come from skins (with real openings); short edges and the footing get plain wall here
            for i_ in range(len(poly)):
                (ax_, az_), (bx_, bz_) = poly[i_], poly[(i_ + 1) % len(poly)]
                if math.dist((ax_, az_), (bx_, bz_)) < 3:
                    m.face("wall", [(ax_, y0 - 3, az_), (bx_, y0 - 3, bz_), (bx_, y0 + h, bz_), (ax_, y0 + h, az_)], wall_col)
            for e in edges(poly):
                skin(m, e, y0 - 3, y0, [], wall_col)
        if y0 == 0 and style != "tower":  # base course: a slightly proud, darker plinth
            big = [(x * (1 + 0.6 / max(1, abs(x))) if abs(x) > 0.1 else x, z * (1 + 0.6 / max(1, abs(z))) if abs(z) > 0.1 else z) for x, z in poly]
            m.prism("wall", big, -1, 1.8, tuple(int(v * 0.72) for v in wall_col), top=False)
        floors = max(1, int(h // fh))
        if hollow:  # furnish every floor (shop ground floors are furnished as shops above)
            for f in range(floors):
                yb_f = y0 + f * fh
                top_f = (y0 + h) if f == floors - 1 else yb_f + fh
                if f > 0 or not shop_part:
                    if f > 0:
                        m.prism("concrete", poly, yb_f - 0.4, yb_f + 0.3, top=True)  # floor slab
                    furnish(m, poly, yb_f, top_f - yb_f, "office" if style == "campus" else "home", rng)
        for e in edges(poly):
            a, _, u, n, L = e
            street = n[1] < -0.7  # local -z faces the street
            nb = max(1, int(L // bay))
            if style == "tower" and h > 60:  # curtain wall: glass bands, spandrels, mullions
                for f in range(floors):
                    yb = y0 + f * fh
                    mx, mz = a[0] + u[0] * L / 2 + n[0] * 0.2, a[1] + u[1] * L / 2 + n[1] * 0.2
                    m.box("glass", (mx, yb + fh * 0.55, mz), u, L - 1, fh * 0.75, 0.3)
                for j in range(nb + 1):
                    x, z = a[0] + u[0] * L * j / nb + n[0] * 0.5, a[1] + u[1] * L * j / nb + n[1] * 0.5
                    m.box("frame", (x, y0 + h / 2, z), u, 0.6, h, 1.0, frame_col)
                continue
            for f in range(floors):
                yb = y0 + f * fh
                shop = style in ("stucco", "shack") and f == 0 and street and y0 == 0 and shop_part
                if shop and shop_part:  # shopfront: full-width glazing at the wall line into the room, door, sign band
                    cx, cz = a[0] + u[0] * L / 2 + n[0] * 0.05, a[1] + u[1] * L / 2 + n[1] * 0.05
                    m.box("shopglass", (cx, 4.9, cz), u, L - 1, 8.4, 0.15)
                    for k in range(int(L // 7) + 1):  # mullions
                        t = -L / 2 + 0.5 + k * (L - 1) / max(1, int(L // 7))
                        m.box("frame", (cx + u[0] * t, 4.9, cz + u[1] * t), u, 0.4, 8.6, 0.4, (50, 50, 52))
                    m.box("frame", (cx, 0.7, cz), u, L - 1, 0.6, 0.5, (50, 50, 52))  # base rail
                    dx = L / 2 - 4
                    m.box("door", (cx + u[0] * dx + n[0] * 0.1, 4.2, cz + u[1] * dx + n[1] * 0.1), u, 3.6, 8.2, 0.25, (40, 40, 42))
                    m.box("wall", (cx + n[0] * 0.3, (CEIL + 9.1) / 2, cz + n[1] * 0.3), u, L, CEIL - 9.1, 0.8, wall_col)  # sign band
                    skin(m, e, CEIL, (y0 + h) if floors == 1 else fh, [], wall_col)  # wall between the shop ceiling and the floor above
                    acol = rng.choice(AWNING)
                    for k in range(max(1, int(L // 3))):
                        t = (k + 0.5) / max(1, int(L // 3))
                        x, z = a[0] + u[0] * L * t, a[1] + u[1] * L * t
                        col = acol if k % 2 == 0 else (245, 245, 240)
                        m.face("awning", [(x - u[0] * 1.5 + n[0] * 0.2, 11, z - u[1] * 1.5 + n[1] * 0.2), (x + u[0] * 1.5 + n[0] * 0.2, 11, z + u[1] * 1.5 + n[1] * 0.2),
                                          (x + u[0] * 1.5 + n[0] * 5, 9, z + u[1] * 1.5 + n[1] * 5), (x - u[0] * 1.5 + n[0] * 5, 9, z - u[1] * 1.5 + n[1] * 5)], col)
                    continue
                top_y = (y0 + h) if f == floors - 1 else min(yb + fh, y0 + h)
                if True:  # outer skin 0.9 proud with real openings for windows, doors and garages
                    ops = []
                    for j in range(nb):
                        wc = L * (j + 0.5) / nb  # window centre (not `c`: the transform closes over the rotation's cos)
                        is_door = style == "house" and street and pi == 0 and j == nb // 2 and f == 0
                        is_gar = style == "house" and street and pi == 1 and f == 0 and b.get("type") in ("ranch", "l_ranch")
                        if is_gar:
                            if j == 0:
                                ops.append((L / 2, min(L - 3, 16) + 0.6, yb, yb + 9.2))
                        elif is_door:
                            ops.append((wc, 4.2, yb, yb + 8.4))
                        else:
                            ops.append((wc, ww + 1.2, yb + sill, yb + sill + wh))
                    skin(m, e, yb, top_y, ops, wall_col)
                for j in range(nb):
                    along = L * (j + 0.5) / nb
                    if style in ("stucco", "midrise") and f > 0 and rng.random() < 0.12:  # window AC unit
                        x, z = a[0] + u[0] * along + n[0] * 1.4, a[1] + u[1] * along + n[1] * 1.4
                        m.box("metal", (x, yb + sill + 1.3, z), u, ww * 0.75, 2.4, 2.2, (196, 196, 190))
                    if style == "house" and street and pi == 0 and j == nb // 2 and f == 0:  # front door with a little step
                        x, z = a[0] + u[0] * along + n[0] * 0.3, a[1] + u[1] * along + n[1] * 0.3
                        m.box("door", (x, 4, z), u, 3.6, 8, 0.4, rng.choice([(120, 70, 50), (40, 70, 110), (250, 250, 246)]))
                        m.box("trim", (x + n[0] * 1.2, 0.3, z + n[1] * 1.2), u, 6, 0.6, 3)
                        m.box("trim", (x + n[0] * 1.3, 9.2, z + n[1] * 1.3), u, 6.5, 0.5, 2.6)  # door canopy
                        for side in (-1, 1):  # canopy brackets
                            m.box("trim", (x + u[0] * 3 * side + n[0] * 1.3, 8.4, z + u[1] * 3 * side + n[1] * 1.3), u, 0.3, 1.4, 2.4)
                        continue
                    if style == "house" and street and pi == 1 and f == 0 and b.get("type") in ("ranch", "l_ranch"):  # garage door
                        if j == 0:
                            x, z = a[0] + u[0] * L / 2 + n[0] * 0.3, a[1] + u[1] * L / 2 + n[1] * 0.3
                            gw = min(L - 3, 16)
                            m.box("trim", (x, 4.5, z), u, gw, 9, 0.4)
                            for k in range(4):
                                m.box("frame", (x + n[0] * 0.2, 1.5 + k * 2.2, z + n[1] * 0.2), u, gw - 0.5, 0.25, 0.3, (220, 220, 214))
                        continue
                    window(m, e, along, yb + sill, ww, wh, frame_col, rng, shut if style in ("house", "stucco") else None)
                    if style == "deco":  # eyebrow ledge
                        x, z = a[0] + u[0] * along + n[0] * 1.5, a[1] + u[1] * along + n[1] * 1.5
                        m.box("trim", (x, yb + sill + wh + 1.2, z), u, ww + 3, 0.4, 3)
                if style in ("deco", "midrise") and f > 0 and street and rng.random() < 0.5:  # balconies
                    x, z = a[0] + u[0] * L / 2 + n[0] * 2.2, a[1] + u[1] * L / 2 + n[1] * 2.2
                    bw_ = min(L - 4, 16)
                    m.box("trim", (x, yb, z), u, bw_, 0.6, 4.4)  # balcony slab with a metal railing
                    rx, rz = x + n[0] * 2.05, z + n[1] * 2.05
                    m.box("pole", (rx, yb + 3.4, rz), u, bw_, 0.25, 0.25)
                    for k in range(int(bw_ / 0.9) + 1):
                        t = -bw_ / 2 + k * 0.9
                        m.box("pole", (rx + u[0] * t, yb + 1.7, rz + u[1] * t), u, 0.12, 3.4, 0.12)
            if style in ("stucco", "shack") and not street and y0 == 0 and L > 10 and rng.random() < 0.35:  # posters
                for k in range(rng.randint(1, 3)):
                    t = rng.uniform(3, L - 3)
                    x, z = a[0] + u[0] * t + n[0] * 0.95, a[1] + u[1] * t + n[1] * 0.95
                    m.box("awning", (x, rng.uniform(5, 7), z), u, rng.uniform(2.4, 3.6), rng.uniform(3.2, 4.6), 0.05,
                          rng.choice([(200, 60, 50), (40, 80, 150), (230, 200, 60), (240, 240, 230), (30, 30, 30), (60, 140, 90)]))
            if style == "deco":  # pilasters between bays
                for j in range(nb + 1):
                    x, z = a[0] + u[0] * L * j / nb + n[0] * 1.2, a[1] + u[1] * L * j / nb + n[1] * 1.2
                    m.box("wall", (x, y0 + h / 2, z), u, 1.4, h, 0.8, wall_col)
        top = y0 + h
        rect = len(poly) == 4
        if p["roof"] in ("hip", "gable", "gambrel") and rect:
            m.face("roof_flat", [(x, top, z) for x, z in poly][::-1])
            pitched_roof(m, poly, top, "hip" if p["roof"] != "gable" else "gable", tile_col, wall_col, rng)
        elif p["roof"] == "spire":
            xs, zs = [q[0] for q in poly], [q[1] for q in poly]
            apex = (sum(xs) / len(xs), top + 10, sum(zs) / len(zs))
            for i in range(len(poly)):
                m.face("trim", [(poly[i][0], top, poly[i][1]), (poly[i - 1][0], top, poly[i - 1][1]), apex])
        else:
            flat_roof(m, poly, top, rng, wall_col, big=style in ("tower", "midrise", "warehouse"))
    if style == "house" and rng.random() < 0.45:  # backyard pool with coping
        d = b["d"]
        px, pz, pw, pd = rng.uniform(-b["w"] * 0.2, b["w"] * 0.2), d / 2 + 9, rng.uniform(10, 14), 7
        m.box("concrete", (px, 0.1, pz), (1, 0), pw + 3, 0.4, pd + 3)
        m.box("pool", (px, 0.35, pz), (1, 0), pw, 0.1, pd)
    if style == "house":  # driveway to the street
        m.box("concrete", (b["w"] * 0.3, 0.12, -b["d"] / 2 - 14), (1, 0), 10, 0.25, 28)
    if style == "house":  # AC condenser on a pad at the side, gutters and downspouts at the corners
        sx = b["w"] / 2 + 2.2
        m.box("concrete", (sx, 0.15, 2), (1, 0), 3.6, 0.3, 3.6)
        m.box("metal", (sx, 1.9, 2), (1, 0), 3, 3.2, 3, (150, 150, 146))
        m.box("pole", (sx, 3.6, 2), (1, 0), 2.4, 0.15, 2.4)
        top = max((p["h"] for p in parts if p["base"] == 0), default=12)
        for cx in (-b["w"] / 2 + 0.6, b["w"] / 2 - 0.6):
            for cz in (-b["d"] / 2 + 0.6, b["d"] / 2 - 0.6):
                if rng.random() < 0.6:
                    m.box("trim", (cx * 1.02, top / 2, cz * 1.02), (1, 0), 0.45, top, 0.45, (226, 224, 216))
    if style in ("stucco", "shack") and parts:  # shop sign above the awning
        p0 = parts[0]
        poly = [(p0["pts"][i], p0["pts"][i + 1]) for i in range(0, len(p0["pts"]), 2)]
        zs = [z for _, z in poly]
        width = (max(x for x, _ in poly) - min(x for x, _ in poly))
        if width > 12:
            sign_col = rng.choice([(30, 40, 60), (120, 30, 30), (20, 80, 70), (230, 220, 200), (60, 40, 30)])
            m.box("door", (0, 13.6, min(zs) - 0.6), (1, 0), min(width * 0.6, 26), 2.6, 0.6, sign_col)
            SIGNS.append((tf, min(zs) - 1.0, min(width * 0.55, 24), rng, SIGN_TEXT.get(b.get("use"))))
    return m.finish()


def streets(zone_roads):
    m = Model("streets", lambda x, y, z: (x, -z, y))
    lights = 0
    for r in zone_roads:
        ax, az, bx, bz, w = r["ax"], r["az"], r["bx"], r["bz"], r["width"]
        L = math.hypot(bx - ax, bz - az)
        if L < 1:
            continue
        u = ((bx - ax) / L, (bz - az) / L)
        n = (-u[1], u[0])
        mx, mz = (ax + bx) / 2, (az + bz) / 2
        y = ground(mx, mz) + 0.5
        m.box("asphalt", (mx, y - 0.6, mz), u, L + w * 0.5, 1.2, w)
        for side in (-1, 1):  # curb + sidewalk
            sx, sz = mx + n[0] * (w / 2 + 4) * side, mz + n[1] * (w / 2 + 4) * side
            m.box("concrete", (sx, y - 0.3, sz), u, L + 9, 1.4, 8)  # overlap the next slab so bends stay continuous
            cx, cz = mx + n[0] * (w / 2 + 0.3) * side, mz + n[1] * (w / 2 + 0.3) * side
            m.box("trim", (cx, y - 0.1, cz), u, L, 1.0, 0.6)
        if w >= 20:  # dashed centre line
            for k in range(int(L // 12)):
                t = (k + 0.5) * 12 - L / 2
                m.box("paint", (mx + u[0] * t, y + 0.02, mz + u[1] * t), u, 5, 0.05, 0.5, (230, 200, 60) if w < 40 else (250, 250, 250))
        lights += L
        if lights > 70:  # street light on the sidewalk
            lights = 0
            sx, sz = mx + n[0] * (w / 2 + 2), mz + n[1] * (w / 2 + 2)
            m.box("pole", (sx, y + 9, sz), u, 0.6, 18, 0.6)
            m.box("pole", (sx - n[0] * 2.5, y + 17.8, sz - n[1] * 2.5), (n[0], n[1]), 5, 0.4, 0.4)
            m.box("lamp", (sx - n[0] * 4.6, y + 17.4, sz - n[1] * 4.6), (n[0], n[1]), 1.6, 0.4, 1)
    return m.finish()


def hero_shots(detailed, gy, preset):
    """Four fixed eye-level views (6.5 studs, ~1.7 m) to judge realism where players stand; one contact sheet."""
    import math as _m
    from PIL import Image

    def local_cam(b, eye, look):  # building-local (x along the street, z away from it) -> world camera
        c, sn = _m.cos(_m.radians(b["rot"])), _m.sin(_m.radians(b["rot"]))
        w = lambda lx, lz: (b["x"] + c * lx - sn * lz, b["z"] + s_ * 0 + sn * lx + c * lz)  # noqa: E731
        ex, ez = w(eye[0], eye[1])
        tx, tz = w(look[0], look[1])
        return (ex, -ez, gy + 6.5), (tx, -tz, gy + look[2])
    s_ = 0
    near = lambda style: min((b for _, b in detailed if b["style"] == style), key=lambda b: _m.hypot(b["x"] - CX, b["z"] - CZ))  # noqa: E731
    shots = []
    shop, house = near("stucco"), near("house")
    shots.append(local_cam(shop, (-18, -shop["d"] / 2 - 48), (4, -shop["d"] / 2, 7)))
    shots.append(local_cam(house, (16, -house["d"] / 2 - 40), (-2, 0, 7)))
    paths = realism.HERO_SPOTS.get("paths") or []
    if paths:
        pth = max(paths, key=lambda g: g.area)
        ring = pth.exterior
        p0, p1 = ring.interpolate(0.1, normalized=True), ring.interpolate(0.18, normalized=True)
        shots.append(((p0.x, -p0.y, gy + 6.5), (p1.x, -p1.y, gy + 5)))
    paved = [g for g in (realism.HERO_SPOTS.get("paved") or []) if not g.is_empty]
    if paved:
        lot = max(paved, key=lambda g: g.area)
        c0 = lot.representative_point()
        x0, z0, x1, z1 = lot.bounds
        shots.append(((x0 + 4, -(z0 + 4), gy + 6.5), (c0.x, -c0.y, gy + 6)))
    names = []
    for k, (pos, tgt) in enumerate(shots):
        realism.real_camera(pos, tgt, 30, focus=50, fstop=11)
        name = f"hero_{k + 1}_{preset}"
        render(name)
        realism.lens(f"screenshots/{name}.png")
        names.append(f"screenshots/{name}.png")
    ims = [Image.open(n).resize((640, 360)) for n in names]
    sheet = Image.new("RGB", (1280, 360 * ((len(ims) + 1) // 2)))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % 2) * 640, (i // 2) * 360))
    sheet.save(f"screenshots/hero_{preset}.png")
    print("wrote", f"screenshots/hero_{preset}.png")


def main_real():
    """Hyper-real render of the block (realism.py): real materials, bevels, proper streets, street life."""
    import math as _m
    from shapely.geometry import Polygon as SPoly
    from shapely.ops import unary_union as union
    rng = random.Random(7)
    reset()
    s = bpy.context.scene
    s.render.resolution_x, s.render.resolution_y = 1920, 1080
    s.cycles.samples = 96
    s.cycles.use_denoising = True
    if "--quick" in sys.argv:
        s.render.resolution_x, s.render.resolution_y, s.cycles.samples = (960, 540, 20) if "--hero" in sys.argv else (1280, 720, 24)
    zone = (CX - R, CZ - R, CX + R, CZ + R)
    in_zone = lambda x, z: zone[0] < x < zone[2] and zone[1] < z < zone[3]  # noqa: E731
    detailed, keep = [], set()
    for i, b in enumerate(W["buildings"]):
        if in_zone(b["x"], b["z"]):
            detailed.append((i + 1, b))
            keep.add(f"b{i + 1}")
    T["pieces"] = [p for p in T["pieces"] if p["g"] not in keep and not (p["shape"] == "box" and abs(p["s"][1] - 1.2) < 0.01 and in_zone(p["p"][0], p["p"][2]))]
    hero_spots = [it for it in T["items"] if in_zone(it[1], it[2]) and it[0] in ("PalmCoconut", "PalmCabbage", "LiveOak")]
    T["items"] = [it for it in T["items"] if it not in hero_spots]
    build_terrain(T)
    gy = ground(CX, CZ)
    objs = [building(i, b) for i, b in detailed]
    realism.realify(objs, gy)
    roads = [r for r in W["roads"] if in_zone((r["ax"] + r["bx"]) / 2, (r["az"] + r["bz"]) / 2) and r["kind"] not in ("freeway", "ramp", "drive")]
    asphalt, junctions, walk_outer = realism.streets(roads, zone, gy)
    palms = [realism.hero_palm(k) for k in range(4)]
    oaks = [realism.hero_oak(k) for k in range(2)]
    realism.photo_upgrade()
    for name, x, z, y, rot, sc in hero_spots:
        realism.place(rng.choice(oaks if name == "LiveOak" else palms), x, z, y, _m.radians(rot), sc)
    r = min(roads, key=lambda r: _m.hypot((r["ax"] + r["bx"]) / 2 - CX, (r["az"] + r["bz"]) / 2 - CZ) - _m.hypot(r["bx"] - r["ax"], r["bz"] - r["az"]) * 2)
    realism.street_life(roads, asphalt, junctions, detailed, zone, gy, rng, no_cars=r)
    realism.signs(SIGNS)
    realism.weather(objs)
    realism.haze(CX, CZ, gy)
    lawn, beds, fences = realism.landcover(detailed, walk_outer, zone, gy, rng, palms, oaks, ground)
    realism.PLANTS.update(realism.florida_plants())
    print("bed plants:", realism.plant_beds(beds, gy, rng, walk_outer.buffer(10)))
    print("fence plants:", realism.plants_on_fences(fences, gy, rng, realism.PLANTS))
    preset = next((a.split("=")[1] for a in sys.argv if a.startswith("--time=")), "day")
    realism.clutter(roads, asphalt, walk_outer, zone, gy, rng, wet=preset in ("rain", "night", "dusk"))
    realism.real_trees(oaks, palms)
    terrain = bpy.data.objects["ground"]
    realism.grass(terrain, (CX - 220, CZ - 220, CX + 220, CZ + 220), lawn)
    Lr = _m.hypot(r["bx"] - r["ax"], r["bz"] - r["az"])
    realism.time_of_day(preset, ((r["bx"] - r["ax"]) / Lr, (r["bz"] - r["az"]) / Lr))
    if "--hero" in sys.argv:
        hero_shots(detailed, gy, preset)
        return
    # 1) street level on the sidewalk, mid-block, looking along the most central street
    L = _m.hypot(r["bx"] - r["ax"], r["bz"] - r["az"])
    ux, uz = (r["bx"] - r["ax"]) / L, (r["bz"] - r["az"]) / L
    ex, ez = r["ax"] + ux * L * 0.3 - uz * (r["width"] / 2 + 5), r["az"] + uz * L * 0.3 + ux * (r["width"] / 2 + 5)
    realism.real_camera((ex, -ez, gy + 7), (ex + ux * 120 + uz * 8, -(ez + uz * 120 - ux * 8), gy + 9), 30, focus=60, fstop=11)
    render(f"real_street_{preset}")
    realism.lens(f"screenshots/real_street_{preset}.png")
    # 2) low aerial over the block
    realism.real_camera((CX + 240, -(CZ + 220), gy + 150), (CX - 10, -(CZ - 10), gy + 5), 35)
    if preset == "day":
        render("real_aerial")
        realism.lens("screenshots/real_aerial.png")


def main():
    reset()
    s = bpy.context.scene
    s.cycles.samples = 48
    s.view_settings.view_transform, s.view_settings.look, s.view_settings.exposure = "Standard", "None", -4.5
    in_zone = lambda x, z: abs(x - CX) < R and abs(z - CZ) < R  # noqa: E731
    keep = set()
    detailed = []
    for i, b in enumerate(W["buildings"]):
        if in_zone(b["x"], b["z"]):
            detailed.append((i + 1, b))  # Luau index, as in greybox piece groups
            keep.add(f"b{i + 1}")
    # greybox outside the zone (and freeways / elevated bits inside it); detailed models inside
    T["pieces"] = [p for p in T["pieces"] if p["g"] not in keep and not (p["shape"] == "box" and abs(p["s"][1] - 1.2) < 0.01 and in_zone(p["p"][0], p["p"][2]))]
    build_terrain(T)
    zone_roads = [r for r in W["roads"] if in_zone((r["ax"] + r["bx"]) / 2, (r["az"] + r["bz"]) / 2) and r["kind"] not in ("freeway", "ramp", "drive")]
    objs = [building(i, b) for i, b in detailed]
    streets(zone_roads)
    tris = [sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs]
    print(f"{len(objs)} detailed buildings, {sum(tris)} triangles (max {max(tris)} per building), {len(zone_roads)} street segments")
    if "--export" in sys.argv:
        os.makedirs("assets/roblox/buildings", exist_ok=True)
        for o in objs:
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.export_scene.fbx(filepath=f"assets/roblox/buildings/{o.name}.fbx", use_selection=True, axis_forward="-Z", axis_up="Y")
    sky(35, 200)
    gy = ground(CX, CZ)
    camera((CX + 330, -(CZ + 300), gy + 230), (CX - 20, -(CZ - 10), gy), 32)
    render("detail_aerial")
    # street level: along the longest street segment near the centre
    r = min(zone_roads, key=lambda r: math.hypot((r["ax"] + r["bx"]) / 2 - CX, (r["az"] + r["bz"]) / 2 - CZ) - math.hypot(r["bx"] - r["ax"], r["bz"] - r["az"]) * 2)
    L = math.hypot(r["bx"] - r["ax"], r["bz"] - r["az"])
    ux, uz = (r["bx"] - r["ax"]) / L, (r["bz"] - r["az"]) / L
    ex, ez = r["ax"] - ux * 20 + uz * (r["width"] / 2 + 3), r["az"] - uz * 20 - ux * (r["width"] / 2 + 3)
    camera((ex, -ez, ground(ex, ez) + 6.5), (ex + ux * 100, -(ez + uz * 100), ground(ex, ez) + 9), 26)
    render("detail_street")


if "--real" in sys.argv:
    main_real()
else:
    main()
