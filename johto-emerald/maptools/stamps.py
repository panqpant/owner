"""Auto-extract every Emerald building (door + footprint) from vanilla outdoor maps into a stamp library."""
import sys, os, json, glob, pickle, collections
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
import tiler

def category(dest):
    d = dest.upper()
    for key, cat in (('POKEMON_CENTER', 'pokecenter'), ('MART', 'mart'), ('GYM', 'gym'), ('LAB', 'lab'),
                     ('HOUSE', 'house'), ('CONTEST', 'big'), ('DEPARTMENT', 'big'), ('MUSEUM', 'big'),
                     ('POKEMON_SCHOOL', 'house'), ('DAYCARE', 'house'), ('DAY_CARE', 'house')):
        if key in d: return cat
    return 'other'

def build_library():
    lay = {l['id']: l for l in json.load(open(ROOT + '/data/layouts/layouts.json'))['layouts'] if 'id' in l}
    lib = []
    for mj in glob.glob(ROOT + '/data/maps/*/map.json'):
        m = json.load(open(mj))
        if m.get('map_type') not in ('MAP_TYPE_TOWN', 'MAP_TYPE_CITY', 'MAP_TYPE_ROUTE'): continue
        l = lay.get(m['layout'])
        if not l or l['primary_tileset'] != 'gTileset_General': continue
        cells = read_map(l); w, h = l['width'], l['height']
        mt = lambda x, y: cells[y * w + x] & 0x3FF
        blocked = lambda x, y: 0 <= x < w and 0 <= y < h and (cells[y * w + x] >> 10) & 3 and mt(x, y) not in tiler.TREE
        for wp in m.get('warp_events', []):
            x, y = wp['x'], wp['y']
            if not (0 < y < h): continue
            # footprint: blocked cells connected to the tile above the door (the door tile itself joins it)
            seen, todo = {(x, y)}, [(x, y - 1)] if blocked(x, y - 1) else []
            seen.update(todo)
            while todo:
                cx, cy = todo.pop()
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if (nx, ny) not in seen and blocked(nx, ny) and ny <= y:
                        seen.add((nx, ny)); todo.append((nx, ny))
            if len(seen) < 4: continue
            xs = [p[0] for p in seen]; ys = [p[1] for p in seen]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            # roofs often overhang on walkable tiles above the solid part: take those rows too
            beh = tiler.behaviors(); tiler._gen = tiler._gen or Tileset('gTileset_General')
            def ground(xx, yy):
                v = cells[yy * w + xx]; m = v & 0x3FF
                return m < 512 and tiler.classify(m, (v >> 10) & 3, beh) != 'X'
            while y0 > 0 and any(not ground(xx, y0 - 1) for xx in range(x0, x1 + 1)):
                y0 -= 1
                seen.update((xx, y0) for xx in range(x0, x1 + 1) if not ground(xx, y0))
            if x1 - x0 > 14 or y1 - y0 > 12: continue
            rect = [[cells[(yy) * w + xx] for xx in range(x0, x1 + 1)] for yy in range(y0, y1 + 1)]
            lib.append({'map': m['name'], 'cat': category(wp['dest_map']), 'dest': wp['dest_map'],
                        'secondary': l['secondary_tileset'], 'w': x1 - x0 + 1, 'h': y1 - y0 + 1,
                        'door': (x - x0, y - y0), 'cells': rect,
                        'mask': [[(xx, yy) in seen for xx in range(x0, x1 + 1)] for yy in range(y0, y1 + 1)]})
    # drop exact duplicates
    uniq = {}
    for s in lib:
        key = (s['secondary'], str(s['cells']))
        uniq.setdefault(key, s)
    return list(uniq.values())

_lib = None
def library():
    global _lib
    if _lib is None:
        p = os.path.join(os.path.dirname(__file__), 'stamps.pkl')
        if not os.path.exists(p): pickle.dump(build_library(), open(p, 'wb'))
        _lib = pickle.load(open(p, 'rb'))
    return _lib

if __name__ == '__main__':
    lib = library()
    c = collections.Counter((s['cat'], s['secondary'][9:]) for s in lib)
    for k, v in sorted(c.items()): print(k, v)
    print(len(lib))
