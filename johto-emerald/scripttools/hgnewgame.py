"""HGSS's new-game setup script (scr_seq_0149) compiled into C and run when a new game starts."""
import re, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import hgtext
PHG, PE = hgtext.PHG, hgtext.PE

def install(alloc):
    lines = []
    for raw in open(PHG + '/files/fielddata/script/scr_seq/scr_seq_0149.s'):
        m = re.match(r'\s*(SetFlag|ClearFlag)\s+(FLAG_\w+)', raw)
        if m:
            f = alloc.flag.get(m.group(2), '0')
            if f != '0': lines.append('    %s(%s);' % ('FlagSet' if m.group(1) == 'SetFlag' else 'FlagClear', f))
            continue
        m = re.match(r'\s*SetVar\s+(VAR_\w+),\s*(\w+)', raw)
        if m and alloc.var.get(m.group(1), '').startswith('VAR_HG_'):
            lines.append('    VarSet(%s, %s);' % (alloc.var[m.group(1)], m.group(2)))
    open(PE + '/src/hg_new_game.c', 'w').write(
        '#include "global.h"\n#include "event_data.h"\n#include "constants/flags.h"\n#include "constants/vars.h"\n\n'
        '// HGSS new-game setup (generated from HGSS script scr_seq_0149): hides everyone who appears later\n'
        'void HGSS_InitNewGame(void)\n{\n' + '\n'.join(lines) + '\n}\n')
    p = PE + '/ld_script.ld'; s = open(p).read()
    if 'hg_new_game.o' not in s:
        s = s.replace('        src/field_specials.o(.text);\n', '        src/field_specials.o(.text);\n        src/hg_new_game.o(.text);\n', 1)
        open(p, 'w').write(s)
    p = PE + '/src/new_game.c'; s = open(p).read()
    if 'HGSS_InitNewGame' not in s:
        s = s.replace('static void WarpToTruck(void);', 'static void WarpToTruck(void);\nvoid HGSS_InitNewGame(void);', 1)
        s = s.replace('    RunScriptImmediately(EventScript_ResetAllMapFlags);', '    RunScriptImmediately(EventScript_ResetAllMapFlags);\n    HGSS_InitNewGame();', 1)
        open(p, 'w').write(s)
    return len(lines)
