"""Shared Blender helpers for Ragdoll Couriers art.

Everything is built in studs (1 Blender unit = 1 stud), facing +Y (front) with +Z up.
The FBX export maps that to Roblox's -Z forward / +Y up, so imported models face LookVector.
Every mesh uses one palette texture: each face's UVs sit on a single colour swatch.
"""

import json
import math
import os

import bpy  # must come first: the bpy wheel provides bmesh and mathutils
import bmesh
from mathutils import Euler, Matrix, Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(ROOT, "export")
PREVIEWS = os.path.join(ROOT, "previews")

# name: (hex colour, metalness 0-1, roughness 0-1, alpha 0-1)
PALETTE = {
    "white": ("f4f4f8", 0, 0.6, 1),
    "cream": ("fff1d6", 0, 0.7, 1),
    "lightgrey": ("c9ccd4", 0, 0.6, 1),
    "grey": ("8a8f9c", 0, 0.6, 1),
    "charcoal": ("3a3d46", 0, 0.6, 1),
    "black": ("1b1c21", 0, 0.5, 1),
    "rubber": ("26272b", 0, 0.95, 1),
    "red": ("e8443a", 0, 0.45, 1),
    "coral": ("ff7b5c", 0, 0.5, 1),
    "orange": ("ff9a2e", 0, 0.45, 1),
    "yellow": ("ffd23f", 0, 0.45, 1),
    "lime": ("a6e34a", 0, 0.5, 1),
    "green": ("43b85c", 0, 0.5, 1),
    "darkgreen": ("2c7a43", 0, 0.7, 1),
    "teal": ("1fb5a8", 0, 0.45, 1),
    "skyblue": ("6ec6ff", 0, 0.45, 1),
    "blue": ("3a7bf0", 0, 0.45, 1),
    "navy": ("23306b", 0, 0.5, 1),
    "purple": ("8b5cf6", 0, 0.45, 1),
    "pink": ("ff8fc7", 0, 0.55, 1),
    "magenta": ("e83e8c", 0, 0.45, 1),
    "brown": ("8b5a3c", 0, 0.75, 1),
    "darkbrown": ("51331f", 0, 0.8, 1),
    "tan": ("d2a679", 0, 0.75, 1),
    "wood": ("b07a4a", 0, 0.8, 1),
    "cardboard": ("c69c6d", 0, 0.9, 1),
    "tape": ("e9d8a6", 0, 0.4, 1),
    "skin": ("f2c79a", 0, 0.7, 1),
    "gold": ("ffc83d", 1, 0.25, 1),
    "chrome": ("dfe3ea", 1, 0.15, 1),
    "steel": ("9aa3b0", 1, 0.4, 1),
    "glass": ("bfe6ff", 0, 0.05, 0.35),
    "water": ("4fb3ff", 0, 0.05, 0.55),
    "screen": ("10141c", 0, 0.1, 1),
    "neongreen": ("5cff8f", 0, 0.3, 1),
    "neonorange": ("ffb02e", 0, 0.3, 1),
    "neonblue": ("5ce1ff", 0, 0.3, 1),
    "headlight": ("fffbe0", 0, 0.1, 1),
    "taillight": ("ff2a2a", 0, 0.2, 1),
    "brick": ("b9553f", 0, 0.9, 1),
    "stone": ("a8a29a", 0, 0.9, 1),
    "asphalt": ("40424a", 0, 0.95, 1),
    "concrete": ("b8b6b0", 0, 0.9, 1),
    "grass": ("6cc04a", 0, 0.9, 1),
    "sand": ("e8d39a", 0, 0.95, 1),
    "rust": ("a4552c", 0.4, 0.8, 1),
    "icing": ("fff6fb", 0, 0.35, 1),
    "chocolate": ("6b3b25", 0, 0.5, 1),
    "pizza": ("f0b44c", 0, 0.8, 1),
    "pumpkin": ("ff8a1f", 0, 0.6, 1),
    "alien": ("8dff5a", 0, 0.3, 1),
    "comb": ("e8243a", 0, 0.6, 1),
    "tint": ("7fb4d9", 0.2, 0.08, 1),  # opaque tower glass: reads as glass without transparency costs
    "tintdark": ("3d6f99", 0.2, 0.08, 1),
}
NAMES = list(PALETTE)
GRID = 8  # 8x8 swatches
SWATCH = 32  # px each -> 256px textures


def uv_of(colour: str):
    i = NAMES.index(colour)
    x, y = i % GRID, i // GRID
    return ((x + 0.5) / GRID, 1 - (y + 0.5) / GRID)


def write_palette():
    """Writes palette_color.png (RGBA), palette_metal.png and palette_rough.png."""
    from PIL import Image

    size = GRID * SWATCH
    col = Image.new("RGBA", (size, size), (255, 0, 255, 255))
    metal = Image.new("L", (size, size), 0)
    rough = Image.new("L", (size, size), 255)
    for i, (hexc, m, r, a) in enumerate(PALETTE.values()):
        x, y = (i % GRID) * SWATCH, (i // GRID) * SWATCH
        rgb = tuple(int(hexc[j : j + 2], 16) for j in (0, 2, 4))
        box = (x, y, x + SWATCH, y + SWATCH)
        col.paste(rgb + (int(a * 255),), box)
        metal.paste(int(m * 255), box)
        rough.paste(int(r * 255), box)
    os.makedirs(EXPORT, exist_ok=True)
    col.save(os.path.join(EXPORT, "palette_color.png"))
    metal.save(os.path.join(EXPORT, "palette_metal.png"))
    rough.save(os.path.join(EXPORT, "palette_rough.png"))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def material():
    if "Palette" in bpy.data.materials:
        return bpy.data.materials["Palette"]
    m = bpy.data.materials.new("Palette")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]

    def tex(name, colour_space):
        img = bpy.data.images.load(os.path.join(EXPORT, name), check_existing=True)
        img.colorspace_settings.name = colour_space
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.interpolation = "Closest"
        return node

    c = tex("palette_color.png", "sRGB")
    nt.links.new(c.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(c.outputs["Alpha"], bsdf.inputs["Alpha"])
    nt.links.new(tex("palette_metal.png", "Non-Color").outputs["Color"], bsdf.inputs["Metallic"])
    nt.links.new(tex("palette_rough.png", "Non-Color").outputs["Color"], bsdf.inputs["Roughness"])
    return m


def _matrix(loc, rot, scale=(1, 1, 1)):
    return Matrix.LocRotScale(Vector(loc), Euler([math.radians(a) for a in rot]), Vector(scale))


class Mesh:
    """Accumulates coloured primitives into one mesh object (one Roblox MeshPart)."""

    def __init__(self, name: str):
        self.name = name
        self.bm = bmesh.new()
        self.bm.loops.layers.uv.new("UVMap")

    def _merge(self, tmp: bmesh.types.BMesh, colour: str, matrix: Matrix, bevel: float, segments: int, angle: float = 30):
        if bevel > 0:
            edges = [e for e in tmp.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(angle)]
            if edges:
                bmesh.ops.bevel(tmp, geom=edges, offset=bevel, segments=segments, profile=0.5, affect="EDGES", clamp_overlap=True)
        bmesh.ops.transform(tmp, matrix=matrix, verts=tmp.verts)
        uv = tmp.loops.layers.uv.verify()
        u = uv_of(colour)
        for f in tmp.faces:
            for loop in f.loops:
                loop[uv].uv = u
        me = bpy.data.meshes.new("tmp")
        tmp.to_mesh(me)
        tmp.free()
        self.bm.from_mesh(me)
        bpy.data.meshes.remove(me)
        return self

    def box(self, size, loc=(0, 0, 0), colour="white", rot=(0, 0, 0), bevel=0.08, segments=2):
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1)
        bmesh.ops.scale(tmp, vec=Vector(size), verts=tmp.verts)
        return self._merge(tmp, colour, _matrix(loc, rot), min(bevel, min(size) * 0.45), segments)

    def wedge(self, size, loc=(0, 0, 0), colour="white", rot=(0, 0, 0), bevel=0.05):
        """Box whose top slopes down toward +Y (a ramp rising toward -Y)."""
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1)
        for v in tmp.verts:
            if v.co.z > 0 and v.co.y > 0:
                v.co.z = -0.5 + 0.02
        bmesh.ops.remove_doubles(tmp, verts=tmp.verts, dist=0.001)
        bmesh.ops.scale(tmp, vec=Vector(size), verts=tmp.verts)
        return self._merge(tmp, colour, _matrix(loc, rot), bevel, 1)

    def cyl(self, r, h, loc=(0, 0, 0), colour="white", rot=(0, 0, 0), segments=24, bevel=0.05, r2=None, bseg=2):
        """Cylinder (or cone with r2) along local Z, centred."""
        tmp = bmesh.new()
        bmesh.ops.create_cone(tmp, cap_ends=True, cap_tris=False, segments=segments, radius1=r, radius2=r if r2 is None else r2, depth=h)
        return self._merge(tmp, colour, _matrix(loc, rot), min(bevel, h * 0.45, r * 0.45), bseg, angle=50)

    def sphere(self, r, loc=(0, 0, 0), colour="white", scale=(1, 1, 1), rot=(0, 0, 0), segments=20, rings=12):
        tmp = bmesh.new()
        bmesh.ops.create_uvsphere(tmp, u_segments=segments, v_segments=rings, radius=r)
        return self._merge(tmp, colour, _matrix(loc, rot, scale), 0, 1)

    def tube(self, a, b, r, colour="steel", segments=12):
        """Cylinder from point a to point b."""
        a, b = Vector(a), Vector(b)
        d = b - a
        tmp = bmesh.new()
        bmesh.ops.create_cone(tmp, cap_ends=True, segments=segments, radius1=r, radius2=r, depth=d.length)
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        return self._merge(tmp, colour, Matrix.Translation((a + b) / 2) @ rot, 0, 1)

    def lathe(self, profile, loc=(0, 0, 0), colour="white", rot=(0, 0, 0), segments=32):
        """Spin a (radius, z) profile around local Z. Closes the ends at radius 0."""
        tmp = bmesh.new()
        verts = [tmp.verts.new((r, 0, z)) for r, z in profile]
        edges = [tmp.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
        bmesh.ops.spin(tmp, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=math.tau, steps=segments, use_merge=True)
        bmesh.ops.remove_doubles(tmp, verts=tmp.verts, dist=0.0005)
        bmesh.ops.recalc_face_normals(tmp, faces=tmp.faces)
        return self._merge(tmp, colour, _matrix(loc, rot), 0, 1)

    def tire(self, r, width, loc=(0, 0, 0), colour="rubber", hub="chrome", rot=(0, 90, 0), segments=28):
        """A rounded tyre with a hub, axle along local Z (rot default puts the axle on X)."""
        t = width / 2
        rr = r * 0.62
        prof = [(rr, -t), (r - t * 0.6, -t), (r - t * 0.15, -t * 0.75), (r, -t * 0.3), (r, t * 0.3), (r - t * 0.15, t * 0.75), (r - t * 0.6, t), (rr, t)]
        self.lathe(prof, loc, colour, rot, segments)
        self.cyl(rr, width * 0.9, loc, hub, rot, segments=segments, bevel=0.06)
        return self.cyl(rr * 0.35, width * 1.05, loc, "charcoal", rot, segments=12, bevel=0.03)

    def rock(self, r, loc=(0, 0, 0), colour="stone", scale=(1, 1, 1), seed=1, lumpiness=0.22, subdivisions=2):
        """Faceted lumpy rock (icosphere with each vertex pushed in or out)."""
        import random

        rnd = random.Random(seed)
        tmp = bmesh.new()
        bmesh.ops.create_icosphere(tmp, subdivisions=subdivisions, radius=r)
        for v in tmp.verts:
            v.co *= 1 + rnd.uniform(-lumpiness, lumpiness)
        return self._merge(tmp, colour, _matrix(loc, (0, 0, rnd.uniform(0, 360)), scale), 0, 1)

    def done(self, location=(0, 0, 0), sharp=35) -> bpy.types.Object:
        me = bpy.data.meshes.new(self.name)
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.0001)
        self.bm.to_mesh(me)
        self.bm.free()
        for p in me.polygons:
            p.use_smooth = True
        me.set_sharp_from_angle(angle=math.radians(sharp))
        me.materials.append(material())
        obj = bpy.data.objects.new(self.name, me)
        obj.location = location
        bpy.context.scene.collection.objects.link(obj)
        return obj


def tris(objs) -> int:
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)


def export(asset: str, objs, meta: dict | None = None):
    """One FBX per asset; meta (attachment points etc.) goes to export/<asset>.json."""
    os.makedirs(EXPORT, exist_ok=True)
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(EXPORT, asset + ".fbx"),
        use_selection=True,
        object_types={"MESH"},
        apply_unit_scale=True,
        apply_scale_options="FBX_SCALE_UNITS",
        axis_forward="-Z",
        axis_up="Y",
        bake_space_transform=True,
        mesh_smooth_type="FACE",
        use_mesh_modifiers=True,
        path_mode="STRIP",
    )
    info = {"triangles": tris(objs), "parts": {}}
    for o in objs:
        lo, hi = bounds([o])
        c = [(lo[i] + hi[i]) / 2 for i in range(3)]
        # Roblox frame: x right, y up, -z forward. "centre" is where the imported MeshPart sits.
        info["parts"][o.name] = {"triangles": tris([o]), "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)]}
    lo, hi = bounds(objs)
    info["size_studs"] = [round(hi[0] - lo[0], 2), round(hi[2] - lo[2], 2), round(hi[1] - lo[1], 2)]  # Roblox X, Y, Z
    if meta:
        info.update(meta)
    with open(os.path.join(EXPORT, asset + ".json"), "w") as f:
        json.dump(info, f, indent=1)
    return info


def bounds(objs):
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def preview(asset: str, objs, samples: int = 24, res: int = 420):
    """3/4 front view, Cycles on CPU, soft studio light."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = res
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    lo, hi = bounds(objs)
    centre = Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
    extent = max(hi[i] - lo[i] for i in range(3))

    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.75, 0.82, 0.95, 1)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.9
    scene.world = world

    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.2
    sun.data.angle = math.radians(12)
    sun.rotation_euler = Euler((math.radians(50), 0, math.radians(140)))
    scene.collection.objects.link(sun)

    floor = Mesh("floor").box((extent * 8, extent * 8, 0.02), (centre.x, centre.y, lo[2] - 0.011), "lightgrey", bevel=0).done()

    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = extent * 1.45
    direction = Vector((1.0, 1.25, 0.8)).normalized()
    cam.location = centre + direction * extent * 4
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = extent * 20
    scene.collection.objects.link(cam)
    scene.camera = cam

    os.makedirs(PREVIEWS, exist_ok=True)
    scene.render.filepath = os.path.join(PREVIEWS, asset + ".png")
    bpy.ops.render.render(write_still=True)
    for o in (sun, floor, cam):
        bpy.data.objects.remove(o)


def contact_sheet(names, out: str, cols: int = 5):
    from PIL import Image, ImageDraw

    imgs = [(n, Image.open(os.path.join(PREVIEWS, n + ".png"))) for n in names]
    w, h = imgs[0][1].size
    rows = math.ceil(len(imgs) / cols)
    sheet = Image.new("RGB", (cols * w, rows * (h + 28)), (30, 32, 40))
    d = ImageDraw.Draw(sheet)
    for i, (n, im) in enumerate(imgs):
        x, y = (i % cols) * w, (i // cols) * (h + 28)
        sheet.paste(im.convert("RGB"), (x, y))
        d.text((x + 8, y + h + 6), n, fill=(240, 240, 240))
    sheet.save(os.path.join(PREVIEWS, out))
