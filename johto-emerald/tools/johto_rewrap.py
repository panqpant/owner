"""Re-wrap any dialogue paragraph whose renamed text no longer fits the message box."""
import re, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from textwidth import load
root = sys.argv[1]
width = load(root)
LIMIT = 208

BLOCK_RE = re.compile(r'((?:^[ \t]*\.string "(?:[^"\\]|\\.)*"\n)+)', re.M)

def rewrap_block(block):
    indent = re.match(r'[ \t]*', block).group(0)
    text = ''.join(re.findall(r'\.string "((?:[^"\\]|\\.)*)"', block))
    # paragraphs end in \p or $; lines inside them are split by \n or \l
    parts = re.split(r'(\\p|\$)', text)
    out, changed = [], False
    for i in range(0, len(parts) - 1, 2):
        para, end = parts[i], parts[i + 1]
        lines = re.split(r'\\[nl]', para)
        if all(width(l) <= LIMIT for l in lines):
            out.append((para, end)); continue
        words = ' '.join(l.strip() for l in lines).split(' ')
        wrapped, cur = [], ''
        for wd in words:
            cand = (cur + ' ' + wd) if cur else wd
            if width(cand) > LIMIT and cur:
                wrapped.append(cur); cur = wd
            else:
                cur = cand
        wrapped.append(cur)
        para = wrapped[0] + ''.join(('\\n' if k == 1 else '\\l') + l for k, l in enumerate(wrapped[1:], 1))
        out.append((para, end)); changed = True
    if not changed or len(parts) % 2 == 0 or parts[-1]:
        return block if not changed else None
    # emit one .string per displayed line, keeping the separators at line ends
    res = []
    for para, end in out:
        segs = re.split(r'(\\[nl])', para)
        for j in range(0, len(segs), 2):
            sep = segs[j + 1] if j + 1 < len(segs) else end
            res.append('%s.string "%s%s"\n' % (indent, segs[j], sep))
    return ''.join(res)

fixed = skipped = 0
for f in pathlib.Path(root).glob('data/**/*.inc'):
    t = f.read_text()
    def sub(m):
        global fixed, skipped
        r = rewrap_block(m.group(1))
        if r is None:
            skipped += 1; return m.group(1)
        if r != m.group(1): fixed += 1
        return r
    n = BLOCK_RE.sub(sub, t)
    if n != t: f.write_text(n)
print('rewrapped', fixed, 'skipped', skipped)
