"""HGSS caves, towers and forests from HGSS terrain, with HGSS's exact warp tiles."""
import sys, json, re, glob
sys.path.insert(0, '.')
from emr import *
from hg import *
from rooms import zone_matrix
import tiler2, emit
import build_world as bw
from build_interiors import CODE, zone_ev

WATER = {0x10, 0x11, 0x13, 0x15, 0x19}
EXIT = {0x62, 0x63, 0x64, 0x65, 0x6C, 0x6D, 0x6E, 0x6F, 0x69, 0x5E, 0x5F, 0x67}
LADDER = {0x3C, 0x3D, 0x3E}

def cave_consts():
    return [k for k, v in bw.H.items() if v['mapType'] == 'MAP_TYPE_CAVE' and k in CODE and zone_matrix(CODE[k])]

def build_cave(const):
    mw, mh, land = zone_matrix(CODE[const]); W, Hh = mw * 32, mh * 32
    T = terrain()['pieces']
    raw = [[0x8000] * W for _ in range(Hh)]
    for i, li in enumerate(land):
        if li == 0xFFFF or li >= len(T): continue
        for k, v in enumerate(T[li][0]): raw[(i // mw) * 32 + k // 32][(i % mw) * 32 + k % 32] = v
    ev = zone_ev(const)
    # only the part reachable from the map's warps and people is cave; the rest is solid rock
    seeds = [(w['x'], w['z']) for w in ev.get('warps', [])] + [(o['x'], o['z']) for o in ev.get('objects', [])]
    reach, todo = set(), [s for s in seeds if 0 <= s[0] < W and 0 <= s[1] < Hh]
    reach.update(todo)
    while todo:
        x, y = todo.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < W and 0 <= ny < Hh and (nx, ny) not in reach and not (raw[ny][nx] & 0x8000 and (raw[ny][nx] & 0xFF) not in EXIT):
                reach.add((nx, ny)); todo.append((nx, ny))
    def cl(x, y):
        v = raw[y][x]; b = v & 0xFF
        if (x, y) not in reach: return 'w'
        if b in WATER: return 'W'
        if b in LADDER: return 'L'
        if b in EXIT: return 'e'
        if b == 0x3B: return 'v'
        if b == 0x20: return 'I'
        return 'w' if v & 0x8000 else 'f'
    grid = [''.join(cl(x, y) for x in range(W)) for y in range(Hh)]
    cells = tiler2.paint(grid, 'gTileset_General', 'gTileset_Cave')
    return W, Hh, cells, ev

def main(generated):
    layouts, names = [], []
    for c in cave_consts():
        W, Hh, cells, ev = build_cave(c)
        layouts.append(emit.write_layout(c, W, Hh, cells, secondary='gTileset_Cave'))
        hh = bw.H[c]
        warps = [{'x': w['x'], 'y': w['z'], 'elevation': 0, 'dest_map': emit.map_const(w['header']),
                  'dest_warp_id': str(w['anchor'])} for w in ev.get('warps', []) if w['header'] in generated]
        mj = {'id': emit.map_const(c), 'name': emit.map_name(c), 'layout': emit.layout_const(c),
              'music': bw.music(hh['dayMusicId'], 'CAVE'), 'region_map_section': bw.mapsec(hh['mapsec']),
              'requires_flash': False, 'weather': 'WEATHER_NONE', 'map_type': 'MAP_TYPE_UNDERGROUND',
              'allow_cycling': False, 'allow_escaping': True, 'allow_running': True, 'show_map_name': True,
              'battle_scene': 'MAP_BATTLE_SCENE_NORMAL', 'connections': None,
              'object_events': [], 'warp_events': warps, 'coord_events': [], 'bg_events': []}
        emit.write_map(c, mj, '%s_MapScripts::\n\t.byte 0\n' % emit.map_name(c))
        names.append(emit.map_name(c))
    return layouts, names
