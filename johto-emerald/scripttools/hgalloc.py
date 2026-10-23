"""Give every HGSS flag and variable its own Emerald slot, in new ranges reserved for HGSS.
Makes room in the save by trimming Emerald's secret bases (Hoenn-only) from 20 to 14."""
import re, os, glob, json
PHG = os.environ.get('PHG', '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad/phg_full')
PE = os.environ.get('PE', '/tmp/claude-0/-home-user-owner/ff77f0d1-c832-536b-9509-6c7ef5c1b385/scratchpad/pokeemerald')

HG_FLAGS_START = 0x960        # right after Emerald's daily flags
HG_FLAGS_COUNT = 2048
HG_VARS_START = 0x4100        # right after Emerald's vars
HG_VARS_COUNT = 256

# HGSS flags/vars that already mean the same thing in Emerald's engine
FLAG_ALIASES = {'FLAG_NOTHING': '0'}
VAR_ALIASES = {'VAR_SPECIAL_RESULT': 'VAR_RESULT', 'VAR_SPECIAL_LAST_TALKED': 'VAR_LAST_TALKED',
               'VAR_SPECIAL_x8000': 'VAR_0x8000', 'VAR_SPECIAL_x8001': 'VAR_0x8001', 'VAR_SPECIAL_x8002': 'VAR_0x8002',
               'VAR_SPECIAL_x8003': 'VAR_0x8003', 'VAR_SPECIAL_x8004': 'VAR_0x8004', 'VAR_SPECIAL_x8005': 'VAR_0x8005',
               'VAR_SPECIAL_x8006': 'VAR_0x8006', 'VAR_SPECIAL_x8007': 'VAR_0x8007', 'VAR_SPECIAL_x8008': 'VAR_0x8008',
               'VAR_SPECIAL_x8009': 'VAR_0x8009', 'VAR_SPECIAL_x800A': 'VAR_0x800A', 'VAR_SPECIAL_x800B': 'VAR_0x800B'}

def _sources():
    texts = [open(f).read() for f in glob.glob(PHG + '/files/fielddata/script/scr_seq/scr_seq_*.s')]
    texts += [open(f).read() for f in glob.glob(PHG + '/files/fielddata/eventdata/zone_event/*.json')]
    return texts

def collect():
    flags, vars_ = set(), set()
    for t in _sources():
        flags.update(re.findall(r'\b(FLAG_[A-Z0-9_]+)', t))
        vars_.update(re.findall(r'\b(VAR_[A-Za-z0-9_]+)', t))
    return sorted(flags), sorted(vars_)

def emerald_name(hg):          # FLAG_GOT_STARTER -> FLAG_HG_GOT_STARTER
    return hg.replace('FLAG_', 'FLAG_HG_', 1) if hg.startswith('FLAG_') else hg.replace('VAR_', 'VAR_HG_', 1)

class Alloc:
    def __init__(self, extra_flags=()):
        flags, vars_ = collect()
        self.flag = dict(FLAG_ALIASES); self.var = dict(VAR_ALIASES)
        n = 0
        for f in flags:
            if f in self.flag: continue
            m = re.match(r'FLAG_MAPTEMP_(\d+)$', f)
            if m and int(m.group(1)) < 31:
                self.flag[f] = 'FLAG_TEMP_%X' % (int(m.group(1)) + 1)     # cleared on every map change, as in HGSS
                continue
            self.flag[f] = emerald_name(f); n += 1
        self.flag_order = [f for f in flags if self.flag[f].startswith('FLAG_HG_')] + list(extra_flags)
        for f in extra_flags: self.flag[f] = f
        for v in vars_:
            if v in self.var: continue
            m = re.match(r'VAR_TEMP_x40(\w\w)$', v)
            if m and int(m.group(1), 16) < 0x10:
                self.var[v] = 'VAR_TEMP_%X' % int(m.group(1), 16); continue
            if v.startswith('VAR_SPECIAL_'): self.var[v] = 'VAR_0x8000'; continue
            self.var[v] = emerald_name(v)
        self.var_order = [v for v in vars_ if self.var[v].startswith('VAR_HG_')]
        assert len(self.flag_order) <= HG_FLAGS_COUNT, len(self.flag_order)
        assert len(self.var_order) <= HG_VARS_COUNT, len(self.var_order)

    def emerald_names(self):
        if not hasattr(self, '_em'): self._em = set(self.var.values()) | set(self.flag.values())
        return self._em

    def write(self):
        inc = PE + '/include/constants'
        with open(inc + '/hg_flags.h', 'w') as f:
            f.write('#ifndef GUARD_CONSTANTS_HG_FLAGS_H\n#define GUARD_CONSTANTS_HG_FLAGS_H\n\n'
                    '// HGSS story flags, each in its own slot after Emerald\'s flags (generated)\n'
                    '#define HG_FLAGS_START 0x%X\n#define HG_FLAGS_COUNT %d\n\n' % (HG_FLAGS_START, HG_FLAGS_COUNT))
            for i, name in enumerate(self.flag_order):
                f.write('#define %-60s (HG_FLAGS_START + 0x%X)\n' % (self.flag[name], i))
            f.write('\n#endif\n')
        with open(inc + '/hg_vars.h', 'w') as f:
            f.write('#ifndef GUARD_CONSTANTS_HG_VARS_H\n#define GUARD_CONSTANTS_HG_VARS_H\n\n'
                    '// HGSS story variables, each in its own slot after Emerald\'s vars (generated)\n'
                    '#define HG_VARS_START 0x%X\n#define HG_VARS_COUNT %d\n\n' % (HG_VARS_START, HG_VARS_COUNT))
            for i, name in enumerate(self.var_order):
                f.write('#define %-60s (HG_VARS_START + 0x%X)\n' % (self.var[name], i))
            f.write('\n#endif\n')
        # widen Emerald's flag and var tables to cover the HGSS ranges
        p = inc + '/flags.h'; s = open(p).read()
        s = re.sub(r'#define FLAGS_COUNT \(.*?\)\n', '#define FLAGS_COUNT (HG_FLAGS_START + HG_FLAGS_COUNT)\n', s)
        if '#include "constants/hg_flags.h"' not in s:
            s = s.replace('#define FLAGS_COUNT', '#include "constants/hg_flags.h"\n#define FLAGS_COUNT', 1)
        open(p, 'w').write(s)
        p = inc + '/vars.h'; s = open(p).read()
        s = re.sub(r'#define VARS_END\s+0x[0-9A-F]+\n', '#define VARS_END                                         (HG_VARS_START + HG_VARS_COUNT - 1)\n', s)
        if '#include "constants/hg_vars.h"' not in s:
            s = s.replace('#define VARS_END', '#include "constants/hg_vars.h"\n#define VARS_END', 1)
        open(p, 'w').write(s)
        p = inc + '/global.h'; s = open(p).read()
        s = s.replace('#define SECRET_BASES_COUNT 20', '#define SECRET_BASES_COUNT 2  // Johto: secret bases are gone (the code needs two slots to compile); the save space holds HGSS flags/vars')
        open(p, 'w').write(s)

if __name__ == '__main__':
    a = Alloc(); a.write()
    print('flags', len(a.flag_order), 'vars', len(a.var_order))
