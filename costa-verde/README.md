# Costa Verde

An original open-world crime-action game for Roblox, set in a fictional Florida-style state, about 11.5 × 11.5 km.
The whole world is generated from code, so the same seed always builds the same map.

## Layout

| Path | What |
| --- | --- |
| `src/shared/Gen/` | World generator in pure Luau (runs in Roblox and in Lune). Roads are built top-down: `Roads.luau` (freeways and rail routed by A* over the terrain, a continuous arterial grid with downtown boulevards, state roads, every crossing a real junction), then `City.luau` fills each block with local streets grown from the roads around it (`Streets.luau`, styles trained on real US networks), then buildings line the frontage. Also terrain, rural roads, farms, hamlets, Easter eggs, metro and rail. |
| `tools/export-world.luau` | Runs the generator outside Roblox → `build/world.json` |
| `tools/audit_world.py` | Checks the generated world: one connected road network, no major road just stopping, no road over water without a bridge, built-up land used, buildings off roads, street patterns vs real data. Fails loudly. |
| `tools/render_map.py` | Top-down map → `screenshots/map.png` |
| `tools/blender/render_world.py` | 3D Blender preview renders → `screenshots/*.png` |
| `tools/terrain_stats.py`, `tools/train_terrain.py` | Learn terrain from real USGS elevation, fit the generator to it |
| `tools/fetch_roads.py`, `tools/road_stats.py`, `tools/train_streets.py` | Learn street patterns from real Census road data, fit the street styles to it (in the same block setting the game uses) |
| `tools/interchange_stats.py` | Measures the real mix of freeway interchange types from Census ramp data |
| `tools/landmarks.py` | The 200 unique landmarks (checked: exactly 200, all unique) → `LANDMARKS.md`, `tools/data/landmarks.json` |
| `tools/building_stats.py` | Real counts of every building type (Census business data) scaled to the map → `BUILDINGS.md` |
| `tools/fetch_refs.py` | Downloads 50 USGS reference images (public domain) used to study real geography |

## Preview the world (no Roblox needed)

```sh
lune run tools/export-world.luau
python tools/audit_world.py
python tools/render_map.py
python tools/blender/render_world.py sunset
```

The Python tools need `pip install bpy pillow numpy` (bpy is Blender as a Python module).
