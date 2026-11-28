"""Builds the whole city in Blender from plan.py, renders it, and writes the Roblox layout.

Run:  python map/build_map.py            (needs bpy, like build.py; about 10 minutes, mostly rendering)
      python map/build_map.py --no-render

Outputs
  map/city.blend                      the city, every piece a linked instance of the kit (open it in Blender)
  previews/map_*.png                  top-down plan and close-ups
  ../src/map/Layout.luau              what MapBuilder.luau places in Studio (Roblox coordinates)
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
sys.path.insert(0, ART)
sys.path.insert(0, HERE)

import lib  # noqa: E402  (imports bpy)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import plan as city  # noqa: E402
from assets import parcels, vehicles, world  # noqa: E402

KIT = {**world.ASSETS, **vehicles.ASSETS, **parcels.ASSETS}
LAYOUT = os.path.join(os.path.dirname(ART), "src", "map", "Layout.luau")


def hexcol(h: str, alpha=1.0):
    return tuple(int(h[k : k + 2], 16) / 255 for k in (0, 2, 4)) + (alpha,)


def paint_material():
    """Paint parts take their colour from the instancing empty (its object colour)."""
    m = bpy.data.materials.new("Paint")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "INSTANCER"
    attr.attribute_name = "color"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return m


def build_kit(names):
    kit_root = bpy.data.collections.new("Kit")
    bpy.context.scene.collection.children.link(kit_root)
    paint = paint_material()
    info = {}
    for name in sorted(names):
        objs, _meta = KIT[name]()
        coll = bpy.data.collections.new(name)
        kit_root.children.link(coll)
        for o in objs:
            bpy.context.scene.collection.objects.unlink(o)
            coll.objects.link(o)
            if o.name.startswith("Paint"):
                o.data.materials[0] = paint
        lo, hi = lib.bounds(objs)
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        info[name] = {
            # Roblox frame: x, y (up), z (= -Blender y)
            "size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)],
            "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)],
            "paint": any(o.name.startswith("Paint") for o in objs),
        }
        print("kit", name)
    bpy.context.view_layer.layer_collection.children["Kit"].exclude = True
    return info


def ground(p):
    """Flat district colours and the sea. Placeholder until the terrain batch."""
    m = lib.Mesh("Ground")
    order = list(city.DISTRICTS)
    for name in order:
        x0, y0, x1, y1 = p["districts"][name]["rect"]
        m.box((x1 - x0, y1 - y0, 1), ((x0 + x1) / 2, (y0 + y1) / 2, -0.55 + order.index(name) * 0.001), "grass", bevel=0)
    obj = m.done()
    mat = bpy.data.materials.new("Ground")
    mat.use_nodes = True
    obj.data.materials[0] = mat
    # colour per district via a simple face colour attribute
    col = obj.data.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
    faces_per_box = 6
    for k, poly in enumerate(obj.data.polygons):
        h = p["districts"][order[min(k // faces_per_box, len(order) - 1)]]["colour"]
        for li in poly.loop_indices:
            col.data[li].color = hexcol(h)
    attr = mat.node_tree.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    mat.node_tree.links.new(attr.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    half = (city.HALF + 0.5) * city.CELL
    sea_x1 = (city.SEA_I + 0.5) * city.CELL
    sea = lib.Mesh("Sea").box((sea_x1 + half + 400, 2 * half + 800, 1), ((sea_x1 - half - 400) / 2, 0, -2.5), "water", bevel=0).done()
    sea.data.materials[0] = bpy.data.materials.new("SeaMat")
    sea.data.materials[0].use_nodes = True
    b = sea.data.materials[0].node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexcol("3f9be0")
    b.inputs["Roughness"].default_value = 0.15


def place_all(p):
    root = bpy.data.collections.new("City")
    bpy.context.scene.collection.children.link(root)
    groups = {}
    for k, it in enumerate(p["items"]):
        g = groups.get(it["district"])
        if g is None:
            g = groups[it["district"]] = bpy.data.collections.new(it["district"])
            root.children.link(g)
        e = bpy.data.objects.new(f"{it['asset']}.{k}", None)
        e.instance_type = "COLLECTION"
        e.instance_collection = bpy.data.collections[it["asset"]]
        e.location = (it["x"], it["y"], it.get("z", 0))
        e.rotation_euler = (0, 0, math.radians(it["rot"]))
        if "paint" in it:
            e.color = hexcol(it["paint"])
        g.objects.link(e)


def write_layout(p, kit_info):
    def rb(x, y, z=0.0):
        return [round(x, 2), round(z, 2), round(-y, 2)]

    data = {
        "cell": p["cell"],
        "assets": kit_info,
        # m = a hazard the game moves (forklift, dog, wrecking ball, boulder); k = a parked car
        "items": [
            {"a": it["asset"], "p": rb(it["x"], it["y"], it.get("z", 0)), "r": it["rot"], "c": it.get("paint"), "d": it["district"], "m": it.get("moving"), "k": it.get("parked")}
            for it in p["items"]
        ],
        "addresses": [{"d": a["district"], "p": rb(a["x"], a["y"]), "b": a["building"]} for a in p["addresses"]],
        "spawn": {"p": rb(p["spawn"]["x"], p["spawn"]["y"]), "r": p["spawn"]["rot"]},
        # rect in Roblox x/z: [xMin, zMin, xMax, zMax]
        "districts": {k: {"rect": [v["rect"][0], -v["rect"][3], v["rect"][2], -v["rect"][1]], "colour": v["colour"]} for k, v in p["districts"].items()},
        "seaXMax": (city.SEA_I + 0.5) * city.CELL,
        "roads": [[i, -j] for i, j in p["roads"]],  # road cells in Roblox grid (x = i*cell, z = j*cell)
    }
    os.makedirs(os.path.dirname(LAYOUT), exist_ok=True)
    with open(LAYOUT, "w") as f:
        f.write("-- Generated by art/map/build_map.py. Do not edit by hand: change art/map/plan.py and rebuild.\n")
        f.write("return [==[" + json.dumps(data, separators=(",", ":")) + "]==]\n")
    print("layout:", len(data["items"]), "items,", os.path.getsize(LAYOUT) // 1024, "KB")


def setup_render(samples, res_x, res_y):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res_x, res_y
    sc.view_settings.view_transform = "AgX"
    if not sc.world:
        w = bpy.data.worlds.new("Sky")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.78, 1.0, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
        sc.world = w
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
        sun.data.energy = 3.5
        sun.data.angle = math.radians(3)
        sun.rotation_euler = (math.radians(42), 0, math.radians(35))
        sc.collection.objects.link(sun)


def shot(name, location, target, lens=None, ortho=None, samples=48, res=(1600, 900)):
    setup_render(samples, *res)
    cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    if cam.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(cam)
    cam.data.clip_end = 20000
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens or 32
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = os.path.join(lib.PREVIEWS, f"map_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


def main(render=True):
    lib.reset()
    lib.write_palette()
    p = city.plan()
    kit_info = build_kit({it["asset"] for it in p["items"]})
    ground(p)
    place_all(p)
    write_layout(p, kit_info)
    setup_render(8, 64, 64)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "city.blend"))
    if not render:
        return
    C = city.CELL
    shot("topdown", (0, 0, 3000), (0, 0, 0), ortho=2100, samples=24, res=(2048, 2048))
    shot("hub", (230, -220, 150), (0, 60, 10), lens=28)
    shot("suburbs", (12 * C - 60, 4 * C - 150, 70), (14 * C, 6 * C, 0), lens=30)
    shot("oldtown", (2 * C + 10, 11 * C, 45), (-2 * C, 15 * C, 15), lens=26)
    shot("docks", (-12 * C, -6 * C, 140), (-19 * C, 2 * C, 0), lens=30)
    shot("site", (10 * C, -6 * C, 160), (0, -16 * C, 0), lens=30)


if __name__ == "__main__":
    main(render="--no-render" not in sys.argv)
