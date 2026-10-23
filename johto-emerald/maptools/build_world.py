"""Generate every HGSS overworld map into pokeemerald (layouts, maps, connections, names, music, start)."""
import sys, json, re, collections
sys.path.insert(0, '.')
from convert import *
import emit

def _headers():
    src = open(PHG + '/src/data/map_headers.h').read()
    out = {}
    for m in re.finditer(r'\[(MAP_\w+)\] = \{(.*?)\n\s*\},', src, re.S):
        out[m.group(1)] = dict(re.findall(r'\.(\w+)\s*=\s*([^,\n]+),', m.group(2)))
    return {k: {a: b.strip() for a, b in v.items()} for k, v in out.items()}
H = _headers()
MSG_NAMES = [m['en_US'] for m in json.load(open(PHG + '/files/msgdata/msg/msg_0279.json'))['messages']]
HG_SECS = {k: int(v) for k, v in re.findall(r'#define (MAPSEC_\w+)\s+(\d+)', open(PHG + '/include/constants/map_sections.h').read())}

# HGSS music -> closest Emerald/FRLG track until the real HGSS soundtrack is ported
MUSIC = {
    'SEQ_GS_T_WAKABA': 'MUS_LITTLEROOT', 'SEQ_GS_C_YOSHINO': 'MUS_OLDALE', 'SEQ_GS_C_KIKYOU': 'MUS_RUSTBORO',
    'SEQ_GS_T_HIWADA': 'MUS_DEWFORD', 'SEQ_GS_C_KOGANE': 'MUS_SLATEPORT', 'SEQ_GS_C_ENJU': 'MUS_FORTREE',
    'SEQ_GS_C_ASAGI': 'MUS_LILYCOVE', 'SEQ_GS_C_TANBA': 'MUS_PETALBURG', 'SEQ_GS_T_CHOUJI': 'MUS_FALLARBOR',
    'SEQ_GS_C_FUSUBE': 'MUS_SOOTOPOLIS', 'SEQ_GS_T_MASARA': 'MUS_RG_PALLET', 'SEQ_GS_C_TOKIWA': 'MUS_RG_PEWTER',
    'SEQ_GS_C_NIBI': 'MUS_RG_PEWTER', 'SEQ_GS_C_HANADA': 'MUS_RG_PEWTER', 'SEQ_GS_C_KUCHIBA': 'MUS_RG_VERMILLION',
    'SEQ_GS_C_TAMAMUSHI': 'MUS_RG_CELADON', 'SEQ_GS_C_SEKICHIKU': 'MUS_RG_FUCHSIA', 'SEQ_GS_C_YAMABUKI': 'MUS_RG_CELADON',
    'SEQ_GS_T_CHION': 'MUS_RG_LAVENDER', 'SEQ_GS_T_GUREN': 'MUS_RG_CINNABAR',
    'SEQ_GS_R_1_29': 'MUS_ROUTE101', 'SEQ_GS_R_1_30': 'MUS_ROUTE101', 'SEQ_GS_R_2_30': 'MUS_ROUTE104',
    'SEQ_GS_R_3_30': 'MUS_ROUTE104', 'SEQ_GS_R_4_34': 'MUS_ROUTE110', 'SEQ_GS_R_5_34': 'MUS_ROUTE110',
    'SEQ_GS_R_6_34': 'MUS_ROUTE110', 'SEQ_GS_R_8_34': 'MUS_ROUTE110', 'SEQ_GS_R_6_38': 'MUS_ROUTE113',
    'SEQ_GS_R_7_42': 'MUS_ROUTE119', 'SEQ_GS_R_1_26': 'MUS_ROUTE120', 'SEQ_GS_R_9_03': 'MUS_RG_ROUTE3',
    'SEQ_GS_R_10_03': 'MUS_RG_ROUTE3', 'SEQ_GS_R_10_11': 'MUS_RG_ROUTE11', 'SEQ_GS_R_12_03': 'MUS_RG_ROUTE3',
    'SEQ_GS_R_12_24': 'MUS_RG_ROUTE24', 'SEQ_GS_R_13_03': 'MUS_RG_ROUTE3', 'SEQ_GS_R_13_11': 'MUS_RG_ROUTE11',
    'SEQ_GS_R_14_03': 'MUS_RG_ROUTE3', 'SEQ_GS_R_15_03': 'MUS_RG_ROUTE3', 'SEQ_GS_R_16_03': 'MUS_RG_CYCLING',
    'SEQ_GS_R_17_01': 'MUS_RG_ROUTE1', 'SEQ_GS_R_17_03': 'MUS_RG_ROUTE1', 'SEQ_GS_CHAMPROAD': 'MUS_VICTORY_ROAD',
    'SEQ_GS_SAFARI_FIELD': 'MUS_SAFARI_ZONE', 'SEQ_GS_SAFARI_ROAD': 'MUS_SAFARI_ZONE', 'SEQ_GS_D_KOUEN': 'MUS_ROUTE122',
}
def music(seq, maptype):
    if seq in MUSIC: return MUSIC[seq]
    return {'MAP_TYPE_ROUTE': 'MUS_ROUTE101', 'MAP_TYPE_CITY_TOWN': 'MUS_OLDALE'}.get(maptype, 'MUS_PETALBURG_WOODS')

# Emerald location slots the HGSS Johto names move into (Hoenn towns, routes, landmarks)
EM_SECS = json.load(open(ROOT + '/src/data/region_map/region_map_sections.json'))['map_sections']
FREE = [s['id'] for s in EM_SECS[:90] if s['id'] not in ('MAPSEC_SECRET_BASE', 'MAPSEC_DYNAMIC', 'MAPSEC_BATTLE_FRONTIER',
        'MAPSEC_INSIDE_OF_TRUCK') and not s['id'].startswith('MAPSEC_UNDERWATER')]
def em_name(n): return n.upper().replace('’', "'").replace('POKéMON', 'POKéMON')
sec_map = {}
def mapsec(hg_sec):
    if hg_sec in sec_map: return sec_map[hg_sec]
    name = em_name(MSG_NAMES[HG_SECS[hg_sec]])
    for s in EM_SECS[90:]:
        if s['name'] == name: sec_map[hg_sec] = s['id']; return s['id']    # Kanto names already exist
    sid = FREE.pop(0); sec_map[hg_sec] = sid
    for s in EM_SECS:
        if s['id'] == sid: s['name'] = name
    return sid

def main():
    w, h, hdr, alt, land = matrix(0)
    zn, zc = zone_names(), zone_consts()
    zids = sorted({hdr[i] for i in range(w * h) if land[i] != 0xFFFF and zn.get(hdr[i]) != 'EVERYWHERE'})
    zones = {}
    for zid in zids:
        z = Zone(zid, zn[zid]); z.build(); zones[zc[zid]] = z
    ntiles, nmeta = treegen_instance().write_tileset(ROOT)
    emit.register_tileset('Johto', ntiles)
    # connections: any two zones sharing a chunk edge
    owner = {}
    for c, z in zones.items():
        for x, y, _ in zone_chunks(z.zid): owner[(x, y)] = c
    conns = collections.defaultdict(set)
    for (x, y), c in owner.items():
        for dx, dy, d in ((1, 0, 'right'), (-1, 0, 'left'), (0, 1, 'down'), (0, -1, 'up')):
            o = owner.get((x + dx, y + dy))
            if o and o != c:
                a, b = zones[c], zones[o]
                off = (b.cy0 - a.cy0) * 32 if d in ('right', 'left') else (b.cx0 - a.cx0) * 32
                conns[c].add((o, d, off))
    layouts, names = [], []
    for c, z in zones.items():
        hh = H[c]
        layouts.append(emit.write_layout(c, z.w, z.h, z.cells))
        mtype = {'MAP_TYPE_ROUTE': 'MAP_TYPE_ROUTE', 'MAP_TYPE_CITY_TOWN': 'MAP_TYPE_TOWN'}.get(hh['mapType'], 'MAP_TYPE_ROUTE')
        mj = {
            'id': emit.map_const(c), 'name': emit.map_name(c), 'layout': emit.layout_const(c),
            'music': music(hh['dayMusicId'], hh['mapType']), 'region_map_section': mapsec(hh['mapsec']),
            'requires_flash': False, 'weather': 'WEATHER_SUNNY', 'map_type': mtype,
            'allow_cycling': hh.get('bikeAllowed') == 'TRUE', 'allow_escaping': False, 'allow_running': True,
            'show_map_name': True, 'battle_scene': 'MAP_BATTLE_SCENE_NORMAL',
            'connections': [{'map': emit.map_const(o), 'offset': off, 'direction': d} for o, d, off in sorted(conns[c])],
            'object_events': [], 'warp_events': [], 'coord_events': [], 'bg_events': [],
        }
        emit.write_map(c, mj, '%s_MapScripts::\n\t.byte 0\n' % emit.map_name(c))
        names.append(emit.map_name(c))
    import build_interiors
    inames, generated = build_interiors.main(list(zones))
    build_interiors.outdoor_warps(zones, generated)
    groups = {emit.GROUP: names}
    for k in range(0, len(inames), 200):
        groups['gMapGroup_HGIndoor%d' % (k // 200)] = inames[k:k + 200]
    emit.install(layouts, groups)
    emit.register_scripts(names + inames)
    emit.set_new_game_start('MAP_HG_NEW_BARK', 23, 13)
    json.dump({'map_sections': EM_SECS}, open(ROOT + '/src/data/region_map/region_map_sections.json', 'w'), indent=2)
    print('maps', len(names), 'tiles', ntiles, 'metatiles', nmeta)
    return zones

if __name__ == '__main__':
    main()
