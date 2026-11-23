"""Blender preview of the Roblox terrain exactly as src/shared/TerrainBuilder.luau writes it (4-stud
columns, its materials and Florida palette, water at each body's level). Run after
`lune run tools/export-terrain.luau`. Usage (from costa-verde/): python tools/blender/render_terrain.py [area ...]"""
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402
from render_world import P, camera, render, reset, sky  # noqa: E402

SRC = open("src/shared/TerrainBuilder.luau").read()
block = SRC[SRC.index("TerrainBuilder.PALETTE = {"):SRC.index("}\nTerrainBuilder.WATER")]
PALETTE = {m: tuple(int(v) for v in rgb) for m, *rgb in re.findall(r"(\w+) = \{ (\d+), (\d+), (\d+) \}", block)}
WATER = tuple(int(v) for v in re.search(r"WATER = \{ color = \{ (\d+), (\d+), (\d+) \}", SRC).groups())


def lin(c):  # sRGB 0-255 -> linear
    return tuple(((v / 255 + 0.055) / 1.055) ** 2.4 if v / 255 > 0.04045 else v / 255 / 12.92 for v in c)


def build(c):
    nx, nz, res, x0, z0 = c["nx"], c["nz"], c["res"], c["x0"], c["z0"]
    me = bpy.data.meshes.new("ground")
    me.from_pydata([P(x0 + (i + 0.5) * res, z0 + (j + 0.5) * res, c["h"][j * nx + i]) for j in range(nz) for i in range(nx)], [],
                   [(j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i) for j in range(nz - 1) for i in range(nx - 1)])
    col = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    L = {m: lin(v) for m, v in PALETTE.items()}
    for k, m in enumerate(c["material"]):
        col.data[k].color = (*L[m], 1)
    o = bpy.data.objects.new("ground", me)
    bpy.context.collection.objects.link(o)
    m = bpy.data.materials.new("ground")
    m.use_nodes = True
    a = m.node_tree.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "col"
    b = m.node_tree.nodes["Principled BSDF"]
    m.node_tree.links.new(a.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.95
    me.materials.append(m)
    # water: a quad wherever a corner has water, at that body's level
    wv, wf, idx = [], [], {}
    for j in range(nz - 1):
        for i in range(nx - 1):
            ks = [j * nx + i, j * nx + i + 1, (j + 1) * nx + i + 1, (j + 1) * nx + i]
            lv = [c["water"][k] for k in ks if c["water"][k] is not False]
            if not lv or max(lv) <= min(c["h"][k] for k in ks):  # like Roblox: water only where it's above the ground
                continue
            face = []
            for k in ks:
                if k not in idx:
                    idx[k] = len(wv)
                    wv.append(P(x0 + (k % nx + 0.5) * res, z0 + (k // nx + 0.5) * res, max(lv)))
                face.append(idx[k])
            wf.append(face)
    wm = bpy.data.meshes.new("water")
    wm.from_pydata(wv, [], wf)
    wo = bpy.data.objects.new("water", wm)
    bpy.context.collection.objects.link(wo)
    m = bpy.data.materials.new("water")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin(WATER), 1)
    b.inputs["Roughness"].default_value = 0.05
    b.inputs["Transmission Weight"].default_value = 0.55
    b.inputs["IOR"].default_value = 1.33
    wm.materials.append(m)


for name in sys.argv[1:] or ["keys", "wetland", "beach", "country"]:
    c = json.load(open(f"build/terrain_{name}.json"))
    s = reset()
    s.cycles.samples = 32
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    s.view_settings.exposure = -4.5
    build(c)
    sky(40, 135)
    cx, cz, half = c["x0"] + c["nx"] * c["res"] / 2, c["z0"] + c["nz"] * c["res"] / 2, c["nx"] * c["res"] / 2
    camera(P(cx + half * 0.55, cz + half * 0.75, 320), P(cx - half * 0.05, cz - half * 0.1, 0), 24)
    render(f"terrain_{name}")
