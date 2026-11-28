"""Batch 9: store and UI icons. Every vehicle, parcel, upgrade, game pass and developer product as a
512 x 512 transparent PNG with a soft shadow, plus a badge where the item needs one (2x, VIP, PRO...).

Run:  python marketing/build_icons.py         (needs Blender's Python module and Pillow)
Writes export/icons/<group>_<name>.png and previews/_icons.png.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
sys.path.insert(0, ART)

import lib  # noqa: E402  (imports bpy)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

from assets import items, landmarks, parcels, vehicles, world  # noqa: E402

KIT = {**world.ASSETS, **landmarks.ASSETS, **vehicles.ASSETS, **parcels.ASSETS, **items.ASSETS}
OUT = os.path.join(lib.EXPORT, "icons")
FONT = os.path.join(ART, "fonts", "FredokaOne-Regular.ttf")

VEHICLE_PAINT = {"Vehicle_Scooter": "e8443a", "Vehicle_EBike": "3a7bf0", "Vehicle_CargoBike": "43b85c", "Vehicle_Van": "ff9a2e", "Vehicle_RocketScooter": "8b5cf6"}

# (icon name, asset, badge text or None, badge colour)
ICONS = (
    [(f"vehicle_{a[8:].lower()}", a, None, None) for a in vehicles.ASSETS]
    + [(f"parcel_{a[7:].lower()}", a, None, None) for a in parcels.ASSETS]
    + [
        ("upgrade_suspension", "Item_Spring", None, None),
        ("upgrade_padding", "Item_BubbleWrap", None, None),
        ("upgrade_engine", "Item_Engine", None, None),
        ("upgrade_cargo", "Parcel_Post", "+", "43b85c"),
        ("upgrade_brakes", "Item_Brake", None, None),
        ("pass_2xpay", "Item_CoinsLarge", "2x", "43b85c"),
        ("pass_bubblewrap_pro", "Item_BubbleWrap", "PRO", "1fb5a8"),
        ("pass_vip", "Item_Crown", "VIP", "8b5cf6"),
        ("pass_autoroute", "Item_RoutePin", None, None),
        ("pass_garage_slot", "Vehicle_Scooter", "+1", "3a7bf0"),
        ("product_cash_small", "Item_CoinsSmall", "S", "ffb02e"),
        ("product_cash_medium", "Item_CoinsMedium", "M", "ffb02e"),
        ("product_cash_large", "Item_CoinsLarge", "L", "ffb02e"),
        ("product_cash_huge", "Item_CoinsHuge", "XL", "ffb02e"),
        ("product_rocket_boost", "Vehicle_RocketScooter", "BOOST", "e8443a"),
        ("product_insurance", "Item_Shield", None, None),
        ("product_lucky_hour", "Item_Hourglass", "x2", "8b5cf6"),
        ("product_banana", "Item_BananaPeel", None, None),
        ("product_traffic_jam", "Traffic_Car", "JAM", "e8443a"),
        ("product_starter_pack", "Item_StarterPack", None, None),
        ("product_crate", "Item_Crate", None, None),
    ]
)


def paint(objs, hexcol):
    """Give Paint parts a fixed colour for the icon (in game, Paint takes the skin colour)."""
    lin = tuple(((c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4) for c in bytes.fromhex(hexcol))
    m = bpy.data.materials.new("IconPaint")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*lin, 1)
    b.inputs["Roughness"].default_value = 0.4
    for o in objs:
        if o.name.startswith("Paint"):
            o.data.materials[0] = m


def stage():
    """Soft studio light and a shadow catcher, on a transparent background."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x = sc.render.resolution_y = 512
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.85, 0.9, 1.0, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 0.8
    sc.world = w
    key = bpy.data.objects.new("Key", bpy.data.lights.new("Key", "SUN"))
    key.data.energy = 3.2
    key.data.angle = math.radians(10)
    key.rotation_euler = (math.radians(45), 0, math.radians(150))
    sc.collection.objects.link(key)


def frame(objs):
    lo, hi = lib.bounds(objs)
    centre = Vector([(lo[i] + hi[i]) / 2 for i in range(3)])
    size = max(hi[i] - lo[i] for i in range(3))
    floor = lib.Mesh("Floor").box((size * 6, size * 6, 0.01), (centre.x, centre.y, lo[2] - 0.006), "white", bevel=0).done()
    floor.is_shadow_catcher = True
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = (Vector(hi) - Vector(lo)).length * 1.02  # the full diagonal: boxes seen corner-on fit
    d = Vector((1.0, 1.25, 0.75)).normalized()
    cam.location = centre + d * size * 4
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.clip_end = size * 20
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam


def badge(path, text, colour):
    """The 3D pill from marketing/build_logo.py (PILLS sets its colour) in the bottom-right corner."""
    import re

    from PIL import Image

    img = Image.open(path).convert("RGBA")
    pill = Image.open(os.path.join(lib.EXPORT, "marketing", "pill_" + (re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "plus") + ".png")).convert("RGBA")
    k = min((150 if len(text) <= 2 else 120) / pill.height, 300 / pill.width)  # keep the aspect, cap long words
    pill = pill.resize((int(pill.width * k), int(pill.height * k)), Image.LANCZOS)
    img.alpha_composite(pill, (512 - pill.width - 14, 512 - pill.height - 14))
    img.save(path)


def sheet(names):
    from PIL import Image, ImageDraw

    cols, cell = 9, 180
    rows = math.ceil(len(names) / cols)
    out = Image.new("RGB", (cols * cell, rows * (cell + 18)), (52, 56, 70))
    d = ImageDraw.Draw(out)
    for k, n in enumerate(names):
        im = Image.open(os.path.join(OUT, n + ".png")).convert("RGBA").resize((cell - 10, cell - 10))
        x, y = (k % cols) * cell, (k // cols) * (cell + 18)
        out.paste(im, (x + 5, y + 5), im)
        d.text((x + 4, y + cell + 2), n, fill=(225, 225, 230))
    out.save(os.path.join(lib.PREVIEWS, "_icons.png"))


def main(only=()):
    os.makedirs(OUT, exist_ok=True)
    lib.write_palette()
    done = []
    for name, asset, text, colour in ICONS:
        if only and name not in only:
            continue
        lib.reset()
        objs, _ = KIT[asset]()
        if asset in VEHICLE_PAINT:
            paint(objs, VEHICLE_PAINT[asset])
        elif any(o.name.startswith("Paint") for o in objs):
            paint(objs, "e8443a")
        stage()
        frame(objs)
        path = os.path.join(OUT, name + ".png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        if text:
            badge(path, text, colour)
        done.append(name)
        print("icon", name)
    if not only:
        sheet(done)


if __name__ == "__main__":
    main(set(sys.argv[1:]))
