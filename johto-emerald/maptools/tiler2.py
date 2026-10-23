"""Example-based autotiler for any primary/secondary tileset pair (used for caves and dungeons)."""
import sys, os, json, pickle, collections
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
import tiler

OFFS8, OFFS4 = tiler.OFFS8, tiler.OFFS4

def cave_class(beh, coll):
    if beh in ('MB_LADDER',): return 'L'
    if beh in ('MB_POND_WATER', 'MB_DEEP_WATER', 'MB_OCEAN_WATER', 'MB_INTERIOR_DEEP_WATER', 'MB_WATERFALL', 'MB_NO_SURFACING'): return 'W'
    if beh in ('MB_SHALLOW_WATER',): return 'f'
    if beh in ('MB_NON_ANIMATED_DOOR', 'MB_SOUTH_ARROW_WARP', 'MB_NORTH_ARROW_WARP', 'MB_EAST_ARROW_WARP', 'MB_WEST_ARROW_WARP'): return 'e'
    if beh in ('MB_JUMP_SOUTH',): return 'v'
    if beh in ('MB_JUMP_WEST',): return '<'
    if beh in ('MB_JUMP_EAST',): return '>'
    if beh in ('MB_ICE', 'MB_THIN_ICE', 'MB_CRACKED_ICE'): return 'I'
    return 'w' if coll else 'f'

def learn(primary, secondary, classify=cave_class):
    beh = tiler.behaviors()
    d = json.load(open(ROOT + '/data/layouts/layouts.json'))
    pair = Pair(primary, secondary)
    t8, t4, t0 = (collections.defaultdict(collections.Counter) for _ in range(3))
    coll = collections.defaultdict(collections.Counter)
    for l in d['layouts']:
        if l.get('primary_tileset') != primary or l.get('secondary_tileset') != secondary: continue
        cells = read_map(l); w, h = l['width'], l['height']
        def cl(v):
            m = v & 0x3FF
            try: b = beh.get(pair.attr(m) & 0xFF, '')
            except IndexError: return 'w'
            return classify(b, (v >> 10) & 3)
        grid = [[cl(cells[y * w + x]) for x in range(w)] for y in range(h)]
        at = lambda x, y: grid[y][x] if 0 <= x < w and 0 <= y < h else '#'
        for y in range(h):
            for x in range(w):
                c = grid[y][x]; v = cells[y * w + x]; m = v & 0x3FF
                t8[(c,) + tuple(at(x + dx, y + dy) for dx, dy in OFFS8)][m] += 1
                t4[(c,) + tuple(at(x + dx, y + dy) for dx, dy in OFFS4)][m] += 1
                t0[(c,)][m] += 1
                coll[m][v >> 10] += 1
    return {'t8': dict(t8), 't4': dict(t4), 't0': dict(t0), 'coll': {m: c.most_common(1)[0][0] for m, c in coll.items()}}

_models = {}
def model(primary, secondary):
    key = primary + '+' + secondary
    if key not in _models:
        p = os.path.join(os.path.dirname(__file__), 'tiler2_%s.pkl' % key)
        if not os.path.exists(p): pickle.dump(learn(primary, secondary), open(p, 'wb'))
        _models[key] = pickle.load(open(p, 'rb'))
    return _models[key]

FALLBACK = {'e': 'f', 'L': 'f', 'I': 'f', 'v': 'f', '<': 'f', '>': 'f', 'W': 'w'}

def paint(grid, primary, secondary):
    M = model(primary, secondary); h = len(grid); w = len(grid[0])
    at = lambda x, y: grid[y][x] if 0 <= x < w and 0 <= y < h else '#'
    out = []
    for y in range(h):
        for x in range(w):
            c = grid[y][x]
            while True:
                k8 = (c,) + tuple(at(x + dx, y + dy) for dx, dy in OFFS8)
                k4 = (c,) + tuple(at(x + dx, y + dy) for dx, dy in OFFS4)
                hit = next((tab[k].most_common(1)[0][0] for tab, k in ((M['t8'], k8), (M['t4'], k4), (M['t0'], (c,))) if k in tab), None)
                if hit is not None or c not in FALLBACK: break
                c = FALLBACK[c]
            m = hit if hit is not None else 0
            out.append((M['coll'].get(m, 0) << 10) | m)
    return out
