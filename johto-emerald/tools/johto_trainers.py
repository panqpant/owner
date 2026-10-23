"""Rewrite Hoenn bosses into their Johto counterparts (HGSS teams, Emerald level curve)."""
import re, sys
root = sys.argv[1]

# (party array, new name, trainerPic or None, items or None, [(lvl, iv, species, item, [moves])])
M = lambda *m: ['MOVE_' + x for x in m]
BOSSES = {
 'Roxanne1': ('ROXANNE_1', 'FALKNER', None, [
   (12, 100, 'PIDGEY', 'NONE', M('TACKLE','MUD_SLAP','SAND_ATTACK','GUST')),
   (15, 200, 'PIDGEOTTO', 'ORAN_BERRY', M('TACKLE','SAND_ATTACK','GUST','QUICK_ATTACK'))]),
 'Brawly1': ('BRAWLY_1', 'BUGSY', None, [
   (16, 100, 'METAPOD', 'NONE', M('TACKLE','STRING_SHOT','HARDEN')),
   (16, 100, 'KAKUNA', 'NONE', M('POISON_STING','STRING_SHOT','HARDEN')),
   (19, 200, 'SCYTHER', 'SITRUS_BERRY', M('QUICK_ATTACK','LEER','FURY_CUTTER','FOCUS_ENERGY'))]),
 'Wattson1': ('WATTSON_1', 'WHITNEY', 'F', [
   (21, 150, 'CLEFAIRY', 'NONE', M('DOUBLE_SLAP','MIMIC','ENCORE','METRONOME')),
   (24, 200, 'MILTANK', 'SITRUS_BERRY', M('ROLLOUT','ATTRACT','STOMP','MILK_DRINK'))]),
 'Flannery1': ('FLANNERY_1', 'MORTY', 'M', [
   (25, 150, 'GASTLY', 'NONE', M('LICK','SPITE','MEAN_LOOK','CURSE')),
   (26, 150, 'HAUNTER', 'NONE', M('HYPNOSIS','MIMIC','CURSE','NIGHT_SHADE')),
   (27, 150, 'HAUNTER', 'NONE', M('LICK','HYPNOSIS','MEAN_LOOK','CURSE')),
   (29, 200, 'GENGAR', 'SITRUS_BERRY', M('HYPNOSIS','SHADOW_BALL','MEAN_LOOK','DREAM_EATER'))]),
 'Norman1': ('NORMAN_1', 'CHUCK', None, [
   (29, 150, 'PRIMEAPE', 'NONE', M('LEER','RAGE','KARATE_CHOP','FOCUS_ENERGY')),
   (31, 200, 'POLIWRATH', 'SITRUS_BERRY', M('HYPNOSIS','MIND_READER','SURF','DYNAMIC_PUNCH'))]),
 'Winona1': ('WINONA_1', 'JASMINE', None, [
   (30, 150, 'MAGNEMITE', 'NONE', M('THUNDERBOLT','SUPERSONIC','SONIC_BOOM','THUNDER_WAVE')),
   (30, 150, 'MAGNEMITE', 'NONE', M('THUNDERBOLT','SUPERSONIC','SONIC_BOOM','THUNDER_WAVE')),
   (33, 200, 'STEELIX', 'SITRUS_BERRY', M('SCREECH','IRON_TAIL','ROCK_THROW','BIND'))]),
 'TateAndLiza1': ('TATE_AND_LIZA_1', 'PRYCE', 'M', [
   (40, 150, 'SEEL', 'NONE', M('HEADBUTT','ICY_WIND','AURORA_BEAM','REST')),
   (41, 150, 'DEWGONG', 'NONE', M('HEADBUTT','ICY_WIND','AURORA_BEAM','REST')),
   (42, 200, 'PILOSWINE', 'SITRUS_BERRY', M('HAIL','BLIZZARD','AMNESIA','EARTHQUAKE'))]),
 'Juan1': ('JUAN_1', 'CLAIR', 'F', [
   (42, 150, 'DRAGONAIR', 'NONE', M('THUNDER_WAVE','DRAGON_BREATH','SLAM','SURF')),
   (42, 150, 'DRAGONAIR', 'NONE', M('THUNDER_WAVE','DRAGON_BREATH','SLAM','FLAMETHROWER')),
   (43, 150, 'DRAGONAIR', 'NONE', M('THUNDER_WAVE','DRAGON_BREATH','SLAM','ICE_BEAM')),
   (46, 250, 'KINGDRA', 'SITRUS_BERRY', M('SMOKESCREEN','HYDRO_PUMP','DRAGON_BREATH','HYPER_BEAM'))]),
 'Sidney': ('SIDNEY', 'WILL', None, [
   (46, 250, 'XATU', 'NONE', M('QUICK_ATTACK','FUTURE_SIGHT','CONFUSE_RAY','PSYCHIC')),
   (47, 250, 'JYNX', 'NONE', M('DOUBLE_SLAP','LOVELY_KISS','ICE_PUNCH','PSYCHIC')),
   (47, 250, 'EXEGGUTOR', 'NONE', M('REFLECT','LEECH_SEED','EGG_BOMB','PSYCHIC')),
   (48, 250, 'SLOWBRO', 'NONE', M('CURSE','AMNESIA','BODY_SLAM','PSYCHIC')),
   (49, 255, 'XATU', 'SITRUS_BERRY', M('QUICK_ATTACK','FUTURE_SIGHT','CONFUSE_RAY','PSYCHIC'))]),
 'Phoebe': ('PHOEBE', 'KOGA', 'M', [
   (48, 250, 'ARIADOS', 'NONE', M('DOUBLE_TEAM','SPIDER_WEB','BATON_PASS','GIGA_DRAIN')),
   (49, 250, 'VENOMOTH', 'NONE', M('SUPERSONIC','GUST','PSYCHIC','TOXIC')),
   (49, 250, 'FORRETRESS', 'NONE', M('PROTECT','SWIFT','EXPLOSION','SPIKES')),
   (50, 250, 'MUK', 'NONE', M('MINIMIZE','ACID_ARMOR','SLUDGE_BOMB','TOXIC')),
   (51, 255, 'CROBAT', 'SITRUS_BERRY', M('DOUBLE_TEAM','QUICK_ATTACK','WING_ATTACK','TOXIC'))]),
 'Glacia': ('GLACIA', 'BRUNO', 'M', [
   (50, 250, 'HITMONTOP', 'NONE', M('PURSUIT','QUICK_ATTACK','DIG','DETECT')),
   (51, 250, 'HITMONLEE', 'NONE', M('SWAGGER','DOUBLE_KICK','HI_JUMP_KICK','FORESIGHT')),
   (51, 250, 'HITMONCHAN', 'NONE', M('THUNDER_PUNCH','ICE_PUNCH','FIRE_PUNCH','MACH_PUNCH')),
   (51, 250, 'ONIX', 'NONE', M('BIND','EARTHQUAKE','SANDSTORM','ROCK_SLIDE')),
   (53, 255, 'MACHAMP', 'SITRUS_BERRY', M('ROCK_SLIDE','FORESIGHT','VITAL_THROW','CROSS_CHOP'))]),
 'Drake': ('DRAKE', 'KAREN', 'F', [
   (52, 250, 'UMBREON', 'NONE', M('SAND_ATTACK','CONFUSE_RAY','FAINT_ATTACK','MEAN_LOOK')),
   (52, 250, 'VILEPLUME', 'NONE', M('STUN_SPORE','ACID','MOONLIGHT','PETAL_DANCE')),
   (53, 250, 'MURKROW', 'NONE', M('QUICK_ATTACK','WHIRLWIND','PURSUIT','FAINT_ATTACK')),
   (54, 250, 'GENGAR', 'NONE', M('LICK','SPITE','CURSE','DESTINY_BOND')),
   (55, 255, 'HOUNDOOM', 'SITRUS_BERRY', M('ROAR','PURSUIT','FLAMETHROWER','CRUNCH'))]),
 'Wallace': ('WALLACE', 'LANCE', None, [
   (57, 255, 'GYARADOS', 'NONE', M('FLAIL','RAIN_DANCE','SURF','HYPER_BEAM')),
   (56, 255, 'DRAGONITE', 'NONE', M('THUNDER_WAVE','TWISTER','THUNDER','HYPER_BEAM')),
   (57, 255, 'CHARIZARD', 'NONE', M('FLAMETHROWER','WING_ATTACK','SLASH','HYPER_BEAM')),
   (57, 255, 'AERODACTYL', 'NONE', M('WING_ATTACK','ANCIENT_POWER','ROCK_SLIDE','HYPER_BEAM')),
   (56, 255, 'DRAGONITE', 'NONE', M('THUNDER_WAVE','TWISTER','BLIZZARD','HYPER_BEAM')),
   (58, 255, 'DRAGONITE', 'SITRUS_BERRY', M('FIRE_BLAST','SAFEGUARD','OUTRAGE','HYPER_BEAM'))]),
 'Steven': ('STEVEN', 'RED', 'RED', [
   (81, 255, 'PIKACHU', 'LIGHT_BALL', M('VOLT_TACKLE','IRON_TAIL','QUICK_ATTACK','THUNDERBOLT')),
   (73, 255, 'ESPEON', 'NONE', M('MORNING_SUN','REFLECT','PSYCHIC','SHADOW_BALL')),
   (75, 255, 'SNORLAX', 'LEFTOVERS', M('AMNESIA','REST','SLEEP_TALK','BODY_SLAM')),
   (77, 255, 'VENUSAUR', 'NONE', M('SUNNY_DAY','GIGA_DRAIN','SYNTHESIS','SOLAR_BEAM')),
   (77, 255, 'CHARIZARD', 'NONE', M('OVERHEAT','AERIAL_ACE','DRAGON_CLAW','BLAST_BURN')),
   (77, 255, 'BLASTOISE', 'NONE', M('HYDRO_CANNON','BLIZZARD','SURF','FOCUS_PUNCH'))]),
}

def party_src(mons):
    out = []
    for lvl, iv, sp, item, moves in mons:
        out.append('    {\n    .iv = %d,\n    .lvl = %d,\n    .species = SPECIES_%s,\n    .heldItem = ITEM_%s,\n    .moves = {%s}\n    }'
                   % (iv, lvl, sp, item, ', '.join(moves)))
    return ',\n'.join(out)

pp = root + '/src/data/trainer_parties.h'
t = open(pp).read()
for arr, (_, _, _, mons) in BOSSES.items():
    pat = re.compile(r'(static const struct TrainerMonItemCustomMoves sParty_%s\[\] = \{\n)(.*?)(\n\};)' % arr, re.S)
    t, n = pat.subn(lambda m: m.group(1) + party_src(mons) + m.group(3), t)
    assert n == 1, arr

# Silver: rival parties keep their slots but use Johto starters + Silver's team
RIVAL = {'TREECKO':'CHIKORITA','GROVYLE':'BAYLEEF','SCEPTILE':'MEGANIUM',
         'TORCHIC':'CYNDAQUIL','COMBUSKEN':'QUILAVA','BLAZIKEN':'TYPHLOSION',
         'MUDKIP':'TOTODILE','MARSHTOMP':'CROCONAW','SWAMPERT':'FERALIGATR',
         'WINGULL':'ZUBAT','PELIPPER':'GOLBAT','LOTAD':'GASTLY','LOMBRE':'HAUNTER',
         'LUDICOLO':'GENGAR','SLUGMA':'MAGNEMITE','TORKOAL':'MAGNETON','TROPIUS':'SNEASEL'}
def rival_block(m):
    return re.sub(r'SPECIES_(\w+)', lambda s: 'SPECIES_' + RIVAL.get(s.group(1), s.group(1)), m.group(0))
t = re.sub(r'sParty_(?:Brendan|May)(?:Route|Rustboro|Lilycove)\w*\[\] = \{.*?\n\};', rival_block, t, flags=re.S)
open(pp, 'w').write(t)

tp = root + '/src/data/trainers.h'
t = open(tp).read()
for arr, (tid, name, pic, _) in BOSSES.items():
    pat = re.compile(r'(\[TRAINER_%s\] =\n    \{.*?\n    \},)' % tid, re.S)
    def fix(m):
        b = m.group(1)
        b = re.sub(r'\.trainerName = _\("[^"]*"\)', '.trainerName = _("%s")' % name, b)
        if pic == 'F':
            b = re.sub(r'\.encounterMusic_gender = (?:F_TRAINER_FEMALE \| )?TRAINER_ENCOUNTER_MUSIC_MALE',
                       '.encounterMusic_gender = F_TRAINER_FEMALE | TRAINER_ENCOUNTER_MUSIC_FEMALE', b)
        elif pic == 'M':
            b = re.sub(r'\.encounterMusic_gender = (?:F_TRAINER_FEMALE \| )?TRAINER_ENCOUNTER_MUSIC_FEMALE',
                       '.encounterMusic_gender = TRAINER_ENCOUNTER_MUSIC_MALE', b)
        elif pic == 'RED':
            b = re.sub(r'\.trainerPic = \w+', '.trainerPic = TRAINER_PIC_RED', b)
        if tid == 'TATE_AND_LIZA_1':
            b = b.replace('.doubleBattle = TRUE', '.doubleBattle = FALSE')
        return b
    t, n = pat.subn(fix, t)
    assert n == 1, tid
# Rematch entries carry the same leader names
for old, new in [('ROXANNE','FALKNER'),('BRAWLY','BUGSY'),('WATTSON','WHITNEY'),('FLANNERY','MORTY'),
                 ('NORMAN','CHUCK'),('WINONA','JASMINE'),('TATE&LIZA','PRYCE'),('JUAN','CLAIR')]:
    t = t.replace('.trainerName = _("%s")' % old, '.trainerName = _("%s")' % new)
# Pryce's rematches are single battles too
t = re.sub(r'(\[TRAINER_TATE_AND_LIZA_\d\] =\n    \{.*?)\.doubleBattle = TRUE', r'\1.doubleBattle = FALSE', t, flags=re.S)
open(tp, 'w').write(t)

# Pryce fights alone, so his gym uses single battles
gp = root + '/data/maps/MossdeepCity_Gym/scripts.inc'
g = open(gp).read()
g = g.replace('trainerbattle_double TRAINER_TATE_AND_LIZA_1, MossdeepCity_Gym_Text_TateAndLizaIntro, MossdeepCity_Gym_Text_TateAndLizaDefeat, MossdeepCity_Gym_Text_TateAndLizaNeedTwoMons, MossdeepCity_Gym_EventScript_TateAndLizaDefeated, NO_MUSIC',
              'trainerbattle_single TRAINER_TATE_AND_LIZA_1, MossdeepCity_Gym_Text_TateAndLizaIntro, MossdeepCity_Gym_Text_TateAndLizaDefeat, MossdeepCity_Gym_EventScript_TateAndLizaDefeated, NO_MUSIC')
g = g.replace('trainerbattle_rematch_double TRAINER_TATE_AND_LIZA_1, MossdeepCity_Gym_Text_TateAndLizaPreRematch, MossdeepCity_Gym_Text_TateAndLizaRematchDefeat, MossdeepCity_Gym_Text_TateAndLizaRematchNeedTwoMons',
              'trainerbattle_rematch TRAINER_TATE_AND_LIZA_1, MossdeepCity_Gym_Text_TateAndLizaPreRematch, MossdeepCity_Gym_Text_TateAndLizaRematchDefeat')
assert 'trainerbattle_double TRAINER_TATE' not in g and 'rematch_double TRAINER_TATE' not in g
open(gp, 'w').write(g)

sp = root + '/src/starter_choose.c'
s = open(sp).read()
s = s.replace('SPECIES_TREECKO,\n    SPECIES_TORCHIC,\n    SPECIES_MUDKIP,', 'SPECIES_CHIKORITA,\n    SPECIES_CYNDAQUIL,\n    SPECIES_TOTODILE,')
assert 'SPECIES_CHIKORITA' in s
open(sp, 'w').write(s)
print('trainers ok')
