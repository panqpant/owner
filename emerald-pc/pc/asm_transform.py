#!/usr/bin/env python3
"""Convert GBA (ARM gas) data assembly into syntax x86 gas accepts.

Only data directives are used by these files, so the transform is purely
syntactic: ARM '@' comments, power-of-two .align, 4-byte .word, and
ARM-only mode directives.
"""
import re, sys

DROP = re.compile(r'^\s*\.(thumb|arm|thumb_func|syntax|code|cpu|fpu|size)\b')
ALIGN = re.compile(r'(^|\s|;)\.align(\s)')
WORD = re.compile(r'(^|\s|;)\.word(\s)')
TYPE = re.compile(r'^\s*\.type\b')
SECTYPE = re.compile(r',\s*[%@](progbits|nobits)\b')

def strip_comment(line):
    out = []
    q = False
    i = 0
    while i < len(line):
        c = line[i]
        if q:
            out.append(c)
            if c == '\\' and i + 1 < len(line):
                out.append(line[i + 1]); i += 2; continue
            if c == '"':
                q = False
        else:
            if c == '"':
                q = True
            elif c == '@' and not (i > 0 and line[i - 1] == '\\'):
                break
            out.append(c)
        i += 1
    return ''.join(out)

def convert(text):
    res = []
    for line in text.split('\n'):
        line = strip_comment(line)
        if DROP.match(line) or TYPE.match(line):
            res.append('')
            continue
        line = ALIGN.sub(r'\1.p2align\2', line)
        line = WORD.sub(r'\1.4byte\2', line)
        line = SECTYPE.sub('', line)
        res.append(line)
    return '\n'.join(res)

if __name__ == '__main__':
    src = sys.stdin.read() if len(sys.argv) < 2 else open(sys.argv[1], encoding='latin-1').read()
    sys.stdout.write(convert(src))
