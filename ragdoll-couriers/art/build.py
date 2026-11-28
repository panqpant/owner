"""Builds every asset: FBX + metadata JSON into export/, a render of each into previews/.

Run:   python build.py               (all assets)
       python build.py Vehicle_Van   (just the named ones)
Needs Blender's Python module:  pip install bpy==5.3.0 pillow   (Python 3.13)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import lib  # noqa: E402
from assets import parcels, vehicles  # noqa: E402

GROUPS = {"vehicles": vehicles.ASSETS, "parcels": parcels.ASSETS}
TRIANGLE_BUDGET = 10000  # per MeshPart; Roblox's hard limit is 20k, phones like far less


def main(only):
    lib.write_palette()
    for group, assets in GROUPS.items():
        built = []
        for name, make in assets.items():
            if only and name not in only:
                continue
            lib.reset()
            objs, meta = make()
            info = lib.export(name, objs, meta)
            worst = max(p["triangles"] for p in info["parts"].values())
            assert worst <= TRIANGLE_BUDGET, f"{name}: a part has {worst} triangles"
            lib.preview(name, objs)
            built.append(name)
            print(f"built {name}: {info['triangles']} tris, size {info['size_studs']}")
        if built and not only:
            lib.contact_sheet(built, f"_{group}.png")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
