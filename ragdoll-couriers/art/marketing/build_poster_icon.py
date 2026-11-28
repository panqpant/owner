"""Batch 9: the game icon in the front-page "advert" style. One huge screaming courier with a painted
cartoon face, thick black outlines on everything, the TV and scooter flying, on a loud starburst. No
scenery: it has to read at the ~150 px the front page shows it at.

Run:  python marketing/build_poster_icon.py
Writes export/marketing/icon.png (1024) and previews/_icon_check.png (the icon at front-page sizes).
"""

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

import build_thumbnails as bt  # noqa: E402  (vehicle / parcel staging helpers)
import courier as courier_mod  # noqa: E402

OUT = os.path.join(lib.EXPORT, "marketing")
SIZE = 1024
INK = (24, 22, 30, 255)


# ---------------------------------------------------------------- the painted face
def face_texture(path):
    """A screaming cartoon face, drawn big and simple: wide eyes, tiny pupils, brows up, mouth wide open."""
    from PIL import Image, ImageDraw

    n = 1024
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = 22  # outline width
    for cx, tilt in ((300, 1), (724, -1)):
        d.ellipse((cx - 150, 250, cx + 150, 590), fill=(255, 255, 255, 255), outline=INK, width=w)  # eye
        d.ellipse((cx - 42 + tilt * 12, 330, cx + 42 + tilt * 12, 420), fill=INK)  # pupil, shrunk with fright
        d.ellipse((cx - 16 + tilt * 12 + 18, 345, cx + 4 + tilt * 12 + 18, 367), fill=(255, 255, 255, 255))  # catchlight
        # brow: a thick tilted bar, high and raised toward the middle (panic)
        x0, x1 = cx - 150, cx + 150
        y_out, y_in = 235, 165  # low enough to clear the cap's brim
        pts = [(x0, y_out if tilt > 0 else y_in), (x1, y_in if tilt > 0 else y_out)]
        d.line(pts, fill=INK, width=50, joint="curve")
        for p in pts:
            d.ellipse((p[0] - 25, p[1] - 25, p[0] + 25, p[1] + 25), fill=INK)
    # mouth: a wide open D, teeth along the top, tongue at the bottom
    mouth = (372, 640, 652, 1010)  # a tall "O": a scream, not a grin
    d.ellipse(mouth, fill=(120, 20, 30, 255))
    d.chord(mouth, 205, 335, fill=(255, 255, 255, 255))  # top teeth
    d.ellipse((430, 880, 594, 1000), fill=(240, 95, 110, 255))  # tongue
    d.ellipse(mouth, outline=INK, width=w)
    # sweat drops flying off
    for x, y, s in ((60, 120, 1.0), (930, 330, 0.8)):
        d.polygon([(x, y - 70 * s), (x + 38 * s, y), (x - 38 * s, y)], fill=(130, 210, 255, 255))
        d.ellipse((x - 40 * s, y - 30 * s, x + 40 * s, y + 50 * s), fill=(130, 210, 255, 255), outline=INK, width=8)
    img.save(path)
    return path


def face_decal(head, path):
    """The face image on a quad just proud of the head's front (+Y), oriented so it reads from the front."""
    me = bpy.data.meshes.new("Face")
    y, w, z0, z1 = 0.615, 0.64, 0.0, 1.22  # as big as the head front allows
    me.from_pydata([(w, y, z0), (-w, y, z0), (-w, y, z1), (w, y, z1)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for li, c in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = c
    m = bpy.data.materials.new("FaceMat")
    m.use_nodes = True
    nt = m.node_tree
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path)
    b = nt.nodes["Principled BSDF"]
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], b.inputs["Alpha"])
    b.inputs["Roughness"].default_value = 0.6
    me.materials.append(m)
    o = bpy.data.objects.new("Face", me)
    bpy.context.scene.collection.objects.link(o)
    o.parent = head
    return o


# ---------------------------------------------------------------- ink outlines
def outline_material():
    m = bpy.data.materials.new("Ink")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    geo, em, tr, mix, out = (nt.nodes.new(t) for t in ("ShaderNodeNewGeometry", "ShaderNodeEmission", "ShaderNodeBsdfTransparent", "ShaderNodeMixShader", "ShaderNodeOutputMaterial"))
    em.inputs["Color"].default_value = (0.01, 0.008, 0.015, 1)
    # see-through where the hull faces away (its near side: flipped normals point inward) and to every
    # non-camera ray, or the shell would shadow the model inside it black
    lp, inv, mx = nt.nodes.new("ShaderNodeLightPath"), nt.nodes.new("ShaderNodeMath"), nt.nodes.new("ShaderNodeMath")
    inv.operation, mx.operation = "SUBTRACT", "MAXIMUM"
    inv.inputs[0].default_value = 1.0
    nt.links.new(lp.outputs["Is Camera Ray"], inv.inputs[1])
    nt.links.new(geo.outputs["Backfacing"], mx.inputs[0])
    nt.links.new(inv.outputs[0], mx.inputs[1])
    nt.links.new(mx.outputs[0], mix.inputs["Fac"])
    nt.links.new(em.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def ink(objs, thickness):
    """Inverted-hull outlines: a flipped, slightly fatter shell behind every mesh."""
    m = outline_material()
    for o in objs:
        if o.type != "MESH" or o.name.startswith("Face"):
            continue
        o.data.materials.append(m)
        mod = o.modifiers.new("Ink", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = 1
        mod.use_flip_normals = True
        mod.use_rim = False
        mod.material_offset = len(o.data.materials) - 1


# ---------------------------------------------------------------- background and finish
def starburst(n, centre):
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("RGB", (n, n), (255, 178, 30))
    d = ImageDraw.Draw(img)
    cx, cy = centre
    rays = 18
    for k in range(rays):
        a0, a1 = (k * 2) * math.pi / rays, (k * 2 + 1) * math.pi / rays
        R = n * 1.5
        d.polygon([(cx, cy), (cx + math.cos(a0) * R, cy + math.sin(a0) * R), (cx + math.cos(a1) * R, cy + math.sin(a1) * R)], fill=(255, 214, 70))
    glow = Image.new("L", (n, n), 0)
    ImageDraw.Draw(glow).ellipse((cx - n * 0.35, cy - n * 0.35, cx + n * 0.35, cy + n * 0.35), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(n // 8))
    img = Image.composite(Image.new("RGB", (n, n), (255, 250, 220)), img, glow)
    edge = Image.new("L", (n, n), 0)
    ImageDraw.Draw(edge).ellipse((-n * 0.25, -n * 0.25, n * 1.25, n * 1.25), fill=255)
    edge = edge.filter(ImageFilter.GaussianBlur(n // 10))
    return Image.composite(img, Image.new("RGB", (n, n), (230, 90, 20)), edge)  # warm vignette


def finish(render_path, out_path):
    """Starburst behind, a thick dark sticker outline round the whole cut-out, then the render on top."""
    from PIL import Image, ImageFilter

    fg = Image.open(render_path).convert("RGBA")
    n = fg.width
    a = fg.getchannel("A")
    bbox = a.getbbox()
    bg = starburst(n, ((bbox[0] + bbox[2]) // 2, (bbox[1] + bbox[3]) // 2)).convert("RGBA")
    rim = a.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(1.5))
    sticker = Image.new("RGBA", (n, n), INK)
    sticker.putalpha(rim)
    shadow = Image.new("RGBA", (n, n), (90, 30, 0, 0))
    shadow.putalpha(rim.filter(ImageFilter.GaussianBlur(14)).point(lambda v: v * 120 // 255))
    bg.alpha_composite(shadow, (10, 16))
    bg.alpha_composite(sticker)
    bg.alpha_composite(fg)
    bg.convert("RGB").save(out_path)


def check_sheet(icon_path):
    """The icon at the sizes players actually see it: front-page tile, search result, and full."""
    from PIL import Image

    icon = Image.open(icon_path).convert("RGB")
    out = Image.new("RGB", (512 + 40 + 150 + 30 + 90 + 40, 552), (30, 31, 36))
    out.paste(icon.resize((512, 512), Image.LANCZOS), (20, 20))
    out.paste(icon.resize((150, 150), Image.LANCZOS), (552, 20))
    out.paste(icon.resize((90, 90), Image.LANCZOS), (552 + 180, 20))
    out.save(os.path.join(lib.PREVIEWS, "_icon_check.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    lib.reset()
    lib.write_palette()
    sc = bpy.context.scene
    face = face_texture(os.path.join(OUT, "_face_scream.png"))

    # courier, big and central, flung back toward the camera with arms out
    root, parts = courier_mod.courier("fly", location=(0, 0, 0), rotation=(-12, 14, 8), face="none", hair="bacon")
    head = next(p for p in parts if p.name.startswith("C_Head"))
    head.scale = (1.5, 1.5, 1.5)  # cartoon big head: the face is what reads at 150 px
    face_decal(head, face)
    # the camera looks toward -Y, so -X is frame right
    bt.parcel("Parcel_Cake", (-3.0, 2.0, 4.6), (-50, 15, 25))  # flying past the lens, upper right: bright and funny
    bt.vehicle("Vehicle_Scooter", (3.2, -3.0, -0.6), (40, -35, 120), "e8443a")  # flipping away, lower left
    bpy.context.view_layer.update()
    ink([o for o in sc.objects if o.type == "MESH"], 0.07)

    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.film_transparent = True
    sc.render.resolution_x = sc.render.resolution_y = SIZE
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (1, 0.95, 0.85, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.1
    sc.world = w
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy = 3.0
    sun.data.angle = math.radians(15)
    sun.rotation_euler = Vector((0.5, 1.0, 1.2)).to_track_quat("Z", "Y").to_euler()  # from the front, above, left
    sc.collection.objects.link(sun)

    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.lens = 50
    cam.location = (0.6, 14.0, 3.5)  # close: the courier fills most of the square
    cam.rotation_euler = (Vector((0, 0, 2.8)) - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.collection.objects.link(cam)
    sc.camera = cam

    import tempfile

    raw = os.path.join(tempfile.gettempdir(), "_icon_raw.png")
    sc.render.filepath = raw
    bpy.ops.render.render(write_still=True)
    out = os.path.join(OUT, "icon.png")
    finish(raw, out)
    check_sheet(out)
    print("wrote", out)


if __name__ == "__main__":
    main()
