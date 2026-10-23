"""Example-based autotiler: learn which General-tileset metatile Emerald uses for a terrain class
given its neighbourhood, from every vanilla map, then paint new maps from class grids."""
import sys, re, collections, json, pickle, os
sys.path.insert(0, os.path.dirname(__file__))
from emr import *

TREE = {0x1C6,0x1C7,0x1CE,0x1CF,0x1D4,0x1D5,0x1D6,0x1D7,0x1DC,0x1DD,0x1DE,0x1DF,0x1E4,0x1E5,0x1E6,0x1E7,
        0x1EC,0x1ED,0x1F2,0x1F3,0x1F4,0x1F5,0x1FC,0x1FD}
TREE_LEFT = {0x1C6,0x1CE,0x1D4,0x1D6,0x1DC,0x1DE,0x1E4,0x1E6,0x1EC,0x1F2,0x1F4,0x1FC}
TREE_TOP = {0x1C6,0x1C7,0x1CE,0x1CF,0x1D4,0x1D5,0x1D6,0x1D7,0x1F2,0x1F3,0x1FC,0x1FD,0x1EC,0x1ED}
PATH = set(range(0x1D0, 0x1D3)) | set(range(0x1D8, 0x1DB)) | set(range(0x1E0, 0x1E3))

def behaviors():
    src = open(ROOT + '/include/constants/metatile_behaviors.h').read()
    # an enum in order: MB_NORMAL, MB_SECRET_BASE_WALL, ...
    names = re.findall(r'^\s*(MB_\w+)\s*(?:=\s*0)?,', src, re.M)
    return dict(enumerate(names))

_gen = None
def classify(m, coll, beh):
    """Terrain class of a primary metatile ('X' = anything we never generate)."""
    if m >= 512: return 'X'
    if m in TREE: return 'T'
    if m in PATH: return 'P'
    b = beh.get(_gen.attrs[m] & 0xFF, '')
    if b == 'MB_TALL_GRASS': return 't'
    if b in ('MB_OCEAN_WATER', 'MB_POND_WATER', 'MB_DEEP_WATER'): return 'W'
    if b == 'MB_SAND': return 'S'
    if b == 'MB_JUMP_SOUTH': return 'v'
    if b == 'MB_JUMP_WEST': return '<'
    if b == 'MB_JUMP_EAST': return '>'
    if b == 'MB_MOUNTAIN_TOP' or (0x064 <= m <= 0x0BF and b == 'MB_NORMAL' and coll): return 'M'
    if m == 0x001: return 'G'
    if m == 0x004: return 'F'
    return 'X'

def role(m):
    """Which quarter of a 2x2 tree a tree metatile is."""
    return ('L' if m in TREE_LEFT else 'R') + ('T' if m in TREE_TOP else 'B')

OFFS8 = [(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]
OFFS4 = [(0,-1),(-1,0),(1,0),(0,1)]

def learn():
    global _gen
    _gen = Tileset('gTileset_General')
    beh = behaviors()
    d = json.load(open(ROOT + '/data/layouts/layouts.json'))
    t8, t4, t0 = (collections.defaultdict(collections.Counter) for _ in range(3))
    for l in d['layouts']:
        if l.get('primary_tileset') != 'gTileset_General': continue
        cells = read_map(l); w, h = l['width'], l['height']
        cls = [classify(v & 0x3FF, (v >> 10) & 3, beh) for v in cells]
        rol = [role(v & 0x3FF) if c == 'T' else '' for v, c in zip(cells, cls)]
        def at(x, y):
            if 0 <= x < w and 0 <= y < h: return cls[y * w + x]
            return '#'
        for y in range(h):
            for x in range(w):
                c = cls[y * w + x]
                if c == 'X': continue
                m = cells[y * w + x] & 0x3FF
                key0 = (c, rol[y * w + x])
                k8 = key0 + tuple(at(x + dx, y + dy) for dx, dy in OFFS8)
                k4 = key0 + tuple(at(x + dx, y + dy) for dx, dy in OFFS4)
                t8[k8][m] += 1; t4[k4][m] += 1; t0[key0][m] += 1
    return {'t8': dict(t8), 't4': dict(t4), 't0': dict(t0)}

_model = None
def model():
    global _model
    if _model is None:
        p = os.path.join(os.path.dirname(__file__), 'tiler_model.pkl')
        if not os.path.exists(p):
            pickle.dump(learn(), open(p, 'wb'))
        _model = pickle.load(open(p, 'rb'))
    return _model

def paint(grid, roles):
    """grid: list of strings of classes; roles: dict (x,y)->tree role. '#' outside = edge.
    Returns list of metatile ids (None where class isn't generated)."""
    M = model(); h = len(grid); w = len(grid[0])
    def at(x, y):
        if 0 <= x < w and 0 <= y < h:
            c = grid[y][x]
            return c if c in 'TPtWSv<>GFM' else 'X'
        return '#'
    out = []
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            if c not in 'TPtWSv<>GFM':
                out.append(None); continue
            key0 = (c, roles.get((x, y), ''))
            k8 = key0 + tuple(at(x + dx, y + dy) for dx, dy in OFFS8)
            k4 = key0 + tuple(at(x + dx, y + dy) for dx, dy in OFFS4)
            for table, k in ((M['t8'], k8), (M['t4'], k4), (M['t0'], key0)):
                if k in table:
                    out.append(table[k].most_common(1)[0][0]); break
            else:
                out.append(0x001)
    return out
