"""Convert HGSS interior zones (own matrix + terrain) into Emerald rooms."""
import sys, os, glob, struct, json
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
from hg import *
import indoor

HG_SPECIAL = {0x83: 'p', 0x86: 't', 0x85: 'm', 0xE0: 'b', 0xE1: 'b', 0xE2: 'b', 0xEA: 'b', 0xE5: 'h', 0xEB: 'h', 0xEC: 'h',
              0x5E: 's', 0x5F: 's', 0x3C: 's', 0x3D: 's', 0x3E: 's'}
EXITS = {0x62, 0x63, 0x64, 0x65, 0x69, 0x6C, 0x6D, 0x6E, 0x6F, 0x67}

def zone_matrix(code):
    f = glob.glob(PHG + '/files/fielddata/mapmatrix/map_matrix/map_matrix_*_%s.bin' % code)
    if not f: return None
    b = open(f[0], 'rb').read(); w, h, hh, ha, nl = b[:5]; o = 5 + nl
    if hh: o += 2 * w * h
    if ha: o += w * h
    return w, h, struct.unpack_from('<%dH' % (w * h), b, o)

def secondary_for(const):
    c = const.upper()
    if 'POKECENTER' in c: return 'gTileset_PokemonCenter'
    if 'MART' in c or 'SHOP' in c or 'DEPT' in c: return 'gTileset_Shop'
    if 'LAB' in c: return 'gTileset_Lab'
    if 'PLAYER_HOUSE' in c: return 'gTileset_BrendansMaysHouse'
    return 'gTileset_GenericBuilding'

class Room:
    def __init__(self, code, const):
        self.code, self.const = code, const
        mw, mh, land = zone_matrix(code)
        T = terrain()['pieces']
        W, H = mw * 32, mh * 32
        raw = [[0] * W for _ in range(H)]
        for i, li in enumerate(land):
            if li == 0xFFFF: continue
            g = T[li][0]; cx, cy = (i % mw) * 32, (i // mw) * 32
            for k, v in enumerate(g): raw[cy + k // 32][cx + k % 32] = v
        # the room is the bounding box of everything that isn't plain open floor (walls, furniture, warps)
        cells = [(x, y) for y in range(H) for x in range(W) if raw[y][x] & 0x8000 or raw[y][x] & 0xFF]
        self.x0 = min(c[0] for c in cells); self.y0 = min(c[1] for c in cells)
        self.w = max(c[0] for c in cells) - self.x0 + 1; self.h = max(c[1] for c in cells) - self.y0 + 1
        self.raw = [row[self.x0:self.x0 + self.w] for row in raw[self.y0:self.y0 + self.h]]
        self.secondary = secondary_for(const)

    def build(self):
        r = self.raw
        blocked = lambda x, y: bool(r[y][x] & 0x8000) and (r[y][x] & 0xFF) not in EXITS
        def special(x, y):
            b = r[y][x] & 0xFF
            if b in EXITS and not r[y][x] & 0x8000: return 'e'
            return HG_SPECIAL.get(b, '')
        self.grid = indoor.classify_room(blocked, special, self.w, self.h)
        self.cells = indoor.paint(self.grid, self.secondary)
        return self.cells

    def render(self, scale=2):
        p = Pair('gTileset_Building', self.secondary)
        return render_map(p, self.cells, self.w, self.h).resize((self.w * 16 * scale, self.h * 16 * scale), Image.NEAREST)
