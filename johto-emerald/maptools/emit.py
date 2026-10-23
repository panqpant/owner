"""Write converted HGSS maps into the pokeemerald source tree."""
import sys, os, json, re, struct, collections
sys.path.insert(0, os.path.dirname(__file__))
from emr import ROOT

GROUP = 'gMapGroup_HGOverworld'

def camel(const):
    # MAP_ROUTE_29 -> Route29, MAP_NEW_BARK -> NewBark
    parts = const.replace('MAP_', '', 1).split('_')
    return ''.join(p.capitalize() if not p.isdigit() else p for p in parts)

def map_name(const): return 'HG_' + camel(const)
def map_const(const): return 'MAP_HG_' + const.replace('MAP_', '', 1)
def layout_const(const): return 'LAYOUT_HG_' + const.replace('MAP_', '', 1)

def register_tileset(name='Johto', ntiles=None):
    snake = name.lower()
    g = ROOT + '/src/data/tilesets/graphics.h'
    s = open(g).read()
    s = re.sub(r'\nconst u32 gTilesetTiles_%s\[\].*?\n\};\n' % name, '\n', s, flags=re.S)
    s += ('\nconst u32 gTilesetTiles_%s[] = INCGFX_U32("data/tilesets/secondary/%s/tiles.png", ".4bpp.lz", "-num_tiles %d -Wnum_tiles");\n\n'
          'const u16 gTilesetPalettes_%s[][16] =\n{\n' % (name, snake, ntiles, name)
          + ''.join('\tINCGFX_U16("data/tilesets/secondary/%s/palettes/%02d.pal", ".gbapal"),\n' % (snake, i) for i in range(16)) + '};\n')
    open(g, 'w').write(s)
    m = ROOT + '/src/data/tilesets/metatiles.h'
    s = open(m).read()
    if 'gMetatiles_%s[]' % name not in s:
        s += ('\nconst u16 gMetatiles_%s[] = INCBIN_U16("data/tilesets/secondary/%s/metatiles.bin");\n'
              'const u16 gMetatileAttributes_%s[] = INCBIN_U16("data/tilesets/secondary/%s/metatile_attributes.bin");\n' % (name, snake, name, snake))
        open(m, 'w').write(s)
    h = ROOT + '/src/data/tilesets/headers.h'
    s = open(h).read()
    if 'gTileset_%s =' % name not in s:
        s += ('\nconst struct Tileset gTileset_%s =\n{\n    .isCompressed = TRUE,\n    .isSecondary = TRUE,\n'
              '    .tiles = gTilesetTiles_%s,\n    .palettes = gTilesetPalettes_%s,\n    .metatiles = gMetatiles_%s,\n'
              '    .metatileAttributes = gMetatileAttributes_%s,\n    .callback = InitTilesetAnim_Petalburg,\n};\n' % ((name,) * 5))
        open(h, 'w').write(s)

BORDER = [0x1D4, 0x1D5, 0x1DC, 0x1DD]

def write_layout(const, w, h, cells, secondary='gTileset_Johto'):
    name = map_name(const)
    d = ROOT + '/data/layouts/' + name
    os.makedirs(d, exist_ok=True)
    open(d + '/map.bin', 'wb').write(struct.pack('<%dH' % len(cells), *cells))
    open(d + '/border.bin', 'wb').write(struct.pack('<4H', *[(1 << 10) | (3 << 12) | b for b in BORDER]))
    return {'id': layout_const(const), 'name': name + '_Layout', 'width': w, 'height': h,
            'primary_tileset': 'gTileset_General', 'secondary_tileset': secondary,
            'border_filepath': 'data/layouts/%s/border.bin' % name, 'blockdata_filepath': 'data/layouts/%s/map.bin' % name}

def write_map(const, mapjson, scripts):
    name = map_name(const)
    d = ROOT + '/data/maps/' + name
    os.makedirs(d, exist_ok=True)
    json.dump(mapjson, open(d + '/map.json', 'w'), indent=2)
    open(d + '/scripts.inc', 'w').write(scripts)

def install(layouts, maps_by_group):
    lp = ROOT + '/data/layouts/layouts.json'
    L = json.load(open(lp))
    L['layouts'] = [l for l in L['layouts'] if not l.get('id', '').startswith('LAYOUT_HG_')] + layouts
    json.dump(L, open(lp, 'w'), indent=2)
    gp = ROOT + '/data/maps/map_groups.json'
    G = json.load(open(gp))
    for grp in [k for k in G if k.startswith('gMapGroup_HG')]:
        del G[grp]
    G['group_order'] = [g for g in G['group_order'] if not g.startswith('gMapGroup_HG')]
    for grp, names in maps_by_group.items():
        G['group_order'].append(grp); G[grp] = names
    G['connections_include_order'] = [c for c in G['connections_include_order'] if not c.startswith('HG_')] + \
        [n for grp, names in maps_by_group.items() for n in names]
    json.dump(G, open(gp, 'w'), indent=2)

def register_scripts(names):
    """Include each generated map's scripts.inc from data/event_scripts.s (one marked block, rewritten each run)."""
    p = ROOT + '/data/event_scripts.s'
    s = open(p).read()
    s = re.sub(r'\n@ HG maps begin\n.*?@ HG maps end\n', '\n', s, flags=re.S)
    block = '\n@ HG maps begin\n' + ''.join('\t.include "data/maps/%s/scripts.inc"\n' % n for n in names) + '@ HG maps end\n'
    anchor = '\t.include "data/maps/LittlerootTown/scripts.inc"\n'
    s = s.replace(anchor, block + anchor, 1)
    open(p, 'w').write(s)

def set_new_game_start(map_const_name, x, y):
    """A new game warps straight to (x, y) on the given map instead of Emerald's moving truck."""
    p = ROOT + '/src/new_game.c'
    s = open(p).read()
    s = re.sub(r'static void WarpToTruck\(void\)\n\{.*?\n\}\n',
               'static void WarpToTruck(void)\n{\n    // Johto: a new game begins in New Bark Town\n'
               '    SetWarpDestination(MAP_GROUP(%s), MAP_NUM(%s), WARP_ID_NONE, %d, %d);\n    WarpIntoMap();\n}\n'
               % (map_const_name, map_const_name, x, y), s, count=1, flags=re.S)
    open(p, 'w').write(s)
