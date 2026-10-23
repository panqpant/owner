"""Replace Emerald's trainer table with HGSS's 738 trainers (same numbers as in HGSS), with parties and lines."""
import json, re, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import hgdata, hgtext
PHG, PE = hgtext.PHG, hgtext.PE

# HGSS class -> (Emerald class slot, battle sprite, female?, new display name for the slot or None)
CLASSES = {
 'ACE_TRAINER_M': ('COOLTRAINER', 'COOLTRAINER_M', 0, 'ACE TRAINER'), 'ACE_TRAINER_F': ('COOLTRAINER', 'COOLTRAINER_F', 1, None),
 'BEAUTY': ('BEAUTY', 'BEAUTY', 1, None), 'BIKER': ('ARENA_TYCOON', 'CYCLING_TRIATHLETE_M', 0, 'BIKER'),
 'BIRD_KEEPER_GS': ('BIRD_KEEPER', 'BIRD_KEEPER', 0, None), 'BLACK_BELT': ('BLACK_BELT', 'BLACK_BELT', 0, None),
 'BOARDER': ('DOME_ACE', 'COOLTRAINER_M', 0, 'BOARDER'), 'BUG_CATCHER': ('BUG_CATCHER', 'BUG_CATCHER', 0, None),
 'BURGLAR': ('FACTORY_HEAD', 'RUIN_MANIAC', 0, 'BURGLAR'), 'CAMPER': ('CAMPER', 'CAMPER', 0, None),
 'CHAMPION': ('CHAMPION', 'CHAMPION_WALLACE', 0, None), 'DOUBLE_TEAM': ('SIS_AND_BRO', 'SIS_AND_BRO', 0, 'DOUBLE TEAM'),
 'ELDER': ('PALACE_MAVEN', 'EXPERT_M', 0, 'ELDER'),
 'ELITE_FOUR_WILL': ('ELITE_FOUR', 'ELITE_FOUR_SIDNEY', 0, None), 'ELITE_FOUR_KOGA': ('ELITE_FOUR', 'ELITE_FOUR_DRAKE', 0, None),
 'ELITE_FOUR_BRUNO': ('ELITE_FOUR', 'BLACK_BELT', 0, None), 'ELITE_FOUR_KAREN': ('ELITE_FOUR', 'ELITE_FOUR_PHOEBE', 1, None),
 'EXECUTIVE_ARCHER': ('AQUA_ADMIN', 'AQUA_ADMIN_M', 0, 'EXECUTIVE'), 'EXECUTIVE_ARIANA': ('AQUA_ADMIN', 'AQUA_ADMIN_F', 1, None),
 'EXECUTIVE_PROTON': ('MAGMA_ADMIN', 'MAGMA_ADMIN', 0, 'EXECUTIVE'), 'EXECUTIVE_PETREL': ('AQUA_ADMIN', 'AQUA_ADMIN_M', 0, None),
 'FIREBREATHER': ('KINDLER', 'KINDLER', 0, 'FIREBREATHER'), 'FISHERMAN': ('FISHERMAN', 'FISHERMAN', 0, None),
 'GENTLEMAN': ('GENTLEMAN', 'GENTLEMAN', 0, None), 'GUITARIST': ('GUITARIST', 'GUITARIST', 0, None), 'HIKER': ('HIKER', 'HIKER', 0, None),
 'JUGGLER': ('PIKE_QUEEN', 'POKEMANIAC', 0, 'JUGGLER'), 'KIMONO_GIRL': ('SALON_MAIDEN', 'AROMA_LADY', 1, 'KIMONO GIRL'),
 'LASS': ('LASS', 'LASS', 1, None), 'MEDIUM': ('HEX_MANIAC', 'HEX_MANIAC', 1, 'MEDIUM'), 'MYSTERY_MAN': ('EXPERT', 'EXPERT_M', 0, None),
 'PASSERBY': ('PKMN_TRAINER_2', 'COOLTRAINER_M', 0, None), 'PICNICKER': ('PICNICKER', 'PICNICKER', 1, None),
 'POKEFAN': ('POKEFAN', 'POKEFAN_F', 1, None), 'POKEFAN_M': ('POKEFAN', 'POKEFAN_M', 0, None), 'POKE_MANIAC': ('POKEMANIAC', 'POKEMANIAC', 0, 'POKé MANIAC'),
 'POLICEMAN': ('PYRAMID_KING', 'EXPERT_M', 0, 'POLICEMAN'), 'PSYCHIC_M': ('PSYCHIC', 'PSYCHIC_M', 0, None), 'RIVAL': ('RIVAL', 'BRENDAN', 0, None),
 'ROCKET_BOSS': ('MAGMA_LEADER', 'MAGMA_LEADER_MAXIE', 0, 'ROCKET BOSS'), 'SAGE': ('TRIATHLETE', 'EXPERT_M', 0, 'SAGE'),
 'SAILOR': ('SAILOR', 'SAILOR', 0, None), 'SCHOOL_KID_M': ('SCHOOL_KID', 'SCHOOL_KID_M', 0, None),
 'SCIENTIST_GS': ('WINSTRATE', 'POKEMANIAC', 0, 'SCIENTIST'), 'SKIER': ('TUBER_F', 'COOLTRAINER_F', 1, 'SKIER'),
 'SUPER_NERD': ('COLLECTOR', 'COLLECTOR', 0, 'SUPER NERD'), 'SWIMMER_F': ('SWIMMER_F', 'SWIMMER_F', 1, 'SWIMMER♀'),
 'SWIMMER_M': ('SWIMMER_M', 'SWIMMER_M', 0, 'SWIMMER♂'), 'TEACHER': ('LADY', 'LADY', 1, 'TEACHER'),
 'TEAM_ROCKET': ('TEAM_MAGMA', 'MAGMA_GRUNT_M', 0, 'TEAM ROCKET'), 'TEAM_ROCKET_F': ('TEAM_AQUA', 'MAGMA_GRUNT_F', 1, 'TEAM ROCKET'),
 'TWINS': ('TWINS', 'TWINS', 1, None), 'YOUNGSTER': ('YOUNGSTER', 'YOUNGSTER', 0, None), 'YOUNG_COUPLE': ('YOUNG_COUPLE', 'YOUNG_COUPLE', 0, None),
}
LEADER_PICS = {'FALKNER': ('BRAWLY', 0), 'BUGSY': ('WATTSON', 0), 'WHITNEY': ('FLANNERY', 1), 'MORTY': ('JUAN', 0),
               'CHUCK': ('NORMAN', 0), 'JASMINE': ('WINONA', 1), 'PRYCE': ('TATE_AND_LIZA', 0), 'CLAIR': ('ROXANNE', 1),
               'BROCK': ('BRAWLY', 0), 'MISTY': ('WINONA', 1), 'LT_SURGE': ('WATTSON', 0), 'ERIKA': ('ROXANNE', 1),
               'JANINE': ('FLANNERY', 1), 'SABRINA': ('PSYCHIC_F', 1), 'BLAINE': ('NORMAN', 0), 'BLUE': ('RS_BRENDAN', 0)}
PKMN_TRAINER_PICS = {'RED': 'RED', 'LANCE': 'CHAMPION_WALLACE', 'ETHAN': 'BRENDAN'}

def class_info(c):
    c = c.replace('TRAINERCLASS_', '')
    if c.startswith('LEADER_'):
        pic, f = LEADER_PICS.get(c[7:], ('ROXANNE', 1))
        return 'LEADER', ('LEADER_' + pic) if not pic.startswith(('PSYCHIC', 'RS_')) else pic, f, None
    if c.startswith('PKMN_TRAINER_'):
        return 'PKMN_TRAINER_1', PKMN_TRAINER_PICS.get(c[13:], 'COOLTRAINER_M'), 0, None
    return CLASSES.get(c, ('PKMN_TRAINER_1', 'COOLTRAINER_M', 0, None))

def load():
    d = json.load(open(PHG + '/files/poketool/trainer/trainers.json'))['trainers']
    names = {}
    for m in re.finditer(r'#define (TRAINER_\w+)\s+(\d+)', open(PHG + '/include/constants/trainers.h').read()):
        names.setdefault(int(m.group(2)), m.group(1))
    return d, names

def message(t, kind):
    for m in t['messages']:
        if m['type'] == kind:
            return m['message'].replace('\\n', '\n').replace('\\r', '\r').replace('\\f', '\f')
    return ''

def build():
    d, hgnames = load()
    em_ids = {}
    for m in re.finditer(r'#define (TRAINER_\w+)\s+(\d+)', open(PE + '/include/constants/opponents.h').read()):
        em_ids.setdefault(int(m.group(2)), m.group(1))
    parties, entries, texts, consts, renames = [], {}, [], [], {}
    info = {}
    for i, t in enumerate(d):
        if i == 0 or i not in em_ids: continue
        cls, pic, female, rename = class_info(t['class'])
        if rename: renames[cls] = rename
        name = re.sub(r'\{[^}]*\}', '', t['name']).strip().upper()[:10] or 'TRAINER'
        moves = any(p.get('moves') for p in t['party'])
        mons = []
        for p in t['party'] or [{'species': 'SPECIES_RATTATA', 'level': 5, 'difficulty': 0}]:
            ent = ['    .iv = %d,' % min(255, p.get('difficulty', 0)), '    .lvl = %d,' % p['level'],
                   '    .species = %s,' % hgdata.species(p['species'])]
            ent.append('    .heldItem = %s,' % hgdata.item(p.get('item', 'ITEM_NONE')))
            if moves:
                mv = [hgdata.move(m) for m in (p.get('moves') or [])][:4]
                mv += ['MOVE_NONE'] * (4 - len(mv))
                ent.append('    .moves = {%s}' % ', '.join(mv))
            mons.append('    {\n' + '\n'.join(ent) + '\n    }')
        kind = 'TrainerMonItemCustomMoves' if moves else 'TrainerMonItemDefaultMoves'
        macro = 'ITEM_CUSTOM_MOVES' if moves else 'ITEM_DEFAULT_MOVES'
        parties.append('static const struct %s sParty_HG_%d[] = {\n%s\n};\n' % (kind, i, ',\n'.join(mons)))
        items = [hgdata.item(x) for x in t['items']][:4]
        items = [x for x in items if x != 'ITEM_NONE'] + ['ITEM_NONE'] * (4 - len([x for x in items if x != 'ITEM_NONE']))
        entries[em_ids[i]] = ('    [%s] =\n    {\n        .trainerClass = TRAINER_CLASS_%s,\n'
            '        .encounterMusic_gender = %sTRAINER_ENCOUNTER_MUSIC_%s,\n        .trainerPic = TRAINER_PIC_%s,\n'
            '        .trainerName = _("%s"),\n        .items = {%s},\n        .doubleBattle = %s,\n'
            '        .aiFlags = AI_SCRIPT_CHECK_BAD_MOVE | AI_SCRIPT_TRY_TO_FAINT | AI_SCRIPT_CHECK_VIABILITY,\n'
            '        .party = %s(sParty_HG_%d),\n    },\n') % (em_ids[i], cls, 'F_TRAINER_FEMALE | ' if female else '',
            'FEMALE' if female else 'MALE', pic, name, ', '.join(items), 'TRUE' if t['double'] else 'FALSE', macro, i)
        hg = hgnames.get(i, 'TRAINER_%d' % i)
        consts.append('#define %-44s %d' % (hg.replace('TRAINER_', 'TRAINER_HG_', 1), i))
        lbl = 'HGTrainer_%d' % i
        for kind, suffix in (('TRMSG_INTRO', 'Intro'), ('TRMSG_LOSE', 'Defeat'), ('TRMSG_AFTER', 'After')):
            texts.append('%s_Text_%s:' % (lbl, suffix))
            texts += hgtext.to_strings(hgtext.convert(message(t, kind) or '...', {0: '{PLAYER}', 1: '{RIVAL}'}))
        info[hg] = {'id': i, 'const': hg.replace('TRAINER_', 'TRAINER_HG_', 1), 'intro': lbl + '_Text_Intro',
                    'defeat': lbl + '_Text_Defeat', 'after': lbl + '_Text_After', 'double': bool(t['double'])}
    return parties, entries, texts, consts, renames, info

def write():
    parties, entries, texts, consts, renames, info = build()
    p = PE + '/src/data/trainer_parties.h'; s = open(p).read()
    s = re.sub(r'\n// HGSS parties begin\n.*?// HGSS parties end\n', '\n', s, flags=re.S)
    s += '\n// HGSS parties begin\n' + '\n'.join(parties) + '// HGSS parties end\n'
    open(p, 'w').write(s)
    p = PE + '/src/data/trainers.h'; s = open(p).read()
    def sub(m):
        return entries.get(m.group(1), m.group(0))
    s = re.sub(r'    \[(TRAINER_\w+)\] =\n    \{.*?\n    \},\n', sub, s, flags=re.S)
    open(p, 'w').write(s)
    open(PE + '/include/constants/hg_trainers.h', 'w').write(
        '#ifndef GUARD_CONSTANTS_HG_TRAINERS_H\n#define GUARD_CONSTANTS_HG_TRAINERS_H\n\n'
        '// HGSS trainers keep their HGSS numbers (generated)\n' + '\n'.join(consts) + '\n\n#endif\n')
    p = PE + '/include/constants/opponents.h'; s = open(p).read()
    if 'hg_trainers.h' not in s:
        s = s.replace('#define GUARD_CONSTANTS_OPPONENTS_H', '#define GUARD_CONSTANTS_OPPONENTS_H\n\n#include "constants/hg_trainers.h"', 1)
        open(p, 'w').write(s)
    p = PE + '/src/data/text/trainer_class_names.h'; s = open(p).read()
    for cls, nm in renames.items():
        s = re.sub(r'(\[TRAINER_CLASS_%s\] = _\(")[^"]*("\))' % cls, lambda m: m.group(1) + nm + m.group(2), s)
    open(p, 'w').write(s)
    os.makedirs(PE + '/data/scripts', exist_ok=True)
    open(PE + '/data/scripts/hg_trainer_texts.inc', 'w').write('\n'.join(texts) + '\n')
    p = PE + '/data/event_scripts.s'; s = open(p).read()
    if 'hg_trainer_texts.inc' not in s:
        s = s.replace('\t.include "data/maps/LittlerootTown/scripts.inc"', '\t.include "data/scripts/hg_trainer_texts.inc"\n\t.include "data/maps/LittlerootTown/scripts.inc"', 1)
        open(p, 'w').write(s)
    json.dump(info, open(os.path.join(os.path.dirname(__file__), 'trainer_info.json'), 'w'))
    return info

if __name__ == '__main__':
    info = write(); print('trainers', len(info))
