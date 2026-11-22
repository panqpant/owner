"""3D preview renders of build/world.json.
Usage (from costa-verde/): python tools/blender/render_world.py [shot ...]
Roblox coords -> Blender: x -> X, z (south) -> -Y, height -> Z. 1 Blender unit = 1 stud."""
import json
import math
import sys


import bpy
import bmesh  # must come after bpy when running as a module
from mathutils import Matrix, Vector

W = json.load(open("build/world.json"))
SIZE = W["size"]


def P(x, z, h=0.0):
    return (x, -z, h)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = 48
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = 1600, 900
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Punchy"
    return s


def mat(name, color, rough=0.6, metal=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def window_mat(name, facade, glass, night):
    """Facade with a grid of windows (brick texture in world space); windows glow at night."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    add = nt.nodes.new("ShaderNodeMath")
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    brick = nt.nodes.new("ShaderNodeTexBrick")
    brick.offset = 0
    brick.inputs["Scale"].default_value = 0.08
    brick.inputs["Mortar Size"].default_value = 0.35
    brick.inputs["Color1"].default_value = (1, 1, 1, 1)
    brick.inputs["Color2"].default_value = (0.2, 0.2, 0.2, 1)
    brick.inputs["Mortar"].default_value = (0, 0, 0, 1)
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], add.inputs[0])
    nt.links.new(sep.outputs["Y"], add.inputs[1])
    nt.links.new(add.outputs[0], comb.inputs["X"])
    nt.links.new(sep.outputs["Z"], comb.inputs["Y"])
    nt.links.new(comb.outputs[0], brick.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs["A"].default_value = (*facade, 1)
    mix.inputs["B"].default_value = (*glass, 1)
    nt.links.new(brick.outputs["Fac"], mix.inputs["Factor"])
    nt.links.new(mix.outputs["Result"], b.inputs["Base Color"])
    rough = nt.nodes.new("ShaderNodeMapRange")
    rough.inputs["To Min"].default_value = 0.7
    rough.inputs["To Max"].default_value = 0.08
    nt.links.new(brick.outputs["Fac"], rough.inputs["Value"])
    nt.links.new(rough.outputs[0], b.inputs["Roughness"])
    if night:
        # random lit windows: brick colour (random per brick) thresholded
        lit = nt.nodes.new("ShaderNodeMath")
        lit.operation = "GREATER_THAN"
        lit.inputs[1].default_value = 0.45
        nt.links.new(brick.outputs["Color"], lit.inputs[0])
        both = nt.nodes.new("ShaderNodeMath")
        both.operation = "MULTIPLY"
        nt.links.new(lit.outputs[0], both.inputs[0])
        nt.links.new(brick.outputs["Fac"], both.inputs[1])
        b.inputs["Emission Color"].default_value = (1.0, 0.75, 0.45, 1)
        nt.links.new(both.outputs[0], b.inputs["Emission Strength"])
    return m


def terrain():
    hm = W["heightmap"]
    n, cell = hm["n"], hm["cell"]
    me = bpy.data.meshes.new("terrain")
    verts = [P((i + 0.5) * cell, (j + 0.5) * cell, max(hm["h"][j * n + i], -40)) for j in range(n) for i in range(n)]
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i) for j in range(n - 1) for i in range(n - 1)]
    me.from_pydata(verts, [], faces)
    col = me.color_attributes.new("col", "FLOAT_COLOR", "POINT")
    # linear-space colours matched by eye to the USGS references
    C = {"Sand": (0.62, 0.55, 0.36), "Grass": (0.12, 0.17, 0.04), "LeafyGrass": (0.05, 0.1, 0.025), "Mud": (0.08, 0.08, 0.04), "Ground": (0.16, 0.1, 0.05)}
    B = {"mangrove": (0.02, 0.05, 0.015), "hammock": (0.025, 0.06, 0.015), "scrub": (0.09, 0.12, 0.05), "wetland": (0.16, 0.14, 0.06)}
    urban = {"downtown", "midtown", "docks", "calle", "beach", "northshore", "westside", "palmgrove", "university", "gulftown"}
    for k, m in enumerate(hm["material"]):
        bi = hm["biome"][k]
        c = B.get(bi) if bi in B and not (bi == "wetland" and m == "Mud") else C.get(m, (0.1, 0.12, 0.05))
        if hm["district"][k] in urban and bi != "beach":
            c = (0.2, 0.2, 0.19)  # paved city ground
        col.data[k].color = (*c, 1)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("terrain", me)
    bpy.context.collection.objects.link(o)
    m = bpy.data.materials.new("ground")
    m.use_nodes = True
    a = m.node_tree.nodes.new("ShaderNodeAttribute")
    a.attribute_name = "col"
    m.node_tree.links.new(a.outputs["Color"], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    m.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    me.materials.append(m)


def water():
    bpy.ops.mesh.primitive_plane_add(size=SIZE * 3, location=(SIZE / 2, -SIZE / 2, 0))
    m = bpy.data.materials.new("water")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.01, 0.12, 0.16, 1)
    b.inputs["Roughness"].default_value = 0.04
    b.inputs["Coat Weight"].default_value = 0.4
    wave = nt.nodes.new("ShaderNodeTexNoise")
    wave.inputs["Scale"].default_value = 0.05
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    nt.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    bpy.context.object.data.materials.append(m)


def ground_h(x, z):
    hm = W["heightmap"]
    n, cell = hm["n"], hm["cell"]
    i = min(n - 1, max(0, int(x / cell)))
    j = min(n - 1, max(0, int(z / cell)))
    return hm["h"][j * n + i]


def roads(night):
    me = bpy.data.meshes.new("roads")
    bm = bmesh.new()
    for r in W["roads"]:
        a, b = Vector((r["ax"], r["az"])), Vector((r["bx"], r["bz"]))
        d = b - a
        if d.length < 1:
            continue
        nrm = Vector((-d.y, d.x)).normalized() * r["width"] / 2
        ha = 24 if r["bridge"] else max(ground_h(*a), 0) + 0.8
        hb = 24 if r["bridge"] else max(ground_h(*b), 0) + 0.8
        vs = [bm.verts.new(P(*(a + nrm), ha)), bm.verts.new(P(*(b + nrm), hb)),
              bm.verts.new(P(*(b - nrm), hb)), bm.verts.new(P(*(a - nrm), ha))]
        bm.faces.new(vs)
    bm.to_mesh(me)
    o = bpy.data.objects.new("roads", me)
    bpy.context.collection.objects.link(o)
    me.materials.append(mat("asphalt", (0.04, 0.04, 0.045), 0.5 if night else 0.8))


STYLE_COL = {
    "tower": ((0.55, 0.6, 0.66), (0.08, 0.16, 0.24)),
    "midrise": ((0.7, 0.68, 0.62), (0.1, 0.15, 0.2)),
    "deco": ((0.95, 0.72, 0.75), (0.15, 0.3, 0.35)),
    "stucco": ((0.92, 0.82, 0.6), (0.12, 0.14, 0.16)),
    "warehouse": ((0.5, 0.42, 0.36), (0.2, 0.2, 0.2)),
    "house": ((0.92, 0.9, 0.84), (0.15, 0.18, 0.2)),
    "campus": ((0.66, 0.32, 0.24), (0.12, 0.15, 0.18)),
    "shack": ((0.45, 0.36, 0.26), (0.1, 0.1, 0.1)),
    "farmhouse": ((0.9, 0.9, 0.86), (0.12, 0.12, 0.12)),
    "barn": ((0.45, 0.06, 0.04), (0.3, 0.05, 0.04)),
    "silo": ((0.7, 0.72, 0.74), (0.7, 0.72, 0.74)),
    "store": ((0.3, 0.45, 0.7), (0.1, 0.12, 0.15)),
    "gas": ((0.9, 0.75, 0.1), (0.1, 0.12, 0.15)),
    "church": ((0.95, 0.95, 0.95), (0.2, 0.25, 0.4)),
    "diner": ((0.85, 0.3, 0.5), (0.1, 0.12, 0.15)),
    "trailer": ((0.8, 0.8, 0.76), (0.2, 0.2, 0.2)),
}
ROOF = {"house": (0.55, 0.2, 0.14), "shack": (0.35, 0.33, 0.3)}


def buildings(night, region=None):
    me = bpy.data.meshes.new("buildings")
    bm = bmesh.new()
    styles = list(STYLE_COL)
    for bd in W["buildings"]:
        if region and not (region[0] <= bd["x"] <= region[2] and region[1] <= bd["z"] <= region[3]):
            continue
        if bd["w"] < 4 or bd["d"] < 4:
            continue
        x, z, w, d, h = bd["x"], bd["z"], bd["w"], bd["d"], bd["h"]
        y = max(bd["y"], 0)
        r = bmesh.ops.create_cube(bm, size=1)
        bmesh.ops.scale(bm, vec=(w, d, h), verts=r["verts"])
        bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(-math.radians(bd["rot"]), 3, "Z"), verts=r["verts"])
        bmesh.ops.translate(bm, vec=(x, -z, y + h / 2), verts=r["verts"])
        idx = styles.index(bd["style"]) if bd["style"] in styles else 0
        for f in {f for v in r["verts"] for f in v.link_faces}:
            f.material_index = idx
        # setback crown on tall towers
        if bd["style"] == "tower" and h > 260:
            r2 = bmesh.ops.create_cube(bm, size=1)
            bmesh.ops.scale(bm, vec=(w * 0.6, d * 0.6, h * 0.18), verts=r2["verts"])
            bmesh.ops.translate(bm, vec=(x, -z, y + h + h * 0.09), verts=r2["verts"])
            for f in {f for v in r2["verts"] for f in v.link_faces}:
                f.material_index = idx
    bm.to_mesh(me)
    o = bpy.data.objects.new("buildings", me)
    bpy.context.collection.objects.link(o)
    for s in styles:
        facade, glass = STYLE_COL[s]
        me.materials.append(window_mat(s, facade, glass, night))


def rails():
    me = bpy.data.meshes.new("rails")
    bm = bmesh.new()
    for t in W["tracks"]:
        a, b = Vector((t["ax"], t["az"])), Vector((t["bx"], t["bz"]))
        d = b - a
        if d.length < 1:
            continue
        nrm = Vector((-d.y, d.x)).normalized() * (9 if t["kind"] == "metro" else 7)
        lift = 40 if t["elevated"] else (24 if t["bridge"] else 1.2)
        ha, hb = max(ground_h(*a), 0) + lift, max(ground_h(*b), 0) + lift
        vs = [bm.verts.new(P(*(a + nrm), ha)), bm.verts.new(P(*(b + nrm), hb)), bm.verts.new(P(*(b - nrm), hb)), bm.verts.new(P(*(a - nrm), ha))]
        f = bm.faces.new(vs)
        bmesh.ops.solidify(bm, geom=[f], thickness=4)
    bm.to_mesh(me)
    o = bpy.data.objects.new("rails", me)
    bpy.context.collection.objects.link(o)
    me.materials.append(mat("rail", (0.25, 0.24, 0.22), 0.7))


def parks():
    me = bpy.data.meshes.new("parks")
    bm = bmesh.new()
    for p in W["parks"]:
        r = bmesh.ops.create_cube(bm, size=1)
        bmesh.ops.scale(bm, vec=(p["w"], p["d"], 1), verts=r["verts"])
        bmesh.ops.translate(bm, vec=(p["x"], -p["z"], max(p["y"], 0) + 0.6), verts=r["verts"])
    bm.to_mesh(me)
    o = bpy.data.objects.new("parks", me)
    bpy.context.collection.objects.link(o)
    me.materials.append(mat("park", (0.1, 0.3, 0.06), 0.9))


def sky(elev, rot, strength=1.0, night=False):
    w = bpy.data.worlds.new("sky")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    if night:
        bg.inputs["Color"].default_value = (0.004, 0.008, 0.025, 1)
        bg.inputs["Strength"].default_value = 1.0
        bpy.ops.object.light_add(type="SUN", rotation=(math.radians(50), 0, math.radians(30)))
        bpy.context.object.data.energy = 0.08
        bpy.context.object.data.color = (0.6, 0.7, 1.0)
        return
    st = nt.nodes.new("ShaderNodeTexSky")
    st.sky_type = "NISHITA" if "NISHITA" in [i.identifier for i in st.bl_rna.properties["sky_type"].enum_items] else st.sky_type
    try:
        st.sun_elevation = math.radians(elev)
        st.sun_rotation = math.radians(rot)
        st.altitude = 200
    except AttributeError:
        pass
    nt.links.new(st.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(90 - elev), 0, math.radians(rot + 90)))
    bpy.context.object.data.energy = 4.0
    bpy.context.object.data.color = (1.0, 0.8, 0.6) if elev < 15 else (1, 0.97, 0.92)
    bpy.context.object.data.angle = math.radians(1.5)


def camera(pos, target, lens=35):
    bpy.ops.object.camera_add(location=pos)
    c = bpy.context.object
    c.data.lens = lens
    c.data.clip_end = 60000
    c.data.clip_start = 5
    c.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = c


def render(name):
    s = bpy.context.scene
    s.render.filepath = f"{bpy.path.abspath('//')}screenshots/{name}.png" if bpy.data.filepath else f"screenshots/{name}.png"
    bpy.ops.render.render(write_still=True)
    print("wrote", s.render.filepath)


D = {d["id"]: d for d in W["districts"]}


def shot_sunset():
    reset()
    terrain(); water(); roads(False); rails(); parks(); buildings(False)
    sky(6, 250)
    dt = D["downtown"]
    camera(P(dt["x"] + 6500, dt["z"] + 4200, 1700), P(dt["x"] - 600, dt["z"] - 900, 120), 30)
    render("aerial_sunset")


def shot_day_beach():
    reset()
    terrain(); water(); roads(False); rails(); parks(); buildings(False)
    sky(45, 120)
    b = D["beach"]
    camera(P(b["x"] + 1500, b["z"] + 2300, 520), P(b["x"] - 200, b["z"] - 600, 40), 30)
    render("beach_day")


def shot_night():
    reset()
    terrain(); water(); roads(True); rails(); parks(); buildings(True)
    sky(0, 0, night=True)
    dt = D["downtown"]
    camera(P(dt["x"] + 2900, dt["z"] + 1700, 700), P(dt["x"], dt["z"] - 200, 150), 35)
    bpy.context.scene.cycles.samples = 64
    render("downtown_night")


def shot_keys():
    reset()
    terrain(); water(); roads(False); rails(); parks(); buildings(False)
    sky(25, 200)
    camera(P(0.47 * SIZE, 0.84 * SIZE, 900), P(0.33 * SIZE, 0.94 * SIZE, 0), 28)
    render("keys_bridge")


def shot_country():
    reset()
    terrain(); water(); roads(False); rails(); parks(); buildings(False)
    sky(30, 160)
    st = next(s for s in W["stations"] if s["line"] == "Gulf Line") if W["stations"] else D["truckstop"]
    camera(P(st["x"] + 2200, st["z"] + 1800, 900), P(st["x"] - 600, st["z"] - 700, 0), 30)
    render("countryside")


SHOTS = {"country": shot_country, "sunset": shot_sunset, "beach": shot_day_beach, "night": shot_night, "keys": shot_keys}
for name in (sys.argv[1:] or SHOTS):
    SHOTS[name]()
