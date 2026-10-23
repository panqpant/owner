"""Put HGSS people, trainers, items, signs, triggers and translated scripts onto every generated map."""
import sys, os, json, re, glob, collections
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'maptools'))
import hgtext, hgscript, hgdata, sprites, hgalloc
PHG, PE = hgtext.PHG, hgtext.PE

HG_ITEMS = set(re.findall(r'#define (ITEM_\w+)', open(PHG + '/include/constants/items.h').read()))

def item_from_label(label, prefix):
    toks = label[len(prefix):].split('_')
    for k in range(len(toks)):
        cand = 'ITEM_' + '_'.join(toks[k:]).upper()
        if cand in HG_ITEMS: return hgdata.item(cand)
    return 'ITEM_POTION'

def ev_index(sid):
    m = re.search(r'_(\d+)\s*\+\s*1$', str(sid))
    return int(m.group(1)) if m else None

def hidden_flag(label): return 'FLAG_HG_HIDDEN_' + label.replace('std_hiddenitem_', '').upper()

def all_hidden_labels():
    out = set()
    for f in glob.glob(PHG + '/files/fielddata/eventdata/zone_event/*.json'):
        for b in json.load(open(f)).get('bgs', []):
            if str(b['scriptId']).startswith('std_hiddenitem_'): out.add(b['scriptId'])
    return sorted(out)

class Builder:
    def __init__(self, H, CODE, emit):
        self.H, self.CODE, self.emit = H, CODE, emit
        self.alloc = hgalloc.Alloc(extra_flags=[hidden_flag(l) for l in all_hidden_labels()])
        self.trainers = json.load(open(os.path.join(os.path.dirname(__file__), 'trainer_info.json')))
        self.unsupported = collections.Counter()

    def files(self, const):
        h = self.H[const]
        sb = re.sub(r'_bin$', '', h.get('scriptsBank', ''))
        hb = re.sub(r'_bin$', '', h.get('scriptHeaderBank', ''))
        sf = PHG + '/files/fielddata/script/scr_seq/%s.s' % sb
        hf = PHG + '/files/fielddata/script/scr_seq/%s.s' % hb
        return (sf if os.path.exists(sf) else None), (hf if os.path.exists(hf) else None), h.get('msgBank')

    def header(self, ms, hf):
        """HGSS init scripts -> Emerald map script table."""
        if not hf: return [], []
        entries, tables, extra = [], {}, []
        transition = []
        cur = None
        for raw in open(hf):
            line = raw.strip()
            m = re.match(r'InitScriptEntry_(OnTransition|OnResume|OnLoad|OnFrameTable|OnWarpInto)\s+(.*)', line)
            if m:
                kind, target = m.groups()
                if kind == 'OnFrameTable':
                    lab = '%s_FrameTable_%s' % (ms.em, target.strip())
                    entries.append('\tmap_script MAP_SCRIPT_ON_FRAME_TABLE, %s' % lab); tables[target.strip()] = (lab, [])
                else:
                    idx = ev_index(target)
                    if idx is None: continue
                    if kind in ('OnTransition', 'OnWarpInto', 'OnResume'):
                        # HGSS runs these before the map's people are placed; Emerald's ON_RESUME runs after,
                        # so OnResume also runs on transition (and still on resume, e.g. after a battle)
                        transition.append(ms.script_label(idx))
                    if kind == 'OnResume': entries.append('\tmap_script MAP_SCRIPT_ON_RESUME, %s' % ms.script_label(idx))
                    if kind == 'OnLoad': entries.append('\tmap_script MAP_SCRIPT_ON_LOAD, %s' % ms.script_label(idx))
                continue
            m = re.match(r'(\w+):$', line)
            if m: cur = m.group(1); continue
            m = re.match(r'InitScriptGoToIfEqual\s+(\w+),\s*(\w+),\s*(.*)', line)
            if m and cur in tables:
                idx = ev_index(m.group(3))
                if idx is not None:
                    tables[cur][1].append('\tmap_script_2 %s, %s, %s' % (ms.var(m.group(1)), m.group(2), ms.script_label(idx)))
        for lab, rows in tables.values():
            extra += ['%s:' % lab] + rows + ['\t.2byte 0', '']
        for t in transition:      # the engine runs every ON_TRANSITION entry (see hgspecials.install)
            entries.append('\tmap_script MAP_SCRIPT_ON_TRANSITION, %s' % t)
        return entries, extra

    def build_map(self, const, origin, transform=None, generated=None):
        """origin: HGSS coordinate of the map's top-left; transform: optional (x, y) -> (x, y) for template rooms."""
        f = glob.glob(PHG + '/files/fielddata/eventdata/zone_event/*_%s.json' % self.CODE.get(const, '#'))
        ev = json.load(open(f[0])) if f else {}
        sf, hf, mb = self.files(const)
        name = self.emit.map_name(const)
        objs = ev.get('objects', [])
        map_consts = {k: self.emit.map_const(k) for k in (generated or [])}
        ms = hgscript.MapScripts(name, sf, mb, [o['id'] for o in objs], origin, map_consts, self.alloc, hgdata.item, self.trainers)
        pos = (lambda x, y: transform(x - origin[0], y - origin[1])) if transform else (lambda x, y: (x - origin[0], y - origin[1]))
        extra_scripts = []
        object_events = []
        for i, o in enumerate(objs):
            x, y = pos(o['x'], o['z'])
            sid = str(o['scriptId'])
            gfx = sprites.emerald(o['spriteId'])
            script, ttype, sight = '0x0', 'TRAINER_TYPE_NONE', '0'
            if sid.startswith('std_trainer'):
                m = re.search(r'\((TRAINER_\w+)\)', sid)
                t = self.trainers.get(m.group(1)) if m else None
                if t:
                    lab = '%s_EventScript_Trainer%d' % (name, i)
                    battle = 'trainerbattle_double' if t['double'] else 'trainerbattle_single'
                    extra_scripts += ['%s::' % lab,
                                      '\t%s %s, %s, %s%s' % (battle, t['const'], t['intro'], t['defeat'],
                                                             ', gText_JohtoNeedTwoMons' if t['double'] else ''),
                                      '\tmsgbox %s, MSGBOX_AUTOCLOSE' % t['after'], '\tend', '']
                    script, ttype, sight = lab, 'TRAINER_TYPE_NORMAL', str(max(1, o.get('param0', 3)))
            elif sid.startswith('std_itemball_'):
                lab = '%s_EventScript_Item%d' % (name, i)
                extra_scripts += ['%s::' % lab, '\tfinditem %s' % item_from_label(sid, 'std_itemball_'), '\tend', '']
                script = lab
            elif sid == 'std_field_cut': script = 'EventScript_CutTree'
            elif sid == 'std_field_rock_smash': script = 'EventScript_RockSmash'
            elif sid == 'std_field_strength': script = 'EventScript_StrengthBoulder'
            elif sid == 'std_nurse_joy':
                lab = '%s_EventScript_Nurse%d' % (name, i)
                extra_scripts += ['%s::' % lab, '\tsetvar VAR_0x800B, %d' % (i + 1), '\tcall Common_EventScript_PkmnCenterNurse',
                                  '\twaitmessage', '\twaitbuttonpress', '\trelease', '\tend', '']
                script = lab
            elif ev_index(sid) is not None:
                script = ms.script_label(ev_index(sid))
            object_events.append({
                'local_id': 'LOCALID_%s_%d' % (name.upper(), i + 1) if False else None,
                'graphics_id': gfx, 'x': x, 'y': y, 'elevation': 3,
                'movement_type': sprites.movement(o['movement'], o['facingDirection']),
                'movement_range_x': o.get('xRange', 0), 'movement_range_y': o.get('yRange', 0),
                'trainer_type': ttype, 'trainer_sight_or_berry_tree_id': sight, 'script': script,
                'flag': self.alloc.flag.get(o['eventFlag'], '0') if o.get('eventFlag') else '0'})
            if object_events[-1]['local_id'] is None: del object_events[-1]['local_id']
        bg_events = []
        for b in ev.get('bgs', []):
            x, y = pos(b['x'], b['z']); sid = str(b['scriptId'])
            if sid.startswith('std_hiddenitem_'):
                bg_events.append({'type': 'hidden_item', 'x': x, 'y': y, 'elevation': 3,
                                  'item': item_from_label(sid, 'std_hiddenitem_'), 'flag': hidden_flag(sid)})
            elif ev_index(sid) is not None:
                bg_events.append({'type': 'sign', 'x': x, 'y': y, 'elevation': 0,
                                  'player_facing_dir': 'BG_EVENT_PLAYER_FACING_ANY', 'script': ms.script_label(ev_index(sid))})
        coord_events = []
        for c in ev.get('coords', []):
            idx = ev_index(c['scriptId'])
            if idx is None: continue
            for dx in range(c.get('w', 1)):
                for dy in range(c.get('h', 1)):
                    x, y = pos(c['x'] + dx, c['z'] + dy)
                    coord_events.append({'type': 'trigger', 'x': x, 'y': y, 'elevation': 3, 'var': ms.var(c['var']),
                                         'var_value': str(c['val']), 'script': ms.script_label(idx)})
        entries, tables = self.header(ms, hf)
        body = ms.render(entries) if sf else '%s_MapScripts::\n\t.byte 0\n' % name
        body += '\n' + '\n'.join(tables) + '\n' + '\n'.join(extra_scripts) + '\n'
        # every script an event points at must exist, even when HGSS had none there
        defined = set(re.findall(r'^(\w+)::?', body, re.M))
        stubs = [e['script'] for e in object_events + bg_events if e.get('script') and e['script'] != '0x0'
                 and e['script'].startswith(name) and e['script'] not in defined]
        stubs += [e['script'] for e in coord_events if e['script'] not in defined]
        for s in sorted(set(stubs)): body += '%s::\n\tend\n' % s
        self.unsupported.update(ms.unsupported)
        return object_events, bg_events, coord_events, body

def write_alloc(builder):
    builder.alloc.write()

COMMON = '''gText_JohtoNeedTwoMons::
\t.string "You need two Pokémon for a\\n"
\t.string "double battle.$"
'''

def write_common():
    open(PE + '/data/scripts/hg_common.inc', 'w').write(COMMON)
    p = PE + '/data/event_scripts.s'; s = open(p).read()
    if 'hg_common.inc' not in s:
        s = s.replace('\t.include "data/scripts/hg_trainer_texts.inc"', '\t.include "data/scripts/hg_trainer_texts.inc"\n\t.include "data/scripts/hg_common.inc"', 1)
        open(p, 'w').write(s)
