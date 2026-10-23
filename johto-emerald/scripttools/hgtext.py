"""HGSS message text -> Emerald .string lines (control codes, names, re-wrapped to Emerald's box)."""
import json, re, os, sys, glob
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tools'))
from textwidth import load as _load_width
PHG = os.environ.get('PHG', '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad/phg_full')
PE = os.environ.get('PE', '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad/pokeemerald')
LIMIT = 208
_width = None

def width(s):
    global _width
    if _width is None: _width = _load_width(PE)
    return _width(s)

_chars = None
def _charset():
    global _chars
    if _chars is None:
        _chars = set(re.findall(r"^'(.)'\s*=", open(PE + '/charmap.txt', encoding='utf-8').read(), re.M))
    return _chars

_banks = {}
def bank(name):
    """msg_0543_T20R0101 -> list of message strings (index = message number)."""
    if name not in _banks:
        f = glob.glob(PHG + '/files/msgdata/msg/%s.json' % name)
        msgs = json.load(open(f[0]))['messages'] if f else []
        out = []
        for m in msgs:
            t = m.get('en_US', '')
            out.append(''.join(t) if isinstance(t, list) else t)
        _banks[name] = out
    return _banks[name]

# Emerald's font has curly quotes, ellipsis, x-sign and the gender symbols, so HGSS punctuation mostly carries over
PLAIN = {'—': '-', '–': '-', '\u3000': ' ', '\u00a0': ' '}

def convert(text, buffers):
    """-> list of (line, sep) where sep is the Emerald break after the line: '\\n', '\\l', '\\p' or '$'.
    buffers: {slot: '{PLAYER}' | '{RIVAL}' | '{STR_VAR_n}'} as the script set them up before this message."""
    t = text
    holders = {}
    def strvar(m):
        args = [a.strip() for a in m.group(2).split(',')]
        slot = int(args[1]) if len(args) > 1 and args[1].isdigit() else 0   # {STRVAR_1 type, slot, 0}
        key = '\x01%d\x01' % len(holders)
        holders[key] = buffers.get(slot, '{STR_VAR_%d}' % (min(slot, 2) + 1))
        return key
    t = re.sub(r'\{(STRVAR_\d|STRVAR)\s+([^}]*)\}', strvar, t)
    t = re.sub(r'\{[A-Z_0-9]+[^}]*\}', '', t)               # colour, speed, YESNO and other DS-only codes
    for a, b in PLAIN.items(): t = t.replace(a, b)
    # straight double quotes become curly ones (Emerald's text encoder has no plain ")
    n = [0]
    def q(_):
        n[0] += 1; return '“' if n[0] % 2 else '”'
    t = re.sub('"', q, t)
    t = ''.join(ch for ch in t if ch in _charset() or ch in '\n\r\f{}\x01' or ch.isascii() and ch.isprintable())
    for k, v in holders.items(): t = t.replace(k, v)
    parts = re.split(r'(\n|\r|\f)', t)
    raw = []                                   # (line, separator-from-HGSS)
    for i in range(0, len(parts), 2):
        line = parts[i].strip(); sep = parts[i + 1] if i + 1 < len(parts) else ''
        if line: raw.append([line, sep])
        elif raw and sep in ('\r', '\f'): raw[-1][1] = sep
    out, box_line = [], 0
    for idx, (line, sep) in enumerate(raw):
        # split lines that are too wide for Emerald's box
        words, pieces, cur = line.split(), [], ''
        for w in words:
            cand = (cur + ' ' + w) if cur else w
            if cur and width(cand) > LIMIT: pieces.append(cur); cur = w
            else: cur = cand
        if cur: pieces.append(cur)
        for k, piece in enumerate(pieces):
            last_piece = k == len(pieces) - 1
            if not last_piece: brk = 'line'
            elif idx == len(raw) - 1: brk = 'end'
            elif sep == '\r': brk = 'box'          # HGSS \r: wait, then a fresh box
            elif sep == '\f': brk = 'line'         # HGSS \f: wait, then scroll up one line
            else: brk = 'line'
            if brk == 'end': out.append((piece, '$'))
            elif brk == 'box': out.append((piece, '\\p')); box_line = 0
            else:
                out.append((piece, '\\n' if box_line == 0 else '\\l')); box_line += 1
    return out

def to_strings(lines):
    """(line, separator) pairs -> Emerald .string directives."""
    if not lines: return ['\t.string "$"']
    return ['\t.string "%s%s"' % (line, sep) for line, sep in lines]
