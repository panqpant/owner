"""Batch 9: the game's logo, taglines and badge pills as real 3D lettering (extruded, bevelled, gradient
faces, thick dark outline), rendered to transparent PNGs that the thumbnails and icons composite on.

Run:  python marketing/build_logo.py
Writes export/marketing/logo.png, export/marketing/tagline_<slug>.png and export/marketing/pill_<slug>.png.
"""

import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
sys.path.insert(0, ART)

import lib  # noqa: E402  (imports bpy)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

OUT = os.path.join(lib.EXPORT, "marketing")
FONT = os.path.join(ART, "fonts", "FredokaOne-Regular.ttf")
INK = "1b1c21"
TAGLINES = ("DELIVER ANYTHING!", "LEGENDARY DELIVERIES!", "LOADING THE CITY...")
# badge text -> fill colour, used by build_icons.py
PILLS = {"+": "43b85c", "2x": "43b85c", "PRO": "1fb5a8", "VIP": "8b5cf6", "+1": "3a7bf0", "S": "ffb02e", "M": "ffb02e", "L": "ffb02e", "XL": "ffb02e", "BOOST": "e8443a", "x2": "8b5cf6", "JAM": "e8443a"}


def slug(text):
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "plus"


def lin(hexcol):
    return tuple(((c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4) for c in bytes.fromhex(hexcol)) + (1,)


def mat(name, top, bottom=None, rough=0.35):
    """A flat colour, or a top-to-bottom gradient across the object's height (generated Y)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    if bottom is None:
        b.inputs["Base Color"].default_value = lin(top)
        return m
    tc, sep, ramp = nt.nodes.new("ShaderNodeTexCoord"), nt.nodes.new("ShaderNodeSeparateXYZ"), nt.nodes.new("ShaderNodeValToRGB")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    ramp.color_ramp.elements[0].color = lin(bottom)
    ramp.color_ramp.elements[1].color = lin(top)
    ramp.color_ramp.elements[0].position = 0.15
    ramp.color_ramp.elements[1].position = 0.8
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    return m


def text(body, size, loc, front, side, extrude=0.16, outline=0.075, rot=0.0):
    """Lettering as two meshes: the face (gradient on the front, darker sides) and a fatter ink outline behind it."""
    objs = []
    for part, ext, off, z in (("face", extrude, 0.0, 0.0), ("ink", extrude * 0.8, outline, -extrude * 0.5)):
        cu = bpy.data.curves.new(f"{body}_{part}", "FONT")
        cu.body = body
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
        cu.size = size
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        cu.space_character = 1.07  # the ink outline needs room between letters
        cu.extrude = ext
        cu.offset = off  # grows the glyph outline: the ink sits proud of the face all round
        cu.bevel_depth = 0.025 if part == "face" else 0.02
        cu.bevel_resolution = 3
        tmp = bpy.data.objects.new("tmp", cu)
        bpy.context.scene.collection.objects.link(tmp)
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        bpy.data.objects.remove(tmp)
        o = bpy.data.objects.new(f"{body}_{part}", me)
        bpy.context.scene.collection.objects.link(o)
        o.location = (loc[0], loc[1], z)
        o.rotation_euler = (0, 0, math.radians(rot))
        if part == "face":
            me.materials.append(front)
            me.materials.append(side)
            for p in me.polygons:
                p.material_index = 0 if p.normal.z > 0.75 else 1
        else:
            me.materials.append(mat("ink", INK, rough=0.5))
        for p in me.polygons:
            p.use_smooth = True
        objs.append(o)
    return objs


def pill_mesh(w, h, fill_hex, loc=(0, 0), rot=0.0):
    """A chunky rounded banner with an ink rim, behind the lettering."""
    out = []
    for name, ww, hh, z, col in (("ink", w + 0.16, h + 0.16, -0.32, INK), ("fill", w, h, -0.18, fill_hex)):
        r = hh / 2  # a stadium: straight middle, round ends
        ends = [(ww / 2 - r + math.cos(a) * r, math.sin(a) * r) for a in (math.radians(-90 + k * 10) for k in range(19))]
        o = lib.Mesh("Pill_" + name).prism(ends + [(-x, -y) for x, y in ends], 0.1, "white", thickness=0.2).done(sharp=60)
        o.data.materials.clear()
        o.data.materials.append(mat("pill_" + name, col) if name == "ink" else mat("pill_fill", lighten(col), col))
        o.location = (loc[0], loc[1], z)
        o.rotation_euler = (0, 0, math.radians(rot))
        out.append(o)
    return out


def lighten(hexcol, k=0.35):
    return "".join(f"{int(c + (255 - c) * k):02x}" for c in bytes.fromhex(hexcol))


def darken(hexcol, k=0.45):
    return "".join(f"{int(c * (1 - k)):02x}" for c in bytes.fromhex(hexcol))


def stage(objs, path, px_per_unit=180, margin=0.35):
    """Ortho camera looking straight down, tilted a touch so the extruded sides show below each letter."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 32
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"  # flat UI colours, as picked
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (1, 1, 1, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.75
    sc.world = w
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 2.2
    sun.data.angle = math.radians(20)
    sun.rotation_euler = (math.radians(30), math.radians(-20), 0)
    sc.collection.objects.link(sun)
    lo, hi = lib.bounds(objs)
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    w_, h_ = hi[0] - lo[0] + margin * 2, hi[1] - lo[1] + margin * 2
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(w_, h_)
    tilt = math.radians(14)
    cam.location = Vector((cx, cy - 20 * math.sin(tilt), 20 * math.cos(tilt)))
    cam.rotation_euler = (tilt, 0, 0)
    sc.collection.objects.link(cam)
    sc.camera = cam
    sc.render.resolution_x = int(w_ * px_per_unit)
    sc.render.resolution_y = int(h_ * px_per_unit * math.cos(tilt))
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    trim(path)
    print("wrote", path)


def trim(path, pad=8):
    from PIL import Image

    img = Image.open(path)
    box = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    img.crop((max(box[0] - pad, 0), max(box[1] - pad, 0), min(box[2] + pad, img.width), min(box[3] + pad, img.height))).save(path)


def logo():
    lib.reset()
    objs = text("RAGDOLL", 1.25, (0, 0.62), mat("rag", "ffe866", "ff9a1f"), mat("rag_side", "c4560f"), rot=3)
    objs += text("COURIERS", 1.0, (0.12, -0.5), mat("cou", "ffffff", "8fd0ff"), mat("cou_side", "2f6fd6"), rot=3)
    # a cardboard parcel tumbling off the end of RAGDOLL
    box = lib.Mesh("Parcel")
    box.box((0.62, 0.62, 0.62), (0, 0, 0), "cardboard", bevel=0.05)
    box.box((0.64, 0.14, 0.64), (0, 0, 0), "tape", bevel=0.01)
    p = box.done()
    p.location, p.rotation_euler = (2.95, 1.05, 0.2), (math.radians(25), math.radians(-30), math.radians(20))
    stage(objs + [p], os.path.join(OUT, "logo.png"))


def tagline(line):
    lib.reset()
    objs = text(line, 0.5, (0, 0), mat("tag", "ffffff", "ffe9c7"), mat("tag_side", "8a3d0c"), extrude=0.08, outline=0.05)
    lo, hi = lib.bounds(objs)
    objs += pill_mesh(hi[0] - lo[0] + 0.6, 0.85, "ff8a1f")
    for o in objs:
        o.rotation_euler.z = math.radians(2)
    stage(objs, os.path.join(OUT, f"tagline_{slug(line)}.png"), px_per_unit=200, margin=0.15)


def pill(label, colour):
    lib.reset()
    objs = text(label, 0.75, (0, 0), mat("p", "ffffff", "e6e6ee"), mat("p_side", darken(colour)), extrude=0.1, outline=0.06)
    lo, hi = lib.bounds(objs)
    objs += pill_mesh(max(hi[0] - lo[0] + 0.55, 1.05), 1.05, colour)
    stage(objs, os.path.join(OUT, f"pill_{slug(label)}.png"), px_per_unit=200, margin=0.1)


def main():
    os.makedirs(OUT, exist_ok=True)
    lib.write_palette()
    logo()
    for line in TAGLINES:
        tagline(line)
    for label, colour in PILLS.items():
        pill(label, colour)


if __name__ == "__main__":
    main()
