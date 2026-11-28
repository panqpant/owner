"""Batch 8: custom skyboxes (day and sunset) rendered as the six faces Roblox's Sky object takes.

Run:  python sky/build_sky.py        (needs Blender's Python module, like build.py)

Writes export/sky/<mood>/Skybox{Ft,Bk,Lf,Rt,Up,Dn}.png (1024 px) and previews/_sky_<mood>.png,
a cross layout for checking that the faces meet at their edges.

Faces, in Roblox terms: Ft looks along -Z (the default LookVector), Bk +Z, Rt +X, Lf -X, Up +Y, Dn -Y.
The Up face is rendered with its top edge toward Bk and Dn with its top toward Ft. If the seam along
the top of the sky looks wrong in Studio, rotate SkyboxUp in 90 degree steps until it lines up.
"""

import math
import os
import random

import bpy  # noqa: F401  (must load before mathutils)
from mathutils import Euler, Vector

ART = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ART, "export", "sky")

MOODS = {
    "day": {
        "horizon": (0.78, 0.89, 1.0), "zenith": (0.25, 0.52, 0.95), "ground": (0.62, 0.72, 0.80),
        "sun_dir": (0.45, 0.55, 0.70), "sun_col": (1.0, 0.97, 0.90), "sun_size": 0.9994, "glow": 0.6,
        "cloud": (0.86, 0.88, 0.92), "cloud_shadow": (0.62, 0.70, 0.84), "sun_energy": 2.2,
    },
    "sunset": {
        "horizon": (1.0, 0.58, 0.32), "zenith": (0.20, 0.20, 0.48), "ground": (0.45, 0.30, 0.35),
        "sun_dir": (-0.98, 0.15, 0.05), "sun_col": (1.0, 0.70, 0.40), "sun_size": 0.9990, "glow": 1.6,
        "cloud": (1.0, 0.72, 0.60), "cloud_shadow": (0.55, 0.38, 0.55), "sun_energy": 3.0,
    },
}

# Blender looks: +Y is Roblox's front (-Z). Camera rotations for each face.
FACES = {
    "Ft": (90, 0, 0),
    "Bk": (90, 0, 180),
    "Rt": (90, 0, -90),
    "Lf": (90, 0, 90),
    "Up": (180, 0, 0),
    "Dn": (0, 0, 0),
}


def world(mood):
    w = bpy.data.worlds.new("Sky")
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        if n.type != "OUTPUT_WORLD":
            nt.nodes.remove(n)
    out = next(n for n in nt.nodes if n.type == "OUTPUT_WORLD")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(coord.outputs["Generated"], sep.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")  # ground below the horizon, horizon band, zenith above
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, (*mood["ground"], 1)
    cr.elements[1].position, cr.elements[1].color = 1.0, (*mood["zenith"], 1)
    e = cr.elements.new(0.5)
    e.color = (*mood["horizon"], 1)
    e2 = cr.elements.new(0.62)
    e2.color = tuple((a + b) / 2 for a, b in zip(mood["horizon"], mood["zenith"])) + (1,)
    remap = nt.nodes.new("ShaderNodeMapRange")  # z in -1..1 -> 0..1
    remap.inputs["From Min"].default_value, remap.inputs["From Max"].default_value = -1, 1
    nt.links.new(sep.outputs["Z"], remap.inputs["Value"])
    nt.links.new(remap.outputs["Result"], ramp.inputs["Fac"])
    # Sun disc and glow: dot(view, sun) pushed through a steep curve.
    sun = Vector(mood["sun_dir"]).normalized()
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(coord.outputs["Generated"], dot.inputs[0])
    dot.inputs[1].default_value = sun
    disc = nt.nodes.new("ShaderNodeMath")
    disc.operation = "GREATER_THAN"
    disc.inputs[1].default_value = mood["sun_size"]
    nt.links.new(dot.outputs["Value"], disc.inputs[0])
    glow = nt.nodes.new("ShaderNodeMath")
    glow.operation = "POWER"
    clamp = nt.nodes.new("ShaderNodeClamp")
    nt.links.new(dot.outputs["Value"], clamp.inputs["Value"])
    nt.links.new(clamp.outputs["Result"], glow.inputs[0])
    glow.inputs[1].default_value = 24
    glow_amt = nt.nodes.new("ShaderNodeMath")
    glow_amt.operation = "MULTIPLY"
    glow_amt.inputs[1].default_value = mood["glow"]
    nt.links.new(glow.outputs[0], glow_amt.inputs[0])
    total = nt.nodes.new("ShaderNodeMath")
    total.operation = "ADD"
    nt.links.new(disc.outputs[0], total.inputs[0])
    nt.links.new(glow_amt.outputs[0], total.inputs[1])
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "ADD"
    nt.links.new(total.outputs[0], mix.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = (*mood["sun_col"], 1)
    bg = nt.nodes.new("ShaderNodeBackground")
    nt.links.new(mix.outputs[2], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def clouds(mood, seed=3):
    """Low-poly cloud clusters on a ring 1800 studs out, lit by a sun lamp from the sky's sun."""
    mat = bpy.data.materials.new("Cloud")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*mood["cloud"], 1)
    b.inputs["Roughness"].default_value = 1.0
    b.inputs["Emission Color"].default_value = (*mood["cloud_shadow"], 1)
    b.inputs["Emission Strength"].default_value = 0.35  # shadows on clouds stay soft and tinted
    rnd = random.Random(seed)
    import bmesh

    for k in range(28):
        az = rnd.uniform(0, math.tau)
        el = math.radians(rnd.uniform(5, 38))
        dist = 1800
        centre = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el))) * dist
        bm = bmesh.new()
        size = rnd.uniform(170, 320)  # big enough to read as clouds, not specks, from the city
        for j in range(rnd.randint(5, 8)):
            tmp = bmesh.new()
            bmesh.ops.create_icosphere(tmp, subdivisions=2, radius=size * rnd.uniform(0.45, 0.8))
            for v in tmp.verts:
                v.co *= 1 + rnd.uniform(-0.12, 0.12)
                v.co.z *= 0.75
                v.co += Vector(((j - 3) * size * 0.45, rnd.uniform(-0.3, 0.3) * size, rnd.uniform(0, 0.25) * size))
            me = bpy.data.meshes.new("t")
            tmp.to_mesh(me)
            tmp.free()
            bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        me = bpy.data.meshes.new(f"Cloud{k}")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        obj = bpy.data.objects.new(f"Cloud{k}", me)
        obj.location = centre
        obj.rotation_euler = (0, 0, az + math.pi / 2)  # long side faces the camera
        bpy.context.scene.collection.objects.link(obj)
    lamp = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    lamp.data.energy = mood["sun_energy"]  # day clouds blow out to flat white if this is too strong
    lamp.data.color = mood["sun_col"]
    lamp.rotation_euler = Vector(mood["sun_dir"]).to_track_quat("Z", "Y").to_euler()  # light travels away from the sun
    bpy.context.scene.collection.objects.link(lamp)


def render(mood_name):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mood = MOODS[mood_name]
    sc = bpy.context.scene
    sc.world = world(mood)
    clouds(mood)
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 32
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 1024
    sc.view_settings.view_transform = "Standard"  # Roblox shows the images as they are
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.angle = math.pi / 2  # exactly 90 degrees: faces meet edge to edge
    cam.data.clip_end = 10000
    sc.collection.objects.link(cam)
    sc.camera = cam
    folder = os.path.join(OUT, mood_name)
    os.makedirs(folder, exist_ok=True)
    for face, rot in FACES.items():
        cam.rotation_euler = Euler([math.radians(a) for a in rot])
        sc.render.filepath = os.path.join(folder, f"Skybox{face}.png")
        bpy.ops.render.render(write_still=True)
        print("sky", mood_name, face)
    cross(folder, mood_name)


def cross(folder, mood_name):
    """Unfolded cube for eyeballing the seams: Up above Ft, then Lf Ft Rt Bk, Dn below Ft."""
    from PIL import Image

    s = 256
    sheet = Image.new("RGB", (4 * s, 3 * s), (30, 30, 30))
    faces = {f: Image.open(os.path.join(folder, f"Skybox{f}.png")).convert("RGB").resize((s, s)) for f in FACES}
    for f, (cx, cy) in {"Lf": (0, 1), "Ft": (1, 1), "Rt": (2, 1), "Bk": (3, 1), "Up": (1, 0), "Dn": (1, 2)}.items():
        sheet.paste(faces[f], (cx * s, cy * s))
    sheet.save(os.path.join(ART, "previews", f"_sky_{mood_name}.png"))


if __name__ == "__main__":
    for m in MOODS:
        render(m)
