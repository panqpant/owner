# Costa Verde

An original open-world crime-action game for Roblox, set in a fictional Florida-style state, about 11.5 × 11.5 km.
The whole world is generated from code, so the same seed always builds the same map.

## Layout

| Path | What |
| --- | --- |
| `src/shared/Gen/` | World generator in pure Luau (runs in Roblox and in Lune): terrain, districts, city grid, rural roads, farms, hamlets, Easter eggs, rail and metro |
| `tools/export-world.luau` | Runs the generator outside Roblox → `build/world.json` |
| `tools/render_map.py` | Top-down map → `screenshots/map.png` |
| `tools/blender/render_world.py` | 3D Blender preview renders → `screenshots/*.png` |
| `tools/fetch_refs.py` | Downloads 50 USGS reference images (public domain) used to study real geography |

## Preview the world (no Roblox needed)

```sh
lune run tools/export-world.luau
python tools/render_map.py
python tools/blender/render_world.py sunset
```

The Python tools need `pip install bpy pillow numpy` (bpy is Blender as a Python module).
