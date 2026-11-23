"""Export the street level of the detailed block for Roblox (buildings: export_block_roblox.py).

Builds the same scene as the hyper-real render (detail_town.main_real, without grass strands), then writes:
  surfaces  -> build/roblox_block/env/<name>.fbx: streets, sidewalks, lots, fences, paint, drains... (tiled under
               Roblox's 20k-triangle limit); Roblox materials and colours per surface are in the manifest
  models    -> build/roblox_block/env/m_<name>.fbx: each distinct prop / plant / tree / car once, leaves made real
  placements-> every instance (model, position, yaw, scale) in Roblox coordinates
plus leaf.png (leaf card colour + alpha) and src/shared/BlockEnvManifest.luau.
Usage (from costa-verde/): python tools/blender/export_block_env.py"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402
import bmesh  # noqa: E402  (must come after bpy)
from mathutils import Vector  # noqa: E402

import detail_town as dt  # noqa: E402

OUT = "build/roblox_block/env"
OFFSET = -40960 / 2
LIMIT = 19000
# Roblox look per surface (material, colour); anything else falls back to SmoothPlastic grey
SURFACES = {
    "asphalt": ("Asphalt", (58, 58, 60)), "lots": ("Asphalt", (66, 66, 68)), "sidewalk": ("Concrete", (188, 184, 176)),
    "path": ("Concrete", (196, 192, 184)), "stalls": ("SmoothPlastic", (232, 232, 226)), "paint_white": ("SmoothPlastic", (232, 232, 226)),
    "paint_yellow": ("SmoothPlastic", (222, 180, 50)), "mulch": ("Ground", (92, 66, 48)), "dirt": ("Ground", (150, 130, 100)),
    "fences": ("WoodPlanks", (170, 140, 104)), "manholes": ("Metal", (70, 68, 64)), "drains": ("Metal", (30, 30, 30)),
    "tar_snakes": ("SmoothPlastic", (12, 12, 12)), "puddles": ("Glass", (30, 34, 38)), "wires": ("SmoothPlastic", (20, 20, 20)),
    "frond": ("Fabric", (140, 110, 70)),
}


def rb(v):  # Blender world -> Roblox world
    return [round(v.x + OFFSET, 3), round(v.z, 3), round(-v.y + OFFSET, 3)]


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, use_mesh_modifiers=True, axis_forward="-Z", axis_up="Y", path_mode="STRIP")


def tiles(o):
    """Split a mesh into grid tiles until each is under the triangle limit."""
    n = 1
    while tris(o) / (n * n) > LIMIT * 0.7:
        n += 1
    if n == 1:
        return [o]
    xs = [(o.matrix_world @ Vector(v)).x for v in o.bound_box]
    ys = [(o.matrix_world @ Vector(v)).y for v in o.bound_box]
    x0, y0, sx, sy = min(xs), min(ys), (max(xs) - min(xs)) / n + 1e-6, (max(ys) - min(ys)) / n + 1e-6
    out = []
    for i in range(n):
        for j in range(n):
            me = o.data.copy()
            bm = bmesh.new()
            bm.from_mesh(me)
            drop = [f for f in bm.faces if not (i <= int(((o.matrix_world @ f.calc_center_median()).x - x0) // sx) <= i
                                                and j <= int(((o.matrix_world @ f.calc_center_median()).y - y0) // sy) <= j)]
            bmesh.ops.delete(bm, geom=drop, context="FACES")
            bm.to_mesh(me)
            bm.free()
            if len(me.polygons):
                t = bpy.data.objects.new(f"{o.name}_{i}{j}", me)
                t.matrix_world = o.matrix_world.copy()
                bpy.context.collection.objects.link(t)
                out.append(t)
    return out


def realize(coll):
    """Instance a collection at the origin with particles made real; returns one joined mesh object."""
    root = bpy.data.objects.new("tmp_" + coll.name, None)
    root.instance_type, root.instance_collection = "COLLECTION", coll
    bpy.context.collection.objects.link(root)
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.object.duplicates_make_real(use_base_parent=False, use_hierarchy=False)
    made = [o for o in bpy.context.selected_objects if o.type in ("MESH", "CURVE")]
    for o in list(made):  # leaf cards on particle emitters become real geometry
        for md in list(o.modifiers):
            if md.type == "PARTICLE_SYSTEM":
                st = md.particle_system.settings
                if st.count > 6000:
                    st.count = 6000  # shortcut: fewer leaves than the render so one tree fits a Roblox mesh; raise via LOD later
                bpy.ops.object.select_all(action="DESELECT")
                o.select_set(True)
                bpy.context.view_layer.objects.active = o
                bpy.ops.object.duplicates_make_real()
                made += [p for p in bpy.context.selected_objects if p is not o and p.type == "MESH"]
                if not o.show_instancer_for_render:
                    made.remove(o)
                    o.hide_render = True
                o.modifiers.remove(md)
    bpy.data.objects.remove(root)
    meshes = []
    for o in made:
        if o.type == "CURVE":
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.convert(target="MESH")
            o = bpy.context.view_layer.objects.active
        if o.type == "MESH" and not o.hide_render:
            meshes.append(o)
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        for md in list(o.modifiers):  # bake displacement / bevel / boolean into the mesh
            try:
                bpy.ops.object.modifier_apply(modifier=md.name)
            except RuntimeError:
                o.modifiers.remove(md)
    if not meshes:
        return None
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    m = bpy.context.view_layer.objects.active
    m.name = "m_" + coll.name
    return m


def leaf_png():
    import numpy as np
    from PIL import Image
    c = np.asarray(Image.open("assets/cc0/Leaf001/Leaf001_1K-JPG_Color.jpg").convert("RGB"))
    a = np.asarray(Image.open("assets/cc0/Leaf001/Leaf001_1K-JPG_Opacity.jpg").convert("L"))
    Image.fromarray(np.dstack([c, a])).resize((512, 512)).save(f"{OUT}/leaf.png")


def main():
    os.makedirs(OUT, exist_ok=True)
    dt.main_real(build_only=True)
    manifest = {"surfaces": [], "models": {}, "placements": []}
    # surfaces
    frond = [o for o in bpy.data.objects if o.name.startswith("frond") and o.type == "MESH"]
    if len(frond) > 1:
        bpy.ops.object.select_all(action="DESELECT")
        for o in frond:
            o.select_set(True)
        bpy.context.view_layer.objects.active = frond[0]
        bpy.ops.object.join()
    wires = bpy.data.objects.get("wires")
    if wires:
        bpy.ops.object.select_all(action="DESELECT")
        wires.select_set(True)
        bpy.context.view_layer.objects.active = wires
        bpy.ops.object.convert(target="MESH")
    for o in list(bpy.data.objects):
        key = next((k for k in SURFACES if o.name.startswith(k)), None)
        if key is None or o.type != "MESH" or not len(o.data.polygons):
            continue
        for t in tiles(o):
            export([t], f"{OUT}/{t.name}.fbx")
            bb = [t.matrix_world @ Vector(v) for v in t.bound_box]
            centre = sum(bb, Vector()) / 8
            mat, col = SURFACES[key]
            manifest["surfaces"].append({"name": t.name, "center": rb(centre), "material": mat, "color": col, "tris": tris(t)})
    # models + placements
    instances = [o for o in bpy.data.objects if o.type == "EMPTY" and o.instance_collection and not o.name.startswith("tmp_")]
    for coll in {o.instance_collection for o in instances}:
        m = realize(coll)
        if m is None:
            continue
        bb = [m.matrix_world @ Vector(v) for v in m.bound_box]
        c = sum(bb, Vector()) / 8
        leafy = any(mt and "leaf_card" in mt.name for mt in m.data.materials)
        export([m], f"{OUT}/{m.name}.fbx")
        manifest["models"][m.name] = {"offset": [round(c.x, 3), round(c.z, 3), round(-c.y, 3)], "tris": tris(m), "leaf": leafy,
                                      "over_limit": tris(m) > 20000}
        bpy.data.objects.remove(m)
    for o in instances:
        manifest["placements"].append({"model": "m_" + o.instance_collection.name, "pos": rb(o.location),
                                       "yaw": round(o.rotation_euler.z, 4), "scale": round(o.scale.x, 3)})
    leaf_png()
    json.dump(manifest, open(f"{OUT}/manifest.json", "w"), indent=1)
    with open("src/shared/BlockEnvManifest.luau", "w") as f:
        f.write("-- Generated by tools/blender/export_block_env.py. Do not edit.\nreturn [==[" + json.dumps(manifest) + "]==]\n")
    over = [k for k, v in manifest["models"].items() if v["over_limit"]]
    print(f"{len(manifest['surfaces'])} surface meshes, {len(manifest['models'])} models, {len(manifest['placements'])} placements; "
          f"models over 20k triangles: {over or 'none'}")
    _ = math


main()
