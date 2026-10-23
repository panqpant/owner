"""Translate HGSS (pokeheartgold) map scripts into Emerald (pokeemerald) event scripts."""
import re, os, glob, json, sys, collections
sys.path.insert(0, os.path.dirname(__file__))
import hgtext, hgdata
PHG = hgtext.PHG

DIRS = {'North': 'up', 'South': 'down', 'East': 'right', 'West': 'left'}
DIR_CONST = {'DIR_NORTH': 'DIR_NORTH', 'DIR_SOUTH': 'DIR_SOUTH', 'DIR_EAST': 'DIR_EAST', 'DIR_WEST': 'DIR_WEST',
             '0': 'DIR_NORTH', '1': 'DIR_SOUTH', '2': 'DIR_WEST', '3': 'DIR_EAST'}

# movement commands: HGSS name pattern -> Emerald movement macro (direction filled in)
MOVES = [
    (r'WalkNormal(North|South|East|West)', 'walk_%s'), (r'WalkSlow(North|South|East|West)', 'walk_slow_%s'),
    (r'WalkSlightlyFast(North|South|East|West)', 'walk_fast_%s'), (r'WalkFast(North|South|East|West)', 'walk_fast_%s'),
    (r'WalkFaster(North|South|East|West)', 'walk_faster_%s'), (r'Run(North|South|East|West)', 'walk_faster_%s'),
    (r'Face(North|South|East|West)', 'face_%s'),
    (r'WalkOnSpotNormal(North|South|East|West)', 'walk_in_place_%s'), (r'WalkOnSpotFast(North|South|East|West)', 'walk_in_place_fast_%s'),
    (r'WalkOnSpotFaster(North|South|East|West)', 'walk_in_place_faster_%s'), (r'WalkOnSpotSlow(North|South|East|West)', 'walk_in_place_slow_%s'),
    (r'JumpFar(North|South|East|West)', 'jump_2_%s'), (r'JumpNear(?:Fast)?(North|South|East|West)', 'jump_%s'),
    (r'JumpOnSpot(?:Fast|Slow)?(North|South|East|West)', 'jump_in_place_%s'),
]
MOVE_SIMPLE = {'EmoteExclamationMark': 'emote_exclamation_mark', 'EmoteQuestionMark': 'emote_question_mark',
               'SetInvisible': 'set_invisible', 'SetVisible': 'set_visible', 'LockDir': 'lock_facing_direction',
               'UnlockDir': 'unlock_facing_direction', 'Delay1': 'delay_1', 'Delay2': 'delay_2', 'Delay4': 'delay_4',
               'Delay8': 'delay_8', 'Delay15': 'delay_16', 'Delay16': 'delay_16', 'Delay32': 'delay_16\n\tdelay_16',
               'EndMovement': 'step_end'}

def is_move(cmd):
    return cmd in MOVE_SIMPLE or any(re.fullmatch(p, cmd) for p, _ in MOVES)

def move_line(cmd, args):
    n = int(args[0]) if args and args[0].isdigit() else 1
    if cmd in MOVE_SIMPLE: return [MOVE_SIMPLE[cmd]] * (1 if cmd == 'EndMovement' else n)
    for p, fmt in MOVES:
        m = re.fullmatch(p, cmd)
        if m: return [fmt % DIRS[m.group(1)]] * n
    return []

SE = {'SEQ_SE_DP_SELECT': 'SE_SELECT', 'SEQ_SE_DP_DOOR': 'SE_DOOR', 'SEQ_SE_DP_KAIDAN2': 'SE_EXIT', 'SEQ_SE_DP_WALL_HIT': 'SE_WALL_HIT',
      'SEQ_SE_GS_PHONE0': 'SE_POKENAV_CALL', 'SEQ_SE_DP_PC_ON': 'SE_PC_ON', 'SEQ_SE_DP_PC_LOGIN': 'SE_PC_LOGIN',
      'SEQ_SE_DP_PC_LOGOFF': 'SE_PC_OFF', 'SEQ_SE_DP_KI_GASYAN': 'SE_SELECT', 'SEQ_SE_DP_BOX03': 'SE_SELECT'}
FANFARE = {'SEQ_ME_ITEM': 'MUS_OBTAIN_ITEM', 'SEQ_ME_KEYITEM': 'MUS_OBTAIN_ITEM', 'SEQ_ME_POKEGET': 'MUS_OBTAIN_ITEM',
           'SEQ_ME_BADGE': 'MUS_OBTAIN_BADGE', 'SEQ_ME_WAZA': 'MUS_OBTAIN_TMHM', 'SEQ_ME_ASA': 'MUS_HEAL',
           'SEQ_ME_KINOMI': 'MUS_OBTAIN_BERRY', 'SEQ_ME_ACCE': 'MUS_OBTAIN_ITEM', 'SEQ_ME_POKEGEAR_REGIST': 'MUS_REGISTER_MATCH_CALL'}

CMP = {'Eq': 'eq', 'Ne': 'ne', 'Lt': 'lt', 'Gt': 'gt', 'Le': 'le', 'Ge': 'ge'}

class Unsupported(Exception): pass

def _defines(paths):
    out = {}
    for p in paths:
        for f in glob.glob(p):
            for m in re.finditer(r'#define\s+([A-Z][A-Z0-9_]+)\s+\(?\s*(-?0x[0-9A-Fa-f]+|-?\d+)\s*\)?', open(f, errors='ignore').read()):
                out.setdefault(m.group(1), m.group(2))
    return out
def _enums(paths):
    out = {}
    for p in paths:
        for f in glob.glob(p, recursive=True):
            for body in re.findall(r'enum\s*\w*\s*\{(.*?)\}', open(f, errors='ignore').read(), re.S):
                n = 0
                for item in body.split(','):
                    item = re.sub(r'//.*|/\*.*?\*/', '', item, flags=re.S).strip()
                    m = re.match(r'([A-Z][A-Z0-9_]+)\s*(?:=\s*(-?0x[0-9A-Fa-f]+|-?\d+))?$', item)
                    if not m: continue
                    if m.group(2): n = int(m.group(2), 0)
                    out.setdefault(m.group(1), str(n)); n += 1
    return out
HG_CONST = _defines([PHG + '/include/constants/*.h']); HG_CONST.update({k: v for k, v in _enums([PHG + '/include/**/*.h']).items() if k not in HG_CONST})
EM_CONST = set(_defines([hgtext.PE + '/include/constants/*.h'])) | set(_enums([hgtext.PE + '/include/**/*.h']))

def parse(path):
    """-> (script order, {label: [(cmd, [args])]}, label order)"""
    order, body, labels, cur = [], {}, [], None
    src = open(path).read()
    aliases = dict(re.findall(r'^#define\s+(\w+)\s+(\S+)', src, re.M))     # script-local names
    for raw in src.split('\n'):
        line = raw.split('//')[0].rstrip()
        if aliases and not line.startswith('#'):
            line = re.sub(r'\b(\w+)\b', lambda m: aliases.get(m.group(1), m.group(1)), line)
        if not line.strip() or line.strip().startswith(('#', '.balign', '.align', '.include')): continue
        m = re.match(r'^(\w+):\s*$', line)
        if m:
            cur = m.group(1); body[cur] = []; labels.append(cur); continue
        parts = line.strip().split(None, 1)
        cmd = parts[0]; args = [a.strip() for a in parts[1].split(',')] if len(parts) > 1 else []
        if cmd == 'ScrDef': order.append(args[0]); continue
        if cmd == 'ScrDefEnd': continue
        if cur is not None: body[cur].append((cmd, args))
    return order, body, labels

class MapScripts:
    def __init__(self, emname, script_file, msg_bank, objects, origin, map_consts, alloc, items, trainers):
        self.em = emname; self.msgs = hgtext.bank(msg_bank) if msg_bank else []
        self.order, self.body, self.labels = parse(script_file) if script_file else ([], {}, [])
        self.objects = objects                    # HGSS person ids in order
        self.ox, self.oy = origin
        self.map_consts = map_consts              # HGSS map const -> Emerald map const (generated maps only)
        self.A = alloc; self.items = items; self.trainers = trainers
        self.texts = collections.OrderedDict()    # label -> lines
        self.out = []; self.n_local = 0; self.unsupported = collections.Counter()
        self.buffers = {}

    # ---- naming ------------------------------------------------------------
    def L(self, hg_label): return '%s_%s' % (self.em, hg_label.lstrip('_'))
    def script_label(self, idx): return '%s_EventScript_%d' % (self.em, idx)
    def new_local(self):
        self.n_local += 1; return '%s_Local_%d' % (self.em, self.n_local)
    def person(self, a):
        if a in ('obj_player', '255'): return 'OBJ_EVENT_ID_PLAYER'
        if a in self.objects: return str(self.objects.index(a) + 1)
        if a.isdigit(): return str(int(a) + 1)
        return None
    def var(self, a):
        if a.startswith('VAR_'): return self.A.var.get(a, 'VAR_TEMP_F')
        return a
    def flag(self, a):
        if a.startswith('FLAG_'): return self.A.flag.get(a, '0')
        return a
    def val(self, a):
        if a.startswith('VAR_'): return self.var(a)
        if a.startswith('FLAG_'): return self.flag(a)
        if a.startswith('DIR_'): return DIR_CONST.get(a, a)
        if a.startswith('ITEM_'): return self.items(a)
        if a.startswith('SPECIES_'): return hgdata.species(a)
        if re.fullmatch(r'-?\d+|0x[0-9A-Fa-f]+', a): return a
        # an HGSS-only symbolic constant: use its HGSS value
        if a not in EM_CONST and a in HG_CONST: return HG_CONST[a]
        if re.fullmatch(r'[A-Z][A-Z0-9_]+', a) and a not in EM_CONST: return '0'
        return a
    def text(self, msg_ref):
        m = re.search(r'_(\d+)$', msg_ref)
        idx = int(m.group(1)) if m else int(msg_ref) if msg_ref.isdigit() else 0
        raw = self.msgs[idx] if idx < len(self.msgs) else ''
        key = (idx, tuple(sorted(self.buffers.items())))
        label = '%s_Text_%d' % (self.em, idx) if not self.buffers or self.buffers == {0: '{PLAYER}'} else \
                '%s_Text_%d_%d' % (self.em, idx, abs(hash(key)) % 1000)
        if label not in self.texts:
            self.texts[label] = hgtext.to_strings(hgtext.convert(raw, self.buffers))
        waits = raw.rstrip().endswith(('\r', '\f'))
        return label, waits

    def coord(self, a, origin, scratch):
        """An HGSS coordinate (number or variable) as a map-local value; variables are converted at runtime."""
        if re.fullmatch(r'-?\d+', a): return str(int(a) - origin)
        self.emit('copyvar %s, %s' % (scratch, self.var(a)))
        if origin: self.emit('subvar %s, %d' % (scratch, origin))
        return scratch

    # ---- emission -------------------------------------------------------------
    def emit(self, s):
        if not s.startswith('@'):
            # any HGSS variable/flag name that reached the output raw gets its Emerald slot
            done = self.A.emerald_names()          # already translated, keep as is
            s = re.sub(r'\bVAR_[A-Za-z0-9_]+\b', lambda m: m.group(0) if m.group(0) in EM_CONST or m.group(0) in done else self.var(m.group(0)), s)
            s = re.sub(r'\bFLAG_[A-Za-z0-9_]+\b', lambda m: m.group(0) if m.group(0) in EM_CONST or m.group(0) in done else self.flag(m.group(0)), s)
        self.out.append('\t' + s)

    def msg(self, ref, wait_button_if_marked=True):
        label, waits = self.text(ref)
        self.emit('message %s' % label); self.emit('waitmessage')
        if waits: self.emit('waitbuttonpress')

    def translate_cmd(self, cmd, a):
        E = self.emit
        if cmd == 'End': E('end')
        elif cmd == 'Return': E('return')
        elif cmd == 'GoTo': E('goto %s' % self.L(a[0]))
        elif cmd == 'Call': E('call %s' % self.L(a[0]))
        elif cmd in ('Compare', 'CompareVarToValue', 'CompareVarToVar'): E('compare %s, %s' % (self.var(a[0]), self.val(a[1])))
        elif re.fullmatch(r'(GoTo|Call)If(Eq|Ne|Lt|Gt|Le|Ge)', cmd):
            k, c = re.fullmatch(r'(GoTo|Call)If(Eq|Ne|Lt|Gt|Le|Ge)', cmd).groups()
            E('%s_if_%s %s' % ('goto' if k == 'GoTo' else 'call', CMP[c], self.L(a[0])))
        elif cmd == 'GoToIf':
            c = {'1': 'eq', 'eq': 'eq', '5': 'ne', 'ne': 'ne', '0': 'lt', 'lt': 'lt', '2': 'gt', 'gt': 'gt', '3': 'le', 'le': 'le', '4': 'ge', 'ge': 'ge'}.get(a[0], 'eq')
            E('goto_if_%s %s' % (c, self.L(a[1])))
        elif cmd in ('GoToIfSet', 'GoToIfUnset', 'CallIfSet', 'CallIfUnset'):
            k = 'goto' if cmd.startswith('GoTo') else 'call'; s = 'set' if cmd.endswith('Set') and not cmd.endswith('Unset') else 'unset'
            E('%s_if_%s %s, %s' % (k, s, self.flag(a[0]), self.L(a[1])))
        elif cmd == 'Switch': E('copyvar VAR_0x8008, %s' % self.var(a[0]))
        elif cmd == 'Case': E('goto_if_eq VAR_0x8008, %s, %s' % (self.val(a[0]), self.L(a[1])))
        elif cmd == 'SetVar': E('setvar %s, %s' % (self.var(a[0]), self.val(a[1])))
        elif cmd in ('CopyVar', 'SetOrCopyVar'):
            E(('copyvar %s, %s' if a[1].startswith('VAR_') else 'setvar %s, %s') % (self.var(a[0]), self.val(a[1])))
        elif cmd == 'AddVar': E('addvar %s, %s' % (self.var(a[0]), self.val(a[1])))
        elif cmd == 'SubVar': E('subvar %s, %s' % (self.var(a[0]), self.val(a[1])))
        elif cmd == 'SetFlag': E('setflag %s' % self.flag(a[0]))
        elif cmd == 'ClearFlag': E('clearflag %s' % self.flag(a[0]))
        elif cmd in ('LockAll',): E('lockall')
        elif cmd in ('ReleaseAll',): E('releaseall')
        elif cmd == 'Lock': E('lock')
        elif cmd == 'Release': E('release')
        elif cmd == 'FacePlayer': E('faceplayer')
        elif cmd in ('NPCMsg', 'NonNPCMsg', 'NonNPCMsgVar', 'NPCMsgVar', 'TrainerMessage'):
            self.msg(a[-1] if cmd == 'TrainerMessage' else a[0])
        elif cmd == 'SimpleNPCMsg':
            E('lock'); E('faceplayer'); self.msg(a[0]); E('waitbuttonpress'); E('closemessage'); E('release')
        elif cmd == 'GenderMsgBox':
            f, done = self.new_local(), self.new_local()
            E('checkplayergender'); E('goto_if_eq VAR_RESULT, FEMALE, %s' % f)
            self.msg(a[0]); E('goto %s' % done)
            self.out.append('%s:' % f); self.msg(a[1]); self.out.append('%s:' % done)
        elif cmd in ('WaitButton', 'WaitABPress', 'WaitButtonOrDelay', 'WaitABPressTime'): E('waitbuttonpress')
        elif cmd in ('CloseMsg', 'HoldMsg'): E('closemessage')
        elif cmd == 'ApplyMovement':
            who = self.person(a[0])
            if who is None: return
            E('applymovement %s, %s' % (who, self.L(a[1])))
        elif cmd == 'WaitMovement': E('waitmovement 0')
        elif cmd == 'PlaySE': E('playse %s' % SE.get(a[0], 'SE_SELECT'))
        elif cmd == 'WaitSE': E('waitse')
        elif cmd == 'PlayFanfare': E('playfanfare %s' % FANFARE.get(a[0], 'MUS_OBTAIN_ITEM'))
        elif cmd == 'WaitFanfare': E('waitfanfare')
        elif cmd == 'PlayCry': E('playmoncry %s, CRY_MODE_NORMAL' % self.val(a[0]))
        elif cmd == 'WaitCry': E('waitmoncry')
        elif cmd == 'FadeScreen':          # FadeScreen speed, frames, direction (0 out / 1 in), colour
            E('fadescreen %s' % ('FADE_TO_BLACK' if len(a) > 2 and a[2] == '0' else 'FADE_FROM_BLACK'))
        elif cmd == 'WaitFade': pass
        elif cmd in ('Wait',): E('delay %s' % a[0])
        elif cmd == 'HidePerson':
            who = self.person(a[0])
            if who: E('removeobject %s' % who)
        elif cmd == 'ShowPerson':
            who = self.person(a[0])
            if who: E('addobject %s' % who)
        elif cmd == 'MovePersonFacing':
            who = self.person(a[0])
            if who:
                x, z = self.coord(a[1], self.ox, 'VAR_0x800A'), self.coord(a[3], self.oy, 'VAR_0x800B')
                E('setobjectxyperm %s, %s, %s' % (who, x, z))
                E('turnobject %s, %s' % (who, DIR_CONST.get(a[4], 'DIR_SOUTH')))
        elif cmd == 'MovePerson':
            who = self.person(a[0])
            if who: E('setobjectxyperm %s, %s, %s' % (who, self.coord(a[1], self.ox, 'VAR_0x800A'), self.coord(a[3], self.oy, 'VAR_0x800B')))
        elif cmd == 'Warp':
            dest = self.map_consts.get(a[0])
            if dest: E('warp %s, %s, %s' % (dest, a[2] if len(a) > 2 else 0, a[3] if len(a) > 3 else 0))
        elif cmd == 'BufferPlayersName': self.buffers[int(a[0])] = '{PLAYER}'
        elif cmd == 'BufferRivalsName': self.buffers[int(a[0])] = '{RIVAL}'
        elif cmd in ('BufferItemName', 'BufferItemNamePlural', 'BufferItemNameIndef'):
            slot = min(int(a[0]), 2); self.buffers[int(a[0])] = '{STR_VAR_%d}' % (slot + 1)
            E('bufferitemname STR_VAR_%d, %s' % (slot + 1, self.val(a[1])))
        elif cmd in ('BufferMonSpeciesName', 'BufferPartyMonSpeciesName'):
            slot = min(int(a[0]), 2); self.buffers[int(a[0])] = '{STR_VAR_%d}' % (slot + 1)
            E('getpartymonname STR_VAR_%d, %s' % (slot + 1, a[1] if len(a) > 1 else 0) if False else
              'bufferpartymonnick STR_VAR_%d, %s' % (slot + 1, a[1] if len(a) > 1 else 0))
        elif cmd == 'BufferSpeciesName':
            slot = min(int(a[0]), 2); self.buffers[int(a[0])] = '{STR_VAR_%d}' % (slot + 1)
            E('bufferspeciesname STR_VAR_%d, %s' % (slot + 1, self.val(a[1])))
        elif cmd == 'BufferInt':
            slot = min(int(a[0]), 2); self.buffers[int(a[0])] = '{STR_VAR_%d}' % (slot + 1)
            E('buffernumberstring STR_VAR_%d, %s' % (slot + 1, self.val(a[1])))
        elif cmd == 'GiveItem': E('additem %s, %s' % (self.val(a[0]), self.val(a[1])))
        elif cmd == 'TakeItem': E('removeitem %s, %s' % (self.val(a[0]), self.val(a[1])))
        elif cmd == 'HasItem': E('checkitem %s, %s' % (self.val(a[0]), self.val(a[1]))); E('copyvar %s, VAR_RESULT' % self.var(a[2]))
        elif cmd == 'HasSpaceForItem': E('checkitemspace %s, %s' % (self.val(a[0]), self.val(a[1]))); E('copyvar %s, VAR_RESULT' % self.var(a[2]))
        elif cmd == 'CallStd': self.std(a[0])
        elif cmd in ('DirectionSignpostEx', 'TrainerTipsEx', 'DirectionSignpost', 'TrainerTips', 'MapSign'):
            self.msg(a[-1] if cmd.endswith('Ex') else a[0]); E('waitbuttonpress'); E('closemessage')
        elif cmd == 'ItemVars':
            E('setvar VAR_0x8004, %s' % self.val(a[0])); E('setvar VAR_0x8005, %s' % self.val(a[1]))
        elif cmd == 'GoToIfNoItemSpace':
            E('checkitemspace %s, %s' % (self.val(a[0]), self.val(a[1]))); E('goto_if_eq VAR_RESULT, FALSE, %s' % self.L(a[2]))
        elif cmd == 'GiveItemNoCheck':
            E('giveitem %s, %s' % (self.val(a[0]), self.val(a[1])))
        elif cmd == 'GiveMon': E('givemon %s, %s, %s' % (self.val(a[0]), self.val(a[1]), self.val(a[2]) if len(a) > 2 and a[2] != '0' else 'ITEM_NONE'))
        elif cmd == 'WildBattle': E('setwildbattle %s, %s' % (self.val(a[0]), self.val(a[1]))); E('dowildbattle')
        elif cmd == 'TrainerBattle':
            t = self.trainers.get(a[0])
            if t: E('trainerbattle_no_intro %s, %s' % (t['const'], t['defeat']))
        elif cmd == 'CheckBattleWon': E('setvar %s, 1' % self.var(a[0]))
        elif cmd == 'WhiteOut': pass
        elif cmd == 'HealParty': E('special HealPlayerParty')
        elif cmd == 'CheckBadge':
            E('setvar %s, 0' % self.var(a[1])); skip = self.new_local()
            E('goto_if_unset FLAG_BADGE0%d_GET, %s' % (min(int(a[0]) % 8 + 1, 8) if a[0].isdigit() else 1, skip))
            E('setvar %s, 1' % self.var(a[1])); self.out.append('%s:' % skip)
        elif cmd == 'GiveBadge': E('setflag FLAG_BADGE0%d_GET' % (int(a[0]) % 8 + 1 if a[0].isdigit() else 1))
        elif cmd == 'GetPlayerFacing': E('specialvar %s, HGSS_GetPlayerFacing' % self.var(a[0]))
        elif cmd == 'GetPlayerCoords': E('getplayerxy %s, %s' % (self.var(a[0]), self.var(a[1])))
        elif cmd == 'GetWeekday': E('specialvar %s, HGSS_GetWeekday' % self.var(a[0]))
        elif cmd == 'Random': E('random %s' % self.val(a[1])); E('copyvar %s, VAR_RESULT' % self.var(a[0]))
        elif cmd == 'GetPartyCount': E('specialvar %s, CalculatePlayerPartyCount' % self.var(a[0]))
        elif cmd == 'GetPlayerGender': E('checkplayergender'); E('copyvar %s, VAR_RESULT' % self.var(a[0]))
        elif cmd == 'ChooseStarter': E('special ChooseStarter'); E('waitstate')
        elif cmd == 'StopBGM': E('fadedefaultbgm')
        elif cmd in ('PlayBGM', 'TempBGM'): pass
        elif cmd == 'ScreenShake': E('setvar VAR_0x8004, 2'); E('setvar VAR_0x8005, 2'); E('setvar VAR_0x8006, 8'); E('setvar VAR_0x8007, 3'); E('special ShakeCamera'); E('waitstate')
        elif cmd in ('SetObjectEventVisible', 'MakeObjectVisible'): pass
        elif cmd in ('TouchscreenMenuShow', 'TouchscreenMenuHide', 'ToggleFollowingPokemonMovement', 'FollowingPokemonMovement',
                     'WaitFollowingPokemonMovement', 'ScriptOverlayCmd', 'RemoveWaitingIcon', 'AddWaitingIcon',
                     'SetFollowMonInhibitState', 'GetFriendSprite', 'Noop', 'NopVar490', 'InitScriptEnd', 'RestoreOverworld'):
            pass
        else:
            self.unsupported[cmd] += 1
            E('@ HGSS %s %s' % (cmd, ', '.join(a)))

    def std(self, name):
        E = self.emit
        if name == 'std_give_item_verbose' or name == 'std_obtain_item_verbose':
            E('copyvar VAR_0x8000, VAR_0x8004'); E('copyvar VAR_0x8001, VAR_0x8005'); E('callstd STD_OBTAIN_ITEM')
        elif name == 'std_bag_is_full': E('msgbox gText_TooBadBagIsFull, MSGBOX_DEFAULT')
        elif name == 'std_nurse_joy': E('call Common_EventScript_PkmnCenterNurse')
        else:
            self.unsupported['CallStd ' + name] += 1; E('@ HGSS CallStd %s' % name)

    def translate(self):
        movement_labels = {l for l, b in self.body.items() if b and is_move(b[0][0])}
        for lab in self.labels:
            b = self.body[lab]
            if lab in movement_labels:
                self.out.append('%s:' % self.L(lab))
                for cmd, a in b:
                    for m in move_line(cmd, a): self.out.append('\t' + m)
                continue
            # a ScrDef entry point gets its stable public label too
            if lab in self.order:
                self.out.append('%s::' % self.script_label(self.order.index(lab)))
            self.out.append('%s:' % self.L(lab))
            for cmd, a in b:
                mark = len(self.out)
                try:
                    self.translate_cmd(cmd, a)
                except (IndexError, ValueError, KeyError):
                    # an argument layout this translator doesn't know: leave a marked stub, keep going
                    del self.out[mark:]
                    self.unsupported[cmd + ' (args)'] += 1
                    self.emit('@ HGSS %s %s' % (cmd, ', '.join(a)))
        return self.out

    def render(self, header=None):
        lines = list(self.translate())
        hdr = ['%s_MapScripts::' % self.em]
        if header: hdr += header
        hdr.append('\t.byte 0')
        txt = []
        for label, strs in self.texts.items():
            txt.append('%s:' % label); txt += strs; txt.append('')
        return '\n'.join(hdr + [''] + lines + [''] + txt) + '\n'
