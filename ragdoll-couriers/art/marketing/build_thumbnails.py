"""Batch 9: game thumbnails, the game icon and the loading screen, staged in the real city.

Run:  python marketing/build_thumbnails.py [names...] [--draft]
Needs map/city.blend (from map/build_map.py). Writes export/marketing/*.png (1920 x 1080, icon 512)
and previews/_thumbnails.png. Thumbnails with "_title" have the game's name on them; Roblox lets you
upload several and tests which gets the most clicks.
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.dirname(HERE)
sys.path.insert(0, ART)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ART, "map"))
sys.path.insert(0, os.path.join(ART, "sky"))

import lib  # noqa: E402  (imports bpy)
import bpy  # noqa: E402
from mathutils import Euler, Vector  # noqa: E402

import courier as courier_mod  # noqa: E402
from assets import parcels, vehicles  # noqa: E402

OUT = os.path.join(lib.EXPORT, "marketing")
FONT = os.path.join(ART, "fonts", "FredokaOne-Regular.ttf")
DRAFT = "--draft" in sys.argv


def rad(v):
    return Euler([math.radians(a) for a in v])


def place(objs, location, rotation=(0, 0, 0), paint_hex=None, name="Prop"):
    """Parent a freshly built asset to an empty so the whole thing moves and spins as one."""
    root = bpy.data.objects.new(name, None)
    root.location = location
    root.rotation_euler = rad(rotation)
    bpy.context.scene.collection.objects.link(root)
    for o in objs:
        o.parent = root
        if paint_hex and o.name.startswith("Paint"):
            lin = tuple(((c / 255) / 12.92 if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4) for c in bytes.fromhex(paint_hex))
            m = bpy.data.materials.new("ThumbPaint")
            m.use_nodes = True
            m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*lin, 1)
            o.data.materials[0] = m
    return root


def vehicle(kind, location, rotation, colour="e8443a"):
    objs, _ = vehicles.ASSETS[kind]()
    return place(objs, location, rotation, colour, kind)


def parcel(kind, location, rotation):
    objs, _ = parcels.ASSETS[kind]()
    return place(objs, location, rotation, None, kind)


def confetti(centre, count=60, spread=10, seed=1):
    rnd = random.Random(seed)
    m = lib.Mesh("Confetti")
    for _ in range(count):
        m.box((0.5, 0.1, 0.9), (centre[0] + rnd.uniform(-spread, spread), centre[1] + rnd.uniform(-spread, spread), centre[2] + rnd.uniform(0, spread)),
              rnd.choice(("red", "yellow", "blue", "lime", "pink", "orange", "purple")), rot=(rnd.uniform(0, 360), rnd.uniform(0, 360), rnd.uniform(0, 360)), bevel=0)
    m.done()


def sky(mood):
    import build_sky

    bpy.context.scene.world = build_sky.world(build_sky.MOODS[mood])
    sun = bpy.data.objects.get("Sun")
    if sun:
        sun.rotation_euler = Vector(build_sky.MOODS[mood]["sun_dir"]).to_track_quat("Z", "Y").to_euler()
        sun.data.color = build_sky.MOODS[mood]["sun_col"]
        sun.data.energy = 3.5 if mood == "day" else 3.0


def camera(location, target, lens, res):
    sc = bpy.context.scene
    cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.type = "PERSP"
    cam.data.lens = lens
    cam.data.clip_end = 20000
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 12 if DRAFT else 40
    sc.cycles.use_denoising = True
    w, h = res
    scale = 0.5 if DRAFT else 1.0
    sc.render.resolution_x, sc.render.resolution_y = int(w * scale), int(h * scale)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"  # thumbnails want saturated, high-contrast colour


def mountain_frame(frac):
    import plan

    p = plan.plan()
    pts = next(r for r in p["free_roads"] if r["name"] == "Mountain")["points"]
    k = int(len(pts) * frac)
    (x0, y0, z0), (x1, y1, _) = pts[k], pts[k + 2]
    heading = math.degrees(math.atan2(y1 - y0, x1 - x0)) - 90  # vehicles face +Y
    return (x0, y0, z0), heading


def causeway_frame(frac):
    import plan

    p = plan.plan()
    pts = next(r for r in p["free_roads"] if r["name"] == "Causeway")["points"]
    k = int(len(pts) * frac)
    (x0, y0, z0), (x1, y1, _) = pts[k], pts[k + 2]
    return (x0, y0, z0), math.degrees(math.atan2(y1 - y0, x1 - x0)) - 90


# ---------------------------------------------------------------- scenes
def crash(cam, target, vehicle_kind, parcel_kind, colour, pose="fly", near=13.0, lens=30, spin=0):
    """A crash composed around the camera, so the action fills the frame wherever it's staged:
    courier `near` studs out on the line of sight, the parcel flying past nearer the lens to one side,
    the vehicle tumbling further back to the other."""
    c, t = Vector(cam), Vector(target)
    f = (t - c).normalized()
    r = f.cross(Vector((0, 0, 1))).normalized()
    u = r.cross(f)
    yaw = math.degrees(math.atan2(f.y, f.x)) + 90  # the courier faces back toward the camera
    courier_mod.courier(pose, location=tuple(c + f * near - u * 1.5), rotation=(-25, 20 + spin, yaw + 160))
    parcel(parcel_kind, tuple(c + f * (near - 4) + r * 4.2 + u * 2.6), (30, 40, yaw + 20))
    vehicle(vehicle_kind, tuple(c + f * (near + 9) - r * 6 - u * 2.5), (45, -30, yaw + 130), colour)
    return cam, target, lens


def scene_hub_ramp():
    sky("day")  # from the ramp's landing side looking back at the ramp and the depot
    return crash((10, -62, 5), (-2, -10, 12), "Vehicle_Scooter", "Parcel_TV", "e8443a")


def scene_oldtown():
    sky("day")
    return crash((160, 606, 4), (160, 660, 9), "Vehicle_EBike", "Parcel_FishTank", "3a7bf0", pose="tumble", spin=40)


def scene_mountain():
    sky("day")
    (x, y, z), heading = mountain_frame(0.62)
    vehicle("Vehicle_Scooter", (x, y, z + 1.8), (0, 8, heading))
    r = math.radians(heading)
    courier_mod.courier("ride", location=(x - math.sin(r) * -0.35, y + math.cos(r) * -0.35, z + 0.9), rotation=(0, 8, heading))
    parcel("Parcel_Cake", (x + math.sin(r) * 1.75, y - math.cos(r) * 1.75, z + 3.9), (0, 0, heading))
    fx, fy = -math.sin(r), math.cos(r)  # the way it's heading
    return (x + fx * 18 + fy * 12, y + fy * 18 - fx * 12, z + 8), (x - fx * 14, y - fy * 14, z - 3), 28


def scene_docks():
    sky("day")  # off the end of the quay, the ship behind
    return crash((-880, 60, 5), (-905, 110, 9), "Vehicle_Scooter", "Parcel_Chicken", "ffd23f", spin=-30)


def scene_skeleton():
    sky("day")
    return crash((112, -455, 10), (80, -510, 22), "Vehicle_Scooter", "Parcel_Laptop", "43b85c", near=15)


def scene_causeway():
    sky("sunset")
    (x, y, z), heading = causeway_frame(0.5)
    vehicle("Vehicle_Scooter", (x + 6, y, z + 1.8), (0, 6, heading), "8b5cf6")
    r = math.radians(heading)
    courier_mod.courier("ride", location=(x + 6 + math.sin(r) * 0.35, y - math.cos(r) * 0.35, z + 0.9), rotation=(0, 6, heading))
    parcel("Parcel_Present", (x + 6 + math.sin(r) * 1.75, y - math.cos(r) * 1.75, z + 3.6), (0, 0, heading + 15))
    return (x + 24, y - 18, z + 4), (x + 4, y + 2, z + 3), 32


def scene_piano():
    sky("day")  # down the middle of the Downtown avenue
    return crash((0, -540, 4), (0, -480, 12), "Vehicle_CargoBike", "Parcel_Piano", "ff9a2e", pose="tumble", near=14, spin=60)


def scene_legendary():
    sky("day")
    gx, gy = 560, 160  # a suburbs street
    parcel("Parcel_GoldStatue", (gx - 2, gy - 6, 1.3), (0, 0, 200))
    courier_mod.courier("wave", location=(gx + 4, gy, 0), rotation=(0, 0, 210))
    vehicle("Vehicle_Scooter", (gx - 6, gy + 3, 1.8), (0, 0, 120))
    confetti((gx, gy, 6), count=90, spread=12)
    return (gx + 22, gy - 24, 6), (gx, gy, 4), 32


SCENES = {
    "thumb_ramp_crash": scene_hub_ramp,
    "thumb_oldtown_fishtank": scene_oldtown,
    "thumb_mountain": scene_mountain,
    "thumb_docks": scene_docks,
    "thumb_skeleton_jump": scene_skeleton,
    "thumb_causeway_sunset": scene_causeway,
    "thumb_piano": scene_piano,
    "thumb_legendary": scene_legendary,
}


def title(path, out, line2="DELIVER ANYTHING!"):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(img)
    s = img.width / 1920
    f1, f2 = ImageFont.truetype(FONT, int(150 * s)), ImageFont.truetype(FONT, int(80 * s))
    d.text((int(60 * s), int(40 * s)), "RAGDOLL", font=f1, fill=(255, 210, 63), stroke_width=int(12 * s), stroke_fill=(27, 28, 33))
    d.text((int(60 * s), int(190 * s)), "COURIERS", font=f1, fill=(255, 255, 255), stroke_width=int(12 * s), stroke_fill=(27, 28, 33))
    d.text((int(66 * s), int(350 * s)), line2, font=f2, fill=(255, 154, 46), stroke_width=int(9 * s), stroke_fill=(27, 28, 33))
    img.save(out)


def render_scene(name, fn, res=(1920, 1080)):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(ART, "map", "city.blend"))
    cam_loc, target, lens = fn()
    camera(cam_loc, target, lens, res)
    path = os.path.join(OUT, name + ".png")
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", name)
    return path


def main(only):
    os.makedirs(OUT, exist_ok=True)
    done = []
    for name, fn in SCENES.items():
        if only and name not in only:
            continue
        path = render_scene(name, fn)
        done.append(name)
        if name in ("thumb_ramp_crash", "thumb_oldtown_fishtank", "thumb_legendary"):
            title(path, os.path.join(OUT, name + "_title.png"), "LEGENDARY DELIVERIES!" if "legendary" in name else "DELIVER ANYTHING!")
            done.append(name + "_title")
    if not only or "icon" in only:  # the game icon: the ramp crash, close and square
        bpy.ops.wm.open_mainfile(filepath=os.path.join(ART, "map", "city.blend"))
        sky("day")  # the icon: a tight crash against open sky, readable at phone size
        cam = crash((0, -40, 2), (0, 10, 12), "Vehicle_Scooter", "Parcel_TV", "e8443a", near=9)
        camera(cam[0], cam[1], 24, (512, 512))
        bpy.context.scene.render.filepath = os.path.join(OUT, "icon.png")
        bpy.ops.render.render(write_still=True)
        done.append("icon")
        print("rendered icon")
    if not only or "loading" in only:  # loading screen: the city from above the hub, title on top
        bpy.ops.wm.open_mainfile(filepath=os.path.join(ART, "map", "city.blend"))
        sky("day")
        camera((0, -420, 130), (0, 220, 20), 24, (1920, 1080))
        path = os.path.join(OUT, "loading_screen.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        title(path, path, "LOADING THE CITY...")
        done.append("loading_screen")
        print("rendered loading")
    if not only:
        sheet(done)


def sheet(names):
    from PIL import Image, ImageDraw

    cols, w, h = 3, 640, 360
    rows = math.ceil(len(names) / cols)
    out = Image.new("RGB", (cols * w, rows * (h + 20)), (30, 30, 36))
    d = ImageDraw.Draw(out)
    for k, n in enumerate(names):
        im = Image.open(os.path.join(OUT, n + ".png")).convert("RGB")
        im.thumbnail((w, h))
        x, y = (k % cols) * w, (k // cols) * (h + 20)
        out.paste(im, (x, y))
        d.text((x + 6, y + h + 3), n, fill=(230, 230, 230))
    out.save(os.path.join(lib.PREVIEWS, "_thumbnails.png"))


if __name__ == "__main__":
    main({a for a in sys.argv[1:] if not a.startswith("--")})
