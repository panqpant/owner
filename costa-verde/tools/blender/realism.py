"""Hyper-real render layer for the detailed block (tools/blender/detail_town.py): procedural PBR materials
(stucco grain and grime, tile relief, asphalt aggregate and cracks, concrete, glass, lawn), bevelled edges,
continuous streets (Shapely: asphalt, raised sidewalks and curbs that wrap the junction corners, crosswalks,
stop lines, lane dashes), parked cars, utility poles with sagging wires, street props, shrubs and hedges,
hero palms and oaks with real fronds and leaf clumps, grass blades, physical sky and a real camera.
All geometry and materials are made by code; nothing is downloaded."""
import math
import random

import bmesh
import bpy
from mathutils import Vector, geometry
from shapely.geometry import LineString, Point, Polygon, box as sbox
from shapely.ops import unary_union

# ---------------------------------------------------------------- materials


def _lin(c):
    return tuple(((v / 255 + 0.055) / 1.055) ** 2.4 if v / 255 > 0.04045 else v / 255 / 12.92 for v in c)


def _nodes(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    return m, nt, nt.nodes["Principled BSDF"]


def _n(nt, kind, **inputs):
    node = nt.nodes.new(kind)
    for k, v in inputs.items():
        if k in node.inputs:
            node.inputs[k].default_value = v
        else:
            setattr(node, k, v)
    return node


def _mix(nt, a, b, fac, blend="MIX"):
    mx = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type=blend)
    nt.links.new(fac, mx.inputs["Factor"])
    if isinstance(a, tuple):
        mx.inputs["A"].default_value = (*a, 1)
    else:
        nt.links.new(a, mx.inputs["A"])
    if isinstance(b, tuple):
        mx.inputs["B"].default_value = (*b, 1)
    else:
        nt.links.new(b, mx.inputs["B"])
    return mx.outputs["Result"]


def _bump(nt, b, height, strength, distance=0.1):
    bp = _n(nt, "ShaderNodeBump", Strength=strength, Distance=distance)
    nt.links.new(height, bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])


def _coords(nt):
    return _n(nt, "ShaderNodeTexCoord").outputs["Object"]


def mat_wall(ground_z):
    """Stucco: vertex colour, fine grain, darker crevices (AO), grime and rain streaks near the base."""
    m, nt, b = _nodes("real_wall")
    col = _n(nt, "ShaderNodeAttribute", attribute_name="col").outputs["Color"]
    co = _coords(nt)
    grain = _n(nt, "ShaderNodeTexNoise", Scale=1.8, Detail=10.0, Roughness=0.6)
    nt.links.new(co, grain.inputs["Vector"])
    c1 = _mix(nt, col, (0.32, 0.30, 0.27), _rng(nt, grain.outputs["Fac"], 0.35, 0.65, 0, 0.14))
    ao = _n(nt, "ShaderNodeAmbientOcclusion", Distance=2.0)
    c2 = _mix(nt, c1, (0.06, 0.055, 0.05), _rng(nt, ao.outputs["AO"], 0.4, 1.0, 0.45, 0))
    sep = _n(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(co, sep.inputs["Vector"])
    base = _rng(nt, sep.outputs["Z"], ground_z, ground_z + 5, 0.35, 0)
    streak = _n(nt, "ShaderNodeTexNoise", Scale=0.6, Detail=4.0)
    sc = _n(nt, "ShaderNodeMapping")
    sc.inputs["Scale"].default_value = (3, 3, 0.15)
    nt.links.new(co, sc.inputs["Vector"])
    nt.links.new(sc.outputs["Vector"], streak.inputs["Vector"])
    st = _rng(nt, streak.outputs["Fac"], 0.5, 0.75, 0, 0.3)  # rain streaks
    dirt = _n(nt, "ShaderNodeMath", operation="MAXIMUM")
    nt.links.new(base, dirt.inputs[0])
    nt.links.new(st, dirt.inputs[1])
    c3 = _mix(nt, c2, (0.13, 0.11, 0.08), dirt.outputs["Value"])
    blot = _n(nt, "ShaderNodeTexNoise", Scale=0.08, Detail=3.0)  # sun-bleached / patched areas
    nt.links.new(co, blot.inputs["Vector"])
    c3 = _mix(nt, c3, (0.8, 0.78, 0.72), _rng(nt, blot.outputs["Fac"], 0.55, 0.75, 0, 0.18))
    nt.links.new(c3, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    fine = _n(nt, "ShaderNodeTexNoise", Scale=25.0, Detail=8.0)
    nt.links.new(co, fine.inputs["Vector"])
    _bump(nt, b, fine.outputs["Fac"], 0.25, 0.05)
    return m


def _rng(nt, v, a, b, c, d):
    r = _n(nt, "ShaderNodeMapRange")
    r.inputs["From Min"].default_value, r.inputs["From Max"].default_value = a, b
    r.inputs["To Min"].default_value, r.inputs["To Max"].default_value = c, d
    nt.links.new(v, r.inputs["Value"])
    return r.outputs["Result"]


def mat_roof():
    """Clay tiles / shingles: rows of relief along the slope, per-tile colour variation, weathering."""
    m, nt, b = _nodes("real_roof")
    col = _n(nt, "ShaderNodeAttribute", attribute_name="col").outputs["Color"]
    co = _coords(nt)
    rows = _n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z", Scale=0.55, Distortion=0.4, Detail=2.0)
    nt.links.new(co, rows.inputs["Vector"])
    cells = _n(nt, "ShaderNodeTexVoronoi", Scale=0.9)
    nt.links.new(co, cells.inputs["Vector"])
    c1 = _mix(nt, col, cells.outputs["Color"], _rng(nt, rows.outputs["Fac"], 0, 1, 0.06, 0.1), "OVERLAY")
    weather = _n(nt, "ShaderNodeTexNoise", Scale=0.15, Detail=6.0)
    nt.links.new(co, weather.inputs["Vector"])
    c2 = _mix(nt, c1, (0.03, 0.03, 0.028), _rng(nt, weather.outputs["Fac"], 0.42, 0.7, 0, 0.6))  # black roof mildew
    nt.links.new(c2, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.8
    _bump(nt, b, rows.outputs["Fac"], 0.8, 0.3)
    return m


def mat_asphalt():
    m, nt, b = _nodes("real_asphalt")
    co = _coords(nt)
    agg = _n(nt, "ShaderNodeTexVoronoi", Scale=6.0)
    nt.links.new(co, agg.inputs["Vector"])
    wear = _n(nt, "ShaderNodeTexNoise", Scale=0.08, Detail=6.0)
    nt.links.new(co, wear.inputs["Vector"])
    c1 = _mix(nt, (0.035, 0.035, 0.038), (0.08, 0.078, 0.075), _rng(nt, wear.outputs["Fac"], 0.4, 0.65, 0, 1))
    c2 = _mix(nt, c1, (0.12, 0.12, 0.11), _rng(nt, agg.outputs["Distance"], 0, 0.25, 0.35, 0))
    crack = _n(nt, "ShaderNodeTexVoronoi", Scale=0.05, feature="DISTANCE_TO_EDGE")
    nt.links.new(co, crack.inputs["Vector"])
    sparse = _n(nt, "ShaderNodeTexNoise", Scale=0.04, Detail=3.0)  # cracks only in patches
    nt.links.new(co, sparse.inputs["Vector"])
    cm = _n(nt, "ShaderNodeMath", operation="MULTIPLY")
    nt.links.new(_rng(nt, crack.outputs["Distance"], 0, 0.006, 1, 0), cm.inputs[0])
    nt.links.new(_rng(nt, sparse.outputs["Fac"], 0.55, 0.65, 0, 0.8), cm.inputs[1])
    cmask = cm.outputs["Value"]
    c3 = _mix(nt, c2, (0.015, 0.015, 0.015), cmask)
    oil = _n(nt, "ShaderNodeTexVoronoi", Scale=0.35)  # oil drips and patches
    nt.links.new(co, oil.inputs["Vector"])
    c3 = _mix(nt, c3, (0.012, 0.012, 0.012), _rng(nt, oil.outputs["Distance"], 0, 0.12, 0.7, 0))
    patch = _n(nt, "ShaderNodeTexNoise", Scale=0.02, Detail=2.0)  # repaved patches
    nt.links.new(co, patch.inputs["Vector"])
    c3 = _mix(nt, c3, (0.025, 0.025, 0.027), _rng(nt, patch.outputs["Fac"], 0.6, 0.62, 0, 0.8))
    nt.links.new(c3, b.inputs["Base Color"])
    rough = _rng(nt, wear.outputs["Fac"], 0.3, 0.7, 0.8, 0.95)
    nt.links.new(rough, b.inputs["Roughness"])
    _bump(nt, b, agg.outputs["Distance"], 0.35, 0.05)
    return m


def mat_concrete(tint=(0.42, 0.41, 0.38), name="real_concrete"):
    m, nt, b = _nodes(name)
    co = _coords(nt)
    n1 = _n(nt, "ShaderNodeTexNoise", Scale=0.3, Detail=8.0)
    nt.links.new(co, n1.inputs["Vector"])
    c1 = _mix(nt, tint, tuple(x * 0.7 for x in tint), _rng(nt, n1.outputs["Fac"], 0.45, 0.7, 0, 1))
    joints = _n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="X", Scale=0.035, wave_profile="SAW")
    nt.links.new(co, joints.inputs["Vector"])
    c2 = _mix(nt, c1, (0.1, 0.1, 0.1), _rng(nt, joints.outputs["Fac"], 0.97, 1.0, 0, 0.8))
    nt.links.new(c2, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88
    fine = _n(nt, "ShaderNodeTexNoise", Scale=30.0, Detail=6.0)
    nt.links.new(co, fine.inputs["Vector"])
    _bump(nt, b, fine.outputs["Fac"], 0.2, 0.03)
    return m


def mat_glass():
    m, nt, b = _nodes("real_glass")
    b.inputs["Base Color"].default_value = (0.012, 0.016, 0.02, 1)
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["Specular IOR Level"].default_value = 0.8
    b.inputs["Coat Weight"].default_value = 1.0
    return m


def mat_simple(name, col, rough=0.6, metal=0.0, vertex=False, emit=None):
    m, nt, b = _nodes(name)
    if vertex:
        a = _n(nt, "ShaderNodeAttribute", attribute_name="col")
        nt.links.new(a.outputs["Color"], b.inputs["Base Color"])
    else:
        b.inputs["Base Color"].default_value = (*_lin(col), 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emit:
        b.inputs["Emission Color"].default_value = (*emit, 1)
        b.inputs["Emission Strength"].default_value = 3
    return m


def mat_foliage(name, col, var=0.25):
    """Leaves: colour variation and a little translucency."""
    m, nt, b = _nodes(name)
    co = _coords(nt)
    n1 = _n(nt, "ShaderNodeTexNoise", Scale=0.6, Detail=4.0)
    nt.links.new(co, n1.inputs["Vector"])
    c = _lin(col)
    c1 = _mix(nt, tuple(x * (1 - var) for x in c), tuple(min(1, x * (1 + var)) for x in c), n1.outputs["Fac"])
    nt.links.new(c1, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.55
    b.inputs["Subsurface Weight"].default_value = 0.15
    return m


def realify(objs, ground_z):
    """Swap the detail-model materials for real ones and soften every edge with a bevel."""
    wall, roof, glass, conc, asph = mat_wall(ground_z), mat_roof(), mat_glass(), mat_concrete(), mat_asphalt()
    swap = {"wall": wall, "roof_tile": roof, "glass": glass, "concrete": conc, "asphalt": asph,
            "trim": mat_simple("real_trim", (240, 238, 230), 0.55, vertex=True), "frame": mat_simple("real_frame", (0, 0, 0), 0.45, vertex=True),
            "door": mat_simple("real_door", (0, 0, 0), 0.5, vertex=True), "awning": mat_simple("real_awning", (0, 0, 0), 0.85, vertex=True),
            "roof_flat": mat_concrete((0.5, 0.49, 0.46), "real_roof_flat"), "metal": mat_simple("real_metal", (176, 178, 180), 0.35, 0.8),
            "pool": mat_simple("real_pool", (40, 150, 190), 0.03), "paint": mat_simple("real_paint", (0, 0, 0), 0.6, vertex=True),
            "pole": mat_simple("real_pole", (80, 82, 84), 0.45, 0.7), "lamp": mat_simple("real_lamp", (255, 240, 210), 0.3, emit=(1, 0.85, 0.6))}
    for o in objs:
        me = o.data
        for i, mt in enumerate(me.materials):
            if mt and mt.name.split(".")[0] in swap:
                me.materials[i] = swap[mt.name.split(".")[0]]
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.005)
        bm.to_mesh(me)
        bm.free()
        bev = o.modifiers.new("soft edges", "BEVEL")
        bev.width, bev.segments, bev.limit_method = 0.12, 2, "ANGLE"
        bev.harden_normals = True


# ---------------------------------------------------------------- streets


def _slab(name, geom, y0, y1, mat):
    """Extrude shapely (Multi)Polygon(s) with holes into a closed slab mesh."""
    polys = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    verts, faces = [], []
    for p in polys:
        if p.is_empty or p.area < 1:
            continue
        rings = [list(p.exterior.coords)[:-1]] + [list(r.coords)[:-1] for r in p.interiors]
        flat = [pt for r in rings for pt in r]
        tris = geometry.tessellate_polygon([[Vector((x, z, 0)) for x, z in r] for r in rings])
        base = len(verts)
        verts += [(x, -z, y1) for x, z in flat]
        faces += [(base + a, base + b, base + c) for a, b, c in tris]
        off = 0
        for r in rings:  # side walls (curbs)
            n = len(r)
            for i in range(n):
                a, b = r[i], r[(i + 1) % n]
                k = len(verts)
                verts += [(a[0], -a[1], y1), (b[0], -b[1], y1), (b[0], -b[1], y0), (a[0], -a[1], y0)]
                faces.append((k, k + 1, k + 2, k + 3))
            off += n
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(o)
    return o


def streets(roads, zone, gy):
    """Asphalt as the union of the roads, sidewalks 8 studs wide around it, curbs where they meet;
    crosswalks and stop lines at junctions, lane dashes between them. Returns junction data for props."""
    clip = sbox(*zone)
    lines = [(LineString([(r["ax"], r["az"]), (r["bx"], r["bz"])]), r["width"]) for r in roads]
    asphalt = unary_union([ln.buffer(w / 2, cap_style="round", join_style="round") for ln, w in lines]).intersection(clip)
    walk = unary_union([ln.buffer(w / 2 + 8, cap_style="round") for ln, w in lines]).difference(asphalt).intersection(clip)
    walk_outer = unary_union([ln.buffer(w / 2 + 8, cap_style="round") for ln, w in lines])
    _slab("asphalt", asphalt, gy - 1, gy + 0.5, mat_asphalt())
    _slab("sidewalk", walk, gy - 1, gy + 1.0, mat_concrete())
    # junctions: vertices used by 3+ segment ends
    deg = {}
    for r in roads:
        for k in ((round(r["ax"]), round(r["az"])), (round(r["bx"]), round(r["bz"]))):
            deg[k] = deg.get(k, 0) + 1
    junctions = [k for k, n in deg.items() if n >= 3 and zone[0] < k[0] < zone[2] and zone[1] < k[1] < zone[3]]
    paint_w, paint_y = [], []
    for r in roads:
        ax, az, bx, bz, w = r["ax"], r["az"], r["bx"], r["bz"], r["width"]
        L = math.hypot(bx - ax, bz - az)
        if L < 1:
            continue
        ux, uz = (bx - ax) / L, (bz - az) / L
        nx, nz = -uz, ux
        ends = [deg.get((round(ax), round(az)), 0) >= 3, deg.get((round(bx), round(bz)), 0) >= 3]
        for e, at_start in ((ends[0], True), (ends[1], False)):
            if not e:
                continue
            sx, sz = (ax, az) if at_start else (bx, bz)
            dx, dz = (ux, uz) if at_start else (-ux, -uz)
            d0 = w / 2 + 9
            for k in range(int(w / 2.4)):  # zebra crosswalk across the arm
                o = -w / 2 + 1.2 + k * 2.4
                cx, cz = sx + dx * (d0 + 3) + nx * o, sz + dz * (d0 + 3) + nz * o
                paint_w.append(((cx, cz), (dx, dz), 6, 1.2))
            cx, cz = sx + dx * (d0 + 7.5), sz + dz * (d0 + 7.5)  # stop line on the approaching half
            paint_w.append(((cx + nx * w / 4 * (1 if at_start else -1), cz + nz * w / 4 * (1 if at_start else -1)), (nx, nz), w / 2 - 1, 1.0))
        # centre dashes, kept clear of junctions
        t = 0.0
        while t < L:
            dist_a, dist_b = t, L - t
            if (not ends[0] or dist_a > w / 2 + 20) and (not ends[1] or dist_b > w / 2 + 20):
                paint_y.append(((ax + ux * t, az + uz * t), (ux, uz), 5, 0.5))
            t += 12
    for name, items, col in (("paint_white", paint_w, (235, 235, 228)), ("paint_yellow", paint_y, (226, 186, 52))):
        verts, faces = [], []
        for (cx, cz), (dx, dz), length, width in items:
            if not (zone[0] < cx < zone[2] and zone[1] < cz < zone[3]):
                continue
            px, pz = -dz, dx
            k = len(verts)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                x, z = cx + dx * length / 2 * a + px * width / 2 * b, cz + dz * length / 2 * a + pz * width / 2 * b
                verts.append((x, -z, gy + 0.52))
            faces.append((k, k + 1, k + 2, k + 3))
        me = bpy.data.meshes.new(name)
        me.from_pydata(verts, [], faces)
        me.materials.append(mat_paint(name, col))
        o = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(o)
    return asphalt, junctions, walk_outer


# ---------------------------------------------------------------- models (built once, instanced)


def _collection(name):
    c = bpy.data.collections.new(name)
    return c


def _obj(name, bm, mats, col):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    return o


def _cube(bm, c, s, mi=0):
    r = bmesh.ops.create_cube(bm, size=1)
    bmesh.ops.scale(bm, vec=s, verts=r["verts"])
    bmesh.ops.translate(bm, vec=c, verts=r["verts"])
    for f in {f for v in r["verts"] for f in v.link_faces}:
        f.material_index = mi
    return r["verts"]


def _cyl(bm, c, r1, r2, h, seg=12, mi=0, axis="Z"):
    from mathutils import Matrix
    rot = {"Z": Matrix(), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r1, radius2=r2, depth=h, matrix=Matrix.Translation(c) @ rot)
    for f in {f for v in res["verts"] for f in v.link_faces}:
        f.material_index = mi
    return res["verts"]


CAR_COLOURS = [((236, 236, 232), 25), ((24, 24, 26), 20), ((128, 130, 132), 16), ((190, 192, 194), 14), ((40, 66, 120), 10),
               ((150, 30, 28), 10), ((60, 70, 60), 3), ((200, 170, 120), 2)]


def car_models():
    """Sedan, SUV and pickup at ~3 studs per metre, each in a few real-world colours."""
    glass, tyre, rim = mat_glass(), mat_simple("tyre", (22, 22, 22), 0.85), mat_simple("rim", (170, 172, 176), 0.25, 0.9)
    light_f, light_r = mat_simple("headlight", (240, 240, 230), 0.1, emit=(0.6, 0.6, 0.55)), mat_simple("taillight", (160, 20, 20), 0.2)
    shapes = {"sedan": (13.5, 5.4, 2.6, 1.9, 7.0, 0.6), "suv": (14.5, 5.8, 3.4, 2.4, 8.5, 1.4), "pickup": (16.5, 5.8, 3.3, 2.3, 6.0, 3.5)}
    models = []
    rng = random.Random(4)
    for kind, (L, Wd, body_h, cab_h, cab_l, cab_off) in shapes.items():
        for v in range(3):
            col = rng.choices([c for c, _ in CAR_COLOURS], [w for _, w in CAR_COLOURS])[0]
            paint = mat_simple(f"paint_{kind}{v}", col, 0.18, 0.6)
            paint.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 1.0
            coll = _collection(f"car_{kind}_{v}")
            bm = bmesh.new()
            _cube(bm, (0, 0, 1.2 + body_h / 2), (L, Wd, body_h), 0)
            cab = _cube(bm, (-cab_off * 0.5 + (0 if kind != "pickup" else 2.2), 0, 1.2 + body_h + cab_h / 2), (cab_l, Wd * 0.86, cab_h), 1)
            for vv in cab:  # taper the cabin roof for a windscreen rake
                if vv.co.z > 1.2 + body_h + cab_h * 0.4:
                    vv.co.x *= 0.82
                    vv.co.y *= 0.92
            for sx in (-1, 1):
                for sy in (-1, 1):
                    _cyl(bm, (sx * L * 0.32, sy * Wd * 0.46, 1.25), 1.25, 1.25, 1.0, 16, 2, "Y")
                    _cyl(bm, (sx * L * 0.32, sy * Wd * 0.5, 1.25), 0.75, 0.75, 0.2, 10, 3, "Y")
                _cube(bm, (sx * L / 2, 0.0, 1.2 + body_h * 0.7), (0.2, Wd * 0.8, 0.5), 4 if sx > 0 else 5)
            o = _obj(f"car_{kind}_{v}", bm, [paint, glass, tyre, rim, light_f, light_r], coll)
            bev = o.modifiers.new("b", "BEVEL")
            bev.width, bev.segments = 0.35, 3
            models.append(coll)
    return models


def hero_palm(seed):
    """Coconut palm: ringed curving trunk, 16 fronds each with ~40 pairs of drooping leaflets, coconuts, a dead frond."""
    rng = random.Random(seed)
    coll = _collection(f"hero_palm_{seed}")
    trunk_m = mat_simple(f"palm_trunk{seed}", (126, 108, 88), 0.9)
    leaf_m, dead_m = mat_foliage(f"palm_leaf{seed}", (74, 112, 40), 0.22), mat_simple(f"palm_dead{seed}", (150, 120, 70), 0.9)
    nut_m = mat_simple(f"coconut{seed}", (96, 84, 40), 0.7)
    bm = bmesh.new()
    H = rng.uniform(34, 44)
    lean = rng.uniform(4, 10)
    segs = 28
    for i in range(segs):  # ringed trunk: alternating ring diameters
        t0, t1 = i / segs, (i + 1) / segs
        p0 = Vector((lean * t0 ** 1.6, 0, H * t0))
        p1 = Vector((lean * t1 ** 1.6, 0, H * t1))
        r = 1.15 - 0.4 * t0 + (0.08 if i % 2 else 0)
        d = p1 - p0
        from mathutils import Matrix
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=r, radius2=r * 0.97, depth=d.length, matrix=Matrix.Translation((p0 + p1) / 2) @ rot)
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 0
    top = Vector((lean, 0, H))
    for k in range(16):
        a = 2 * math.pi * k / 16 + rng.uniform(-0.15, 0.15)
        up = rng.uniform(-0.2, 0.7)  # some fronds rise, most arch and droop
        dead = k < 2 and rng.random() < 0.7
        length = rng.uniform(13, 17) * (0.8 if dead else 1)
        pts = []
        for j in range(21):  # rachis: arcs out and down
            t = j / 20
            r = length * t
            z = r * up - (r ** 2) * 0.045 * (1.6 if dead else 1) - (8 * t if dead else 0)
            pts.append(top + Vector((math.cos(a) * r, math.sin(a) * r, z)))
        side = Vector((-math.sin(a), math.cos(a), 0))
        mi = 2 if dead else 1
        for j in range(1, 20):
            t = j / 20
            ll = 3.4 * math.sin(math.pi * min(1, t * 1.05)) + 0.3
            base = pts[j]
            dirv = (pts[j + 1] - pts[j - 1]).normalized()
            for s in (-1, 1):  # a leaflet each side, drooping
                tip = base + side * s * ll * 0.85 + dirv * ll * 0.45 + Vector((0, 0, -ll * 0.55))
                v1 = bm.verts.new(base)
                v2 = bm.verts.new(base + dirv * 0.35)
                v3 = bm.verts.new(tip)
                f = bm.faces.new((v1, v2, v3))
                f.material_index = mi
    for k in range(rng.randint(3, 7)):
        a = rng.uniform(0, 2 * math.pi)
        res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.75)
        bmesh.ops.translate(bm, vec=top + Vector((math.cos(a) * 0.9, math.sin(a) * 0.9, -1.0)), verts=res["verts"])
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 3
    _obj(f"hero_palm_{seed}", bm, [trunk_m, leaf_m, dead_m, nut_m], coll)
    return coll


def hero_oak(seed):
    """Live oak: thick limbs and ~30 displaced leaf clumps."""
    rng = random.Random(seed)
    coll = _collection(f"hero_oak_{seed}")
    bark = mat_simple(f"oak_bark{seed}", (90, 80, 68), 0.95)
    leaf = mat_foliage(f"oak_leaf{seed}", (52, 78, 36), 0.3)
    bm = bmesh.new()
    _cyl(bm, (0, 0, 5), 2.4, 1.8, 10, 12, 0)
    from mathutils import Matrix
    for i in range(5):
        a = i * 2 * math.pi / 5 + rng.uniform(-0.3, 0.3)
        end = Vector((math.cos(a) * 15, math.sin(a) * 15, 17))
        st = Vector((0, 0, 9))
        d = end - st
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        res = bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=1.3, radius2=0.5, depth=d.length, matrix=Matrix.Translation((st + end) / 2) @ rot)
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 0
    o_trunk = _obj(f"hero_oak_trunk_{seed}", bm, [bark], coll)
    bm = bmesh.new()
    for _ in range(30):
        p = Vector((rng.uniform(-17, 17), rng.uniform(-17, 17), rng.uniform(15, 24)))
        if p.xy.length > 19:
            continue
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=rng.uniform(4, 6.5))
        bmesh.ops.scale(bm, vec=(1.2, 1.2, 0.7), verts=res["verts"])
        bmesh.ops.translate(bm, vec=p, verts=res["verts"])
    o = _obj(f"hero_oak_leaves_{seed}", bm, [leaf], coll)
    tex = bpy.data.textures.new(f"oakdisp{seed}", "CLOUDS")
    tex.noise_scale = 1.2
    disp = o.modifiers.new("clumps", "DISPLACE")
    disp.texture, disp.strength = tex, 2.2
    _ = o_trunk
    return coll


def shrub_models():
    """Hedge block and flowering shrub, displaced so they read as foliage."""
    out = []
    for name, col, scale, sub in (("hedge", (58, 92, 44), (6, 2.2, 3.0), 3), ("shrub_pink", (196, 70, 120), (2.6, 2.6, 2.4), 3),
                                  ("shrub_green", (70, 104, 50), (2.8, 2.8, 2.6), 3), ("shrub_white", (226, 226, 214), (2.4, 2.4, 2.2), 3)):
        coll = _collection(name)
        bm = bmesh.new()
        res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1)
        bmesh.ops.scale(bm, vec=scale, verts=res["verts"])
        bmesh.ops.translate(bm, vec=(0, 0, scale[2] * 0.8), verts=res["verts"])
        leaf = mat_foliage(f"{name}_mat", col, 0.3)
        if name.startswith("shrub_") and name != "shrub_green":  # flowers over green foliage
            leaf = mat_foliage(f"{name}_mat", col, 0.4)
        o = _obj(name, bm, [leaf], coll)
        tex = bpy.data.textures.new(f"{name}_disp", "CLOUDS")
        tex.noise_scale = 0.5
        d = o.modifiers.new("leafy", "DISPLACE")
        d.texture, d.strength = tex, 0.9
        out.append(coll)
    return out


def prop_models():
    """Fire hydrant, stop sign, trash can, mailbox, wooden utility pole with crossarm."""
    props = {}
    yellow, red, wood = mat_simple("hydrant", (210, 180, 40), 0.5), mat_simple("stopsign", (180, 20, 24), 0.4), mat_simple("pole_wood", (96, 78, 60), 0.95)
    steel, white, green, black = mat_simple("steel", (140, 142, 146), 0.4, 0.8), mat_simple("signwhite", (240, 240, 236), 0.4), mat_simple("can", (40, 70, 50), 0.6), mat_simple("mailbox", (30, 30, 32), 0.4, 0.6)
    for name, build, mats in (
        ("hydrant", lambda bm: (_cyl(bm, (0, 0, 1.4), 0.55, 0.55, 2.8, 12, 0), _cyl(bm, (0, 0, 3.0), 0.65, 0.2, 0.7, 12, 0), _cyl(bm, (0, 0, 1.9), 0.25, 0.25, 1.8, 8, 0, "X")), [yellow]),
        ("stop", lambda bm: (_cyl(bm, (0, 0, 4.5), 0.12, 0.12, 9, 8, 0), _cyl(bm, (0, 0.15, 8.4), 1.25, 1.25, 0.1, 8, 1, "Y")), [steel, red]),
        ("trashcan", lambda bm: _cyl(bm, (0, 0, 1.5), 0.9, 0.9, 3.0, 14, 0), [green]),
        ("mailbox", lambda bm: (_cube(bm, (0, 0, 1.8), (0.3, 0.3, 3.6), 0), _cube(bm, (0, 0, 3.9), (1.6, 0.8, 0.8), 1)), [wood, black]),
        ("utility_pole", lambda bm: (_cyl(bm, (0, 0, 17), 0.55, 0.4, 34, 10, 0), _cube(bm, (0, 0, 32), (0.5, 9, 0.5), 0),
                                     _cyl(bm, (0, -4, 32.7), 0.18, 0.18, 0.9, 6, 1), _cyl(bm, (0, 0, 33.6), 0.18, 0.18, 0.9, 6, 1), _cyl(bm, (0, 4, 32.7), 0.18, 0.18, 0.9, 6, 1),
                                     _cyl(bm, (0.9, 0, 28), 0.9, 0.9, 2.6, 12, 2)), [wood, white, steel]),
    ):
        coll = _collection(name)
        bm = bmesh.new()
        build(bm)
        _obj(name, bm, mats, coll)
        props[name] = coll
    return props


def place(coll, x, z, y, rot=0.0, scale=1.0):
    e = bpy.data.objects.new(coll.name, None)
    e.instance_type, e.instance_collection = "COLLECTION", coll
    e.location = (x, -z, y)
    e.rotation_euler = (0, 0, rot)
    e.scale = (scale, scale, scale)
    bpy.context.collection.objects.link(e)
    return e


def street_life(roads, asphalt, junctions, buildings, zone, gy, rng):
    """Parked cars, utility poles with wires, hydrants, stop signs, trash cans, mailboxes."""
    cars, props = car_models(), prop_models()
    jpts = [Point(j) for j in junctions]
    from shapely.prepared import prep
    road_area = prep(asphalt.buffer(2.5))
    off_road = lambda x, z: not road_area.contains(Point(x, z))  # noqa: E731
    wires = bpy.data.curves.new("wires", "CURVE")
    wires.dimensions, wires.bevel_depth = "3D", 0.07
    poles = []
    for r in roads:
        ax, az, bx, bz, w = r["ax"], r["az"], r["bx"], r["bz"], r["width"]
        L = math.hypot(bx - ax, bz - az)
        if L < 10 or w > 40:
            continue
        ux, uz = (bx - ax) / L, (bz - az) / L
        nx, nz = -uz, ux
        ang = math.atan2(-uz, ux)
        t = rng.uniform(8, 16)
        while t < L - 8:  # parked cars along both curbs, clear of junctions
            for side in (-1, 1):
                x, z = ax + ux * t + nx * (w / 2 - 3.6) * side, az + uz * t + nz * (w / 2 - 3.6) * side
                if zone[0] < x < zone[2] and zone[1] < z < zone[3] and rng.random() < 0.32 and all(Point(x, z).distance(j) > w / 2 + 22 for j in jpts):
                    place(rng.choice(cars), x, z, gy + 0.5, ang + (0 if side > 0 else math.pi) + rng.uniform(-0.03, 0.03))
            t += 17
        t = 20.0
        while t < L:  # utility poles on one side, behind the sidewalk
            x, z = ax + ux * t + nx * (w / 2 + 9.5), az + uz * t + nz * (w / 2 + 9.5)
            if zone[0] < x < zone[2] and zone[1] < z < zone[3] and off_road(x, z):
                place(props["utility_pole"], x, z, gy + 1, ang + math.pi / 2)
                poles.append((x, z, ang))
            t += 55
        hx, hz = ax + ux * 25 + nx * (w / 2 + 1.5), az + uz * 25 + nz * (w / 2 + 1.5)
        if rng.random() < 0.5 and zone[0] < hx < zone[2] and zone[1] < hz < zone[3] and off_road(hx, hz):  # hydrant
            place(props["hydrant"], hx, hz, gy + 1)
    for (x0, z0, a0), (x1, z1, a1) in zip(poles, poles[1:]):  # sagging wires between neighbouring poles
        if math.hypot(x1 - x0, z1 - z0) > 70:
            continue
        for off, hgt in ((-4, 32.9), (0, 33.8), (4, 32.9)):
            sp = wires.splines.new("POLY")
            pts = []
            for k in range(9):
                t = k / 8
                ox0, oz0 = -math.sin(a0) * 0, 0
                x = x0 + (x1 - x0) * t + math.cos(a0 + math.pi / 2) * off
                z = z0 + (z1 - z0) * t - math.sin(a0 + math.pi / 2) * off
                pts.append((x, -z, gy + 1 + hgt - 2.2 * 4 * t * (1 - t), 1))
                _ = ox0, oz0
            sp.points.add(len(pts) - 1)
            for p, c in zip(sp.points, pts):
                p.co = c
    wo = bpy.data.objects.new("wires", wires)
    wires.materials.append(mat_simple("wire", (20, 20, 20), 0.5))
    bpy.context.collection.objects.link(wo)
    for (jx, jz) in junctions:  # stop signs on the corners of minor junctions
        for dx, dz in ((1, 1), (-1, 1), (1, -1), (-1, -1)):  # on a corner that is sidewalk, not road
            sx, sz = jx + dx * 17, jz + dz * 17
            if off_road(sx, sz):
                place(props["stop"], sx, sz, gy + 1, rng.uniform(0, 6.28))
                break
    for i, b in buildings:  # shrubs, hedges, mailboxes, trash cans
        c, s = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
        to_world = lambda lx, lz: (b["x"] + c * lx - s * lz, b["z"] + s * lx + c * lz)  # noqa: E731
        front = -b["d"] / 2 - 2.6
        if b["style"] == "house":
            hedge, flowers = shrubs_by_name("hedge"), [shrubs_by_name(n) for n in ("shrub_pink", "shrub_green", "shrub_white")]
            k = -b["w"] / 2 + 3
            while k < b["w"] / 2 - 3:
                if abs(k) > 5:  # keep the door clear
                    x, z = to_world(k, front)
                    place(rng.choice(flowers) if rng.random() < 0.6 else hedge, x, z, b["y"], -math.radians(b["rot"]), rng.uniform(0.8, 1.2))
                k += rng.uniform(3.5, 6)
            x, z = to_world(b["w"] * 0.3 + 7, -b["d"] / 2 - 26)
            place(props["mailbox"], x, z, b["y"] + 0.2, -math.radians(b["rot"]))
        elif rng.random() < 0.4:
            x, z = to_world(b["w"] / 2 - 2, front - 4)
            place(props["trashcan"], x, z, b["y"] + 1)


_SHRUBS = {}


def shrubs_by_name(name):
    if not _SHRUBS:
        for c in shrub_models():
            _SHRUBS[c.name] = c
    return _SHRUBS[name]


def grass(terrain_obj, zone, lawn, density=900000):
    """Grass blades on lawn ground inside the zone, kept off roads, sidewalks and buildings."""
    me = terrain_obj.data
    vg = terrain_obj.vertex_groups.new(name="lawn")
    col = me.color_attributes["col"]
    from shapely.prepared import prep
    inc = prep(lawn.buffer(-1.5))
    idx = []
    for v in me.vertices:
        x, z = v.co.x, -v.co.y
        if zone[0] < x < zone[2] and zone[1] < z < zone[3]:
            r, g, b, _ = col.data[v.index].color
            if inc.contains(Point(x, z)):
                idx.append(v.index)
    vg.add(idx, 1.0, "REPLACE")
    mod = terrain_obj.modifiers.new("grass", "PARTICLE_SYSTEM")
    ps = mod.particle_system
    ps.vertex_group_density = "lawn"
    st = ps.settings
    st.type, st.count, st.hair_length = "HAIR", density, 1.8
    st.use_advanced_hair = True
    st.factor_random = 0.6
    st.brownian_factor = 0.08
    try:
        st.root_radius, st.tip_radius = 0.06, 0.0
        st.radius_scale = 1.0
    except AttributeError:
        pass
    st.render_type = "PATH"
    blade = mat_foliage("grass_blades", (84, 118, 46), 0.35)
    me.materials.append(blade)
    st.material = len(me.materials)
    return ps


def sky_and_sun(elev, azim, exposure=0.0):
    s = bpy.context.scene
    w = bpy.data.worlds.new("sky")
    s.world = w
    w.use_nodes = True
    nt = w.node_tree
    sk = nt.nodes.new("ShaderNodeTexSky")
    sk.sky_type = "MULTIPLE_SCATTERING"
    sk.sun_disc = False
    sk.sun_elevation, sk.sun_rotation = math.radians(elev), math.radians(azim)
    sk.air_density, sk.aerosol_density = 1.0, 2.2  # Florida humidity
    nt.links.new(sk.outputs["Color"], nt.nodes["Background"].inputs["Color"])
    nt.nodes["Background"].inputs["Strength"].default_value = 0.35
    bpy.ops.object.light_add(type="SUN", rotation=(math.radians(90 - elev), 0, math.radians(azim + 90)))
    sun = bpy.context.object
    sun.data.energy, sun.data.angle = 5.5, math.radians(0.6)
    sun.data.color = (1.0, 0.93, 0.82)
    s.view_settings.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "AgX - Punchy", "None"):
        try:
            s.view_settings.look = look
            break
        except TypeError:
            continue
    s.view_settings.exposure = exposure


def real_camera(pos, target, lens=35, focus=None, fstop=8):
    bpy.ops.object.camera_add(location=pos)
    c = bpy.context.object
    c.data.lens = lens
    c.data.clip_start, c.data.clip_end = 0.5, 20000
    c.rotation_euler = (Vector(target) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
    if focus:
        c.data.dof.use_dof = True
        c.data.dof.focus_distance = focus
        c.data.dof.aperture_fstop = fstop
    bpy.context.scene.camera = c
    return c


def mat_paint(name, col):
    """Road paint, worn through to the asphalt in patches."""
    m, nt, b = _nodes(name)
    co = _coords(nt)
    wear = _n(nt, "ShaderNodeTexNoise", Scale=0.9, Detail=8.0)
    nt.links.new(co, wear.inputs["Vector"])
    c = _mix(nt, tuple(x * 0.85 for x in _lin(col)), (0.05, 0.05, 0.05), _rng(nt, wear.outputs["Fac"], 0.45, 0.7, 0, 0.75))
    nt.links.new(c, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    return m


SHOP_NAMES = ["PHARMACY", "CAFE", "LAUNDROMAT", "BARBER", "TACOS", "LIQUORS", "NAILS", "INSURANCE", "BAKERY", "DELI", "PAWN",
              "TATTOO", "BAIT & TACKLE", "CIGARS", "MARKET", "DENTAL", "PIZZA", "THRIFT", "HARDWARE", "VAPE"]


def signs(items):
    """Shop names in raised letters on the sign boards."""
    mat = mat_simple("sign_letters", (244, 240, 228), 0.4)
    for tf, z, width, rng in items:
        cu = bpy.data.curves.new("sign", "FONT")
        cu.body = rng.choice(SHOP_NAMES)
        cu.align_x, cu.align_y = "CENTER", "CENTER"
        cu.extrude = 0.12
        cu.size = 1.7
        o = bpy.data.objects.new("sign", cu)
        cu.materials.append(mat)
        x, y, zz = tf(0, 13.6, z)
        x2, y2, _ = tf(1, 13.6, z)
        o.location = (x, y, zz)
        o.rotation_euler = (math.pi / 2, 0, math.atan2(y2 - y, x2 - x) + math.pi)  # face the street, not the wall
        bpy.context.collection.objects.link(o)
        dims = max(o.dimensions.x, 0.1)
        if dims > width:
            o.scale = (width / dims,) * 3


def weather(objs):
    """Lawns: brown and straw dry patches and bare dirt; applied to the terrain ground material."""
    g = bpy.data.materials.get("ground")
    if not g:
        return
    nt = g.node_tree
    b = nt.nodes["Principled BSDF"]
    src = b.inputs["Base Color"].links[0].from_socket
    co = _coords(nt)
    n1 = _n(nt, "ShaderNodeTexNoise", Scale=0.05, Detail=6.0)
    nt.links.new(co, n1.inputs["Vector"])
    c = _mix(nt, src, (0.2, 0.17, 0.08), _rng(nt, n1.outputs["Fac"], 0.5, 0.68, 0, 0.55))
    n2 = _n(nt, "ShaderNodeTexNoise", Scale=0.4, Detail=8.0)
    nt.links.new(co, n2.inputs["Vector"])
    c = _mix(nt, c, (0.11, 0.08, 0.05), _rng(nt, n2.outputs["Fac"], 0.62, 0.72, 0, 0.6))
    nt.links.new(c, b.inputs["Base Color"])
    _bump(nt, b, n2.outputs["Fac"], 0.3, 0.2)


def haze(cx, cz, gy):
    """Humid air: a thin volume so distance fades to a warm haze (aerial perspective)."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, -cz, gy + 300))
    o = bpy.context.object
    o.scale = (3000, 3000, 600)
    o.name = "haze"
    m = bpy.data.materials.new("haze")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes["Principled BSDF"])
    v = nt.nodes.new("ShaderNodeVolumePrincipled")
    v.inputs["Color"].default_value = (0.85, 0.88, 0.95, 1)
    v.inputs["Density"].default_value = 0.00035
    nt.links.new(v.outputs["Volume"], nt.nodes["Material Output"].inputs["Volume"])
    o.data.materials.append(m)


def lens(path):
    """Camera imperfections real photos have: vignette, lateral colour fringing, highlight bloom, grain."""
    import numpy as np
    from PIL import Image, ImageFilter
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.float32) / 255
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a *= (1 - 0.22 * np.clip(r - 0.35, 0, None) ** 1.6)[..., None]
    shift = max(1, w // 900)  # chromatic aberration: red out, blue in, toward the edges
    a[..., 0] = np.roll(a[..., 0], shift, axis=1) * 0.5 + a[..., 0] * 0.5
    a[..., 2] = np.roll(a[..., 2], -shift, axis=1) * 0.5 + a[..., 2] * 0.5
    bright = Image.fromarray((np.clip(a - 0.78, 0, 1) * 255 * 3).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(w / 120))
    a = a + np.asarray(bright).astype(np.float32) / 255 * 0.18
    a += np.random.default_rng(1).normal(0, 0.012, a.shape).astype(np.float32)
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(path)


# ---------------------------------------------------------------- CC0 photo materials (ambientCG, tools/fetch_cc0.py)

def cc0(nt, mid, size):
    """Box-projected (world space) photo texture set, one tile = `size` studs. Returns sockets dict."""
    import os
    co = _coords(nt)
    mp = _n(nt, "ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (1 / size, 1 / size, 1 / size)
    nt.links.new(co, mp.inputs["Vector"])
    out = {}
    for key, cs in (("Color", "sRGB"), ("Roughness", "Non-Color"), ("Displacement", "Non-Color"), ("Opacity", "Non-Color")):
        path = os.path.abspath(f"assets/cc0/{mid}/{mid}_1K-JPG_{key}.jpg")
        if not os.path.exists(path):
            continue
        img = _n(nt, "ShaderNodeTexImage")
        img.image = bpy.data.images.load(path, check_existing=True)
        img.image.colorspace_settings.name = cs
        img.projection, img.projection_blend = "BOX", 0.25
        nt.links.new(mp.outputs["Vector"], img.inputs["Vector"])
        out[key] = img.outputs["Color"]
    return out


def photo(mat_name, mid, size, tint_vertex=False, tint=None, bump=0.6):
    """Photo material, optionally tinted by the building's vertex colour (stucco colours) or a fixed tint."""
    m, nt, b = _nodes(mat_name)
    t = cc0(nt, mid, size)
    col = t["Color"]
    if tint_vertex or tint:
        src = _n(nt, "ShaderNodeAttribute", attribute_name="col").outputs["Color"] if tint_vertex else None
        g = _n(nt, "ShaderNodeRGBToBW")
        nt.links.new(col, g.inputs["Color"])
        mul = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
        mul.inputs["Factor"].default_value = 1.0
        if src:
            nt.links.new(src, mul.inputs["A"])
        else:
            mul.inputs["A"].default_value = (*_lin(tint), 1)
        bright = _n(nt, "ShaderNodeMath", operation="MULTIPLY", Value=1.6)
        bright.inputs[1].default_value = 1.6
        nt.links.new(g.outputs["Val"], bright.inputs[0])
        nt.links.new(bright.outputs["Value"], mul.inputs["B"])
        col = mul.outputs["Result"]
    nt.links.new(col, b.inputs["Base Color"])
    if "Roughness" in t:
        nt.links.new(t["Roughness"], b.inputs["Roughness"])
    if "Displacement" in t:
        _bump(nt, b, t["Displacement"], bump, 0.15)
    if "Opacity" in t:
        nt.links.new(t["Opacity"], b.inputs["Alpha"])
    return m, nt, b, col


def mat_window_interior():
    """Windows: strong reflection over a room behind the glass; every window differs (dark, lit, blinds, curtains)."""
    m, nt, b = _nodes("real_glass_interior")
    co = _coords(nt)
    cell = _n(nt, "ShaderNodeTexVoronoi", Scale=0.11)  # one cell ~ one window
    nt.links.new(co, cell.inputs["Vector"])
    sep = _n(nt, "ShaderNodeSeparateColor")
    nt.links.new(cell.outputs["Color"], sep.inputs["Color"])
    room = _mix(nt, (0.006, 0.006, 0.007), (0.05, 0.035, 0.025), _rng(nt, sep.outputs["Green"], 0, 1, 0, 1))
    blinds = _n(nt, "ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z", Scale=2.2)
    nt.links.new(co, blinds.inputs["Vector"])
    blind_col = _mix(nt, (0.35, 0.33, 0.28), (0.22, 0.2, 0.17), blinds.outputs["Fac"])
    is_blind = _rng(nt, sep.outputs["Red"], 0.55, 0.56, 0, 1)
    c = _mix(nt, room, blind_col, is_blind)
    curtain = _mix(nt, (0.30, 0.18, 0.12), (0.18, 0.22, 0.28), sep.outputs["Blue"])
    c = _mix(nt, c, curtain, _rng(nt, sep.outputs["Red"], 0.82, 0.83, 0, 1))
    nt.links.new(c, b.inputs["Base Color"])
    lit = _rng(nt, sep.outputs["Blue"], 0.86, 0.87, 0, 1.2)  # a few lit rooms
    b.inputs["Emission Color"].default_value = (1.0, 0.78, 0.5, 1)
    nt.links.new(lit, b.inputs["Emission Strength"])
    b.inputs["Roughness"].default_value = 0.03
    b.inputs["Specular IOR Level"].default_value = 1.0
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.0
    return m


def photo_upgrade():
    """Swap the procedural building / street materials for the photo ones, keeping grime layers on walls."""
    walls, _, _, _ = photo("photo_wall", "Plaster001", 14, tint_vertex=True, bump=0.5)
    roof, nt, b, col = photo("photo_roof", "RoofingTiles013A", 10, bump=1.2)
    tint = _n(nt, "ShaderNodeAttribute", attribute_name="col").outputs["Color"]  # per-house tile / shingle colour
    mx = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
    mx.inputs["Factor"].default_value = 0.55
    nt.links.new(col, mx.inputs["A"])
    nt.links.new(tint, mx.inputs["B"])
    nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])
    gravel_roof = photo("photo_roof_flat", "Gravel043", 8, tint=(170, 166, 158))[0]
    asph = photo("photo_asphalt", "Asphalt031", 22, bump=0.4)[0]
    conc = photo("photo_concrete", "Concrete034", 16, bump=0.3)[0]
    swaps = {"real_wall": walls, "real_roof": roof, "real_concrete": conc, "real_asphalt": asph, "real_glass": mat_window_interior(),
             "real_roof_flat": gravel_roof}
    for o in bpy.data.objects:
        if o.type == "MESH":
            for i, mt in enumerate(o.data.materials):
                if mt and mt.name in swaps:
                    o.data.materials[i] = swaps[mt.name]
    return {"grass": "Grass004", "gravel": "Gravel043", "mulch": "Ground037", "bark": "Bark014", "leaf": "Leaf001", "wood": "WoodSiding011"}


# ---------------------------------------------------------------- land cover, trees with real leaves

def landcover(detailed, street_area, zone, gy, rng, palms, oaks):
    """Every bit of ground gets a real use: paved lots, alleys, mulch beds, fences, parks, dirt. Returns lawn area."""
    from shapely.geometry import MultiPoint
    from shapely.ops import voronoi_diagram
    clip = sbox(*zone)
    feet, cents, styles = [], [], []
    for _, b in detailed:
        c, s = math.cos(math.radians(b["rot"])), math.sin(math.radians(b["rot"]))
        ps = []
        for p in b.get("parts", []):
            pts = [(b["x"] + c * p["pts"][i] - s * p["pts"][i + 1], b["z"] + s * p["pts"][i] + c * p["pts"][i + 1]) for i in range(0, len(p["pts"]), 2)]
            ps.append(Polygon(pts).buffer(0))
        f = unary_union(ps)
        feet.append(f)
        cents.append(Point(b["x"], b["z"]))
        styles.append(b["style"])
    built = unary_union(feet)
    land = clip.difference(street_area).difference(built.buffer(0.3))
    cells = voronoi_diagram(MultiPoint(cents), envelope=clip)
    paved, mulch, lawn, dirt, fences, stalls = [], [], [], [], [], []
    for cell in cells.geoms:
        k = next((i for i, p in enumerate(cents) if cell.contains(p)), None)
        if k is None:
            continue
        lot = cell.intersection(land).intersection(feet[k].buffer(45))  # lots end ~45 studs from their building
        if lot.is_empty:
            continue
        if styles[k] == "house":
            bed = feet[k].buffer(4).difference(feet[k]).intersection(lot)
            mulch.append(bed)
            lawn.append(lot.difference(bed))
            edge = lot.boundary.difference(street_area.buffer(16))  # privacy fence: sides and back only
            fences.append(edge)
        else:
            strip = lot.difference(lot.buffer(-3))  # planted edge around the car park
            mulch.append(strip.difference(street_area.buffer(1)))
            inner = lot.buffer(-3)
            paved.append(inner.union(lot.intersection(street_area.buffer(12))))  # lot entrance reaches the street
            if not inner.is_empty:  # parking bays: stripes every 9 studs across the lot
                x0, z0, x1, z1 = inner.bounds
                a = math.radians(rng.choice([0, 90]))
                ux, uz = math.cos(a), math.sin(a)
                cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
                span = max(x1 - x0, z1 - z0)
                for t in range(int(-span / 2), int(span / 2), 9):
                    for row in (-11, 11):
                        ln = LineString([(cx + ux * t - uz * (row - 8), cz + uz * t + ux * (row - 8)), (cx + ux * t - uz * (row + 8), cz + uz * t + ux * (row + 8))])
                        seg = ln.intersection(inner.buffer(-2))
                        if not seg.is_empty and seg.length > 10:
                            stalls.append(seg.buffer(0.35, cap_style="flat"))
    covered = unary_union(paved + mulch + lawn)
    rest = land.difference(covered)
    parks = [g for g in (rest.geoms if hasattr(rest, "geoms") else [rest]) if g.area > 3000]
    for g in (rest.geoms if hasattr(rest, "geoms") else [rest]):
        if g.area <= 3000:
            dirt.append(g)
    paths = []
    for p in parks:  # park: lawn, a footpath loop, trees
        inner = p.buffer(-14)
        if not inner.is_empty:
            ring = inner.boundary.buffer(2.5).intersection(p)
            paths.append(ring)
        lawn.append(p.difference(unary_union(paths)) if paths else p)
        x0, z0, x1, z1 = p.bounds
        for _ in range(int(p.area / 1100)):
            x, z = rng.uniform(x0, x1), rng.uniform(z0, z1)
            if p.buffer(-6).contains(Point(x, z)) and not any(q.contains(Point(x, z)) for q in paths):
                place(rng.choice(oaks + palms), x, z, gy, rng.uniform(0, 6.28), rng.uniform(0.8, 1.15))
    asph = bpy.data.materials.get("photo_asphalt") or mat_asphalt()
    _slab("lots", unary_union(paved), gy - 0.5, gy + 0.32, asph)
    _slab("stalls", unary_union(stalls).intersection(unary_union(paved)), gy + 0.32, gy + 0.36, mat_paint("stall_paint", (236, 236, 230)))
    _slab("mulch", unary_union(mulch), gy - 0.5, gy + 0.18, photo("photo_mulch", "Ground037", 6, tint=(120, 84, 60))[0])
    _slab("dirt", unary_union(dirt), gy - 0.5, gy + 0.08, photo("photo_dirt", "Ground037", 10, tint=(190, 170, 140))[0])
    _slab("paths", unary_union(paths) if paths else Polygon(), gy - 0.5, gy + 0.2, bpy.data.materials.get("photo_concrete") or mat_concrete())
    fence_mat = photo("photo_fence", "WoodSiding011", 6, tint=(190, 160, 120))[0]
    verts, faces = [], []
    for fl in fences:
        for ln in (fl.geoms if hasattr(fl, "geoms") else [fl]):
            if ln.is_empty or ln.geom_type not in ("LineString", "LinearRing"):
                continue
            cs = list(ln.coords)
            for (ax, az), (bx, bz) in zip(cs, cs[1:]):
                L = math.hypot(bx - ax, bz - az)
                if L < 1:
                    continue
                nx, nz = -(bz - az) / L * 0.25, (bx - ax) / L * 0.25
                k = len(verts)
                for (x, z), y in (((ax + nx, az + nz), gy), ((bx + nx, bz + nz), gy), ((bx + nx, bz + nz), gy + 6), ((ax + nx, az + nz), gy + 6),
                                  ((ax - nx, az - nz), gy), ((bx - nx, bz - nz), gy), ((bx - nx, bz - nz), gy + 6), ((ax - nx, az - nz), gy + 6)):
                    verts.append((x, -z, y))
                faces += [(k, k + 1, k + 2, k + 3), (k + 5, k + 4, k + 7, k + 6), (k + 3, k + 2, k + 6, k + 7)]
    me = bpy.data.meshes.new("fences")
    me.from_pydata(verts, [], faces)
    me.materials.append(fence_mat)
    bpy.context.collection.objects.link(bpy.data.objects.new("fences", me))
    return unary_union(lawn), unary_union(mulch)


def leaf_card(name, length, width, tint):
    """A leaf card with the photo leaf texture and its alpha cut-out, double-sided."""
    me = bpy.data.meshes.new(name)
    me.from_pydata([(-width / 2, 0, 0), (width / 2, 0, 0), (width / 2, length, 0), (-width / 2, length, 0)], [], [(0, 1, 2, 3)])
    me.uv_layers.new(name="UVMap")
    for li, uv in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        me.uv_layers[0].data[li].uv = uv
    m, nt, b = _nodes(name + "_mat")
    import os
    for key, target in (("Color", "Base Color"), ("Opacity", "Alpha")):
        img = _n(nt, "ShaderNodeTexImage")
        img.image = bpy.data.images.load(os.path.abspath(f"assets/cc0/Leaf001/Leaf001_1K-JPG_{key}.jpg"), check_existing=True)
        if key == "Opacity":
            img.image.colorspace_settings.name = "Non-Color"
            nt.links.new(img.outputs["Color"], b.inputs[target])
        else:
            mul = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
            mul.inputs["Factor"].default_value = 1.0
            mul.inputs["B"].default_value = (*_lin(tint), 1)
            nt.links.new(img.outputs["Color"], mul.inputs["A"])
            nt.links.new(mul.outputs["Result"], b.inputs[target])
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Subsurface Weight"].default_value = 0.2
    me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    return o


def foliate(emitter, card, count, size=1.0):
    """Cover an emitter (hidden blob canopy) with leaf cards."""
    mod = emitter.modifiers.new("leaves", "PARTICLE_SYSTEM")
    st = mod.particle_system.settings
    st.type, st.count = "HAIR", count
    st.use_advanced_hair = True
    st.hair_length = 1.0
    st.render_type, st.instance_object = "OBJECT", card
    st.particle_size, st.size_random = size, 0.5
    st.use_rotations, st.rotation_mode = True, "NOR"
    st.rotation_factor_random, st.phase_factor_random = 0.6, 2.0
    st.distribution = "RAND"
    emitter.show_instancer_for_render = False


def real_trees(oaks, palms):
    """Give the hero oaks real leaves and Spanish moss, palms bark, shrubs leaves."""
    import os
    holder = bpy.data.collections.new("leaf_cards")  # cards must exist but not render on their own
    oak_leaf = leaf_card("oak_leaf_card", 1.4, 0.9, (150, 175, 120))
    shrub_leaf = leaf_card("shrub_leaf_card", 0.9, 0.6, (160, 190, 120))
    for c in (oak_leaf, shrub_leaf):
        holder.objects.link(c)
    bark = photo("photo_bark", "Bark014", 6, tint=(140, 126, 110), bump=1.0)[0]
    moss = mat_simple("spanish_moss", (128, 134, 118), 0.9)
    for coll in oaks:
        rng = random.Random(coll.name)
        for o in list(coll.objects):
            if "leaves" in o.name:
                foliate(o, oak_leaf, 14000, 1.0)
            elif "trunk" in o.name:
                o.data.materials[0] = bark
                bm = bmesh.new()  # Spanish moss hanging from the limbs
                for _ in range(260):  # wispy, irregular strands in clusters
                    x, y = rng.uniform(-16, 16), rng.uniform(-16, 16)
                    if x * x + y * y > 17 ** 2:
                        continue
                    for _ in range(rng.randint(2, 5)):
                        L = rng.uniform(1.5, 6)
                        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=3, radius1=0.015, radius2=rng.uniform(0.08, 0.2), depth=L)
                        lean = (rng.uniform(-0.25, 0.25), rng.uniform(-0.25, 0.25))
                        for v in res["verts"]:  # strands sway and taper irregularly
                            t = (v.co.z + L / 2) / L
                            v.co.x += lean[0] * (1 - t) * L
                            v.co.y += lean[1] * (1 - t) * L
                        bmesh.ops.translate(bm, vec=(x + rng.uniform(-1, 1), y + rng.uniform(-1, 1), rng.uniform(13, 18) - L / 2), verts=res["verts"])
                me = bpy.data.meshes.new("moss")
                bm.to_mesh(me)
                bm.free()
                me.materials.append(moss)
                coll.objects.link(bpy.data.objects.new("moss", me))
    for coll in palms:
        for o in coll.objects:
            if o.data.materials and o.data.materials[0].name.startswith("palm_trunk"):
                o.data.materials[0] = bark
    for name in ("hedge", "shrub_pink", "shrub_green", "shrub_white"):
        c = _SHRUBS.get(name)
        if c:
            for o in c.objects:
                foliate(o, shrub_leaf, 700, 0.9)
    _ = os
