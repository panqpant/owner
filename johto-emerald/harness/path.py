"""path.py MAPDIR x0 y0 x1 y1 -> harness 'hold' lines walking around collisions and NPCs"""
import json, sys, struct, collections, os
PE = os.path.dirname(os.path.abspath(__file__)) + '/../pokeemerald'
m = sys.argv[1]; x0, y0, x1, y1 = map(int, sys.argv[2:6])
mj = json.load(open(f'{PE}/data/maps/{m}/map.json'))
lay = next(l for l in json.load(open(f'{PE}/data/layouts/layouts.json'))['layouts'] if l.get('id') == mj['layout'])
w, h = lay['width'], lay['height']
raw = open(f"{PE}/{lay['blockdata_filepath']}", 'rb').read()
blk = struct.unpack('<%dH' % (w * h), raw)
busy = {(o['x'], o['y']) for o in mj['object_events']}
ok = lambda x, y: 0 <= x < w and 0 <= y < h and ((blk[y * w + x] >> 10) & 3) == 0 and (x, y) not in busy
prev = {(x0, y0): None}; q = collections.deque([(x0, y0)])
D = {(1, 0): 'R', (-1, 0): 'L', (0, -1): 'U', (0, 1): 'D'}
while q:
    c = q.popleft()
    if c == (x1, y1): break
    for d in D:
        n = (c[0] + d[0], c[1] + d[1])
        if n not in prev and (ok(*n) or n == (x1, y1)): prev[n] = (c, d); q.append(n)
if (x1, y1) not in prev: sys.exit('no path')
steps = []; c = (x1, y1)
while prev[c]: c, d = prev[c]; steps.append(D[d])
for s in reversed(steps): print('hold 16 ' + s)
