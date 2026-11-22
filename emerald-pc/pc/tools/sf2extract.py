#!/usr/bin/env python3
"""Pull the few General MIDI instruments the game's orchestra uses out of an
SF2 soundfont into hd/orchestra.bin (read by m4a_pc.c).

    sf2extract.py FluidR3_GM.sf2 hd/orchestra.bin [program ...]

Format (little endian): "EORC", u32 instruments; per instrument: u8 program,
u8 zones; per zone: u8 keyLo, keyHi, root, pad; f32 tuneCents, f32 gain,
u32 rate, start, length, loopStart, loopEnd (loopEnd == 0: one-shot);
then u32 sample count and the s16 samples.
"""
import struct, sys

PROGRAMS = [0, 17, 19, 21, 33, 35, 48, 52, 56, 58, 60, 68, 73, 77, 78]


def chunks(data, off, end):
    while off + 8 <= end:
        cid, size = struct.unpack_from('<4sI', data, off)
        yield cid, off + 8, size
        off += 8 + size + (size & 1)


def parse(data):
    assert data[:4] == b'RIFF' and data[8:12] == b'sfbk', 'not an SF2 file'
    smpl, pdta = None, {}
    for cid, off, size in chunks(data, 12, len(data)):
        if cid != b'LIST':
            continue
        kind = data[off:off + 4]
        for sid, soff, ssize in chunks(data, off + 4, off + size):
            if kind == b'sdta' and sid == b'smpl':
                smpl = memoryview(data)[soff:soff + ssize].cast('h')
            elif kind == b'pdta':
                pdta[sid.decode()] = data[soff:soff + ssize]
    return smpl, pdta


def table(raw, fmt):
    n = struct.calcsize(fmt)
    return [struct.unpack_from(fmt, raw, i) for i in range(0, len(raw) - n + 1, n)]


def zones(bags, gens, first, last):
    """Generator dicts of the bags first..last-1 (keyRange kept as (lo, hi))."""
    out = []
    for b in range(first, last):
        g = {}
        for k in range(bags[b][0], bags[b + 1][0]):
            op, amt = gens[k]
            if op in (43, 44):
                g[op] = (amt & 0xFF, amt >> 8)
            else:
                g[op] = amt - 65536 if amt >= 32768 and op not in (41, 53) else amt
        out.append(g)
    return out


def main():
    src, dst = sys.argv[1], sys.argv[2]
    progs = [int(p) for p in sys.argv[3:]] or PROGRAMS
    data = open(src, 'rb').read()
    smpl, p = parse(data)
    phdr = table(p['phdr'], '<20sHHHIII')
    pbag, pgen = table(p['pbag'], '<HH'), table(p['pgen'], '<HH')
    inst, ibag, igen = table(p['inst'], '<20sH'), table(p['ibag'], '<HH'), table(p['igen'], '<HH')
    shdr = table(p['shdr'], '<20sIIIIIBbHH')

    pcm, out, placed = [], [b'EORC', struct.pack('<I', len(progs))], {}
    for prog in progs:
        ph = next(i for i, h in enumerate(phdr[:-1]) if h[1] == prog and h[2] == 0)
        zl, covered = [], set()
        for pz in zones(pbag, pgen, phdr[ph][3], phdr[ph + 1][3]):
            if 41 not in pz:
                continue
            ii = pz[41]
            iz = zones(ibag, igen, inst[ii][1], inst[ii + 1][1])
            glob = iz[0] if iz and 53 not in iz[0] else {}
            plo, phi = pz.get(43, (0, 127))
            for z in iz:
                if 53 not in z:
                    continue
                g = dict(glob); g.update(z)
                vlo, vhi = g.get(44, (0, 127))
                if not vlo <= 100 <= vhi:
                    continue
                s = shdr[g[53]]
                if s[9] & 0x8000 or s[9] == 2:   # ROM sample, or the right half of a stereo pair
                    continue
                lo, hi = g.get(43, (0, 127))
                lo, hi = max(lo, plo), min(hi, phi)
                if lo > hi or covered.issuperset(range(lo, hi + 1)):
                    continue   # one sample per key: layered extras dropped
                covered.update(range(lo, hi + 1))
                off = lambda fine, coarse: g.get(fine, 0) + g.get(coarse, 0) * 32768
                start, end = s[1] + off(0, 4), s[2] + off(1, 12)
                ls, le = s[3] + off(2, 45), s[4] + off(3, 50)
                root = g.get(58, s[6])
                if root > 127:
                    root = 60
                cents = (g.get(51, 0) + pz.get(51, 0)) * 100 + g.get(52, 0) + pz.get(52, 0) + s[7]
                att = (g.get(48, 0) + pz.get(48, 0)) / 10.0
                loops = g.get(54, 0) & 1 and le > ls
                if (start, end) not in placed:   # a sample shared by several zones is stored once
                    placed[start, end] = len(pcm)
                    pcm.extend(smpl[start:end])
                base = placed[start, end]
                zl.append(struct.pack('<BBBBffIIIII', lo, hi, root, 0, float(cents), 10 ** (-att / 20),
                                      s[5], base, end - start, ls - start if loops else 0, le - start if loops else 0))
        assert zl, 'program %d has no zones' % prog
        out.append(struct.pack('<BB', prog, len(zl)))
        out.extend(zl)
        print('program %3d: %2d zones  %s' % (prog, len(zl), phdr[ph][0].split(b'\0')[0].decode()))
    out.append(struct.pack('<I', len(pcm)))
    out.append(struct.pack('<%dh' % len(pcm), *pcm))
    open(dst, 'wb').write(b''.join(out))
    print('%s: %.1f MB' % (dst, len(pcm) * 2 / 1e6))


if __name__ == '__main__':
    main()
