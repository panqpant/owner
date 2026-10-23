"""Minimal Nintendo DS NSBMD (BMD0) reader for HGSS map pieces: walks each shape's display list,
tags every polygon with its material name, and rasterises the top-down view onto the 32x32 tile grid."""
import struct

def u8(b, o): return b[o]
def u16(b, o): return struct.unpack_from('<H', b, o)[0]
def u32(b, o): return struct.unpack_from('<I', b, o)[0]
def s32(b, o): return struct.unpack_from('<i', b, o)[0]
def s16(b, o): return struct.unpack_from('<h', b, o)[0]

def read_dict(b, o):
    """NNS 3D dictionary -> list of (name, data_offset_in_file)."""
    count = b[o + 1]
    p = o + 4
    hdr_size = u16(b, p); sect_size = u16(b, p + 2)
    p += hdr_size + 4 * count            # skip patricia tree entries
    unit = u16(b, p); p += 4
    entries = [p + i * unit for i in range(count)]
    names_o = p + count * unit
    names = [bytes(b[names_o + i * 16: names_o + i * 16 + 16]).split(b'\0')[0].decode('latin1') for i in range(count)]
    return list(zip(names, entries)), unit

PARAMS = {0x00: 0, 0x10: 1, 0x11: 0, 0x12: 1, 0x13: 1, 0x14: 1, 0x15: 0, 0x16: 16, 0x17: 12, 0x18: 16, 0x19: 12,
          0x1A: 9, 0x1B: 3, 0x1C: 3, 0x20: 1, 0x21: 1, 0x22: 1, 0x23: 2, 0x24: 1, 0x25: 1, 0x26: 1, 0x27: 1,
          0x28: 1, 0x29: 1, 0x2A: 1, 0x2B: 1, 0x30: 1, 0x31: 1, 0x32: 1, 0x33: 1, 0x34: 32, 0x40: 1, 0x41: 0,
          0x50: 1, 0x60: 1, 0x70: 3, 0x71: 2, 0x72: 1}

def s10(v): v &= 0x3FF; return v - 0x400 if v & 0x200 else v

def display_list(b, o, size):
    """Yield polygons (list of (x,y,z)) from a GX display list."""
    end = o + size; p = o
    v = [0.0, 0.0, 0.0]; prim = 0; cur = []; polys = []
    def flush_prim():
        if not cur: return
        if prim == 0:
            for i in range(0, len(cur) - 2, 3): polys.append(cur[i:i + 3])
        elif prim == 1:
            for i in range(0, len(cur) - 3, 4): polys.append(cur[i:i + 4])
        elif prim == 2:
            for i in range(len(cur) - 2): polys.append(cur[i:i + 3])
        elif prim == 3:
            for i in range(0, len(cur) - 3, 2): polys.append([cur[i], cur[i + 1], cur[i + 3], cur[i + 2]])
    while p + 4 <= end:
        cmds = b[p:p + 4]; p += 4
        for c in cmds:
            n = PARAMS.get(c)
            if n is None: return polys
            args = [u32(b, p + 4 * k) for k in range(n)] if p + 4 * n <= end else []
            p += 4 * n
            if c == 0x40: prim = args[0] & 3; cur = []
            elif c == 0x41: flush_prim(); cur = []
            elif c == 0x23:
                v = [s16(b, p - 8) / 4096, s16(b, p - 6) / 4096, s16(b, p - 4) / 4096]; cur.append(tuple(v))
            elif c == 0x24:
                a = args[0]; v = [s10(a) / 64, s10(a >> 10) / 64, s10(a >> 20) / 64]; cur.append(tuple(v))
            elif c == 0x25:
                a = args[0]; v[0] = struct.unpack('<h', struct.pack('<H', a & 0xFFFF))[0] / 4096; v[1] = struct.unpack('<h', struct.pack('<H', a >> 16))[0] / 4096; cur.append(tuple(v))
            elif c == 0x26:
                a = args[0]; v[0] = struct.unpack('<h', struct.pack('<H', a & 0xFFFF))[0] / 4096; v[2] = struct.unpack('<h', struct.pack('<H', a >> 16))[0] / 4096; cur.append(tuple(v))
            elif c == 0x27:
                a = args[0]; v[1] = struct.unpack('<h', struct.pack('<H', a & 0xFFFF))[0] / 4096; v[2] = struct.unpack('<h', struct.pack('<H', a >> 16))[0] / 4096; cur.append(tuple(v))
            elif c == 0x28:
                a = args[0]; v = [v[0] + s10(a) / 4096, v[1] + s10(a >> 10) / 4096, v[2] + s10(a >> 20) / 4096]; cur.append(tuple(v))
    flush_prim()
    return polys

def parse(b):
    """-> list of (material_name, polygons) with positions in model units (posScale applied)."""
    if bytes(b[:4]) != b'BMD0': raise ValueError('not BMD0')
    nsec = u16(b, 14)
    mdl = None
    for i in range(nsec):
        so = u32(b, 16 + 4 * i)
        if bytes(b[so:so + 4]) == b'MDL0': mdl = so
    models, _ = read_dict(b, mdl + 8)
    out = []
    for _, ent in models[:1]:
        m = mdl + u32(b, ent)
        ofs_sbc, ofs_mat, ofs_shp = u32(b, m + 4), u32(b, m + 8), u32(b, m + 12)
        num_mat, num_shp = b[m + 0x18], b[m + 0x19]   # model info starts at +0x14
        pos_scale = s32(b, m + 0x1C) / 4096
        mats, _ = read_dict(b, m + ofs_mat + 4)
        mat_names = [n for n, _ in mats]
        shps, _ = read_dict(b, m + ofs_shp)
        shapes = []
        for _, e in shps:
            sh = m + ofs_shp + u32(b, e)
            dl_o, dl_s = u32(b, sh + 8), u32(b, sh + 12)
            shapes.append(display_list(b, sh + dl_o, dl_s))
        # structure bytecode: MAT sets the current material, SHP draws a shape with it
        p = m + ofs_sbc; cur_mat = 0; drawn = set()
        while p < m + ofs_mat:
            op = b[p]; base = op & 0x1F
            if base == 0x01: break
            if base == 0x00: p += 1
            elif base == 0x02: p += 3
            elif base == 0x03: p += 2
            elif base == 0x04: cur_mat = b[p + 1]; p += 2
            elif base == 0x05:
                sid = b[p + 1]; p += 2
                if sid < len(shapes):
                    out.append((mat_names[cur_mat] if cur_mat < len(mat_names) else '?',
                                [[(x * pos_scale, y * pos_scale, z * pos_scale) for x, y, z in poly] for poly in shapes[sid]]))
                    drawn.add(sid)
            elif base == 0x06: p += 4 + (1 if op & 0x20 else 0) + (1 if op & 0x40 else 0)
            elif base == 0x07: p += 2 + (1 if op & 0x20 else 0) + (1 if op & 0x40 else 0)
            elif base == 0x08: p += 2 + (1 if op & 0x20 else 0) + (1 if op & 0x40 else 0)
            elif base == 0x09: n = b[p + 2]; p += 3 + 2 * n + (0)
            elif base == 0x0B: p += 1
            elif base in (0x0C, 0x0D): p += 3
            else: p += 1
        for sid, sh in enumerate(shapes):        # shapes the bytecode never referenced: material unknown
            if sid not in drawn: out.append(('?', [[(x * pos_scale, y * pos_scale, z * pos_scale) for x, y, z in poly] for poly in sh]))
    return out

def top_materials(b, tile=16.0, n=32):
    """Material visible from above at each tile centre (highest surface wins)."""
    parts = parse(b)
    best = [[(-1e9, None)] * n for _ in range(n)]
    half = tile * n / 2
    for mat, polys in parts:
        for poly in polys:
            # fan-triangulate, then test tile centres inside the XZ projection
            for k in range(1, len(poly) - 1):
                a, bb, c = poly[0], poly[k], poly[k + 1]
                xs = (a[0], bb[0], c[0]); zs = (a[2], bb[2], c[2])
                tx0 = max(0, int((min(xs) + half) // tile)); tx1 = min(n - 1, int((max(xs) + half) // tile))
                tz0 = max(0, int((min(zs) + half) // tile)); tz1 = min(n - 1, int((max(zs) + half) // tile))
                den = (bb[2] - c[2]) * (a[0] - c[0]) + (c[0] - bb[0]) * (a[2] - c[2])
                if abs(den) < 1e-9: continue
                for tz in range(tz0, tz1 + 1):
                    for tx in range(tx0, tx1 + 1):
                        px, pz = tx * tile - half + tile / 2, tz * tile - half + tile / 2
                        l1 = ((bb[2] - c[2]) * (px - c[0]) + (c[0] - bb[0]) * (pz - c[2])) / den
                        l2 = ((c[2] - a[2]) * (px - c[0]) + (a[0] - c[0]) * (pz - c[2])) / den
                        l3 = 1 - l1 - l2
                        if min(l1, l2, l3) < -1e-6: continue
                        y = l1 * a[1] + l2 * bb[1] + l3 * c[1]
                        if y > best[tz][tx][0]: best[tz][tx] = (y, mat)
    return [[best[z][x][1] for x in range(n)] for z in range(n)]
