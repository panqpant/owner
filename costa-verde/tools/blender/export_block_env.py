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
    "frond": ("Fabric", (140, 110, 70)), "sign": ("SmoothPlastic", (244, 240, 228)),
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
    """One mesh for a collection, read straight from the evaluated scene: modifiers applied, particle leaves
    included, materials kept. No temporary objects or operators, so it stays fast and light on memory."""
    for o in coll.all_objects:
        for ps in getattr(o, "particle_systems", []):
            if ps.settings.count > 6000:
                ps.settings.count = 6000  # shortcut: fewer leaves than the render so one tree fits a Roblox mesh; LODs later
    root = bpy.data.objects.new("tmp_" + coll.name, None)
    root.instance_type, root.instance_collection = "COLLECTION", coll
    bpy.context.collection.objects.link(root)
    dg = bpy.context.evaluated_depsgraph_get()
    mats, bm = [], bmesh.new()
    for inst in dg.object_instances:
        if not inst.is_instance or inst.parent is None or inst.parent.original != root:
            continue
        ob = inst.object
        src = ob.original
        if ob.type not in ("MESH", "CURVE", "FONT") or src.hide_render:
            continue
        if src.particle_systems and not src.show_instancer_for_render:  # hidden leaf emitter
            continue
        me = bpy.data.meshes.new_from_object(ob, preserve_all_data_layers=True, depsgraph=dg)
        me.transform(inst.matrix_world)
        remap = []
        for m in me.materials:
            if m not in mats:
                mats.append(m)
            remap.append(mats.index(m))
        for poly in me.polygons:
            poly.material_index = remap[poly.material_index] if remap else 0
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    bpy.data.objects.remove(root)
    if not bm.faces:
        bm.free()
        return None
    me = bpy.data.meshes.new("m_" + coll.name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new("m_" + coll.name, me)
    bpy.context.collection.objects.link(o)
    return o


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
    import time
    t0 = time.time()
    # placements first, then strip everything not exported so each Blender operation works on a near-empty scene
    instances = [o for o in bpy.data.objects if o.type == "EMPTY" and o.instance_collection]
    for o in instances:
        manifest["placements"].append({"model": "m_" + o.instance_collection.name, "pos": rb(o.location),
                                       "yaw": round(o.rotation_euler.z, 4), "scale": round(o.scale.x, 3)})
    colls = {o.instance_collection for o in instances}
    for o in list(bpy.data.objects):
        if o.type == "EMPTY" or (o.type == "MESH" and o.name.startswith("b") and o.name[1:2].isdigit()):
            bpy.data.objects.remove(o)
    print(f"setup + strip {time.time() - t0:.0f}s", flush=True)
    # surfaces (signs and fallen fronds joined into one mesh each)
    for prefix in ("frond", "sign"):
        grp = [o for o in bpy.data.objects if o.name.startswith(prefix) and o.type in ("MESH", "FONT", "CURVE")]
        if not grp:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for o in grp:
            o.select_set(True)
        bpy.context.view_layer.objects.active = grp[0]
        if any(o.type != "MESH" for o in grp):
            bpy.ops.object.convert(target="MESH")
            grp = list(bpy.context.selected_objects)
        if len(grp) > 1:
            bpy.ops.object.join()
        bpy.context.view_layer.objects.active.name = prefix
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
    print(f"surfaces {time.time() - t0:.0f}s", flush=True)
    # models
    for coll in colls:
        m = realize(coll)
        if m is None:
            continue
        if tris(m) > LIMIT:  # reduce anything over Roblox's limit just under it, keeping the shape
            dec = m.modifiers.new("fit", "DECIMATE")
            dec.ratio = LIMIT / tris(m)
            dg = bpy.context.evaluated_depsgraph_get()
            me = bpy.data.meshes.new_from_object(m.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            m.modifiers.remove(dec)
            m.data = me
        bb = [m.matrix_world @ Vector(v) for v in m.bound_box]
        c = sum(bb, Vector()) / 8
        leafy = any(mt and "leaf_card" in mt.name for mt in m.data.materials)
        export([m], f"{OUT}/{m.name}.fbx")
        manifest["models"][m.name] = {"offset": [round(c.x, 3), round(c.z, 3), round(-c.y, 3)], "tris": tris(m), "leaf": leafy,
                                      "over_limit": tris(m) > 20000}
        bpy.data.objects.remove(m)
    print(f"models {time.time() - t0:.0f}s", flush=True)
    leaf_png()
    json.dump(manifest, open(f"{OUT}/manifest.json", "w"), indent=1)
    with open("src/shared/BlockEnvManifest.luau", "w") as f:
        f.write("-- Generated by tools/blender/export_block_env.py. Do not edit.\nreturn [==[" + json.dumps(manifest) + "]==]\n")
    over = [k for k, v in manifest["models"].items() if v["over_limit"]]
    print(f"{len(manifest['surfaces'])} surface meshes, {len(manifest['models'])} models, {len(manifest['placements'])} placements; "
          f"models over 20k triangles: {over or 'none'}")
    _ = math


main()
