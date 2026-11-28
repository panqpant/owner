"""Builds the whole city in Blender from plan.py, renders it, and writes the Roblox layout.

Run:  python map/build_map.py            (needs bpy, like build.py; about 10 minutes, mostly rendering)
      python map/build_map.py --no-render
      python map/build_map.py oldtown hub   (render only these shots)

Outputs
  map/city.blend                      the city, every piece a linked instance of the kit (open it in Blender)
  previews/map_*.png                  top-down plan and close-ups
  ../src/map/Layout.luau              what MapBuilder.luau places in Studio (Roblox coordinates)
"""

import json
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

import plan as city  # noqa: E402
import terrain  # noqa: E402
from assets import dressing, landmarks, parcels, vehicles, world  # noqa: E402

KIT = {**world.ASSETS, **landmarks.ASSETS, **dressing.ASSETS, **vehicles.ASSETS, **parcels.ASSETS}
LAYOUT = os.path.join(os.path.dirname(ART), "src", "map", "Layout.luau")


def hexcol(h: str, alpha=1.0):
    """Hex (sRGB, as Roblox reads it) to the linear colour Blender's shaders expect."""

    def lin(c):
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return tuple(lin(int(h[k : k + 2], 16) / 255) for k in (0, 2, 4)) + (alpha,)


def paint_material():
    """Paint parts take their colour from the instancing empty (its object colour)."""
    m = bpy.data.materials.new("Paint")
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = "INSTANCER"
    attr.attribute_name = "color"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.5
    return m


def build_kit(names):
    kit_root = bpy.data.collections.new("Kit")
    bpy.context.scene.collection.children.link(kit_root)
    paint = paint_material()
    info = {}
    for name in sorted(names):
        objs, _meta = KIT[name]()
        coll = bpy.data.collections.new(name)
        kit_root.children.link(coll)
        for o in objs:
            bpy.context.scene.collection.objects.unlink(o)
            coll.objects.link(o)
            if o.name.startswith("Paint"):
                o.data.materials[0] = paint
        lo, hi = lib.bounds(objs)
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        info[name] = {
            # Roblox frame: x, y (up), z (= -Blender y)
            "size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)],
            "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)],
            "paint": any(o.name.startswith("Paint") for o in objs),
        }
        print("kit", name)
    bpy.context.view_layer.layer_collection.children["Kit"].exclude = True
    return info


STEP, CHUNK = 10, 250  # terrain grid spacing and chunk size, studs


def build_terrain(p):
    """Faceted terrain in 250-stud chunks (one MeshPart each), exported as four quarter FBX files.
    Flat same-colour areas are merged into big faces, so the city costs almost nothing."""
    import bmesh

    t = p["terrain"]
    n = int(2 * terrain.EXTENT / STEP) + 1
    xs = [-terrain.EXTENT + k * STEP for k in range(n)]
    heights = [[t.height(x, y) for y in xs] for x in xs]
    per = CHUNK // STEP
    nch = (n - 1) // per
    coll = bpy.data.collections.new("Terrain")
    bpy.context.scene.collection.children.link(coll)
    quarters = {}
    for cx in range(nch):
        for cy in range(nch):
            centre = (xs[cx * per] + CHUNK / 2, xs[cy * per] + CHUNK / 2)
            bm = bmesh.new()
            uv = bm.loops.layers.uv.new("UVMap")
            v = {}
            for a in range(per + 1):
                for b in range(per + 1):
                    ix, iy = cx * per + a, cy * per + b
                    v[a, b] = bm.verts.new((xs[ix] - centre[0], xs[iy] - centre[1], heights[ix][iy]))
            for a in range(per):
                for b in range(per):
                    q = (v[a, b], v[a + 1, b], v[a + 1, b + 1], v[a, b + 1])
                    tris = ((q[0], q[1], q[2]), (q[0], q[2], q[3])) if (a + b) % 2 == 0 else ((q[0], q[1], q[3]), (q[1], q[2], q[3]))
                    for tri in tris:
                        f = bm.faces.new(tri)
                        f.normal_update()
                        c = (tri[0].co + tri[1].co + tri[2].co) / 3
                        wx, wy = c.x + centre[0], c.y + centre[1]
                        district = city.district_of(round(wx / city.CELL), round(wy / city.CELL))
                        u = lib.uv_of(t.colour(wx, wy, c.z, 1 - abs(f.normal.z), district))
                        for loop in f.loops:
                            loop[uv].uv = u
            bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(1), verts=bm.verts[:], edges=bm.edges[:], delimit={"UV"})
            bmesh.ops.triangulate(bm, faces=bm.faces[:])
            me = bpy.data.meshes.new(f"Chunk_{cx}_{cy}")
            bm.to_mesh(me)
            bm.free()
            me.materials.append(lib.material())
            obj = bpy.data.objects.new(f"Chunk_{cx}_{cy}", me)
            obj.location = (centre[0], centre[1], 0)
            coll.objects.link(obj)
            name = "Terrain_" + ("N" if cy >= nch // 2 else "S") + ("E" if cx >= nch // 2 else "W")
            quarters.setdefault(name, []).append(obj)
    info, items = {}, []
    for name, objs in quarters.items():
        meta = lib.export(name, objs, {"kind": "terrain"})
        assert max(part["triangles"] for part in meta["parts"].values()) <= 10000, name
        lo, hi = lib.bounds(objs)
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        info[name] = {"size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)], "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)], "paint": False}
        items.append({"asset": name, "x": 0, "y": 0, "rot": 0, "district": "Terrain"})
        print(f"terrain {name}: {meta['triangles']} tris in {len(objs)} chunks")

    water = lib.Mesh("Water").box((2 * terrain.EXTENT, 2 * terrain.EXTENT, 0.2), (0, 0, terrain.WATER - 0.1), "water", bevel=0).done()
    mat = bpy.data.materials.new("WaterMat")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexcol("3f9be0")
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Alpha"].default_value = 0.85
    water.data.materials[0] = mat
    return info, items


def _runs(ks, keep):
    """Contiguous runs (2+ samples) of ks where keep(k) holds."""
    out, run = [], []
    for k in ks:
        if keep(k):
            run.append(k)
        else:
            if len(run) > 1:
                out.append(run)
            run = []
    if len(run) > 1:
        out.append(run)
    return out


def _ribbon(road, bridged, t):
    """Mesh one free road in ~200-stud parts. Width can taper (mountain foot) and the edge can change
    from city pavement to crash barriers; a roundabout ring leaves its outer kerb open at the entries."""
    pts, closed, n = road["points"], road.get("closed", False), len(road["points"])
    full = road["width"] / 2
    k_full, k_end, w_from = road.get("taper", (0, 0, road["width"]))

    def hw(k):
        k = k % n
        if k <= k_full:
            return w_from / 2
        if k >= k_end:
            return full
        return w_from / 2 + (full - w_from / 2) * (k - k_full) / (k_end - k_full)

    def edge(k):
        return "pavement" if (k % n) < k_full or road["edge"] == "pavement" else road["edge"]

    def frame(k):
        k %= n
        a, b = pts[(k - 1) % n if closed else max(k - 1, 0)], pts[(k + 1) % n if closed else min(k + 1, n - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        return pts[k], (-dy / ln, dx / ln), math.degrees(math.atan2(dy, dx))

    def off(ks, side, extra=0.0, dz=0.0):
        """Points at side*(hw + extra) from the centreline (side +1 is the left of travel)."""
        out = []
        for k in ks:
            (x, y, z), (lx, ly), _ = frame(k)
            d = side * (hw(k) + extra)
            out.append((x + lx * d, y + ly * d, z + dz))
        return out

    def in_gap(k):  # ring entries: the outer kerb and edge line stop here
        if "gaps" not in road:
            return False
        cx, cy, _ = road["island"]
        x, y, _ = pts[k % n]
        ang = math.atan2(y - cy, x - cx)
        return any(abs((ang - a + math.pi) % math.tau - math.pi) < g for a, g in road["gaps"])

    outer = -1 if closed else None  # the ring runs anticlockwise, so its outer edge is on the right
    span = list(range(n + 1)) if closed else list(range(n))
    objs = []
    for c0 in range(0, len(span) - 1, 50):
        ks = span[c0 : c0 + 51]
        m = lib.Mesh(f"{road['name']}_{c0 // 50}")
        m.strip(off(ks, 1), off(ks, -1), "asphalt", thickness=1)
        for side in (-1, 1):
            gapped = side == outer
            for kind in ("pavement", road["edge"]):
                # A pavement run also takes the sample where the edge changes, so it meets the shoulder exactly.
                def keep(k, kind=kind):
                    own = edge(k) == kind or (kind == "pavement" and k > 0 and edge(k - 1) == "pavement")
                    return own and not (gapped and in_gap(k))

                for run in _runs(ks, keep):
                    colour = "yellow" if kind == "pavement" else "white"
                    m.strip(off(run, side, -0.85, 0.03), off(run, side, -1.15, 0.03), colour, thickness=0.03)  # edge line: same place as the grid tiles' (14 +- 0.15 from the centre)
                    if kind == "pavement":
                        m.strip(off(run, side, 0, 0.4), off(run, side, 5, 0.4), "concrete", thickness=1.4)
                    else:  # mountain: gravel shoulder and crash barrier
                        m.strip(off(run, side), off(run, side, 3), "stone", thickness=1.5)
                        m.strip(off(run, side, 2.3, 2.6), off(run, side, 2.7, 2.6), "chrome", thickness=1.0)
                        for k in run[::3]:
                            (x, y, z), (lx, ly), yaw = frame(k)
                            d = side * (hw(k) + 2.5)
                            m.box((0.5, 0.5, 2.8), (x + lx * d, y + ly * d, z + 1.3), "steel", rot=(0, 0, yaw), bevel=0)
                if kind == road["edge"]:
                    break
        for k in ks[:-1]:  # centre dashes
            if (k // 3) % 2 == 0:
                a = [(x + lx * 0.25, y + ly * 0.25, z + 0.03) for (x, y, z), (lx, ly), _ in (frame(k), frame(k + 1))]
                b = [(x - lx * 0.25, y - ly * 0.25, z + 0.03) for (x, y, z), (lx, ly), _ in (frame(k), frame(k + 1))]
                m.strip(a, b, "white", thickness=0.03)
        flags = [bridged[k % n] for k in ks]
        if any(flags):  # bridge: deck, railings, pillars down to the lake bed
            m.strip(off(ks, 1, 6, -1), off(ks, -1, 6, -1), "concrete", thickness=2.5)
            for side in (-1, 1):
                for run in _runs(ks, lambda k: bridged[k % n]):
                    m.strip(off(run, side, 4.4, 3.2), off(run, side, 4.9, 3.2), "steel", thickness=0.5)
                    for k in run[::3]:
                        (x, y, z), (lx, ly), yaw = frame(k)
                        d = side * (hw(k) + 4.6)
                        m.box((0.5, 0.5, 2.8), (x + lx * d, y + ly * d, z + 1.6), "steel", rot=(0, 0, yaw), bevel=0)
            for k in ks:
                if k % 10 == 0 and bridged[k % n]:
                    (x, y, z), (lx, ly), _ = frame(k)
                    bed = t.water_floor(x, y)
                    for side in (-1, 1):
                        m.cyl(1.6, z - bed, (x + lx * hw(k) * 0.6 * side, y + ly * hw(k) * 0.6 * side, (z + bed) / 2 - 1.5), "concrete", segments=12, bevel=0)
        lo, hi = road.get("shelter", (2, 2))
        for k in ks[:-1]:
            if lo <= k / n <= hi:  # avalanche shelter: roof and pillars
                m.strip(off((k, k + 1), 1, 4, 14), off((k, k + 1), -1, 4, 14), "concrete", thickness=1.2)
                if k % 4 == 0:
                    (x, y, z), (lx, ly), yaw = frame(k)
                    for side in (-1, 1):
                        d = side * (hw(k) + 3.5)
                        m.box((1.4, 1.4, 14), (x + lx * d, y + ly * d, z + 7), "concrete", rot=(0, 0, yaw), bevel=0.1)
        objs.append(m.done(sharp=40))
    return objs


def _roundabout_arms(ring, arms):
    """Each entry arm is built to fit the ring exactly: its asphalt ends on the ring's own curve at the
    same height, its edge lines stop short of the ring, and its pavements curve into the ring's kerb."""
    cx, cy, _ = ring["island"]
    r_out = ring["points"][0][0] - cx + ring["width"] / 2  # ring centreline radius + half its width
    g = ring["gaps"][0][1]  # where the ring's kerb starts, either side of each arm
    objs = []
    for arm in arms:
        ax, ay, _ = arm["points"][0]
        length = math.hypot(cx - ax, cy - ay)
        dx, dy = (cx - ax) / length, (cy - ay) / length
        lx, ly = -dy, dx
        half = arm["width"] / 2

        def at(tt, u, z=0.0):
            return (ax + dx * tt + lx * u, ay + dy * tt + ly * u, z)

        def polar(radius, phi):
            """Point at `radius` from the ring centre, `phi` radians off this arm's axis (+ is the arm's left)."""
            return (cx - dx * radius * math.cos(phi) + lx * radius * math.sin(phi), cy - dy * radius * math.cos(phi) + ly * radius * math.sin(phi))

        def t_end(u, radius):
            return length - math.sqrt(radius * radius - u * u)

        def arc(u0, u1, radius, steps=12):
            return [at(t_end(u0 + (u1 - u0) * i / steps, radius), u0 + (u1 - u0) * i / steps)[:2] for i in range(steps + 1)]

        def ring_edge(u0, u1):
            """The ring's own outer-edge vertices between lateral offsets u0 and u1, so the arm and ring
            share an edge exactly: no overlap to flicker, no sliver to see through."""
            ends = [at(t_end(u, r_out), u)[:2] for u in (u0, u1)]
            a0, a1 = (math.atan2(py - cy, px - cx) for px, py in ends)
            sweep = (a1 - a0 + math.pi) % math.tau - math.pi
            inner = []
            for k in range(len(ring["points"])):
                a = k * math.tau / len(ring["points"])
                f = ((a - a0 + math.pi) % math.tau - math.pi) / sweep
                if 0 < f < 1:
                    inner.append((f, (cx + r_out * math.cos(a), cy + r_out * math.sin(a))))
            return [ends[0]] + [pt for _, pt in sorted(inner)] + [ends[1]]

        m = lib.Mesh(f"{arm['name']}")
        m.prism([at(0, -half)[:2], at(0, half)[:2]] + ring_edge(half, -half), 0, "asphalt", thickness=1)
        for side in (-1, 1):
            u_in, u_out = side * half, side * (half + 5)
            # Pavement tiles exactly with the ring's kerb (which starts at angle g from this arm's axis):
            # along the kerb's outer edge, down its end, then along the ring's edge. Nothing overlaps.
            r_kerb = r_out + 5
            phi_a, phi_15 = math.asin((half + 5) / r_kerb), math.asin(half / r_out)
            outline = [at(0, u_in)[:2], at(0, u_out)[:2]]
            outline += [polar(r_kerb, side * (phi_a + (g - phi_a) * i / 6)) for i in range(7)]
            outline += [polar(r_out, side * (g + (phi_15 - g) * i / 6)) for i in range(7)]
            m.prism(outline, 0.4, "concrete", thickness=1.4)
            # Fill the inside corner between this pavement's straight edge and the ring's curved kerb.
            pa = at(t_end(u_out, r_out + 5), u_out)[:2]
            pb = at(t_end(u_out, r_out + 5) - 6, u_out)[:2]
            # Its curved side follows the kerb's outer edge (not a chord), so it never overlaps the kerb.
            phi_a = math.asin((half + 5) / (r_out + 5))
            m.prism([pb, pa] + [polar(r_out + 5, side * (phi_a + (6 / (r_out + 5)) * i / 6)) for i in range(1, 7)], 0.4, "concrete", thickness=1.4)
            te = t_end(side * (half - 1), r_out) - 0.6
            m.strip([at(0, side * (half - 0.85), 0.03), at(te, side * (half - 0.85), 0.03)], [at(0, side * (half - 1.15), 0.03), at(te, side * (half - 1.15), 0.03)], "yellow", thickness=0.03)
        tt = 2.0
        while tt + 4 < t_end(0, r_out) - 3:
            m.strip([at(tt, 0.25, 0.03), at(tt + 4, 0.25, 0.03)], [at(tt, -0.25, 0.03), at(tt + 4, -0.25, 0.03)], "white", thickness=0.03)
            tt += 8
        objs.append(m.done(sharp=1))  # flat shading: kerb corners have no smooth normals to go wrong
    return objs


def build_free_roads(p):
    """Mesh the free-form roads (roads.py): the mountain road, the causeway, and the roundabout with its
    arms as one piece. Each is an FBX of ~200-stud MeshParts, placed at the origin like the terrain."""
    t = p["terrain"]
    by_name = {r["name"]: r for r in p["free_roads"]}
    bridge_of, base = {}, 0
    for r in p["free_roads"]:  # bridge flags line up with RoadIndex samples, in road order
        bridge_of[r["name"]] = t.bridge[base : base + len(r["points"])]
        base += len(r["points"])
    info, items = {}, []
    for asset, name in (("Road_Mountain", "Mountain"), ("Road_Causeway", "Causeway"), ("Road_Roundabout", "Roundabout")):
        road = by_name[name]
        objs = _ribbon(road, bridge_of[name], t)
        if name == "Mountain":  # summit car park: starts exactly where the road ends (no overlap), kerbed, marked bays
            x, y, z = road["points"][-1]
            hw = road["width"] / 2
            x0, x1, y0, y1 = x - 80, x, y - hw - 3, y + 46  # wide enough to take the road plus its shoulders
            lot = lib.Mesh("CarPark")
            lot.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z, "asphalt", thickness=1)
            for k in range(6):  # bay lines between the parked cars
                bx = x - 75 + k * 10
                lot.prism([(bx - 0.15, y + 18), (bx + 0.15, y + 18), (bx + 0.15, y + 34), (bx - 0.15, y + 34)], z + 0.03, "white", thickness=0.03)
            for pts in (((x0, y1), (x1, y1), (x1, y1 + 2), (x0, y1 + 2)), ((x0 - 2, y0 - 2), (x0, y0 - 2), (x0, y1 + 2), (x0 - 2, y1 + 2)), ((x0, y0 - 2), (x1, y0 - 2), (x1, y0), (x0, y0))):
                lot.prism(list(pts), z + 0.4, "concrete", thickness=1.4)  # kerbs north, west and south; the road comes in from the east
            objs.append(lot.done(sharp=40))
        if "island" in road:
            cx, cy, r = road["island"]
            circle = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (k * math.tau / 48 for k in range(48))]
            isl = lib.Mesh("Island")
            inner = [(cx + (x - cx) * 0.94, cy + (y - cy) * 0.94) for x, y in circle]
            isl.prism(inner, 1.2, "grass", thickness=2.2)  # grass inside a kerb ring; the kerb stops at the ring's edge
            isl.strip([(x, y, 0.5) for x, y in inner + inner[:1]], [(x, y, 0.5) for x, y in circle + circle[:1]], "concrete", thickness=1.5)
            objs.append(isl.done())
            objs += _roundabout_arms(road, [r for r in p["free_roads"] if "joins" in r])
        meta = lib.export(asset, objs, {"kind": "road"})
        assert max(part["triangles"] for part in meta["parts"].values()) <= 10000, asset
        lo, hi = lib.bounds(objs)
        c = [(lo[k] + hi[k]) / 2 for k in range(3)]
        info[asset] = {"size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)], "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)], "paint": False}
        items.append({"asset": asset, "x": 0, "y": 0, "rot": 0, "district": "Roads"})
        print(f"road {asset}: {meta['triangles']} tris in {len(objs)} parts")
    return info, items


def build_power_lines(p):
    """Sagging cables between consecutive power poles on the same straight run (80 studs apart).
    No collision: riders pass under them. Exported like the roads, as one asset of ~10k-tri parts."""
    poles = [it for it in p["items"] if it["asset"] == "Street_PowerPole"]
    runs = {}
    for it in poles:
        runs.setdefault(tuple(it["line"]), []).append(it)
    spans = []
    for (along_ns, _), group in runs.items():
        group.sort(key=lambda it: it["y"] if along_ns else it["x"])
        for a, b in zip(group, group[1:]):
            if math.dist((a["x"], a["y"]), (b["x"], b["y"])) <= 81:
                spans.append((a, b, along_ns))
    objs, m, count = [], None, 0
    for a, b, along_ns in spans:
        if m is None or count >= 40:
            if m is not None:
                objs.append(m.done(sharp=60))
            m, count = lib.Mesh(f"Lines_{len(objs)}"), 0
        for off in (-3, 0, 3):  # three cables from the crossarm ends and middle
            ox, oy = (off, 0) if along_ns else (0, off)
            p0 = (a["x"] + ox, a["y"] + oy, a.get("z", 0) + 21.6)
            p1 = (b["x"] + ox, b["y"] + oy, b.get("z", 0) + 21.6)
            pts = [(p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, p0[2] + (p1[2] - p0[2]) * t - 2.0 * (1 - (2 * t - 1) ** 2)) for t in (k / 8 for k in range(9))]
            for q0, q1 in zip(pts, pts[1:]):
                m.tube(q0, q1, 0.08, "black", segments=4)
        count += 1
    if m is not None:
        objs.append(m.done(sharp=60))
    meta = lib.export("PowerLines", objs, {"kind": "wires", "note": "CanCollide off: riders pass underneath"})
    assert max(part["triangles"] for part in meta["parts"].values()) <= 10000
    lo, hi = lib.bounds(objs)
    c = [(lo[k] + hi[k]) / 2 for k in range(3)]
    info = {"PowerLines": {"size": [round(hi[0] - lo[0], 3), round(hi[2] - lo[2], 3), round(hi[1] - lo[1], 3)], "centre": [round(c[0], 3), round(c[2], 3), round(-c[1], 3)], "paint": False}}
    print(f"power lines: {len(spans)} spans, {meta['triangles']} tris in {len(objs)} parts")
    return info, [{"asset": "PowerLines", "x": 0, "y": 0, "rot": 0, "district": "Wires"}]


def place_all(p):
    root = bpy.data.collections.new("City")
    bpy.context.scene.collection.children.link(root)
    groups = {}
    for k, it in enumerate(p["items"]):
        g = groups.get(it["district"])
        if g is None:
            g = groups[it["district"]] = bpy.data.collections.new(it["district"])
            root.children.link(g)
        e = bpy.data.objects.new(f"{it['asset']}.{k}", None)
        e.instance_type = "COLLECTION"
        e.instance_collection = bpy.data.collections[it["asset"]]
        e.location = (it["x"], it["y"], it.get("z", 0))
        e.rotation_euler = (0, 0, math.radians(it["rot"]))
        if "paint" in it:
            e.color = hexcol(it["paint"])
        g.objects.link(e)


# Where decals go on each asset: (decal, centre, (width, height)) in Blender asset space, all facing +Y
# (the asset's front, Roblox's Front face). Each sits 0.05 studs in front of its sign board.
# "shop" and "ad" rotate through the shop signs and the billboard ads.
SLOTS = {
    "Hub_Depot": [("sign_depot", (0, 12.75, 13), (29.6, 4.2))],
    "Hub_Garage": [("sign_garage", (0, 12.75, 11.6), (25.6, 3.2))],
    "Hub_VIPGarage": [("sign_vip", (0, 12.75, 11.6), (25.6, 3.2))],
    "Hub_Leaderboard": [("sign_leaderboard", (0, 0.85, 16.1), (15.6, 1.5))],
    "OldTown_Shop": [("shop", (0, 6.5, 9.8), (12.6, 2.2))],
    "Docks_FishMarket": [("sign_shop_8", (0, 10.35, 12.4), (23.6, 2.4))],
    "Mountain_Lodge": [("sign_lodge", (0, 9.5, 8.4), (9.8, 1.1))],
    "Street_Billboard": [("ad", (0, 0.4, 16), (23.8, 11.8))],
}
DECAL_IDS = os.path.join(os.path.dirname(ART), "src", "map", "DecalIds.luau")


def write_decal_ids():
    """A template for the uploaded image IDs. Written only if missing, so filled-in IDs are never lost."""
    if os.path.exists(DECAL_IDS):
        return
    import glob

    names = sorted(os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(lib.EXPORT, "textures", "*", "*.png")))
    sky = sorted(f"sky_{os.path.basename(os.path.dirname(f))}_{os.path.splitext(os.path.basename(f))[0][6:]}" for f in glob.glob(os.path.join(lib.EXPORT, "sky", "*", "*.png")))
    with open(DECAL_IDS, "w") as f:
        f.write("-- Image IDs for art/export/textures and art/export/sky, after uploading them (Asset Manager, bulk import).\n")
        f.write('-- Paste each as "rbxassetid://123..." and rebuild the city; anything left "" is simply skipped.\n')
        f.write("return {\n")
        for n in names + sky:
            f.write(f'\t{n} = "",\n')
        f.write("}\n")
    print("wrote", DECAL_IDS)


def write_layout(p, kit_info, extra_items=()):
    def rb(x, y, z=0.0):
        return [round(x, 2), round(z, 2), round(-y, 2)]

    data = {
        "cell": p["cell"],
        "assets": kit_info,
        # m = a hazard the game moves (forklift, dog, wrecking ball, boulder); k = a parked car
        "items": [
            {"a": it["asset"], "p": rb(it["x"], it["y"], it.get("z", 0)), "r": it["rot"], "c": it.get("paint"), "d": it["district"], "m": it.get("moving"), "k": it.get("parked")}
            for it in list(p["items"]) + list(extra_items)
        ],
        # free-form roads as centrelines (every 8 studs), for routing and the no-import fallback
        "freeRoads": [{"n": r["name"], "w": r["width"], "c": bool(r.get("closed")), "p": [rb(x, y, z) for x, y, z in r["points"][::2]]} for r in p["free_roads"]],
        "links": [[[a[0], -a[1]], [b[0], -b[1]]] for a, b in p["links"]],
        "slots": {a: [{"d": d, "c": [c[0], c[2], -c[1]], "s": list(sz)} for d, c, sz in v] for a, v in SLOTS.items()},
        "ads": ["billboard_couriers", "billboard_bubblewrap", "billboard_rocket", "billboard_insurance", "billboard_lodge", "billboard_fish"],
        "water": terrain.WATER,
        "extent": terrain.EXTENT,
        "addresses": [{"d": a["district"], "p": rb(a["x"], a["y"]), "b": a["building"]} for a in p["addresses"]],
        "spawn": {"p": rb(p["spawn"]["x"], p["spawn"]["y"]), "r": p["spawn"]["rot"]},
        # rect in Roblox x/z: [xMin, zMin, xMax, zMax]
        "districts": {k: {"rect": [v["rect"][0], -v["rect"][3], v["rect"][2], -v["rect"][1]], "colour": v["colour"]} for k, v in p["districts"].items()},
        "seaXMax": (city.SEA_I + 0.5) * city.CELL,
        "roads": [[i, -j] for i, j in p["roads"]],  # road cells in Roblox grid (x = i*cell, z = j*cell)
    }
    os.makedirs(os.path.dirname(LAYOUT), exist_ok=True)
    with open(LAYOUT, "w") as f:
        f.write("-- Generated by art/map/build_map.py. Do not edit by hand: change art/map/plan.py and rebuild.\n")
        f.write("return [==[" + json.dumps(data, separators=(",", ":")) + "]==]\n")
    print("layout:", len(data["items"]), "items,", os.path.getsize(LAYOUT) // 1024, "KB")


def setup_render(samples, res_x, res_y):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res_x, res_y
    sc.view_settings.view_transform = "AgX"
    if not sc.world:
        w = bpy.data.worlds.new("Sky")
        w.use_nodes = True
        w.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.78, 1.0, 1)
        w.node_tree.nodes["Background"].inputs[1].default_value = 1.0
        sc.world = w
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
        sun.data.energy = 3.5
        sun.data.angle = math.radians(3)
        sun.rotation_euler = (math.radians(42), 0, math.radians(35))
        sc.collection.objects.link(sun)


ONLY = {a for a in sys.argv[1:] if not a.startswith("--")}  # e.g. `build_map.py oldtown topdown`


def shot(name, location, target, lens=None, ortho=None, samples=16, res=(1280, 720)):  # previews are for checking: fast over pretty
    if ONLY and name not in ONLY:
        return
    setup_render(samples, *res)
    cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    if cam.name not in bpy.context.scene.collection.objects:
        bpy.context.scene.collection.objects.link(cam)
    cam.data.clip_end = 20000
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    else:
        cam.data.type = "PERSP"
        cam.data.lens = lens or 32
    cam.location = location
    cam.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.context.scene.render.filepath = os.path.join(lib.PREVIEWS, f"map_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("rendered", name)


def main(render=True):
    lib.reset()
    lib.write_palette()
    p = city.plan()
    kit_info = build_kit({it["asset"] for it in p["items"]})
    terrain_info, terrain_items = build_terrain(p)
    road_info, road_items = build_free_roads(p)
    wire_info, wire_items = build_power_lines(p)
    place_all(p)
    write_layout(p, {**kit_info, **terrain_info, **road_info, **wire_info}, terrain_items + road_items + wire_items)
    write_decal_ids()
    setup_render(8, 64, 64)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "city.blend"))
    if not render:
        return
    C = city.CELL
    shot("topdown", (0, 0, 3000), (0, 0, 0), ortho=2100, samples=12, res=(1536, 1536))
    shot("world", (0, 0, 4000), (0, 0, 0), ortho=3000, samples=12, res=(1536, 1536))
    shot("hub", (230, -220, 150), (0, 60, 10), lens=28)
    shot("mountain", (300, 260, 90), (870, 840, 140), lens=30)
    shot("lake", (430, -380, 70), (700, -640, 0), lens=30)
    shot("coast", (-640, -620, 90), (-960, -360, 0), lens=30)
    shot("switchbacks", (760, 420, 260), (1110, 830, 70), lens=28)
    shot("causeway", (500, -480, 60), (660, -700, 0), lens=28)
    shot("roundabout", (560, -800, 70), (640, -880, 0), lens=30)
    # Join checks: every place two road pieces meet, close up from above and low down.
    corner = next(it for it in p["items"] if it["asset"] == "Road_Corner")
    for name, (x, y), size in (("j_round", (640, -880), 150), ("j_armW", (590, -880), 60), ("j_armN", (640, -836), 60), ("j_armE", (690, -880), 60),
                               ("j_mtnfoot", (895, 565), 110), ("j_causeway", (640, -425), 60), ("j_corner", (corner["x"], corner["y"]), 70)):
        shot(name, (x, y, 600), (x, y, 0), ortho=size, samples=16, res=(900, 900))
    shot("j_low_armW", (556, -858, 9), (612, -884, 0), lens=24, samples=16, res=(1200, 700))

    # Landmark checks (batch 6): each one from in front, as a rider would come up to it.
    def look(name, asset, dist, height, lens=30, side=0.5):
        it = next(i for i in p["items"] if i["asset"] == asset)
        r = math.radians(it["rot"])
        fx, fy = -math.sin(r), math.cos(r)  # the way it faces
        z0 = it.get("z", 0)
        cam = (it["x"] + (fx + fy * side) * dist, it["y"] + (fy - fx * side) * dist, z0 + height)
        shot(name, cam, (it["x"], it["y"], z0 + height * 0.35), lens=lens)

    sx, sy, sz = p["summit"]
    shot("j_summit", (sx, sy, sz + 400), (sx, sy, sz), ortho=130, samples=16, res=(900, 900))
    shot("j_low_summit", (sx + 75, sy - 30, sz + 8), (sx + 20, sy - 18, sz + 1), lens=24, samples=16, res=(1200, 700))
    look("lm_school", "Suburbs_School", 75, 30)
    look("lm_church", "OldTown_Church", 75, 32)
    look("lm_clock", "OldTown_ClockTower", 95, 60)
    look("lm_canal", "OldTown_Canal", 45, 16)
    look("lm_lodge", "Mountain_Lodge", 80, 30)
    look("lm_waterfall", "Mountain_Waterfall", 75, 30)
    look("lm_skeleton", "Site_Skeleton", 85, 45)
    shot("lm_harbour", (-1000, -170, 45), (-905, 10, 8), lens=28)
    shot("lm_lighthouse", (-860, 180, 25), (-1020, 300, 14), lens=30)
    shot("lm_plaza", (0, -240, 55), (0, 70, 8), lens=28)
    # Set dressing checks (batch 7).
    look("d_busstop", "Street_BusStop", 30, 9)
    look("d_billboard", "Street_Billboard", 70, 18)
    look("d_phonebox", "Street_PhoneBox", 28, 9)
    look("d_bikerack", "Street_BikeRack", 26, 8)
    pole = next(i for i in p["items"] if i["asset"] == "Street_PowerPole")
    shot("d_powerlines", (pole["x"] + 60, pole["y"] - 70, 30), (pole["x"], pole["y"], 14), lens=30)
    shot("j_low_mtnfoot", (835, 548, 10), (905, 566, 3), lens=24, samples=16, res=(1200, 700))
    shot("suburbs", (12 * C - 60, 4 * C - 150, 70), (14 * C, 6 * C, 0), lens=30)
    shot("oldtown", (2 * C + 10, 11 * C, 45), (-2 * C, 15 * C, 15), lens=26)
    shot("docks", (-12 * C, -6 * C, 140), (-19 * C, 2 * C, 0), lens=30)
    shot("downtown", (9 * C, -7 * C, 110), (0, -15 * C, 20), lens=28)


if __name__ == "__main__":
    main(render="--no-render" not in sys.argv)
