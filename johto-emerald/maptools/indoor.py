"""Indoor autotiler: learns, per Emerald interior tileset, which metatile Emerald uses for each room feature
in a given neighbourhood, then paints HGSS rooms (from the extracted grid) the same way."""
import sys, os, json, pickle, collections
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
import tiler

SPECIAL = {'MB_PC': 'p', 'MB_TELEVISION': 't', 'MB_BOOKSHELF': 'b', 'MB_PICTURE_BOOK_SHELF': 'b',
           'MB_POKEMON_CENTER_BOOKSHELF': 'b', 'MB_REGION_MAP': 'm', 'MB_COUNTER': 'c', 'MB_SHOP_SHELF': 'h',
           'MB_SOUTH_ARROW_WARP': 'e', 'MB_NON_ANIMATED_DOOR': 's', 'MB_UP_ESCALATOR': 's', 'MB_DOWN_ESCALATOR': 's',
           'MB_VASE': 'k'}
CLASSES = 'fwkeptbmchs'
OFFS8 = tiler.OFFS8; OFFS4 = tiler.OFFS4

def classify_room(blocked, special, w, h):
    """blocked/special: dicts over cells. Walls = blocked cells connected to the map edge through blocked cells."""
    wall = set(); todo = [(x, y) for x in range(w) for y in range(h) if (x in (0, w - 1) or y in (0, h - 1)) and blocked(x, y)]
    wall.update(todo)
    while todo:
        x, y = todo.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if 0 <= n[0] < w and 0 <= n[1] < h and n not in wall and blocked(*n) and not special(*n):
                wall.add(n); todo.append(n)
    out = []
    for y in range(h):
        row = ''
        for x in range(w):
            sp = special(x, y)
            row += sp if sp else ('w' if (x, y) in wall else 'k' if blocked(x, y) else 'f')
        out.append(row)
    return out

def learn(secondary):
    beh = tiler.behaviors()
    d = json.load(open(ROOT + '/data/layouts/layouts.json'))
    pair = Pair('gTileset_Building', secondary)
    t8, t4, t0 = (collections.defaultdict(collections.Counter) for _ in range(3))
    coll = collections.defaultdict(collections.Counter)
    for l in d['layouts']:
        if l.get('primary_tileset') != 'gTileset_Building' or l['secondary_tileset'] != secondary: continue
        cells = read_map(l); w, h = l['width'], l['height']
        def b(x, y): return (cells[y * w + x] >> 10) & 3 != 0
        def sp(x, y):
            try: return SPECIAL.get(beh.get(pair.attr(cells[y * w + x] & 0x3FF) & 0xFF, ''), '')
            except IndexError: return ''
        grid = classify_room(b, sp, w, h)
        at = lambda x, y: grid[y][x] if 0 <= x < w and 0 <= y < h else '#'
        for y in range(h):
            for x in range(w):
                c = grid[y][x]; m = cells[y * w + x] & 0x3FF
                k8 = (c,) + tuple(at(x + dx, y + dy) for dx, dy in OFFS8)
                k4 = (c,) + tuple(at(x + dx, y + dy) for dx, dy in OFFS4)
                t8[k8][m] += 1; t4[k4][m] += 1; t0[(c,)][m] += 1
                coll[m][cells[y * w + x] >> 10] += 1
    return {'t8': dict(t8), 't4': dict(t4), 't0': dict(t0), 'coll': {m: c.most_common(1)[0][0] for m, c in coll.items()}}

_models = {}
def model(secondary):
    if secondary not in _models:
        p = os.path.join(os.path.dirname(__file__), 'indoor_%s.pkl' % secondary)
        if not os.path.exists(p): pickle.dump(learn(secondary), open(p, 'wb'))
        _models[secondary] = pickle.load(open(p, 'rb'))
    return _models[secondary]

FALLBACK = {'e': 'f', 's': 'k', 'p': 'k', 't': 'k', 'b': 'k', 'm': 'w', 'c': 'k', 'h': 'k'}

def paint(grid, secondary):
    M = model(secondary); h = len(grid); w = len(grid[0])
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
