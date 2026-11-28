"""Builds the whole city in Blender from plan.py, renders it, and writes the Roblox layout.

Run:  python map/build_map.py            (needs bpy, like build.py; about 10 minutes, mostly rendering)
      python map/build_map.py --no-render
      python map/build_map.py oldtown hub   (render only these shots)

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
import terrain  # noqa: E402
from assets import parcels, vehicles, world  # noqa: E402

KIT = {**world.ASSETS, **vehicles.ASSETS, **parcels.ASSETS}
LAYOUT = os.path.join(os.path.dirname(ART), "src", "map", "Layout.luau")


def hexcol(h: str, alpha=1.0):
    """Hex (sRGB, as Roblox reads it) to the linear colour Blender's shaders expect."""

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return tuple(lin(int(h[k : k + 2], 16) / 255) for k in (0, 2, 4)) + (alpha,)


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


STEP, CHUNK = 10, 250  # terrain grid spacing and chunk size, studs


def build_terrain(p):
    """Faceted terrain in 250-stud chunks (one MeshPart each), exported as four quarter FBX files.
    Flat same-colour areas are merged into big faces, so the city costs almost nothing."""
    import bmesh

    t = p["terrain"]
    n = int(2 * terrain.EXTENT / STEP) + 1
    xs = [-terrain.EXTENT + k * STEP for k in range(n)]
    heights = [[t.height(x, y) for y in xs] for x in xs]
    per = CHUNK // STEP
    nch = (n - 1) // per
    coll = bpy.data.collections.new("Terrain")
    bpy.context.scene.collection.children.link(coll)
    quarters = {}
    for cx in range(nch):
        for cy in range(nch):
            centre = (xs[cx * per] + CHUNK / 2, xs[cy * per] + CHUNK / 2)
            bm = bmesh.new()
            uv = bm.loops.layers.uv.new("UVMap")
            v = {}
            for a in range(per + 1):
                for b in range(per + 1):
                    ix, iy = cx * per + a, cy * per + b
                    v[a, b] = bm.verts.new((xs[ix] - centre[0], xs[iy] - centre[1], heights[ix][iy]))
            for a in range(per):
                for b in range(per):
                    q = (v[a, b], v[a + 1, b], v[a + 1, b + 1], v[a, b + 1])
                    tris = ((q[0], q[1], q[2]), (q[0], q[2], q[3])) if (a + b) % 2 == 0 else ((q[0], q[1], q[3]), (q[1], q[2], q[3]))
                    for tri in tris:
                        f = bm.faces.new(tri)
                        f.normal_update()
                        c = (tri[0].co + tri[1].co + tri[2].co) / 3
                        wx, wy = c.x + centre[0], c.y + centre[1]
                        district = city.district_of(round(wx / city.CELL), round(wy / city.CELL))
                        u = lib.uv_of(t.colour(wx, wy, c.z, 1 - abs(f.normal.z), district))
                        for loop in f.loops:
                            loop[uv].uv = u
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=bm.verts[:], edges=bm.edges[:], delimit={"UV"})
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            me = bpy.data.meshes.new(f"Chunk_{cx}_{cy}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(lib.material())
            obj = bpy.data.objects.new(f"Chunk_{cx}_{cy}", me)
            obj.location = (centre[0], centre[1], 0)
            coll.objects.link(obj)
            name = "Terrain_" + ("N" if cy >= nch // 2 else "S") + ("E" if cx >= nch // 2 else "W")
            quarters.setdefault(name, []).append(obj)
    info, items = {}, []
    for name, objs in quarters.items():
        meta = lib.export(name, objs, {"kind": "terrain"})
        assert max(part["triangles"] for part in meta["parts"].values()) <= 10000, name
        lo, hi = lib.bounds(objs)
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        info[name] = {"size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)], "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)], "paint": False}
        items.append({"asset": name, "x": 0, "y": 0, "rot": 0, "district": "Terrain"})
        print(f"terrain {name}: {meta['triangles']} tris in {len(objs)} chunks")

    water = lib.Mesh("Water").box((2 * terrain.EXTENT, 2 * terrain.EXTENT, 0.2), (0, 0, terrain.WATER - 0.1), "water", bevel=0).done()
    mat = bpy.data.materials.new("WaterMat")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexcol("3f9be0")
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Alpha"].default_value = 0.85
    water.data.materials[0] = mat
    return info, items


def build_free_roads(p):
    """Mesh the free-form roads (roads.py) in ~200-stud MeshParts: asphalt, lines, pavements or
    crash barriers, bridge decks and pillars over water, the avalanche shelter and the roundabout island."""
    t = p["terrain"]
    groups = {"Road_Mountain": ["Mountain"], "Road_Causeway": ["Causeway"], "Road_Roundabout": ["Roundabout", "RoundaboutW", "RoundaboutE", "RoundaboutN"]}
    by_name = {r["name"]: r for r in p["free_roads"]}
    info, items = {}, []
    sample_base = 0
    bridge_of = {}
    for r in p["free_roads"]:  # bridge flags line up with RoadIndex samples, in road order
        bridge_of[r["name"]] = t.bridge[sample_base : sample_base + len(r["points"])]
        sample_base += len(r["points"])

    for asset, names in groups.items():
        objs = []
        for name in names:
            road = by_name[name]
            pts, hw, closed = road["points"], road["width"] / 2, road.get("closed", False)
            n = len(pts)

            def frame(k):
                a, b = pts[(k - 1) % n if closed else max(k - 1, 0)], pts[(k + 1) % n if closed else min(k + 1, n - 1)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                ln = math.hypot(dx, dy) or 1
                return pts[k], (-dy / ln, dx / ln), math.degrees(math.atan2(dy, dx))

            def offset(ks, d, dz=0.0):
                out = []
                for k in ks:
                    (x, y, z), (lx, ly), _ = frame(k % n)
                    out.append((x + lx * d, y + ly * d, z + dz))
                return out

            span = list(range(n + 1)) if closed else list(range(n))
            chunk = 50
            for c0 in range(0, len(span) - 1, chunk):
                ks = span[c0 : c0 + chunk + 1]
                m = lib.Mesh(f"{name}_{c0 // chunk}")
                lift = 0.03 if "joins" in road else 0.0  # approaches overlap the ring: sit a hair above it
                m.strip(offset(ks, hw, lift), offset(ks, -hw, lift), "asphalt", thickness=1)
                if road.get("lines", True):
                    for side in (-1, 1):
                        m.strip(offset(ks, side * (hw - 1.0), 0.03), offset(ks, side * (hw - 1.4), 0.03), "yellow" if road["edge"] == "pavement" else "white", thickness=0.03)
                    for k in ks[:-1]:
                        if (k // 3) % 2 == 0:
                            m.strip(offset((k, k + 1), 0.25, 0.03), offset((k, k + 1), -0.25, 0.03), "white", thickness=0.03)
                bridged = [bridge_of[name][k % n] for k in ks]
                def open_at(k):  # inside a roundabout entry gap: no pavement or kerb here
                    if "joins" in road:  # an approach: pavement stops where the ring's begins
                        jx, jy, jr = road["joins"]
                        return math.hypot(pts[k % n][0] - jx, pts[k % n][1] - jy) < jr
                    if "gaps" not in road:
                        return False
                    cx, cy, _ = road["island"]
                    x, y, _ = pts[k % n]
                    ang = math.atan2(y - cy, x - cx)
                    return any(abs((ang - a + math.pi) % math.tau - math.pi) < g for a, g in road["gaps"])

                runs, run = [], []
                for k in ks:
                    if open_at(k):
                        if len(run) > 1:
                            runs.append(run)
                        run = []
                    else:
                        run.append(k)
                if len(run) > 1:
                    runs.append(run)
                for side in (-1, 1):
                    if road["edge"] == "pavement":
                        gapped = "joins" in road or ("gaps" in road and side < 0)  # ring: only its outer edge opens
                        for rk in runs if gapped else [ks]:
                            m.strip(offset(rk, side * hw, 0.4), offset(rk, side * (hw + 5), 0.4), "concrete", thickness=1.4)
                    else:  # mountain: gravel shoulder and a crash barrier on both sides
                        m.strip(offset(ks, side * hw), offset(ks, side * (hw + 3)), "stone", thickness=1.5)
                        m.strip(offset(ks, side * (hw + 2.3), 2.6), offset(ks, side * (hw + 2.7), 2.6), "chrome", thickness=1.0)
                    for k in ks[::3]:
                        (x, y, z), (lx, ly), yaw = frame(k % n)
                        if road["edge"] != "pavement" or bridged[ks.index(k)]:
                            d = hw + (2.5 if road["edge"] != "pavement" else 4.6)
                            m.box((0.5, 0.5, 2.8), (x + lx * d * side, y + ly * d * side, z + 1.3), "steel", rot=(0, 0, yaw), bevel=0)
                    if any(bridged):  # bridge railing on top of the pavement edge
                        m.strip(offset(ks, side * (hw + 4.4), 3.2), offset(ks, side * (hw + 4.9), 3.2), "steel", thickness=0.5)
                if any(bridged):
                    m.strip(offset(ks, hw + 6, -1), offset(ks, -hw - 6, -1), "concrete", thickness=2.5)  # deck
                    for k in ks:
                        if k % 10 == 0 and bridged[ks.index(k)]:
                            (x, y, z), _, yaw = frame(k % n)
                            bed = t.water_floor(x, y)
                            for side in (-1, 1):
                                (lx, ly) = frame(k % n)[1]
                                px, py = x + lx * hw * 0.6 * side, y + ly * hw * 0.6 * side
                                m.cyl(1.6, z - bed, (px, py, (z + bed) / 2 - 1.5), "concrete", segments=12, bevel=0)
                lo, hi = road.get("shelter", (2, 2))
                for k in ks[:-1]:
                    if lo <= k / n <= hi:  # avalanche shelter: roof and pillars
                        m.strip(offset((k, k + 1), hw + 4, 14), offset((k, k + 1), -hw - 4, 14), "concrete", thickness=1.2)
                        if k % 4 == 0:
                            for side in (-1, 1):
                                (x, y, z), (lx, ly), yaw = frame(k)
                                d = (hw + 3.5) * side
                                m.box((1.4, 1.4, 14), (x + lx * d, y + ly * d, z + 7), "concrete", rot=(0, 0, yaw), bevel=0.1)
                objs.append(m.done(sharp=40))
            if "island" in road:
                cx, cy, r = road["island"]
                circle = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (k * math.tau / 48 for k in range(48))]
                isl = lib.Mesh("Island")
                isl.prism(circle, 1.2, "grass", thickness=2.2)
                isl.strip([(x, y, 0.5) for x, y in circle + circle[:1]], [(cx + (x - cx) * 1.06, cy + (y - cy) * 1.06, 0.5) for x, y in circle + circle[:1]], "concrete", thickness=1.5)
                objs.append(isl.done())
        meta = lib.export(asset, objs, {"kind": "road"})
        assert max(part["triangles"] for part in meta["parts"].values()) <= 10000, asset
        lo, hi = lib.bounds(objs)
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        info[asset] = {"size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)], "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)], "paint": False}
        items.append({"asset": asset, "x": 0, "y": 0, "rot": 0, "district": "Roads"})
        print(f"road {asset}: {meta['triangles']} tris in {len(objs)} parts")
    return info, items


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


def write_layout(p, kit_info, extra_items=()):
    def rb(x, y, z=0.0):
        return [round(x, 2), round(z, 2), round(-y, 2)]

    data = {
        "cell": p["cell"],
        "assets": kit_info,
        # m = a hazard the game moves (forklift, dog, wrecking ball, boulder); k = a parked car
        "items": [
            {"a": it["asset"], "p": rb(it["x"], it["y"], it.get("z", 0)), "r": it["rot"], "c": it.get("paint"), "d": it["district"], "m": it.get("moving"), "k": it.get("parked")}
            for it in list(p["items"]) + list(extra_items)
        ],
        # free-form roads as centrelines (every 8 studs), for routing and the no-import fallback
        "freeRoads": [{"n": r["name"], "w": r["width"], "c": bool(r.get("closed")), "p": [rb(x, y, z) for x, y, z in r["points"][::2]]} for r in p["free_roads"]],
        "links": [[[a[0], -a[1]], [b[0], -b[1]]] for a, b in p["links"]],
        "water": terrain.WATER,
        "extent": terrain.EXTENT,
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


ONLY = {a for a in sys.argv[1:] if not a.startswith("--")}  # e.g. `build_map.py oldtown topdown`


def shot(name, location, target, lens=None, ortho=None, samples=48, res=(1600, 900)):
    if ONLY and name not in ONLY:
        return
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
    terrain_info, terrain_items = build_terrain(p)
    road_info, road_items = build_free_roads(p)
    place_all(p)
    write_layout(p, {**kit_info, **terrain_info, **road_info}, terrain_items + road_items)
    setup_render(8, 64, 64)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "city.blend"))
    if not render:
        return
    C = city.CELL
    shot("topdown", (0, 0, 3000), (0, 0, 0), ortho=2100, samples=24, res=(2048, 2048))
    shot("world", (0, 0, 4000), (0, 0, 0), ortho=3000, samples=24, res=(2048, 2048))
    shot("hub", (230, -220, 150), (0, 60, 10), lens=28)
    shot("mountain", (300, 260, 90), (870, 840, 140), lens=30)
    shot("lake", (430, -380, 70), (700, -640, 0), lens=30)
    shot("coast", (-640, -620, 90), (-960, -360, 0), lens=30)
    shot("switchbacks", (760, 420, 260), (1110, 830, 70), lens=28)
    shot("causeway", (500, -480, 60), (660, -700, 0), lens=28)
    shot("roundabout", (560, -800, 70), (640, -880, 0), lens=30)
    shot("suburbs", (12 * C - 60, 4 * C - 150, 70), (14 * C, 6 * C, 0), lens=30)
    shot("oldtown", (2 * C + 10, 11 * C, 45), (-2 * C, 15 * C, 15), lens=26)
    shot("docks", (-12 * C, -6 * C, 140), (-19 * C, 2 * C, 0), lens=30)
    shot("downtown", (9 * C, -7 * C, 110), (0, -15 * C, 20), lens=28)


if __name__ == "__main__":
    main(render="--no-render" not in sys.argv)
