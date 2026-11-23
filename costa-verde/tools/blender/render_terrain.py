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
    # grey road strips (Roblox: grey parts), on the ground or at deck height on bridges
    def gh(x, z):
        i = min(nx - 1, max(0, int((x - x0) / res)))
        j = min(nz - 1, max(0, int((z - z0) / res)))
        return c["h"][j * nx + i]
    rv, rf = [], []
    for ax, az, bx, bz, wdt, bridge in c.get("roads", []):
        L = math.hypot(bx - ax, bz - az) or 1
        px, pz = -(bz - az) / L * wdt / 2, (bx - ax) / L * wdt / 2
        ha, hb = (max(gh(ax, az), 2) + 6, max(gh(bx, bz), 2) + 6) if bridge else (gh(ax, az) + 0.4, gh(bx, bz) + 0.4)
        n = len(rv)
        rv += [P(ax + px, az + pz, ha), P(bx + px, bz + pz, hb), P(bx - px, bz - pz, hb), P(ax - px, az - pz, ha)]
        rf.append((n, n + 1, n + 2, n + 3))
    rm = bpy.data.meshes.new("roads")
    rm.from_pydata(rv, [], rf)
    ro = bpy.data.objects.new("roads", rm)
    bpy.context.collection.objects.link(ro)
    m = bpy.data.materials.new("road")
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.09, 0.09, 0.09, 1)
    rm.materials.append(m)
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
    # close-up along a rural road, low like a player's view, to show ditches, verges and canals
    rural = [r for r in c.get("roads", []) if r[4] <= 30 and not r[5] and math.hypot(r[2] - r[0], r[3] - r[1]) > 20
             and abs(r[0] - cx) < half * 0.6 and abs(r[1] - cz) < half * 0.6]
    if rural:
        ax, az, bx, bz = rural[len(rural) // 2][:4]
        L = math.hypot(bx - ax, bz - az)
        ux, uz = (bx - ax) / L, (bz - az) / L
        i = min(c["nx"] - 1, max(0, int((ax - c["x0"]) / c["res"])))
        j = min(c["nz"] - 1, max(0, int((az - c["z0"]) / c["res"])))
        g = c["h"][j * c["nx"] + i]
        camera(P(ax - ux * 60 - uz * 30, az - uz * 60 + ux * 30, g + 22), P(ax + ux * 140, az + uz * 140, g), 30)
        render(f"terrain_{name}_close")
