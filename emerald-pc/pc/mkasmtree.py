#!/usr/bin/env python3
"""Mirror the repo's asm sources into build/pc/asmtree, converted for x86 gas.
Non-asm files become symlinks. Only rewrites files whose source changed."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm_transform import convert

ROOT = os.getcwd()
T = os.path.join(ROOT, 'build/pc/asmtree')
for d in ('data', 'asm', 'sound', 'constants', 'include', 'graphics'):
    for dp, dns, fns in os.walk(d):
        os.makedirs(os.path.join(T, dp), exist_ok=True)
        for fn in fns:
            src = os.path.join(dp, fn); dst = os.path.join(T, src)
            if fn.endswith(('.s', '.inc')):
                if os.path.exists(dst) and not os.path.islink(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
                    continue
                with open(src, encoding='latin-1') as f: txt = f.read()
                with open(dst, 'w', encoding='latin-1') as f: f.write(convert(txt))
            elif not os.path.lexists(dst):
                os.symlink(os.path.join(ROOT, src), dst)
os.makedirs(os.path.join(T, 'build'), exist_ok=True)
for name, target in (('build/assets', 'build/assets'), ('charmap.txt', 'charmap.txt')):
    p = os.path.join(T, name)
    if not os.path.lexists(p): os.symlink(os.path.join(ROOT, target), p)
