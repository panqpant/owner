"""Export the detailed test block for Roblox: one FBX per building plus a baked texture, and a manifest.

Per building: the Blender model (detail_town.building) with its real materials (realism) is split into
  opaque  -> UV-unwrapped, colour + ambient occlusion baked into one PNG (grime, photo materials, paint all included)
  glass   -> Roblox Glass parts (transparent, so interiors show)
  lamps   -> Roblox Neon parts; their centres become room lights (switched at night by the loader)
Writes build/roblox_block/<id>.fbx, <id>.png and manifest.json (world positions in Roblox coordinates).
Usage (from costa-verde/, after export-world and export-terrain): python tools/blender/export_block_roblox.py [N]
N = only the first N buildings (quick test)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402
import detail_town as dt  # noqa: E402
import realism  # noqa: E402
from render_world import reset  # noqa: E402

OUT = "build/roblox_block"
TEX = 1024
OFFSET = -40960 / 2  # TerrainBuilder.OFFSET: the world is centred on the origin in Roblox
GLASS = ("real_window_glass", "real_shopglass", "real_glass", "real_glass_interior", "shopglass", "glass")
LAMPS = ("real_lamp", "lamp", "neon")
TRI_LIMIT = 20000  # Roblox MeshPart limit


def split_by_role(o):
    """Separate a building object into opaque / glass / lamp objects by material name."""
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = {"opaque": [], "glass": [], "lamp": []}
    for p in bpy.context.selected_objects:
        names = [m.name.split(".")[0] for m in p.data.materials if m]
        used = {p.data.materials[f.material_index].name.split(".")[0] for f in p.data.polygons if p.data.materials}
        role = "glass" if used & set(GLASS) else "lamp" if used & set(LAMPS) else "opaque"
        _ = names
        parts[role].append(p)
    out = {}
    for role, objs in parts.items():
        if not objs:
            continue
        bpy.ops.object.select_all(action="DESELECT")
        for p in objs:
            p.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        out[role] = bpy.context.view_layer.objects.active
    return out


def bake(o, path):
    """Smart-UV the opaque mesh and bake base colour x ambient occlusion into one texture."""
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    results = {}
    for kind in ("DIFFUSE", "AO"):
        img = bpy.data.images.new(f"{o.name}_{kind}", TEX, TEX)
        nodes = []
        for m in o.data.materials:
            n = m.node_tree.nodes.new("ShaderNodeTexImage")
            n.image = img
            m.node_tree.nodes.active = n
            nodes.append((m, n))
        s = bpy.context.scene
        s.cycles.samples = 1 if kind == "DIFFUSE" else 16
        if kind == "DIFFUSE":
            s.render.bake.use_pass_direct = s.render.bake.use_pass_indirect = False
            s.render.bake.use_pass_color = True
        s.render.bake.margin = 4
        bpy.ops.object.bake(type=kind)
        results[kind] = img
        for m, n in nodes:
            m.node_tree.nodes.remove(n)
    import numpy as np
    from PIL import Image
    col = np.array(results["DIFFUSE"].pixels[:], dtype=np.float32).reshape(TEX, TEX, 4)
    ao = np.array(results["AO"].pixels[:], dtype=np.float32).reshape(TEX, TEX, 4)
    rgb = col[..., :3] * (0.35 + 0.65 * ao[..., :1])  # baked contact shadow / grime depth
    rgb = np.where(rgb <= 0.0031308, rgb * 12.92, 1.055 * np.power(np.clip(rgb, 0, 1), 1 / 2.4) - 0.055)  # linear -> sRGB
    Image.fromarray((np.clip(rgb[::-1], 0, 1) * 255).astype(np.uint8)).save(path)
    for img in results.values():
        bpy.data.images.remove(img)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    reset()
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    os.makedirs(OUT, exist_ok=True)
    zone = (dt.CX - dt.R, dt.CZ - dt.R, dt.CX + dt.R, dt.CZ + dt.R)
    picks = [(i + 1, b) for i, b in enumerate(dt.W["buildings"]) if zone[0] < b["x"] < zone[2] and zone[1] < b["z"] < zone[3]]
    if limit:
        picks = picks[:limit]
    gy = dt.ground(dt.CX, dt.CZ)
    manifest = {"note": "Roblox coordinates (studs); positions are part bounding-box centres", "buildings": []}
    for idx, b in picks:
        o = dt.building(idx, b)
        realism.realify([o], gy)
        o.modifiers.clear()  # no bevel: keeps the triangle budget for Roblox
        realism.photo_upgrade()
        parts = split_by_role(o)
        entry = {"id": f"b{idx}", "use": b.get("use"), "style": b["style"], "parts": {}, "lights": []}
        for role, p in parts.items():
            t = tris(p)
            if role == "opaque":
                bake(p, f"{OUT}/b{idx}.png")
            if role == "lamp":  # each separate lamp face group -> a room light position
                for poly in list(p.data.polygons)[::6]:  # lamps are 6-face boxes: one point per fitting
                    c = p.matrix_world @ poly.center
                    entry["lights"].append([round(c.x + OFFSET, 2), round(c.z, 2), round(-c.y + OFFSET, 2)])
            bb = [p.matrix_world @ __import__("mathutils").Vector(v) for v in p.bound_box]
            cx, cy, cz = (sum(v.x for v in bb) / 8, sum(v.y for v in bb) / 8, sum(v.z for v in bb) / 8)
            p.name = f"b{idx}_{role}"
            entry["parts"][role] = {"center": [round(cx + OFFSET, 3), round(cz, 3), round(-cy + OFFSET, 3)], "tris": t, "over_limit": t > TRI_LIMIT}
        bpy.ops.object.select_all(action="DESELECT")
        for p in parts.values():
            p.select_set(True)
        bpy.ops.export_scene.fbx(filepath=f"{OUT}/b{idx}.fbx", use_selection=True, axis_forward="-Z", axis_up="Y", path_mode="STRIP")
        merged = []  # one light per room: fittings within 10 studs merge
        for pt in entry["lights"]:
            if all(sum((a - b) ** 2 for a, b in zip(pt, q)) > 100 for q in merged):
                merged.append(pt)
        entry["lights"] = merged
        manifest["buildings"].append(entry)
        for p in parts.values():
            bpy.data.objects.remove(p)
        print(f"b{idx}: " + ", ".join(f"{r} {v['tris']} tris" for r, v in entry["parts"].items()) + f", {len(entry['lights'])} lights", flush=True)
    json.dump(manifest, open(f"{OUT}/manifest.json", "w"), indent=1)
    with open("src/shared/BlockManifest.luau", "w") as f:  # Roblox can't read files: ship the manifest as a module
        f.write("-- Generated by tools/blender/export_block_roblox.py. Do not edit.\nreturn [==[" + json.dumps(manifest) + "]==]\n")
    over = [(e["id"], r) for e in manifest["buildings"] for r, v in e["parts"].items() if v["over_limit"]]
    print(f"{len(picks)} buildings exported; over the {TRI_LIMIT}-triangle limit: {over or 'none'}")


main()
