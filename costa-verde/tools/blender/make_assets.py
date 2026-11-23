"""Procedural low-poly Florida vegetation and shoreline props, exported as FBX for Roblox's 3D Importer.
Every asset is built by code (no downloaded models). Units: 1 Blender unit = 1 stud; origin at the base
centre, +Z up (the FBX exporter converts to Roblox's Y-up). Each colour is its own material, so the
importer makes one MeshPart per material; src/shared/Vegetation.luau colours them from ASSET_COLORS.

Usage (from costa-verde/): python tools/blender/make_assets.py   -> assets/roblox/<name>.fbx
Also imported by render_terrain.py to instance the same models in previews."""
import math
import os
import random

import bpy
import bmesh  # must come after bpy when running as a module
from mathutils import Matrix, Vector

# sRGB colours per material slot (mirrored in Vegetation.luau ASSET_COLORS)
COLORS = {
    "trunk": (112, 92, 70), "palm_leaf": (86, 128, 52), "oak_leaf": (52, 84, 40), "pine_leaf": (70, 96, 50),
    "mangrove_leaf": (46, 78, 38), "palmetto_leaf": (98, 130, 70), "sawgrass": (150, 150, 86), "seaoats": (206, 190, 140),
    "root": (96, 82, 64), "wood": (140, 112, 80), "rock": (150, 146, 136), "buoy_red": (200, 50, 40), "buoy_white": (235, 235, 230),
    "coconut": (110, 90, 40),
}
TRIS_LIMIT = 10000  # Roblox MeshParts allow 20k; stay well under


def lin(c):
    return tuple(((v / 255 + 0.055) / 1.055) ** 2.4 if v / 255 > 0.04045 else v / 255 / 12.92 for v in c)


def material(name):
    m = bpy.data.materials.get(name)
    if not m:
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lin(COLORS[name]), 1)
        m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.85
        m.diffuse_color = (*lin(COLORS[name]), 1)
    return m


class Builder:
    """Accumulates geometry per material into one bmesh, then makes a single object."""

    def __init__(self):
        self.bm = bmesh.new()
        self.mats = []

    def slot(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def add(self, geom_fn, mat, matrix=Matrix()):
        tmp = bmesh.new()
        geom_fn(tmp)
        bmesh.ops.transform(tmp, matrix=matrix, verts=tmp.verts)
        idx = self.slot(mat)
        for f in tmp.faces:
            f.material_index = idx
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        tmp.free()

    def finish(self, name):
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in self.mats:
            me.materials.append(material(m))
        for p in me.polygons:
            p.use_smooth = False
        o = bpy.data.objects.new(name, me)
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        assert tris < TRIS_LIMIT, f"{name}: {tris} triangles"
        return o


def cyl(r0, r1, h, seg=7):
    def f(bm):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r0, radius2=r1, depth=h, matrix=Matrix.Translation((0, 0, h / 2)))
    return f


def blob(r, sub=1):
    def f(bm):
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)
    return f


def leaf(length, width, droop):
    """A tapered frond along +X that droops by `droop` at its tip (3 segments)."""
    def f(bm):
        n = 4
        left, right = [], []
        for i in range(n + 1):
            t = i / n
            x, z = length * t, -droop * t * t
            w = width * math.sin(math.pi * min(1, t * 1.1 + 0.05)) * 0.5
            left.append(bm.verts.new((x, w, z)))
            right.append(bm.verts.new((x, -w, z)))
        for i in range(n):
            bm.faces.new((left[i], right[i], right[i + 1], left[i + 1]))
    return f


def trunk_path(b, pts, r0, r1, mat="trunk"):
    """Bent trunk as stacked cylinders between points."""
    for i in range(len(pts) - 1):
        a, c = Vector(pts[i]), Vector(pts[i + 1])
        d = c - a
        r_a = r0 + (r1 - r0) * i / (len(pts) - 1)
        r_c = r0 + (r1 - r0) * (i + 1) / (len(pts) - 1)
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        b.add(cyl(r_a, r_c, d.length, 6), mat, Matrix.Translation(a) @ rot)


def crown(b, top, n, length, width, droop, mat, tilt=0.0, rng=None):
    for i in range(n):
        a = 2 * math.pi * i / n + (rng.uniform(-0.2, 0.2) if rng else 0)
        up = math.radians(25 + (rng.uniform(-15, 15) if rng else 0)) - tilt
        m = Matrix.Translation(top) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Rotation(-up, 4, "Y")
        b.add(leaf(length, width, droop), mat, m)


def coconut_palm(seed=1):
    rng = random.Random(seed)
    b = Builder()
    lean = rng.uniform(4, 9)
    pts = [(0, 0, 0), (lean * 0.15, 0, 14), (lean * 0.5, 0, 28), (lean, 0, 40)]
    trunk_path(b, pts, 1.3, 0.8)
    crown(b, Vector(pts[-1]), 11, 13, 3.2, 6, "palm_leaf", rng=rng)
    for i in range(4):
        a = i * math.pi / 2
        b.add(blob(0.8, 1), "coconut", Matrix.Translation(Vector(pts[-1]) + Vector((math.cos(a), math.sin(a), -1.2))))
    return b.finish("PalmCoconut")


def cabbage_palm(seed=2):
    rng = random.Random(seed)
    b = Builder()
    trunk_path(b, [(0, 0, 0), (0.5, 0, 18), (0.8, 0, 34)], 1.1, 1.0)
    top = Vector((0.8, 0, 34))
    crown(b, top, 12, 8, 3.5, 3.5, "palm_leaf", rng=rng)  # round head: a ring of drooping fans
    crown(b, top + Vector((0, 0, 1)), 8, 6, 3.2, 0.5, "palm_leaf", tilt=-0.7, rng=rng)  # and upright ones
    return b.finish("PalmCabbage")


def live_oak(seed=3):
    rng = random.Random(seed)
    b = Builder()
    b.add(cyl(2.2, 1.6, 9, 7), "trunk")
    for i in range(4):  # low spreading limbs
        a = i * math.pi / 2 + rng.uniform(-0.4, 0.4)
        end = Vector((math.cos(a) * 14, math.sin(a) * 14, 15))
        trunk_path(b, [(0, 0, 8), tuple(end)], 1.2, 0.6)
    for _ in range(9):  # broad, flattened canopy
        p = Vector((rng.uniform(-15, 15), rng.uniform(-15, 15), rng.uniform(16, 22)))
        b.add(blob(rng.uniform(6, 9), 1), "oak_leaf", Matrix.Translation(p) @ Matrix.Diagonal((1.2, 1.2, 0.6, 1)))
    return b.finish("LiveOak")


def slash_pine(seed=4):
    rng = random.Random(seed)
    b = Builder()
    trunk_path(b, [(0, 0, 0), (0.4, 0, 30), (0.2, 0, 58)], 1.2, 0.6)
    for _ in range(6):  # small clumps high up
        p = Vector((rng.uniform(-5, 5), rng.uniform(-5, 5), rng.uniform(44, 60)))
        b.add(blob(rng.uniform(3, 5), 1), "pine_leaf", Matrix.Translation(p) @ Matrix.Diagonal((1.3, 1.3, 0.55, 1)))
    return b.finish("SlashPine")


def mangrove(seed=5):
    rng = random.Random(seed)
    b = Builder()
    for i in range(9):  # arching prop roots from the trunk down into the water
        a = 2 * math.pi * i / 9 + rng.uniform(-0.2, 0.2)
        r = rng.uniform(5, 8)
        trunk_path(b, [(0, 0, 8), (math.cos(a) * r * 0.5, math.sin(a) * r * 0.5, 7), (math.cos(a) * r, math.sin(a) * r, -1)], 0.35, 0.25, "root")
    b.add(cyl(0.9, 0.7, 12, 6), "trunk", Matrix.Translation((0, 0, 6)))
    for _ in range(8):
        p = Vector((rng.uniform(-6, 6), rng.uniform(-6, 6), rng.uniform(13, 18)))
        b.add(blob(rng.uniform(4, 6), 1), "mangrove_leaf", Matrix.Translation(p) @ Matrix.Diagonal((1.2, 1.2, 0.75, 1)))
    return b.finish("Mangrove")


def palmetto(seed=6):
    rng = random.Random(seed)
    b = Builder()
    for _ in range(4):  # several fans per clump
        base = Vector((rng.uniform(-2, 2), rng.uniform(-2, 2), 0))
        crown(b, base + Vector((0, 0, 2)), 6, 4.5, 3, 1.2, "palmetto_leaf", tilt=-0.4, rng=rng)
    return b.finish("Palmetto")


def grass_clump(name, mat, height, seed):
    rng = random.Random(seed)
    b = Builder()
    for _ in range(14):
        a, r = rng.uniform(0, 2 * math.pi), rng.uniform(0, 1.5)
        h = height * rng.uniform(0.7, 1.1)
        m = Matrix.Translation((math.cos(a) * r, math.sin(a) * r, 0)) @ Matrix.Rotation(rng.uniform(-0.35, 0.35), 4, Vector((math.sin(a), -math.cos(a), 0)))
        b.add(cyl(0.25, 0.02, h, 3), mat, m)
    return b.finish(name)


def dock(seed=7):
    b = Builder()
    for i in range(10):  # planks across a 12 x 40 deck at 4 studs above water
        b.add(lambda bm: bmesh.ops.create_cube(bm, size=1), "wood", Matrix.Translation((0, -18 + i * 4, 4)) @ Matrix.Diagonal((12, 3.6, 0.6, 1)))
    for x in (-5.5, 5.5):
        for y in (-18, -6, 6, 18):
            b.add(cyl(0.6, 0.6, 12, 6), "wood", Matrix.Translation((x, y, -7)))
    return b.finish("DockSection")


def piling():
    b = Builder()
    b.add(cyl(0.8, 0.75, 14, 8), "wood", Matrix.Translation((0, 0, -6)))
    return b.finish("Piling")


def buoy():
    b = Builder()
    b.add(cyl(1.2, 1.4, 2, 8), "buoy_white")
    b.add(cyl(0.9, 0.2, 4, 8), "buoy_red", Matrix.Translation((0, 0, 2)))
    return b.finish("Buoy")


def riprap(seed=8):
    rng = random.Random(seed)
    b = Builder()
    for _ in range(9):
        p = Vector((rng.uniform(-6, 6), rng.uniform(-3, 3), rng.uniform(-0.5, 1)))
        s = rng.uniform(1.5, 2.8)
        b.add(blob(s, 0), "rock", Matrix.Translation(p) @ Matrix.Rotation(rng.uniform(0, 3), 4, "Z") @ Matrix.Diagonal((1.3, 1, 0.7, 1)))
    return b.finish("Riprap")


ASSETS = {
    "PalmCoconut": coconut_palm, "PalmCabbage": cabbage_palm, "LiveOak": live_oak, "SlashPine": slash_pine,
    "Mangrove": mangrove, "Palmetto": palmetto,
    "Sawgrass": lambda: grass_clump("Sawgrass", "sawgrass", 5, 9), "SeaOats": lambda: grass_clump("SeaOats", "seaoats", 4, 10),
    "DockSection": dock, "Piling": piling, "Buoy": buoy, "Riprap": riprap,
}


def build_all():
    """Objects for every asset (not linked to a scene)."""
    return {name: fn() for name, fn in ASSETS.items()}


if __name__ == "__main__":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs("assets/roblox", exist_ok=True)
    for name, obj in build_all().items():
        bpy.context.collection.objects.link(obj)
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.export_scene.fbx(filepath=f"assets/roblox/{name}.fbx", use_selection=True, apply_unit_scale=True,
                                 axis_forward="-Z", axis_up="Y", mesh_smooth_type="FACE")
        tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
        print(f"{name}: {tris} triangles, {len(obj.data.materials)} materials -> assets/roblox/{name}.fbx")
