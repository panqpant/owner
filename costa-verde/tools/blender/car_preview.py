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
for k, kind in enumerate(("sedan", "suv", "ev", "van", "pickup")):
    coll = next(c for c in models if c.name.startswith(f"car_{kind}_0"))
    realism.place(coll, (k - 2) * 5, (k - 2) * 12, 0, math.radians(-25))
realism.sky_and_sun(35, 140)
realism.real_camera((40, 30, 9), (0, -3, 2.5), 32)
render("car_lineup")
