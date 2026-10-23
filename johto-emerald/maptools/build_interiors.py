"""Generate HGSS interiors (Emerald templates + HGSS warps) and wire every door both ways."""
import sys, json, re, glob, collections
sys.path.insert(0, '.')
import build_world as bw
from interiors import *
from hg import *
from emr import read_map, ROOT
import emit

H = bw.H
CODE = {k: re.search(r'zone_event_\d+_(\w+)_bin', v['eventsBank']).group(1) for k, v in H.items()
        if 'zone_event' in v.get('eventsBank', '')}

ZC = zone_consts()
def zone_ev(const):
    f = glob.glob(PHG + '/files/fielddata/eventdata/zone_event/*_%s.json' % CODE.get(const, '#'))
    ev = json.load(open(f[0])) if f else {}
    for w in ev.get('warps', []):          # some warps name their destination by number
        if not isinstance(w['header'], str): w['header'] = ZC.get(w['header'], 'MAP_NOTHING')
    return ev

def stem(const):
    return re.sub(r'_(B?\d+F|ROOF|ELEVATOR|EXTERIOR|LIGHT_ROOM|ENTRANCE|BACK)$', '', const)

INDOOR_MUSIC = {'SEQ_GS_POKESEN': 'MUS_POKE_CENTER', 'SEQ_GS_FS': 'MUS_POKE_MART', 'SEQ_GS_GYM': 'MUS_GYM',
                'SEQ_GS_UTSUGI_RABO': 'MUS_BIRCH_LAB', 'SEQ_GS_GAME': 'MUS_GAME_CORNER'}

def interior_consts():
    return [k for k, v in H.items() if v['mapType'] == 'MAP_TYPE_INTERIOR' and k in CODE]

def main(other_consts):
    vm = vanilla_maps()
    lay_ids = {l['id'] for l in json.load(open(ROOT + '/data/layouts/layouts.json'))['layouts'] if 'id' in l}
    inside = interior_consts()
    generated = set(other_consts) | set(inside)
    names = []
    for c in inside:
        ev = zone_ev(c)
        hw = ev.get('warps', [])
        n_inner = sum(1 for w in hw if stem(w['header']) == stem(c))
        lay = pick_template(c, n_inner)
        tmpl = vm.get(lay)
        if not tmpl or lay not in lay_ids: lay = 'LAYOUT_HOUSE1'; tmpl = vm[lay]
        exits, inner = template_warps(tmpl)
        ex_h = sorted([i for i, w in enumerate(hw) if stem(w['header']) != stem(c)], key=lambda i: hw[i]['x'])
        in_h = [i for i, w in enumerate(hw) if stem(w['header']) == stem(c)]
        pos = {}
        for k, i in enumerate(ex_h):
            src = (exits or inner)[min(k, len(exits or inner) - 1)]; pos[i] = (src['x'], src['y'])
        for k, i in enumerate(in_h):
            src = (inner or exits)[min(k, len(inner or exits) - 1)]; pos[i] = (src['x'], src['y'])
        warps = []
        for i, w in enumerate(hw):
            if w['header'] not in generated: continue
            x, y = pos[i]
            warps.append({'x': x, 'y': y, 'elevation': 0, 'dest_map': emit.map_const(w['header']), 'dest_warp_id': str(w['anchor'])})
        hh = H[c]
        parent_music = INDOOR_MUSIC.get(hh['dayMusicId'], bw.music(hh['dayMusicId'], 'MAP_TYPE_CITY_TOWN'))
        mj = {'id': emit.map_const(c), 'name': emit.map_name(c), 'layout': lay, 'music': parent_music,
              'region_map_section': bw.mapsec(hh['mapsec']), 'requires_flash': False, 'weather': 'WEATHER_NONE',
              'map_type': 'MAP_TYPE_INDOOR', 'allow_cycling': False, 'allow_escaping': False, 'allow_running': False,
              'show_map_name': False, 'battle_scene': 'MAP_BATTLE_SCENE_NORMAL', 'connections': None,
              'object_events': [], 'warp_events': warps, 'coord_events': [], 'bg_events': []}
        emit.write_map(c, mj, '%s_MapScripts::\n\t.byte 0\n' % emit.map_name(c))
        names.append(emit.map_name(c))
        LAYOUT_OF[c] = lay
    return names, generated

LAYOUT_OF = {}

def outdoor_warps(zones, generated):
    """Door warps on the outdoor maps, at HGSS's exact door tiles."""
    for c, z in zones.items():
        p = ROOT + '/data/maps/%s/map.json' % emit.map_name(c)
        mj = json.load(open(p))
        for w in z.ev.get('warps', []):
            if not isinstance(w['header'], str): w['header'] = ZC.get(w['header'], 'MAP_NOTHING')
        mj['warp_events'] = [{'x': w['x'] - z.ox, 'y': w['z'] - z.oy, 'elevation': 0,
                              'dest_map': emit.map_const(w['header']), 'dest_warp_id': str(w['anchor'])}
                             for w in z.ev.get('warps', []) if w['header'] in generated]
        json.dump(mj, open(p, 'w'), indent=2)

def room_transform(const, layout_id):
    """Map HGSS room coordinates onto the Emerald template room's floor (proportional, snapped to free floor)."""
    from rooms import zone_matrix
    mw, mh, land = zone_matrix(CODE[const]) or (1, 1, [0xFFFF])
    T = terrain()['pieces']
    cells = []
    for i, li in enumerate(land):
        if li == 0xFFFF or li >= len(T): continue
        for k, v in enumerate(T[li][0]):
            if v & 0x8000 or v & 0xFF: cells.append(((i % mw) * 32 + k % 32, (i // mw) * 32 + k // 32))
    if not cells: return None
    hx0, hy0 = min(c[0] for c in cells), min(c[1] for c in cells)
    hx1, hy1 = max(c[0] for c in cells), max(c[1] for c in cells)
    lay = [l for l in json.load(open(ROOT + '/data/layouts/layouts.json'))['layouts'] if l.get('id') == layout_id][0]
    grid = read_map(lay); w, h = lay['width'], lay['height']
    floor = [(x, y) for y in range(1, h - 1) for x in range(w) if not (grid[y * w + x] >> 10) & 3 and grid[y * w + x] & 0x3FF]
    if not floor: return None
    tx0, ty0 = min(c[0] for c in floor), min(c[1] for c in floor)
    tx1, ty1 = max(c[0] for c in floor), max(c[1] for c in floor)
    used = set()
    def f(x, y):
        fx = (x - hx0) / max(1, hx1 - hx0); fy = (y - hy0) / max(1, hy1 - hy0)
        px, py = tx0 + fx * (tx1 - tx0), ty0 + fy * (ty1 - ty0)
        best = min((c for c in floor if c not in used), key=lambda c: (c[0] - px) ** 2 + (c[1] - py) ** 2, default=(tx0, ty0))
        used.add(best)
        return best
    return f
