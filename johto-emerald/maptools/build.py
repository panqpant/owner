"""Compose Emerald map blockdata from a terrain class grid + building stamps."""
import sys, os, collections, pickle, json
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
import tiler

# Stamps cut from vanilla maps: (layout, x, y, w, h, door_dx, door_dy)
STAMPS = {
    'house4':     ('OldaleTown_Layout', 4, 4, 4, 4, 1, 3),
    'house4b':    ('OldaleTown_Layout', 14, 13, 4, 4, 1, 3),
    'mart':       ('OldaleTown_Layout', 13, 3, 4, 4, 1, 3),
    'pokecenter': ('OldaleTown_Layout', 5, 13, 4, 4, 1, 3),
    'house5L':    ('LittlerootTown_Layout', 2, 4, 5, 5, 3, 4),
    'house5R':    ('LittlerootTown_Layout', 13, 4, 5, 5, 1, 4),
    'lab':        ('LittlerootTown_Layout', 3, 12, 7, 5, 4, 4),
}
SIGN = 0x003

def _collision_table():
    p = os.path.join(os.path.dirname(__file__), 'coll_model.pkl')
    if os.path.exists(p): return pickle.load(open(p, 'rb'))
    d = json.load(open(ROOT + '/data/layouts/layouts.json'))
    cnt = collections.defaultdict(collections.Counter)
    for l in d['layouts']:
        if l.get('primary_tileset') != 'gTileset_General': continue
        for v in read_map(l):
            cnt[v & 0x3FF][v >> 10] += 1
    t = {m: c.most_common(1)[0][0] for m, c in cnt.items()}
    pickle.dump(t, open(p, 'wb'))
    return t

class MapBuilder:
    def __init__(self, w, h, fill='G'):
        self.w, self.h = w, h
        self.g = [[fill] * w for _ in range(h)]
        self.stamps = []   # (name, x, y)
        self.signs = []
        self.raw = {}      # (x,y) -> full u16 cell override
    def rect(self, c, x0, y0, x1, y1):
        """Fill classes over inclusive rect."""
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                self.g[y][x] = c
    def trees(self, x0, y0, x1, y1):
        """Tree blocks must sit on the even 2x2 grid; widen to it."""
        self.rect('T', x0 - x0 % 2, y0 - y0 % 2, x1 | 1, y1 | 1)
    def stamp_at_door(self, name, door_x, door_y):
        _, sx, sy, w, h, dx, dy = STAMPS[name]
        x, y = door_x - dx, door_y - dy
        self.stamps.append((name, x, y))
        self.rect('B', x, y, x + w - 1, y + h - 1)
        return (x, y, w, h)
    def sign(self, x, y):
        self.signs.append((x, y)); self.g[y][x] = 'B'
    def cells(self):
        coll = _collision_table()
        grid = [''.join(r) for r in self.g]
        roles = {}
        for y in range(self.h):
            for x in range(self.w):
                if grid[y][x] == 'T':
                    roles[(x, y)] = ('L' if x % 2 == 0 else 'R') + ('T' if y % 2 == 0 else 'B')
        ids = tiler.paint(grid, roles)
        out = [((coll.get(m, 3 << 2) << 10) | m) if m is not None else 0x001 | (3 << 12) for m in ids]
        for name, x, y in self.stamps:
            lay, sx, sy, w, h, _, _ = STAMPS[name]
            l = load_layout(lay); src = read_map(l); lw = l['width']
            for j in range(h):
                for i in range(w):
                    if 0 <= x + i < self.w and 0 <= y + j < self.h:
                        out[(y + j) * self.w + x + i] = src[(sy + j) * lw + sx + i]
        for x, y in self.signs:
            out[y * self.w + x] = SIGN | (1 << 10) | (3 << 12)
        for (x, y), v in self.raw.items():
            out[y * self.w + x] = v
        return out
    def render(self, prim='gTileset_General', sec='gTileset_Petalburg', scale=1):
        p = Pair(prim, sec)
        im = render_map(p, self.cells(), self.w, self.h)
        return im.resize((self.w * 16 * scale, self.h * 16 * scale), Image.NEAREST)
