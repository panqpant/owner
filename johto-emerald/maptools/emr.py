"""Emerald tileset/map rendering helpers."""
import struct, json, re, os
from PIL import Image, ImageDraw

_SCRATCH = '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad'
ROOT = os.environ.get('PE', _SCRATCH + '/pokeemerald')   # pokeemerald checkout to write into
NUM_TILES_PRIMARY = 512
NUM_METATILES_PRIMARY = 512

def tileset_dir(name):
    # gTileset_General -> data/tilesets/primary/general ; gTileset_Petalburg -> secondary/petalburg
    snake = re.sub(r'(?<!^)(?=[A-Z])', '_', name.replace('gTileset_', '')).lower()
    for kind in ('primary', 'secondary'):
        d = f'{ROOT}/data/tilesets/{kind}/{snake}'
        if os.path.isdir(d):
            return d
    raise FileNotFoundError(name)

def load_pal(path):
    lines = open(path).read().split('\n')[3:19]
    return [tuple(int(x) for x in l.split()) for l in lines]

class Tileset:
    def __init__(self, name):
        self.dir = tileset_dir(name)
        img = Image.open(self.dir + '/tiles.png')
        self.tilesimg = img
        self.ntiles = (img.width // 8) * (img.height // 8)
        mb = open(self.dir + '/metatiles.bin', 'rb').read()
        self.metatiles = [struct.unpack_from('<8H', mb, i) for i in range(0, len(mb), 16)]
        ab = open(self.dir + '/metatile_attributes.bin', 'rb').read()
        self.attrs = [struct.unpack_from('<H', ab, i)[0] for i in range(0, len(ab), 2)]
        self.pals = [load_pal(f'{self.dir}/palettes/{i:02d}.pal') for i in range(16)]
    def tile_indices(self, t):
        w = self.tilesimg.width // 8
        x, y = (t % w) * 8, (t // w) * 8
        return [self.tilesimg.getpixel((x + i, y + j)) for j in range(8) for i in range(8)]

class Pair:
    def __init__(self, prim, sec):
        self.p, self.s = Tileset(prim), Tileset(sec)
        self.cache = {}
    def metatile(self, mid):
        return self.p.metatiles[mid] if mid < NUM_METATILES_PRIMARY else self.s.metatiles[mid - NUM_METATILES_PRIMARY]
    def attr(self, mid):
        return self.p.attrs[mid] if mid < NUM_METATILES_PRIMARY else self.s.attrs[mid - NUM_METATILES_PRIMARY]
    def pal(self, n):
        return self.p.pals[n] if n < 6 else self.s.pals[n]
    def tile_px(self, t):
        if t < NUM_TILES_PRIMARY:
            return self.p.tile_indices(t) if t < self.p.ntiles else [0] * 64
        t -= NUM_TILES_PRIMARY
        return self.s.tile_indices(t) if t < self.s.ntiles else [0] * 64
    def render_metatile(self, mid):
        if mid in self.cache: return self.cache[mid]
        im = Image.new('RGB', (16, 16), (0, 0, 0))
        try:
            mt = self.metatile(mid)
        except IndexError:
            self.cache[mid] = im; return im
        px = im.load()
        for layer in range(2):
            for q in range(4):
                e = mt[layer * 4 + q]
                t, hf, vf, pal = e & 0x3FF, (e >> 10) & 1, (e >> 11) & 1, e >> 12
                data = self.tile_px(t); colors = self.pal(pal)
                ox, oy = (q % 2) * 8, (q // 2) * 8
                for j in range(8):
                    for i in range(8):
                        c = data[j * 8 + i]
                        if c == 0 and layer == 1: continue
                        if c == 0 and layer == 0: c = 0
                        x = 7 - i if hf else i; y = 7 - j if vf else j
                        px[ox + x, oy + y] = colors[c]
        self.cache[mid] = im
        return im

def load_layout(name):
    d = json.load(open(ROOT + '/data/layouts/layouts.json'))
    for l in d['layouts']:
        if l.get('name') == name: return l
    raise KeyError(name)

def read_map(layout):
    b = open(ROOT + '/' + layout['blockdata_filepath'], 'rb').read()
    return [struct.unpack_from('<H', b, i)[0] for i in range(0, len(b), 2)]

def render_map(pair, cells, w, h, grid=False):
    im = Image.new('RGB', (w * 16, h * 16))
    for i, c in enumerate(cells):
        im.paste(pair.render_metatile(c & 0x3FF), ((i % w) * 16, (i // w) * 16))
    return im

def sheet(pair, ids, cols=16, scale=2):
    rows = (len(ids) + cols - 1) // cols
    cw = 16 * scale + 22
    im = Image.new('RGB', (cols * cw, rows * (16 * scale + 10)), (40, 40, 40))
    d = ImageDraw.Draw(im)
    for k, mid in enumerate(ids):
        x, y = (k % cols) * cw, (k // cols) * (16 * scale + 10)
        im.paste(pair.render_metatile(mid).resize((16 * scale, 16 * scale), Image.NEAREST), (x, y + 10))
        d.text((x, y), '%X' % mid, fill=(255, 255, 0))
    return im
