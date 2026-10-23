"""Convert one HGSS zone (real terrain from the ROM + HGSS events) into Emerald map blockdata."""
import sys, os, json, glob, collections
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
import tiler, stamps, build
from hg import *

WATER = {0x10, 0x11, 0x13, 0x15, 0x19, 0x2a}
GRASS = {0x02, 0x03}
LEDGE = {0x3b: 'v', 0x39: '<', 0x38: '>'}
DOORS = {0x69, 0x62, 0x63, 0x64, 0x65, 0x6c, 0x6d, 0x6e, 0x6f, 0x5e, 0x5f}
BUSH = 0x202  # Petalburg secondary: a 1x1 round bush
SEA_ROCK = 0x174  # General: rock standing in the sea
SECONDARY = 'gTileset_Petalburg'
import treegen
from treegen import FIRST_CUSTOM_METATILE
_TG = None
def treegen_instance():
    global _TG
    if _TG is None: _TG = treegen.Trees()
    return _TG

def zone_chunks(zone_const_id, mat=0):
    w, h, hdr, alt, land = matrix(mat)
    return [(x, y, land[y * w + x]) for y in range(h) for x in range(w) if hdr[y * w + x] == zone_const_id and land[y * w + x] != 0xFFFF]

def zone_event(code):
    f = glob.glob(PHG + '/files/fielddata/eventdata/zone_event/*_%s.json' % code)
    return json.load(open(f[0])) if f else {}

import re, pickle, nsbmd
_SURF = None
def surface(li):
    global _SURF
    if _SURF is None:
        f = os.path.join(os.path.dirname(__file__), 'surface_cache.pkl')
        _SURF = pickle.load(open(f, 'rb')) if os.path.exists(f) else {}
    if li not in _SURF:
        try: _SURF[li] = nsbmd.top_materials(terrain()['pieces'][li][3])
        except Exception: _SURF[li] = [[None] * 32 for _ in range(32)]
    return _SURF[li]

def material_class(name):
    n = (name or '').lower()
    if re.search(r'sea_rock|_iwa', n): return 'rock'
    if re.search(r'^tree|_tree|wall\d*_g|ueiki|bush', n): return 'tree'
    if re.search(r'road|miti|kbc_rd|roadline', n): return 'P'
    if re.search(r'beach|sand', n): return 'S'
    if re.search(r'flower|hana', n): return 'F'
    if re.search(r'cliff|wall\d*_d|wallkn|allpeak|rock|slope|peak', n): return 'M'
    if re.search(r'fence|_fe\d|nib_fe|sek_fe|as_fe', n): return 'fence'
    return None

class Zone:
    def __init__(self, zid, code):
        self.zid, self.code = zid, code
        ch = zone_chunks(zid)
        self.cx0 = min(c[0] for c in ch); self.cy0 = min(c[1] for c in ch)
        self.cw = max(c[0] for c in ch) - self.cx0 + 1; self.ch = max(c[1] for c in ch) - self.cy0 + 1
        self.w, self.h = self.cw * 32, self.ch * 32
        self.ox, self.oy = self.cx0 * 32, self.cy0 * 32
        T = terrain()['pieces']
        self.raw = [[0x806B] * self.w for _ in range(self.h)]   # outside the zone: trees
        self.mat = [[None] * self.w for _ in range(self.h)]
        for x, y, li in ch:
            g = T[li][0]
            for i, v in enumerate(g):
                self.raw[(y - self.cy0) * 32 + i // 32][(x - self.cx0) * 32 + i % 32] = 0x806B if v == 0xFFFF else v
            sf = surface(li)
            for j in range(32):
                for i in range(32):
                    self.mat[(y - self.cy0) * 32 + j][(x - self.cx0) * 32 + i] = material_class(sf[j][i])
        self.ev = zone_event(code)

    def cls(self, x, y):
        v = self.raw[y][x]; b = v & 0xFF; blk = v & 0x8000
        if b in WATER: return 'W'
        if b in GRASS: return 't'
        if b in LEDGE: return LEDGE[b]
        if b == 0x21: return 'S'
        if b in DOORS: return 'D'
        if blk and b in (0x6B, 0x06): return 'T'
        mc = self.mat[y][x]
        if blk:
            if mc == 'M': return 'M'
            if mc == 'tree': return 'T'
            if mc == 'rock': return 'R'   # sea rock: drawn over water
            return 'O'
        if mc in ('P', 'S', 'F'): return mc
        return 'G'

    def build(self):
        W, H = self.w, self.h
        g = [[self.cls(x, y) for x in range(W)] for y in range(H)]
        raw_override = {}
        # 1. buildings: door + connected blocked cells above it
        warps = {(e['x'] - self.ox, e['z'] - self.oy): e['header'] for e in self.ev.get('warps', [])}
        lib = [s for s in stamps.library() if s['secondary'] == SECONDARY]
        self.buildings = []
        for (dx, dy), dest in warps.items():
            if not (0 <= dx < W and 0 <= dy < H) or g[dy][dx] not in ('D', 'O'): continue
            if any((dx + ex, dy + ey) in raw_override for ex in (-1, 0, 1) for ey in (-1, 0)): continue
            foot, todo = {(dx, dy)}, [(dx, dy - 1)]
            while todo:
                cx, cy = todo.pop()
                if (cx, cy) in foot or not (0 <= cx < W and 0 <= cy < H) or g[cy][cx] not in ('O', 'D') or cy > dy: continue
                foot.add((cx, cy)); todo += [(cx + 1, cy), (cx - 1, cy), (cx, cy - 1), (cx, cy + 1)]
            cat = stamps.category(dest.replace('POKECENTER', 'POKEMON_CENTER').replace('FRIENDLY_SHOP', 'MART'))
            xs = [p[0] for p in foot]; ys = [p[1] for p in foot]
            fw, fh = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
            cands = [s for s in lib if s['cat'] == cat] or [s for s in lib if s['cat'] == 'house']
            fit = [s for s in cands if s['w'] <= fw and s['h'] <= fh]
            pick = max(fit, key=lambda s: s['w'] * s['h']) if fit else min(cands, key=lambda s: s['w'] * s['h'])
            sx, sy = dx - pick['door'][0], dy - pick['door'][1]
            for j in range(pick['h']):
                for i in range(pick['w']):
                    X, Y = sx + i, sy + j
                    if 0 <= X < W and 0 <= Y < H and (pick['mask'][j][i] or (X, Y) in foot):
                        raw_override[(X, Y)] = pick['cells'][j][i]
                        g[Y][X] = 'B'
            for p in foot:
                if g[p[1]][p[0]] != 'B':
                    g[p[1]][p[0]] = 'B'; raw_override[p] = 0x001 | (1 << 10) | (3 << 12)
            self.buildings.append((dest, cat, pick['map'], (dx, dy), (fw, fh), (pick['w'], pick['h'])))
        # 2. signs
        for e in self.ev.get('bgs', []):
            x, y = e['x'] - self.ox, e['z'] - self.oy
            if e.get('type') == 1 and 0 <= x < W and 0 <= y < H and g[y][x] == 'O':
                raw_override[(x, y)] = build.SIGN | (1 << 10) | (3 << 12); g[y][x] = 'B'
        # 2b. one-tile-wide cliff strips can't be drawn with Emerald cliffs: fold them into a touching tree line
        for _ in range(2):
            for y in range(H):
                for x in range(W):
                    if g[y][x] != 'M': continue
                    in_block = any(all(0 <= x + ax + i < W and 0 <= y + ay + j < H and g[y + ay + j][x + ax + i] == 'M'
                                       for i in (0, 1) for j in (0, 1)) for ax in (-1, 0) for ay in (-1, 0))
                    if not in_block and any(0 <= x + dx < W and 0 <= y + dy < H and g[y + dy][x + dx] == 'T'
                                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                        g[y][x] = 'T'
        # 3. trees: cover tree cells with whole 2x2 trees at any alignment (lower rows first so
        #    upper trees stay whole); leftover single cells get the small one-tile tree
        def is_t(x, y): return 0 <= x < W and 0 <= y < H and g[y][x] == 'T'
        layers = collections.defaultdict(list)   # cell -> [(sprite, ox, oy)]
        used = set(); blocks = []
        for y in range(H - 1):
            for x in range(W - 1):
                blk = [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
                if all(is_t(cx, cy) and (cx, cy) not in used for cx, cy in blk):
                    used.update(blk); blocks.append((x, y))
        # map-edge rows/columns: blocks hanging off the edge are drawn partly
        for y in range(-1, H):
            for x in range(-1, W):
                blk = [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
                inside = [c for c in blk if 0 <= c[0] < W and 0 <= c[1] < H]
                if inside and len(inside) < 4 and all(is_t(*c) and c not in used for c in inside):
                    used.update(inside); blocks.append((x, y))
        for y in range(H):
            for x in range(W):
                if g[y][x] != 'T' or (x, y) in used: continue
                opts = [(ax, ay) for ax in (x - 1, x) for ay in (y - 1, y)
                        if all(is_t(ax + i, ay + j) for i in (0, 1) for j in (0, 1))]
                if opts:
                    ax, ay = max(opts, key=lambda a: sum((a[0] + i, a[1] + j) not in used for i in (0, 1) for j in (0, 1)))
                    used.update((ax + i, ay + j) for i in (0, 1) for j in (0, 1)); blocks.append((ax, ay))
        for bx, by in sorted(blocks, key=lambda b: b[1]):
            for j in range(-1, 2):          # j=-1: the tip row above the tree
                for i in range(2):
                    cx, cy = bx + i, by + j
                    if not (0 <= cx < W and 0 <= cy < H): continue
                    if j == -1 and g[cy][cx] not in ('G', 'T'): continue
                    layers[(cx, cy)].append(('big', i * 16, (j + 1) * 16))
        # leftover single tree cells: a slim tree whose canopy rises into the cell above
        for y in range(H):
            for x in range(W):
                if g[y][x] == 'T' and (x, y) not in used:
                    for j in range(-2, 1):
                        cy = y + j
                        if cy < 0: continue
                        if j < 0 and g[cy][x] not in ('G', 'T'): continue
                        layers[(x, cy)].append(('slim', 0, (j + 2) * 16))
        self.rock_on_land = set()
        # 3a. rock formations standing alone in the water (touching no land) are sea rocks, not cliffs
        seen = set()
        for y in range(H):
            for x in range(W):
                if g[y][x] != 'M' or (x, y) in seen: continue
                comp, todo, land = [], [(x, y)], False
                seen.add((x, y))
                while todo:
                    cx, cy = todo.pop(); comp.append((cx, cy))
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if not (0 <= nx < W and 0 <= ny < H): continue
                            c = g[ny][nx]
                            if c == 'M' and (nx, ny) not in seen and abs(dx) + abs(dy) == 1:
                                seen.add((nx, ny)); todo.append((nx, ny))
                            elif c in 'GTPStFvB<>D':
                                land = True
                wet = any(0 <= cx + dx < W and 0 <= cy + dy < H and g[cy + dy][cx + dx] == 'W'
                          for cx, cy in comp for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                if not land or wet:
                    for cx, cy in comp:
                        g[cy][cx] = 'R'
                        if land: self.rock_on_land.add((cx, cy))   # a shoreline cliff: boulders on the bank
        # 3b. sea rocks and rocky shores: generated boulders composited over animated water,
        #     big ones where a 2x2 fits (overlapping allowed), small ones elsewhere
        TG = treegen_instance()
        rock_layers = collections.defaultdict(list); rused = set(); rblocks = []
        is_r = lambda x, y: 0 <= x < W and 0 <= y < H and g[y][x] == 'R'
        for y in range(H - 1):
            for x in range(W - 1):
                blk = [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
                if all(is_r(*c) and c not in rused for c in blk): rused.update(blk); rblocks.append((x, y))
        for y in range(H):
            for x in range(W):
                if not is_r(x, y) or (x, y) in rused: continue
                opts = [(ax, ay) for ax in (x - 1, x) for ay in (y - 1, y) if all(is_r(ax + i, ay + j) for i in (0, 1) for j in (0, 1))]
                if opts:
                    ax, ay = opts[0]; rused.update((ax + i, ay + j) for i in (0, 1) for j in (0, 1)); rblocks.append((ax, ay))
        for bx, by in sorted(rblocks, key=lambda b: b[1]):
            spr = 'rockL' if (bx * 7 + by * 3) % 2 else 'rockL2'
            for i in (0, 1):
                for j in (0, 1):
                    rock_layers[(bx + i, by + j)].append((spr, i * 16, j * 16))
        for y in range(H):
            for x in range(W):
                if is_r(x, y) and (x, y) not in rused:
                    rock_layers[(x, y)].append(('rockS%d' % (1 + (x * 5 + y * 3) % 3), 0, 0))
        rock_cells = {c: (FIRST_CUSTOM_METATILE + TG.cell_id(('rock', tuple(l), 'grass' if c in self.rock_on_land else 'water'), True))
                         | (1 << 10) | ((3 if c in self.rock_on_land else 1) << 12)
                      for c, l in rock_layers.items()}
        # 4. paint terrain (trees act as grass for the autotiler), overlay trees, buildings, signs, rocks
        grid = [''.join(r).replace('D', 'G').replace('T', 'G') for r in g]
        # rocks standing in water count as water for the shoreline, so no stray shore edges form around them
        tgrid = [''.join('G' if (x, y) in self.rock_on_land else 'W' if c in 'OR' and any(0 <= x + dx < W and 0 <= y + dy < H and grid[y + dy][x + dx] == 'W'
                                                for dx in (-1, 0, 1) for dy in (-1, 0, 1)) else c
                         for x, c in enumerate(r)) for y, r in enumerate(grid)]
        ids = tiler.paint([r.replace('O', 'X').replace('B', 'X').replace('R', 'W') for r in tgrid], {})
        coll = build._collision_table()
        TG = treegen_instance()
        def near_water(x, y):
            return any(0 <= x + dx < W and 0 <= y + dy < H and g[y + dy][x + dx] == 'W' for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        out = []
        for i, m in enumerate(ids):
            x, y = i % W, i // W
            if (x, y) in raw_override: out.append(raw_override[(x, y)])
            elif (x, y) in layers and (g[y][x] in ('T', 'G')):
                blocked = g[y][x] == 'T'
                cid = TG.cell_id(tuple(layers[(x, y)]), blocked)
                out.append(((1 if blocked else 0) << 10) | (3 << 12) | (FIRST_CUSTOM_METATILE + cid))
            elif (x, y) in rock_cells: out.append(rock_cells[(x, y)])
            elif tgrid[y][x] == 'W':
                def land(dx, dy):
                    nx, ny = x + dx, y + dy
                    return 0 <= nx < W and 0 <= ny < H and ((tgrid[ny][nx] != 'W' and (nx, ny) not in rock_cells) or (nx, ny) in self.rock_on_land)
                mask = sum(bit for bit, (dx, dy) in ((1, (0, -1)), (2, (1, 0)), (4, (0, 1)), (8, (-1, 0))) if land(dx, dy))
                for bit, (dx, dy), a, b in ((16, (1, -1), 1, 2), (32, (1, 1), 4, 2), (64, (-1, 1), 4, 8), (128, (-1, -1), 1, 8)):
                    if land(dx, dy) and not mask & (a | b): mask |= bit
                blocked = grid[y][x] == 'O'
                cid = 0x170 if mask == 0 else FIRST_CUSTOM_METATILE + TG.cell_id(('foam', mask), False)
                out.append(cid | ((1 if blocked else 0) << 10) | (1 << 12))
            elif grid[y][x] == 'O' and near_water(x, y):
                # blocked cells in the sea are boundaries in HGSS: water you can't surf into
                out.append(((m if m is not None and tgrid[y][x] == 'W' else 0x170) & 0x3FF) | (1 << 10) | (1 << 12))
            elif grid[y][x] == 'O': out.append(BUSH | (1 << 10) | (3 << 12))
            elif m is None: out.append(0x001 | (3 << 12))
            else: out.append((coll.get(m, 3 << 2) << 10) | m)
        self.cells = out
        return out

    def render(self, scale=1, secondary='gTileset_Johto'):
        p = Pair('gTileset_General', secondary)
        im = render_map(p, self.cells, self.w, self.h)
        return im.resize((self.w * 16 * scale, self.h * 16 * scale), Image.NEAREST) if scale != 1 else im
