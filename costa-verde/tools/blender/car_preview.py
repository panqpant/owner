"""Quick lineup render of the car models (realism.car_models) on asphalt: python tools/blender/car_preview.py"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import bpy  # noqa: E402
import realism  # noqa: E402
from render_world import render, reset  # noqa: E402

reset()
s = bpy.context.scene
s.render.resolution_x, s.render.resolution_y, s.cycles.samples = 1280, 540, 32
bpy.ops.mesh.primitive_plane_add(size=200)
bpy.context.object.data.materials.append(realism.mat_asphalt())
models = realism.car_models()
for k, kind in enumerate(("sedan", "suv", "pickup", "van")):
    coll = next(c for c in models if c.name.startswith(f"car_{kind}_0"))
    realism.place(coll, (k - 1.5) * 6, (k - 1.5) * 13, 0, math.radians(-30))
realism.sky_and_sun(35, 140)
realism.real_camera((34, 30, 11), (0, -2, 2.5), 35)
render("car_lineup")
