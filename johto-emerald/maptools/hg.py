"""Real HGSS terrain (extracted from the player's ROM) + world matrix from pokeheartgold."""
import json, base64, struct, re, os
S = '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad'
PHG = os.environ.get('PHG', S + '/phg_full')                                  # pret/pokeheartgold checkout
TERRAIN = os.environ.get('HGSS_TERRAIN', S + '/hgss_data/terrain.json')       # from the extractor page
_t = None
def terrain():
    global _t
    if _t is None:
        d = json.load(open(TERRAIN))
        pieces = []
        for p in d['pieces']:
            perm, props = base64.b64decode(p['perm']), base64.b64decode(p['props'])
            if d['format'] == 'hgss-land-v1':
                # v1 read the grid at a fixed offset; HGSS puts an extra block first (header word 4 = 0x1234 | extra<<16)
                extra = p['hdr'][4] >> 16
                blob = perm + props
                grid = blob[extra:extra + 0x800]; props = blob[extra + 0x800:]
                grid += b'\xff' * (0x800 - len(grid))
            else:
                grid = perm
            model = base64.b64decode(p['model']) if 'model' in p else b''
            pieces.append((struct.unpack('<1024H', grid), props, p['hdr'], model))
        _t = {'meta': {k: d[k] for k in ('gamecode', 'title', 'count')}, 'pieces': pieces}
    return _t
def zone_names():
    return {int(m.group(2)): m.group(3) for m in re.finditer(r'#define (MAP_\w+)\s+(\d+)\s+// MAP_(\w+)', open(PHG + '/include/constants/maps.h').read())}
def zone_consts():
    return {int(m.group(2)): m.group(1) for m in re.finditer(r'#define (MAP_\w+)\s+(\d+)', open(PHG + '/include/constants/maps.h').read())}
def matrix(n=0):
    import glob
    f = glob.glob(PHG + '/files/fielddata/mapmatrix/map_matrix/map_matrix_%04d*.bin' % n)[0]
    b = open(f, 'rb').read()
    w, h, hh, ha, nl = b[:5]; o = 5 + nl
    hdr = struct.unpack_from('<%dH' % (w * h), b, o) if hh else [0] * (w * h); o += 2 * w * h if hh else 0
    alt = b[o:o + w * h] if ha else bytes(w * h); o += w * h if ha else 0
    land = struct.unpack_from('<%dH' % (w * h), b, o)
    return w, h, hdr, alt, land
def props(piece):
    raw = terrain()['pieces'][piece][1]
    out = []
    for i in range(0, len(raw), 0x30):
        mid, x, y, z = struct.unpack_from('<iiii', raw, i)
        out.append((mid, x / 4096, y / 4096, z / 4096))
    return out
