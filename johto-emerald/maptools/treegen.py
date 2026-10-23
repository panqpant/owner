"""Whole-tree compositor: trees can sit at any position (as HGSS places them) and are always drawn complete.
Each map cell's look = grass + every tree sprite overlapping it (lower trees in front). Unique cell images
become new metatiles appended to a copy of Petalburg's secondary tileset ("Johto")."""
import sys, os, struct, shutil
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
import rockgen

TREE_PAL = 2
GRASS = 0x001

def _px(pair, mid):
    """16x16 of (palette, colour index), top layer wins, index 0 transparent."""
    mt = pair.metatile(mid)
    out = [[None] * 16 for _ in range(16)]
    for layer in range(2):
        for q in range(4):
            e = mt[layer * 4 + q]
            t, hf, vf, pal = e & 0x3FF, (e >> 10) & 1, (e >> 11) & 1, e >> 12
            data = pair.tile_px(t)
            for j in range(8):
                for i in range(8):
                    c = data[j * 8 + i]
                    if c == 0 and layer == 1: continue
                    x = (7 - i if hf else i) + (q % 2) * 8; y = (7 - j if vf else j) + (q // 2) * 8
                    out[y][x] = (pal, c)
    return out

class Trees:
    def __init__(self):
        self.pair = Pair('gTileset_General', 'gTileset_Petalburg')
        g = _px(self.pair, GRASS)
        self.grass = g
        rows = [[0x1CE, 0x1CF], [0x1D6, 0x1D7], [0x1E6, 0x1E7]]
        big = [[None] * 32 for _ in range(48)]
        for r, row in enumerate(rows):
            for c, mid in enumerate(row):
                p = _px(self.pair, mid)
                for y in range(16):
                    for x in range(16):
                        v = p[y][x]
                        big[r * 16 + y][c * 16 + x] = None if v == g[y][x] else v
        self.big = big                     # 32 wide x 48 tall; rows 0-15 = tip over the cell above
        small = [[None] * 16 for _ in range(16)]
        for y in range(16):
            for x in range(16):
                small[y][x] = big[16 + y * 2][x * 2]
        self.small = small
        self.slim = [[big[y][x * 2] if big[y][x * 2] is not None else big[y][x * 2 + 1] for x in range(16)] for y in range(48)]
        self.cells = {}                     # composite key -> cell index
        rock = [[0] * 32 for _ in range(32)]
        for q, mid in enumerate((0x175, 0x176, 0x17D, 0x17E)):
            mt = self.pair.metatile(mid)
            for k in range(4):
                e = mt[4 + k]; t = e & 0x3FF
                data = self.pair.tile_px(t) if t else [0] * 64
                for j in range(8):
                    for i in range(8):
                        rock[(q // 2) * 16 + (k // 2) * 8 + j][(q % 2) * 16 + (k % 2) * 8 + i] = data[j * 8 + i]
        self.small_rock = [[rock[y * 2][x * 2] for x in range(16)] for y in range(16)]
        self.small_rock_id = self.cell_id(('smallrock',), True)
        self.rocks = rockgen.sprites()
        self.water = self.pair.metatile(0x170)[:4]

    def compose(self, layers):
        """layers: tuple of (sprite, ox, oy): sprite pixel (ox+x, oy+y) lands on cell pixel (x, y)."""
        img = [row[:] for row in self.grass]
        for spr, ox, oy in layers:
            s = {'big': self.big, 'small': self.small, 'slim': self.slim}[spr]
            for y in range(16):
                sy = oy + y
                if not (0 <= sy < len(s)): continue
                for x in range(16):
                    sx = ox + x
                    if 0 <= sx < len(s[0]) and s[sy][sx] is not None:
                        img[y][x] = s[sy][sx]
        return img

    def rock_overlay(self, parts):
        img = [[0] * 16 for _ in range(16)]
        for spr, ox, oy in parts:
            sp = self.rocks[spr]
            for y in range(16):
                for x in range(16):
                    if 0 <= oy + y < len(sp) and 0 <= ox + x < len(sp[0]) and sp[oy + y][ox + x]:
                        img[y][x] = sp[oy + y][ox + x]
        return img

    def foam_overlay(self, mask):
        # mask bits: 1 N, 2 E, 4 S, 8 W, 16 NE, 32 SE, 64 SW, 128 NW (land on that side)
        img = [[0] * 16 for _ in range(16)]
        OUT, IN = 2, 11
        def put(x, y, c):
            if 0 <= x < 16 and 0 <= y < 16 and (img[y][x] == 0 or c == OUT): img[y][x] = c
        for i in range(16):
            wave = 1 if (i // 4) % 2 else 0
            if mask & 1: put(i, 0, OUT); put(i, 1 + wave, IN)
            if mask & 4: put(i, 15, OUT); put(i, 14 - wave, IN)
            if mask & 8: put(0, i, OUT); put(1 + wave, i, IN)
            if mask & 2: put(15, i, OUT); put(14 - wave, i, IN)
        for bit, (cx, cy) in ((16, (15, 0)), (32, (15, 15)), (64, (0, 15)), (128, (0, 0))):
            if mask & bit:
                for d in range(3):
                    put(abs(cx - d), cy, OUT); put(cx, abs(cy - d), OUT)
                put(abs(cx - 1), abs(cy - 1), IN)
        return img

    def cell_id(self, layers, blocked):
        key = (tuple(layers), blocked)
        if key not in self.cells: self.cells[key] = len(self.cells)
        return self.cells[key]

    def write_tileset(self, pe_root, name='johto'):
        """Copy Petalburg's secondary tileset and append the composite tiles/metatiles."""
        src = pe_root + '/data/tilesets/secondary/petalburg'
        dst = pe_root + '/data/tilesets/secondary/' + name
        if os.path.exists(dst): shutil.rmtree(dst)
        shutil.copytree(src, dst)
        im = Image.open(dst + '/tiles.png')
        ntiles_old = (im.width // 8) * (im.height // 8)
        used_old = 159
        tiles, tile_index = [], {}
        def tile_of(img, tx, ty):
            pals = {img[ty * 8 + j][tx * 8 + i][0] for j in range(8) for i in range(8)}
            assert len(pals) == 1, pals
            data = tuple(img[ty * 8 + j][tx * 8 + i][1] for j in range(8) for i in range(8))
            if data not in tile_index:
                tile_index[data] = used_old + len(tiles); tiles.append(data)
            return tile_index[data], pals.pop()
        metas, attrs = [], []
        attr_tip = self.pair.attr(0x1CE); attr_body = self.pair.attr(0x1D4)
        for (layers, blocked), idx in sorted(self.cells.items(), key=lambda kv: kv[1]):
            if layers and layers[0] in ('rock', 'foam'):
                over = self.rock_overlay(layers[1]) if layers[0] == 'rock' else self.foam_overlay(layers[1])
                pal = 3 if layers[0] == 'rock' else 4
                on_grass = layers[0] == 'rock' and len(layers) > 2 and layers[2] == 'grass'
                ents = list(self.pair.metatile(GRASS)[:4]) if on_grass else list(self.water)
                for q in range(4):
                    data = tuple(over[(q // 2) * 8 + j][(q % 2) * 8 + i] for j in range(8) for i in range(8))
                    if not any(data): ents.append(0); continue
                    if data not in tile_index:
                        tile_index[data] = used_old + len(tiles); tiles.append(data)
                    ents.append((pal << 12) | (tile_index[data] + 512))
                metas.append(ents)
                attrs.append(self.pair.attr(0x1D4) if on_grass else self.pair.attr(0x17D) if layers[0] == 'rock' else self.pair.attr(0x170))
                continue
            if layers == ('smallrock',):
                water = self.pair.metatile(0x170)[:4]
                ents = []
                for q in range(4):
                    data = tuple(self.small_rock[(q // 2) * 8 + j][(q % 2) * 8 + i] for j in range(8) for i in range(8))
                    if data not in tile_index:
                        tile_index[data] = used_old + len(tiles); tiles.append(data)
                    ents.append((3 << 12) | (tile_index[data] + 512))
                metas.append(list(water) + ents)
                attrs.append(self.pair.attr(0x17D))
                continue
            img = self.compose(layers)
            if blocked:
                ents = []
                for q in range(4):
                    t, pal = tile_of(img, q % 2, q // 2)
                    ents.append((pal << 12) | (t + 512))
                metas.append(ents + [0, 0, 0, 0])
                attrs.append(attr_body)
            else:
                over = [[(v if v != self.grass[y][x] else (TREE_PAL, 0)) for x, v in enumerate(row)] for y, row in enumerate(img)]
                ents = list(self.pair.metatile(GRASS)[:4])
                for q in range(4):
                    t, pal = tile_of(over, q % 2, q // 2)
                    ents.append((pal << 12) | (t + 512))
                metas.append(ents)
                attrs.append(attr_tip)
        total = used_old + len(tiles)
        assert total <= 512, ('too many tiles', total)
        assert 144 + len(metas) <= 512, ('too many metatiles', len(metas))
        rows = (total + 15) // 16
        out = Image.new('P', (128, rows * 8)); out.putpalette(im.getpalette())
        out.paste(im.crop((0, 0, 128, min(im.height, rows * 8))), (0, 0))
        px = out.load()
        for k, data in enumerate(tiles):
            t = used_old + k; x0, y0 = (t % 16) * 8, (t // 16) * 8
            for j in range(8):
                for i in range(8): px[x0 + i, y0 + j] = data[j * 8 + i]
        out.save(dst + '/tiles.png')
        mb = open(dst + '/metatiles.bin', 'rb').read()[:144 * 16]
        mb += b''.join(struct.pack('<8H', *m) for m in metas)
        open(dst + '/metatiles.bin', 'wb').write(mb)
        ab = open(dst + '/metatile_attributes.bin', 'rb').read()[:144 * 2]
        ab += b''.join(struct.pack('<H', a) for a in attrs)
        open(dst + '/metatile_attributes.bin', 'wb').write(ab)
        return total, 144 + len(metas)

FIRST_CUSTOM_METATILE = 512 + 144
