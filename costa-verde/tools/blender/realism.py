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
            "pole": mat_simple("real_pole", (80, 82, 84), 0.45, 0.7), "solar": mat_solar(), "shopglass": mat_clear_glass(),
            "mirror": mat_simple("real_mirror", (230, 232, 234), 0.02, 1.0), "floor": mat_simple("real_floor", (0, 0, 0), 0.3, vertex=True),
            "fabric": mat_simple("real_fabric", (0, 0, 0), 0.8, vertex=True), "lamp": mat_simple("real_lamp", (255, 240, 210), 0.3, emit=(1, 0.85, 0.6))}
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




# Smooth cars: lofted rounded cross-sections + subdivision, cabin as its own loft (glass between pillars),
# wheel arches cut by a boolean. Dimensions in studs (~3 per metre). x along the car (+x = front).
# ---------------------------------------------------------------- cars
# Original designs (no real model copied), each built from the measured proportions of its class.
# Body = one continuous lofted shell: every station ring runs rocker -> door bulge -> shoulder -> beltline ->
# greenhouse -> roof; where there is no cabin the upper points fold down onto a crowned hood / trunk lid, so
# hood, windscreen, roof, rear glass and trunk are one smooth surface. Studs at ~3 per metre; x: rear -> front.

def _car(L_mm, W_mm, H_mm, WB_mm, wheel_mm, clear_mm, top, belt, wb_centre=0.5, extras=()):
    k = 0.003
    return dict(L=L_mm * k, W=W_mm * k, H=H_mm * k, wb=WB_mm * k / 2, wr=wheel_mm * k / 2, clear=clear_mm * k,
                top=top, belt=belt, wbc=wb_centre, extras=set(extras))


# side profiles: (fraction of length from the tail, fraction of height); class proportions from 2025-26 spec data
CAR_SPECS = {
    "sedan": _car(4915, 1840, 1445, 2825, 690, 140,
                  [(0, .42), (.02, .56), (.09, .66), (.17, .69), (.29, .93), (.38, 1), (.55, 1), (.65, .91), (.735, .7), (.9, .64), (.97, .56), (1, .4)],
                  .66, .5, ["sunroof", "fin"]),
    "suv": _car(4650, 1860, 1690, 2700, 740, 210,
                [(0, .4), (.015, .62), (.045, .93), (.1, 1), (.58, 1), (.665, .9), (.77, .67), (.93, .61), (.985, .52), (1, .38)],
                .64, .49, ["rails", "clad", "fin"]),
    "ev": _car(4750, 1920, 1624, 2890, 760, 160,
               [(0, .42), (.03, .63), (.13, .85), (.3, 1), (.56, 1), (.685, .86), (.785, .6), (.94, .55), (1, .42)],
               .63, .5, ["flush", "fin"]),
    "van": _car(5170, 1995, 1740, 3060, 720, 160,
                [(0, .4), (.012, .94), (.045, 1), (.66, 1), (.745, .84), (.845, .59), (.955, .54), (1, .4)],
                .6, .48, ["fin"]),
    "pickup": _car(5884, 2030, 1995, 3694, 820, 240,
                   [(.36, .62), (.375, 1), (.57, 1), (.625, .92), (.69, .7), (.95, .69), (.99, .6), (1, .43)],
                   .62, .44, ["clad", "bed", "truckgrille"]),
}


def _interp(pts, t):
    for (a, za), (b, zb) in zip(pts, pts[1:]):
        if a <= t <= b:
            f = (t - a) / max(b - a, 1e-6)
            f = f * f * (3 - 2 * f)  # smooth between control points
            return za + (zb - za) * f
    return pts[-1][1] if t > pts[-1][0] else pts[0][1]


def _car_mesh(kind):
    sp = CAR_SPECS[kind]
    L, W, H, clear = sp["L"], sp["W"], sp["H"], sp["clear"]
    t0 = sp["top"][0][0]
    belt = sp["belt"] * H
    N = 44
    bm = bmesh.new()
    rings, gh_list, xs = [], [], []
    for i in range(N + 1):
        t = t0 + (1 - t0) * i / N
        x = -L / 2 + L * t
        ztop = _interp(sp["top"], t) * H
        gh = max(0.0, min(1.0, (ztop - belt) / max(H - belt, 1e-6)))  # 1 = full-height greenhouse here
        end = max(0.0, 1 - (abs(t - 0.5) / 0.5) ** 6) ** 0.5  # plan view: corners taper in toward nose / tail
        hw = W / 2 * (0.8 + 0.2 * end)
        off = sp["L"] * (sp["wbc"] - 0.5)
        for ax in (-sp["wb"] + off, sp["wb"] + off):  # fenders swell out over each wheel
            hw += 0.12 * math.exp(-((x - ax) / (sp["wr"] * 1.4)) ** 2)
        lo = clear + 0.3
        bz = min(belt, ztop - 0.25)  # shoulder never above the hood / trunk edge, or the surface folds over itself
        half = [  # (y, z) from bottom centre up to roof centre
            (0.0, lo), (hw - 0.5, lo), (hw - 0.08, lo + 0.5), (hw, lo + (bz - lo) * 0.42),  # rocker, door bulge
            (hw - 0.05, bz - 0.4 * (bz - lo) / max(belt - lo, 1e-6)), (hw - 0.16, bz - 0.05),  # soft shoulder, beltline
        ]
        if gh > 0.02:  # greenhouse: glass tucks inward (tumblehome) up to the roof
            z_top = ztop
            half += [(hw * (0.92 - 0.06 * gh), belt + 0.1), (hw * (0.92 - 0.2 * gh), belt + (z_top - belt) * 0.8),
                     (hw * (0.86 - 0.3 * gh), z_top - 0.05), (0.0, z_top + 0.05)]
        else:  # hood / trunk lid: a gently crowned panel rising from the shoulder (always above it)
            half += [(hw * 0.9, max(ztop - 0.06, bz + 0.05)), (hw * 0.66, max(ztop + 0.02, bz + 0.1)),
                     (hw * 0.34, max(ztop + 0.07, bz + 0.14)), (0.0, max(ztop + 0.09, bz + 0.16))]
        ring = [(-y, z) for y, z in half[::-1][:-1]] + half[1:]  # mirror into a full loop (centre points shared)
        edge = min(t - t0, 1 - t) / max(1 - t0, 1e-6)  # 0 at the very nose / tail
        if edge < 0.06:  # round the fascia in side view: pull the end rings in toward their centre
            k = 0.9 + 0.1 * (edge / 0.06) ** 0.6
            zc = (lo + ztop) / 2
            ring = [(y * (k * 0.97), zc + (z - zc) * k) for y, z in ring]
        rings.append([bm.verts.new((x, y, z)) for y, z in ring])
        gh_list.append(gh)
        xs.append(t)
    n = len(rings[0])
    nh = len(half)
    glass_rows = set()
    for side in (0, 1):  # ring indices of the glass band (belt+ -> glass top) on each side
        for j in (6, 7):
            glass_rows.add(nh - 1 - j if side == 0 else nh - 2 + j - 0)
    cab = [i for i, g in enumerate(gh_list) if g > 0.6]
    pill = set()
    if cab:
        c0, c1 = cab[0], cab[-1]
        pill = {c0, c0 + 1, c1 - 1, c1, (c0 + c1) // 2}  # C, A and B pillars
    for i in range(N):
        g = min(gh_list[i], gh_list[i + 1])
        for j in range(n - 1):
            f = bm.faces.new((rings[i][j], rings[i][j + 1], rings[i + 1][j + 1], rings[i + 1][j]))
            upper = j >= nh - 2 + 5 or j <= nh - 1 - 6  # rows above the beltline (either side)
            top_rows = (nh - 2 + 7 <= j <= nh - 2 + 8) or (nh - 1 - 9 <= j <= nh - 1 - 8)
            if upper and 0.15 < g < 0.98 and (top_rows or j in glass_rows):  # windscreen / rear window
                f.material_index = 1
            elif j in glass_rows and g >= 0.98 and i not in pill:  # side windows
                f.material_index = 1
            elif j in glass_rows and g >= 0.6:
                f.material_index = 2  # blacked-out pillars
            else:
                f.material_index = 0
    for r, rev in ((rings[0], True), (rings[-1], False)):
        f = bm.faces.new(r[::-1] if rev else r)
        f.material_index = 0
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _car_parts(kind, coll, mats):
    """Lights, grille, intakes, bumpers, mirrors on stalks, wipers, handles, skirts, exhausts, badges, roof parts, bed,
    and wheels: tyre sidewalls, multi-spoke rims, brake discs and calipers."""
    from mathutils import Matrix
    sp = CAR_SPECS[kind]
    L, W, H, wb, wr, clear = sp["L"], sp["W"], sp["H"], sp["wb"], sp["wr"], sp["clear"]
    ex = sp["extras"]
    bm = bmesh.new()
    zt = lambda t: _interp(sp["top"], t) * H  # noqa: E731
    h = L / 2
    hood_z, tail_z = zt(0.995), zt(0.01 if kind != "pickup" else 0.36)
    nose_z = 0.9 * zt(0.985) + 0.1 * (clear + 0.3)  # top of the rounded fascia
    for cx in (-wb + L * (sp["wbc"] - 0.5), wb + L * (sp["wbc"] - 0.5)):
        for side in (-1, 1):
            yo = side * (W / 2 - 0.55)
            _cyl(bm, (cx, yo, wr), wr, wr, 1.05, 32, 0, "Y")  # tyre
            _cyl(bm, (cx, side * (W / 2 - 0.04), wr), wr * 0.74, wr * 0.74, 0.04, 28, 1, "Y")  # rim face, flush with the tyre
            _cyl(bm, (cx, side * (W / 2 - 0.22), wr), wr * 0.58, wr * 0.58, 0.1, 24, 7, "Y")  # brake disc behind the spokes
            _cube(bm, (cx + wr * 0.3, side * (W / 2 - 0.3), wr + wr * 0.35), (wr * 0.35, 0.3, wr * 0.25), 8)  # caliper
            for k in range(10):  # ten slim spokes (five pairs)
                a = 2 * math.pi * (k // 2) / 5 + (0.12 if k % 2 else -0.12)
                vs = _cube(bm, (cx, side * (W / 2 - 0.0), wr), (wr * 1.4, 0.05, wr * 0.08), 1)
                bmesh.ops.rotate(bm, verts=vs, cent=(cx, 0, wr), matrix=Matrix.Rotation(a, 3, "Y"))
            _cyl(bm, (cx, side * (W / 2 + 0.02), wr), wr * 0.16, wr * 0.16, 0.08, 16, 6, "Y")  # hub with chrome cap
    for side in (-1, 1):
        # headlight cluster: slim, swept back along the fender; DRL strip above
        _cube(bm, (h - 0.02, side * W * 0.24, nose_z - 0.35), (0.14, W * 0.14, 0.24), 2)  # headlight cluster on the fascia
        _cube(bm, (h - 0.01, side * W * 0.22, nose_z - 0.18), (0.12, W * 0.18, 0.05), 2)  # LED strip
        _cube(bm, (h - 0.03, side * W * 0.26, clear + 0.95), (0.12, 0.32, 0.12), 4)  # fog-lamp bezel
        _cube(bm, (h + 0.02, side * W * 0.26, clear + 0.95), (0.05, 0.22, 0.07), 2)  # fog lamp
        _cube(bm, (L * 0.28, side * (W / 2 + 0.06), sp["belt"] * H - 0.25), (0.45, 0.05, 0.1), 3)  # side indicator
        # tail lamps wrapping the corners
        _cube(bm, (-h + 0.02, side * W * 0.25, tail_z - 0.5), (0.14, W * 0.14, 0.28), 3)
        # mirror on a stalk at the base of the A-pillar
        cab_front = next(t for t in [i / 200 for i in range(200, -1, -1)] if zt(t) > sp["belt"] * H + 0.4) * L - h
        _cube(bm, (cab_front - 0.55, side * (W / 2 * 0.9 + 0.15), sp["belt"] * H + 0.1), (0.2, 0.32, 0.1), 4)  # stalk
        mv = _cube(bm, (cab_front - 0.6, side * (W / 2 * 0.9 + 0.45), sp["belt"] * H + 0.32), (0.32, 0.42, 0.34), 5)  # housing
        bmesh.ops.rotate(bm, verts=mv, cent=(cab_front - 0.6, side * (W / 2 * 0.9 + 0.45), sp["belt"] * H + 0.32), matrix=Matrix.Rotation(-0.25 * side, 3, "Z"))
        for xd in (0.12, 0.45):  # door handles
            _cube(bm, (cab_front - 1.5 - xd * L * 0.35, side * (W / 2 + 0.02), sp["belt"] * H - 0.45), (0.8, 0.05, 0.13),
                  4 if "flush" in ex else 6)
        _cube(bm, (0, side * (W / 2 * 0.9), clear + 0.62), (L * 0.5, 0.2, 0.32), 4 if "clad" in ex else 0)  # side skirt on the sill
        if kind != "ev":
            _cyl(bm, (-h - 0.05, side * W * 0.28, clear + 0.45), 0.2, 0.2, 0.4, 12, 6, "X")  # exhaust tips
    if "flush" not in ex:  # grille: frame + dark mesh, lower intake
        gw = W * (0.66 if "truckgrille" in ex else 0.46)
        gh = 1.2 if "truckgrille" in ex else 0.6
        gh = min(gh, (nose_z - clear - 0.3) * 0.42)
        gz = nose_z - 0.35 - gh / 2 - 0.25
        _cube(bm, (h - 0.03, 0, gz), (0.14, gw, gh), 6 if "truckgrille" in ex else 4)
        for k in range(int(gw / 0.35)):
            _cube(bm, (h + 0.03, -gw / 2 + 0.17 + k * 0.35, gz), (0.06, 0.06, gh * 0.9), 4)
    else:
        _cube(bm, (h - 0.25, 0, hood_z - 0.3), (0.08, W * 0.82, 0.05), 2)  # EV: one light bar across the nose
    _cube(bm, (h - 0.03, 0, clear + 0.75), (0.12, W * 0.48, 0.35), 4)  # lower intake
    _cube(bm, (h - 0.05, 0, clear + 1.3), (0.05, 1.3, 0.45), 6)  # front plate
    _cube(bm, (-h + 0.25, 0, tail_z - 0.5), (0.1, W * 0.84, 0.08), 3)  # full-width tail light bar
    _cube(bm, (-h + 0.2, 0, clear + 0.55), (0.25, W * 0.6, 0.3), 4)  # rear diffuser
    _cube(bm, (-h + 0.06, 0, tail_z - 1.15), (0.05, 1.3, 0.55), 6)  # plate
    _cube(bm, (h + 0.0, 0, hood_z - 0.6), (0.06, 0.55, 0.22), 6)  # badge
    wind = next(t for t in [i / 200 for i in range(200, -1, -1)] if zt(t) > sp["belt"] * H + 0.15) * L - h
    for k in (-1, 1):  # wipers at the base of the windscreen
        vs = _cube(bm, (wind + 0.2, k * W * 0.2, sp["belt"] * H + 0.2), (0.12, W * 0.34, 0.06), 4)
        bmesh.ops.rotate(bm, verts=vs, cent=(wind + 0.2, k * W * 0.2, sp["belt"] * H + 0.2), matrix=Matrix.Rotation(0.25 * k, 3, "Z"))
    cab_ts = [i / 200 for i in range(201) if zt(i / 200) > sp["belt"] * H + 0.4]
    if cab_ts:
        c0, c1 = cab_ts[0] * L - h, cab_ts[-1] * L - h
        for side in (-1, 1):
            y = side * (W / 2 + 0.015)
            _cube(bm, ((c0 + c1) / 2, side * (W / 2 * 0.93), sp["belt"] * H + 0.02), (c1 - c0 - 0.6, 0.1, 0.07), 6)  # chrome belt trim
            off = L * (sp["wbc"] - 0.5)
            ra, fa = -wb + off + wr + 0.5, wb + off - wr - 0.5  # between the arches
            for xd in (c1 - 0.3, (c0 + c1) / 2, c0 + 0.6 if kind not in ("pickup",) else (c0 + c1) / 2 - 2.6):  # door shut lines
                if ra < xd < fa:
                    _cube(bm, (xd, y, (clear + 0.9 + sp["belt"] * H) / 2), (0.05, 0.03, sp["belt"] * H - clear - 1.0), 4)
            _cube(bm, ((ra + fa) / 2, y, clear + 0.95), (fa - ra, 0.03, 0.05), 4)  # sill line
    if "rails" in ex:
        for side in (-1, 1):
            _cube(bm, (-L * 0.08, side * W * 0.3, H - 0.06), (L * 0.42, 0.15, 0.15), 4)
    if "fin" in ex:
        _cube(bm, (-L * 0.2, 0, H + 0.12), (0.7, 0.12, 0.25), 4)  # shark-fin antenna
    if "sunroof" in ex:
        _cube(bm, (L * 0.02, 0, H + 0.07), (L * 0.14, W * 0.34, 0.02), 9)
    if "bed" in ex:  # open bed: floor, side walls with caps, tailgate
        x0, x1 = -h, -h + L * 0.355
        top = sp["belt"] * H
        _cube(bm, ((x0 + x1) / 2, 0, clear + 1.0), (x1 - x0, W * 0.9, 0.4), 4)
        for side in (-1, 1):
            _cube(bm, ((x0 + x1) / 2, side * W * 0.445, (clear + 0.3 + top) / 2), (x1 - x0, 0.32, top - clear - 0.3), 5)
            _cube(bm, ((x0 + x1) / 2, side * W * 0.445, top + 0.04), (x1 - x0, 0.4, 0.08), 4)
        _cube(bm, (x0 + 0.18, 0, (clear + 0.3 + top) / 2), (0.36, W * 0.9, top - clear - 0.3), 5)
    o = _obj(coll.name + "_parts", bm, [mats["tyre"], mats["rim"], mats["head"], mats["tail"], mats["plastic"], mats["paint"],
                                        mats["chrome"], mats["disc"], mats["caliper"], mats["glass"]], coll)
    bev = o.modifiers.new("soft", "BEVEL")  # rounded tyre shoulders and softened trim edges
    bev.width, bev.segments, bev.limit_method = 0.1, 2, "ANGLE"
    return o


CAR_COLOURS = [((236, 236, 232), 25), ((24, 24, 26), 20), ((128, 130, 132), 16), ((190, 192, 194), 14), ((40, 66, 120), 10),
               ((150, 30, 28), 10), ((60, 70, 60), 3), ((200, 170, 120), 2)]


def car_models():
    """Five original cars from real class proportions: midsize sedan, compact crossover, EV crossover, minivan, pickup."""
    glass = mat_glass()
    base = {"tyre": mat_simple("tyre", (24, 24, 24), 0.8), "rim": mat_simple("rim", (186, 188, 192), 0.22, 0.95),
            "plastic": mat_simple("trim_plastic", (24, 24, 26), 0.55), "chrome": mat_simple("chrome", (220, 222, 226), 0.08, 1.0),
            "head": mat_simple("headlight", (245, 245, 240), 0.05, emit=(0.8, 0.82, 0.85)), "tail": mat_simple("taillight", (170, 15, 18), 0.15),
            "disc": mat_simple("brake_disc", (110, 106, 100), 0.45, 0.9), "caliper": mat_simple("caliper", (170, 30, 30), 0.4), "glass": glass}
    models = []
    rng = random.Random(4)
    for kind in CAR_SPECS:
        sp = CAR_SPECS[kind]
        for v in range(3):
            col = rng.choices([c for c, _ in CAR_COLOURS], [w for _, w in CAR_COLOURS])[0]
            paint = mat_simple(f"paint_{kind}{v}", col, 0.15, 0.55)
            paint.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 1.0
            coll = _collection(f"car_{kind}_{v}")
            body = _obj(f"car_{kind}_{v}", _car_mesh(kind), [paint, glass, base["plastic"]], coll)
            sub = body.modifiers.new("smooth", "SUBSURF")
            sub.levels, sub.render_levels = 1, 2
            cut = bmesh.new()  # wheel-arch cutters (hidden), applied as a boolean
            off = sp["L"] * (sp["wbc"] - 0.5)
            for cx in (-sp["wb"] + off, sp["wb"] + off):
                _cyl(cut, (cx, 0, sp["wr"]), sp["wr"] + 0.28, sp["wr"] + 0.28, sp["W"] + 2, 32, 0, "Y")
            cutter = _obj(f"car_{kind}_{v}_arches", cut, [], coll)
            cutter.hide_render = True
            cutter.display_type = "WIRE"
            bo = body.modifiers.new("arches", "BOOLEAN")
            bo.operation, bo.object, bo.solver = "DIFFERENCE", cutter, "EXACT"
            bo.use_self, bo.use_hole_tolerant = True, True
            _car_parts(kind, coll, dict(base, paint=paint))
            models.append(coll)
    return models


def mat_frond(name, base, tip):
    """Palm leaflet: darker at the base, lighter yellow-green toward the tip (UV v), translucent."""
    m, nt, b = _nodes(name)
    uv = _n(nt, "ShaderNodeUVMap")
    sep = _n(nt, "ShaderNodeSeparateXYZ")
    nt.links.new(uv.outputs["UV"], sep.inputs["Vector"])
    c = _mix(nt, _lin(base), _lin(tip), sep.outputs["Y"])
    noise = _n(nt, "ShaderNodeTexNoise", Scale=3.0, Detail=4.0)
    nt.links.new(_coords(nt), noise.inputs["Vector"])
    c = _mix(nt, c, tuple(x * 0.7 for x in _lin(base)), _rng(nt, noise.outputs["Fac"], 0.4, 0.7, 0, 0.5))
    nt.links.new(c, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.45
    b.inputs["Subsurface Weight"].default_value = 0.25
    return m


def hero_palm(seed, dwarf=False):
    """Coconut palm (or a short areca clump stem when dwarf): ringed curving trunk, frond boots, ~16 fronds of
    dense curved leaflets drooping to the tips, coconuts, hanging dead fronds."""
    from mathutils import Matrix
    rng = random.Random(seed)
    coll = _collection(f"hero_palm_{seed}")
    trunk_m = mat_simple(f"palm_trunk{seed}", (126, 108, 88), 0.9)
    leaf_m = mat_frond(f"palm_leaf{seed}", (40, 64, 22), (120, 150, 60))
    dead_m = mat_frond(f"palm_dead{seed}", (110, 86, 50), (170, 140, 90))
    nut_m = mat_simple(f"coconut{seed}", (96, 84, 40), 0.7)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    H = rng.uniform(6, 10) if dwarf else rng.uniform(34, 44)
    lean = rng.uniform(0.5, 1.5) if dwarf else rng.uniform(4, 10)
    segs = 10 if dwarf else 40
    rr = 0.35 if dwarf else 1.15
    for i in range(segs):
        t0, t1 = i / segs, (i + 1) / segs
        p0, p1 = Vector((lean * t0 ** 1.6, 0, H * t0)), Vector((lean * t1 ** 1.6, 0, H * t1))
        r = rr * (1 - 0.35 * t0) * (1 + rng.uniform(-0.015, 0.03))  # subtle, irregular leaf-scar rings
        d = p1 - p0
        rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=r, radius2=r * 0.97, depth=d.length, matrix=Matrix.Translation((p0 + p1) / 2) @ rot)
        for f in {f for v in res["verts"] for f in v.link_faces}:
            f.material_index = 0
    top = Vector((lean, 0, H))
    res = bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=rr * 1.25, radius2=rr * 0.9, depth=rr * 2.2, matrix=Matrix.Translation(top - Vector((0, 0, rr))))
    for f in {f for v in res["verts"] for f in v.link_faces}:  # frond boots
        f.material_index = 2
    nfr = 14 if dwarf else 17
    scale = 0.45 if dwarf else 1.0
    for k in range(nfr):
        a = 2 * math.pi * k / nfr + rng.uniform(-0.15, 0.15)
        dead = (not dwarf) and k < 3 and rng.random() < 0.8
        up = rng.uniform(0.3, 0.9) if not dead else -0.9
        length = rng.uniform(13, 17) * scale * (0.85 if dead else 1)
        pts = []
        for j in range(25):  # rachis arcs up then droops
            t = j / 24
            r = length * t
            z = r * up - (r ** 2) * (0.05 / scale) - (length * 0.5 * t if dead else 0)
            pts.append(top + Vector((math.cos(a) * r * (0.6 if dead else 1), math.sin(a) * r * (0.6 if dead else 1), z)))
        side = Vector((-math.sin(a), math.cos(a), 0))
        mi = 2 if dead else 1
        for j in range(2, 24):
            t = j / 24
            ll = (3.6 * math.sin(math.pi * min(1, t * 1.02)) + 0.4) * scale
            base, dirv = pts[j], (pts[j + 1] - pts[j - 1]).normalized()
            for s in (-1, 1):
                droop = rng.uniform(0.5, 0.9)
                w = 0.28 * scale
                prev = None
                for q in range(4):  # leaflet: 3 curved segments, tapering, sagging toward the tip
                    u = q / 3
                    c = base + side * s * ll * 0.85 * u + dirv * ll * 0.35 * u + Vector((0, 0, -ll * droop * u * u))
                    half = w * (1 - 0.8 * u) + 0.02
                    pa, pb = bm.verts.new(c - dirv * half), bm.verts.new(c + dirv * half)
                    if prev:
                        f = bm.faces.new((prev[0], prev[1], pb, pa))
                        f.material_index = mi
                        for lp, (uu, vv) in zip(f.loops, ((0, (q - 1) / 3), (1, (q - 1) / 3), (1, u), (0, u))):
                            lp[uvl].uv = (uu, vv)
                    prev = (pa, pb)
    if not dwarf:
        for _ in range(rng.randint(3, 7)):
            a = rng.uniform(0, 2 * math.pi)
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.75)
            bmesh.ops.translate(bm, vec=top + Vector((math.cos(a) * 1.1, math.sin(a) * 1.1, -1.4)), verts=res["verts"])
            for f in {f for v in res["verts"] for f in v.link_faces}:
                f.material_index = 3
    _obj(f"hero_palm_{seed}", bm, [trunk_m, leaf_m, dead_m, nut_m], coll)
    return coll


def areca_clump(seed):
    """Clumping areca palm: several short leaning stems with feathery fronds (common Florida yard plant)."""
    rng = random.Random(seed)
    coll = _collection(f"areca_{seed}")
    for k in range(rng.randint(3, 5)):
        sub = hero_palm(seed * 10 + k, dwarf=True)
        for o in list(sub.objects):
            sub.objects.unlink(o)
            o.location = (rng.uniform(-1.2, 1.2), rng.uniform(-1.2, 1.2), 0)
            o.rotation_euler = (rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), rng.uniform(0, 6.28))
            coll.objects.link(o)
        bpy.data.collections.remove(sub)
    return coll


def plant_beds(beds, gy, rng, keep_clear=None):
    """Fill mulch beds and lot-edge strips with shrubs, flowering bushes and areca clumps every few studs."""
    kinds = [shrubs_by_name(n) for n in ("shrub_green", "shrub_pink", "shrub_white", "hedge")]
    kinds += list(PLANTS.values()) if PLANTS else []
    arecas = [areca_clump(900 + k) for k in range(3)]
    geoms = beds.geoms if hasattr(beds, "geoms") else [beds]
    n = 0
    for g in geoms:
        if g.is_empty or g.area < 4:
            continue
        line = g.buffer(-1.0).boundary if not g.buffer(-1.0).is_empty else g.boundary
        L = line.length
        t = rng.uniform(0, 3)
        while t < L:
            p = line.interpolate(t)
            if keep_clear is not None and keep_clear.contains(p):  # storefront side: leave it open
                t += 3
                continue
            if rng.random() < 0.05:
                place(rng.choice(arecas), p.x, p.y, gy + 0.2, rng.uniform(0, 6.28), rng.uniform(0.8, 1.2))
            else:
                place(rng.choice(kinds), p.x, p.y, gy + 0.1, rng.uniform(0, 6.28), rng.uniform(0.6, 1.15))
            n += 1
            t += rng.uniform(6, 11)
    return n


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


LAMPS = []  # street-light heads (x, z, y) for the night presets
HERO_SPOTS = {}  # park paths and paved lots, for the hero cameras
COBRA = []


def cobra_model():
    coll = _collection("cobra_light")
    bm = bmesh.new()
    _cube(bm, (3.2, 0, 0), (6.6, 0.35, 0.35), 0)  # arm
    _cube(bm, (6.6, 0, -0.35), (1.8, 0.9, 0.5), 0)  # head
    _cube(bm, (6.6, 0, -0.62), (1.4, 0.7, 0.05), 1)  # lens
    _obj("cobra_light", bm, [mat_simple("cobra_body", (150, 152, 150), 0.4, 0.6), mat_simple("cobra_lens", (255, 230, 190), 0.2, emit=(1.0, 0.8, 0.55))], coll)
    return coll


def street_life(roads, asphalt, junctions, buildings, zone, gy, rng, no_cars=None):
    """Parked cars, utility poles with wires and street lights, hydrants, stop signs, trash cans, mailboxes."""
    cars, props = car_models(), prop_models()
    cars = [c for c in cars if not c.name.startswith("car_sedan")]  # best of the generated set until the imported models arrive
    COBRA.append(cobra_model())
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
        while t < L - 8 and r is not no_cars:  # parked cars along both curbs, clear of junctions (none on the camera's street)
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
                if True:  # cobra-head street light on each pole, arm over the road
                    place(COBRA[0], x, z, gy + 27, math.atan2(nz, -nx))
                    LAMPS.append((x - nx * 6.5, z - nz * 6.5, gy + 26.4))
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
PLANTS = {}


def shrubs_by_name(name):
    if not _SHRUBS:
        for c in shrub_models():
            _SHRUBS[c.name] = c
    return _SHRUBS[name]


def grass(terrain_obj, zone, lawn, density=340000):
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
    st.type, st.count, st.hair_length = "HAIR", density, 1.4
    st.use_advanced_hair = True
    st.factor_random = 0.12  # mostly upright blades, a little lean
    st.brownian_factor = 0.02
    try:
        st.root_radius, st.tip_radius = 0.035, 0.0
        st.radius_scale = 1.0
    except AttributeError:
        pass
    st.render_type = "PATH"
    st.child_type = "INTERPOLATED"  # dense turf: 6 children per guide strand
    st.rendered_child_count, st.child_percent = 6, 6
    st.child_radius, st.child_length, st.child_length_threshold = 0.6, 0.85, 0.3
    blade, nt, b = _nodes("grass_blades")
    hi = _n(nt, "ShaderNodeHairInfo")
    shade = _mix(nt, _lin((62, 104, 50)), _lin((150, 150, 80)), _rng(nt, hi.outputs["Random"], 0.7, 1.0, 0, 1))  # a few dry blades
    shade = _mix(nt, shade, _lin((44, 80, 36)), _rng(nt, hi.outputs["Random"], 0.0, 0.35, 0.6, 0))  # and darker ones
    tip = _mix(nt, tuple(x * 0.35 for x in _lin((60, 90, 40))), shade, _rng(nt, hi.outputs["Intercept"], 0, 0.6, 0, 1))  # dark at the root
    nt.links.new(tip, b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.6
    b.inputs["Subsurface Weight"].default_value = 0.2
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
    for tf, z, width, rng, text in items:
        cu = bpy.data.curves.new("sign", "FONT")
        cu.body = text or rng.choice(SHOP_NAMES)
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
    photo_grass = cc0(nt, "Grass004", 6)["Color"]
    src2 = _mix(nt, src, photo_grass, _rng(nt, n1.outputs["Fac"], 0, 1, 0.75, 0.75), "MULTIPLY")
    c = _mix(nt, src2, (0.2, 0.17, 0.08), _rng(nt, n1.outputs["Fac"], 0.5, 0.68, 0, 0.55))
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
    lit = _rng(nt, sep.outputs["Blue"], 0.86, 0.87, 0, 1.2)  # a few lit rooms (time presets change this)
    lit.node.name = "lit_rooms"
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
    swaps = {"real_wall": walls, "real_roof": roof, "real_concrete": conc, "real_asphalt": asph, "real_glass": mat_window_glass(),
             "real_roof_flat": gravel_roof}
    for o in bpy.data.objects:
        if o.type == "MESH":
            for i, mt in enumerate(o.data.materials):
                if mt and mt.name in swaps:
                    o.data.materials[i] = swaps[mt.name]
    return {"grass": "Grass004", "gravel": "Gravel043", "mulch": "Ground037", "bark": "Bark014", "leaf": "Leaf001", "wood": "WoodSiding011"}


# ---------------------------------------------------------------- land cover, trees with real leaves

def landcover(detailed, street_area, zone, gy, rng, palms, oaks, ground=None):
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
                place(rng.choice(oaks + palms), x, z, (ground(x, z) if ground else gy) - 0.4, rng.uniform(0, 6.28), rng.uniform(0.8, 1.15))
    asph = bpy.data.materials.get("photo_asphalt") or mat_asphalt()
    _slab("lots", unary_union(paved), gy - 0.5, gy + 0.32, asph)
    _slab("stalls", unary_union(stalls).intersection(unary_union(paved)), gy + 0.32, gy + 0.36, mat_paint("stall_paint", (236, 236, 230)))
    _slab("mulch", unary_union(mulch), gy - 0.5, gy + 0.18, photo("photo_mulch", "Ground037", 6, tint=(120, 84, 60))[0])
    _slab("dirt", unary_union(dirt), gy - 0.5, gy + 0.08, photo("photo_dirt", "Ground037", 10, tint=(190, 170, 140))[0])
    # park footpath flush with the lawn (a few hundredths above the soil, below the grass blades)
    pmat = bpy.data.materials.get("photo_concrete") or mat_concrete()
    for k, pth in enumerate(paths):  # each path at the real ground height along it
        pts = list(pth.exterior.coords) if hasattr(pth, "exterior") else [c for g in pth.geoms for c in g.exterior.coords]
        hs = [ground(x, z) for x, z in pts] if ground else [gy]
        top = sum(hs) / len(hs) + 0.15  # average ground: flush within the lawn's small bumps
        _slab(f"path{k}", pth, top - 1.2, top, pmat)
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
    HERO_SPOTS["paths"], HERO_SPOTS["paved"] = paths, paved
    return unary_union(lawn), unary_union(mulch), fences


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
                foliate(o, shrub_leaf, 260, 1.1)
    for c in PLANTS.values():  # new species: leaves over the flower-speckled body, which shows through the gaps
        for o in c.objects:
            foliate(o, shrub_leaf, 320, 1.2)
            o.show_instancer_for_render = True
    _ = os


def mat_solar():
    """PV panel: dark blue cells in a silver grid, glossy."""
    m, nt, b = _nodes("real_solar")
    grid = _n(nt, "ShaderNodeTexBrick", Scale=0.9, **{"Mortar Size": 0.04})
    nt.links.new(_coords(nt), grid.inputs["Vector"])
    grid.inputs["Color1"].default_value = grid.inputs["Color2"].default_value = (0.01, 0.015, 0.04, 1)
    grid.inputs["Mortar"].default_value = (0.5, 0.5, 0.52, 1)
    nt.links.new(grid.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.06
    b.inputs["Coat Weight"].default_value = 1.0
    return m


# ---------------------------------------------------------------- 5. ground clutter

def _decals(name, polys, y, mat):
    _slab(name, unary_union(polys) if polys else Polygon(), y - 0.02, y, mat)


def clutter(roads, asphalt, walk_outer, zone, gy, rng, wet=False):
    """Manholes, storm drains at the curbs, tyre wear, tar-sealed cracks, puddles, litter, weeds in the cracks,
    fallen palm fronds."""
    clip = sbox(*zone)
    manholes, drains, tyres, tar, puddles = [], [], [], [], []
    for r in roads:
        ax, az, bx, bz, w = r["ax"], r["az"], r["bx"], r["bz"], r["width"]
        L = math.hypot(bx - ax, bz - az)
        if L < 20:
            continue
        ux, uz, nx, nz = (bx - ax) / L, (bz - az) / L, -(bz - az) / L, (bx - ax) / L
        if rng.random() < 0.6:
            t = rng.uniform(0.2, 0.8) * L
            manholes.append(Point(ax + ux * t + nx * rng.uniform(-w / 4, w / 4), az + uz * t + nz * rng.uniform(-w / 4, w / 4)).buffer(1.4, 12))
        for side in (-1, 1):  # storm drain grates at the gutter
            if rng.random() < 0.5:
                t = rng.uniform(0.1, 0.9) * L
                cx, cz = ax + ux * t + nx * (w / 2 - 0.8) * side, az + uz * t + nz * (w / 2 - 0.8) * side
                drains.append(LineString([(cx - ux * 1.6, cz - uz * 1.6), (cx + ux * 1.6, cz + uz * 1.6)]).buffer(0.7, cap_style="flat"))
            for lane in (0.25, 0.75):  # polished tyre tracks in each lane
                o = side * w / 2 * lane
                tyres.append(LineString([(ax + nx * o, az + nz * o), (bx + nx * o, bz + nz * o)]).buffer(0.7, cap_style="flat"))
        for _ in range(rng.randint(0, 3)):  # tar-sealed cracks: wiggly lines
            t0 = rng.uniform(0, L)
            pts = []
            x, z = ax + ux * t0 + nx * rng.uniform(-w / 2, w / 2), az + uz * t0 + nz * rng.uniform(-w / 2, w / 2)
            a = rng.uniform(0, 6.28)
            for _ in range(rng.randint(4, 10)):
                pts.append((x, z))
                a += rng.uniform(-0.8, 0.8)
                x, z = x + math.cos(a) * 2.5, z + math.sin(a) * 2.5
            tar.append(LineString(pts).buffer(0.18))
        for _ in range(3 if wet else 1):
            if rng.random() < (0.9 if wet else 0.35):  # puddles in low spots near the gutters
                t = rng.uniform(0.1, 0.9) * L
                side = rng.choice((-1, 1))
                cx, cz = ax + ux * t + nx * (w / 2 - 3) * side, az + uz * t + nz * (w / 2 - 3) * side
                k = 1.8 if wet else 1.0
                puddles.append(unary_union([Point(cx + rng.uniform(-3, 3) * k, cz + rng.uniform(-1.5, 1.5)).buffer(rng.uniform(1, 2.6) * k, 10) for _ in range(5)]))
    road = asphalt.intersection(clip)
    _decals("manholes", [g.intersection(road) for g in manholes], gy + 0.53, mat_simple("manhole", (52, 50, 46), 0.4, 0.8))
    _decals("drains", drains, gy + 0.53, mat_simple("drain", (20, 20, 20), 0.5, 0.6))
    tyre_m = mat_simple("tyre_wear", (36, 36, 38), 0.82)  # subtle: slightly darker, not shinier
    _ = tyre_m  # shortcut: tyre wear as decals read as painted stripes; needs a blended asphalt-shader mask instead
    _decals("tar_snakes", [g.intersection(road) for g in tar], gy + 0.51, mat_simple("tar", (8, 8, 8), 0.25))
    pud = mat_simple("puddle", (14, 16, 18), 0.0)
    pud.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 1.0
    _decals("puddles", [g.intersection(road) for g in puddles], gy + 0.515, pud)
    # litter and weeds
    litter = []
    for name, size, col in (("cup", (0.5, 0.5, 0.7), (236, 236, 230)), ("can", (0.35, 0.35, 0.6), (190, 40, 40)), ("paper", (1.0, 0.8, 0.05), (220, 216, 200)),
                            ("bag", (1.2, 0.9, 0.4), (40, 40, 44))):
        coll = _collection("litter_" + name)
        bm = bmesh.new()
        _cube(bm, (0, 0, size[2] / 2), size, 0)
        _obj("litter_" + name, bm, [mat_simple("litter_" + name, col, 0.6)], coll)
        litter.append(coll)
    weed = _collection("weed")
    bm = bmesh.new()
    for k in range(9):
        a = k * 0.7
        res = bmesh.ops.create_cone(bm, cap_ends=False, segments=3, radius1=0.12, radius2=0.0, depth=rng.uniform(0.8, 1.8))
        bmesh.ops.rotate(bm, verts=res["verts"], cent=(0, 0, 0), matrix=__import__("mathutils").Matrix.Rotation(0.4, 3, Vector((math.cos(a), math.sin(a), 0))))
        bmesh.ops.translate(bm, vec=(math.cos(a) * 0.3, math.sin(a) * 0.3, 0.5), verts=res["verts"])
    _obj("weed", bm, [mat_foliage("weed_mat", (110, 130, 60), 0.3)], weed)
    walk = walk_outer.difference(asphalt).intersection(clip)
    x0, z0, x1, z1 = walk.bounds
    from shapely.prepared import prep
    pw = prep(walk)
    for _ in range(int(walk.area / 260)):
        x, z = rng.uniform(x0, x1), rng.uniform(z0, z1)
        if pw.contains(Point(x, z)):
            place(rng.choice(litter), x, z, gy + 1.0, rng.uniform(0, 6.28))
    edge = asphalt.intersection(clip).boundary
    t = 0.0
    while t < edge.length:  # weeds where the curb meets the road and the sidewalk joints
        if rng.random() < 0.35:
            p = edge.interpolate(t)
            place(weed, p.x, p.y, gy + 0.5, rng.uniform(0, 6.28), rng.uniform(0.6, 1.3))
        t += 5
    fallen = mat_frond("fallen_frond", (110, 86, 50), (160, 130, 80))
    for o in list(bpy.data.objects):  # fallen fronds under palms
        ic = o.instance_collection
        if ic and ic.name.startswith("hero_palm") and o.type == "EMPTY":
            for _ in range(rng.randint(0, 2)):
                a = rng.uniform(0, 6.28)
                d = rng.uniform(3, 9)
                x, y = o.location.x + math.cos(a) * d, o.location.y + math.sin(a) * d
                L = rng.uniform(6, 11)
                me = bpy.data.meshes.new("frond")
                ca, sa = math.cos(a), math.sin(a)
                me.from_pydata([(x, y, gy + 0.6), (x + ca * L, y + sa * L, gy + 0.6), (x + ca * L - sa * 1.6, y + sa * L + ca * 1.6, gy + 0.62),
                                (x - sa * 1.2, y + ca * 1.2, gy + 0.62)], [], [(0, 1, 2, 3)])
                me.uv_layers.new(name="UVMap")
                me.materials.append(fallen)
                bpy.context.collection.objects.link(bpy.data.objects.new("frond", me))


# ---------------------------------------------------------------- 6. more Florida plants

def florida_plants():
    """Hibiscus (red flowers), croton (variegated red/yellow), sea grape (big round leaves), bougainvillea (magenta)."""
    out = {}
    specs = {"hibiscus": ((50, 90, 40), (200, 30, 40), 2.6, 0.35), "croton": ((150, 120, 30), (180, 50, 30), 2.0, 0.6),
             "seagrape": ((92, 130, 60), (150, 60, 50), 3.4, 0.15), "bougainvillea": ((60, 90, 40), (200, 40, 140), 3.0, 0.65)}
    for name, (leaf, flower, size, share) in specs.items():
        coll = _collection(name)
        bm = bmesh.new()
        res = bmesh.ops.create_icosphere(bm, subdivisions=3, radius=1)
        bmesh.ops.scale(bm, vec=(size, size, size * 0.85), verts=res["verts"])
        bmesh.ops.translate(bm, vec=(0, 0, size * 0.75), verts=res["verts"])
        m, nt, b = _nodes(name + "_mat")
        co = _coords(nt)
        n1 = _n(nt, "ShaderNodeTexVoronoi", Scale=2.2)
        nt.links.new(co, n1.inputs["Vector"])
        c = _mix(nt, _lin(leaf), _lin(flower), _rng(nt, n1.outputs["Distance"], share * 0.6, share * 0.6 + 0.05, 1, 0))
        nt.links.new(c, b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = 0.5
        b.inputs["Subsurface Weight"].default_value = 0.15
        o = _obj(name, bm, [m], coll)
        tex = bpy.data.textures.new(name + "_disp", "CLOUDS")
        tex.noise_scale = 0.45
        d = o.modifiers.new("leafy", "DISPLACE")
        d.texture, d.strength = tex, 0.8
        out[name] = coll
    return out


def plants_on_fences(fence_lines, gy, rng, plants):
    """Bougainvillea and sea grape spilling over fences; crotons and hibiscus joining the bed mix."""
    n = 0
    for fl in fence_lines:
        for ln in (fl.geoms if hasattr(fl, "geoms") else [fl]):
            if ln.is_empty or ln.geom_type not in ("LineString", "LinearRing"):
                continue
            t = rng.uniform(0, 8)
            while t < ln.length:
                if rng.random() < 0.45:
                    p = ln.interpolate(t)
                    place(plants["bougainvillea" if rng.random() < 0.6 else "seagrape"], p.x, p.y, gy, rng.uniform(0, 6.28), rng.uniform(0.8, 1.4))
                    n += 1
                t += rng.uniform(8, 16)
    return n


# ---------------------------------------------------------------- 2. time of day and weather

def _wet(level):
    """Water film on hard surfaces: darker, glossy, with a clear coat that reflects."""
    for name, dark, rough in (("photo_asphalt", 0.42, 0.05), ("real_asphalt", 0.42, 0.05), ("photo_concrete", 0.7, 0.2),
                              ("real_concrete", 0.7, 0.2), ("photo_roof_flat", 0.7, 0.25), ("stall_paint", 0.8, 0.15)):
        m = bpy.data.materials.get(name)
        if not m:
            continue
        nt = m.node_tree
        b = nt.nodes["Principled BSDF"]
        for ln in list(b.inputs["Roughness"].links):
            nt.links.remove(ln)
        b.inputs["Roughness"].default_value = rough
        b.inputs["Coat Weight"].default_value = 1.0 * level
        b.inputs["Coat Roughness"].default_value = 0.02
        src = b.inputs["Base Color"].links[0].from_socket if b.inputs["Base Color"].links else None
        if src:
            mx = _n(nt, "ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
            mx.inputs["Factor"].default_value = 1.0
            mx.inputs["B"].default_value = (dark, dark, dark, 1)
            nt.links.new(src, mx.inputs["A"])
            nt.links.new(mx.outputs["Result"], b.inputs["Base Color"])


def _lights_on(lit_share, lamp_energy, lamp_col):
    """Street lights as real spot lights, a share of windows lit, glowing shop signs."""
    for x, z, y in LAMPS:
        ld = bpy.data.lights.new("streetlight", "SPOT")
        ld.energy, ld.color = lamp_energy, lamp_col
        ld.spot_size, ld.spot_blend = math.radians(125), 0.6
        ld.shadow_soft_size = 0.6
        o = bpy.data.objects.new("streetlight", ld)
        o.location = (x, -z, y)
        bpy.context.collection.objects.link(o)
    m = bpy.data.materials.get("real_glass_interior")
    if m:
        r = m.node_tree.nodes.get("lit_rooms")
        if r:
            r.inputs["From Min"].default_value = 1 - lit_share
            r.inputs["From Max"].default_value = 1 - lit_share + 0.01
            r.inputs["To Max"].default_value = 3.0
    sm = bpy.data.materials.get("sign_letters")
    if sm:
        b = sm.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Color"].default_value = (1.0, 0.92, 0.75, 1)
        b.inputs["Emission Strength"].default_value = 6


PRESETS = {  # sun elevation, azimuth, sun strength, sun colour, sky strength, exposure, wet, lit windows, street lights
    "day": (32, 215, 5.5, (1.0, 0.93, 0.82), 0.35, 0.0, 0, 0, 0),
    "golden": (7, 235, 7.0, (1.0, 0.52, 0.26), 0.22, 0.0, 0, 0.05, 0),
    "rain": (22, 200, 2.2, (0.9, 0.93, 1.0), 0.75, -0.3, 1.0, 0.1, 0),
    "dusk": (0.5, 260, 1.2, (1.0, 0.5, 0.3), 0.6, 1.2, 0.3, 0.25, 9000),
    "night": (-12, 260, 0.0, (1, 1, 1), 1.0, 2.8, 0.4, 0.4, 30000),
}


def time_of_day(preset, view=None):
    elev, azim, sun_e, sun_c, sky_s, expo, wet, lit, lamps = PRESETS[preset]
    if view and preset in ("golden", "dusk"):  # low sun raking down the street toward the camera, a little to one side
        ux, uz = view
        azim = math.degrees(math.atan2(ux, uz)) - 90 + 35
    sky_and_sun(max(elev, -5), azim, exposure=expo)
    s = bpy.context.scene
    bg = s.world.node_tree.nodes["Background"]
    bg.inputs["Strength"].default_value = sky_s
    if preset == "rain":  # overcast: a flat cloud deck dims and greys the sky
        sk = [n for n in s.world.node_tree.nodes if n.type == "TEX_SKY"][0]
        sk.aerosol_density = 3.5  # thinning cloud: a bright break for the wet road to reflect
    if preset == "night":
        bg.inputs["Color"].default_value = (0.004, 0.007, 0.018, 1)  # moonlit sky glow
        for ln in list(bg.inputs["Color"].links):
            s.world.node_tree.links.remove(ln)
    sun = [o for o in bpy.data.objects if o.type == "LIGHT" and o.data.type == "SUN"][-1]
    sun.data.energy, sun.data.color = sun_e, sun_c
    if wet:
        _wet(wet)
    if lamps:
        _lights_on(lit, lamps, (1.0, 0.78, 0.5) if preset == "dusk" else (1.0, 0.85, 0.65))
    elif lit:
        _lights_on(lit, 0, (1, 1, 1))


def mat_clear_glass():
    """Shop windows: clear glass so the modelled display bay shows through, with reflections."""
    m, nt, b = _nodes("real_shopglass")
    b.inputs["Base Color"].default_value = (0.9, 0.95, 0.95, 1)
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["IOR"].default_value = 1.45
    return m


def mat_window_glass():
    """House and apartment windows: clear, slightly tinted glass with reflections, so the furnished rooms show."""
    m, nt, b = _nodes("real_window_glass")
    b.inputs["Base Color"].default_value = (0.75, 0.82, 0.85, 1)
    b.inputs["Transmission Weight"].default_value = 0.92
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["IOR"].default_value = 1.5
    b.inputs["Coat Weight"].default_value = 0.5
    return m
