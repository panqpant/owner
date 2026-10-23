"""Swap every Hoenn-only Pokemon in wild and trainer data for a Johto/Kanto counterpart
with a similar role, type and evolution stage."""
import re, sys
root = sys.argv[1]
SUB = dict(x.split('=') for x in '''
POOCHYENA=HOUNDOUR MIGHTYENA=HOUNDOOM ZIGZAGOON=SENTRET LINOONE=FURRET
WURMPLE=CATERPIE SILCOON=METAPOD BEAUTIFLY=BUTTERFREE CASCOON=KAKUNA DUSTOX=BEEDRILL
LOTAD=HOPPIP LOMBRE=SKIPLOOM LUDICOLO=JUMPLUFF SEEDOT=BELLSPROUT NUZLEAF=WEEPINBELL SHIFTRY=VICTREEBEL
TAILLOW=PIDGEY SWELLOW=PIDGEOT WINGULL=HOOTHOOT PELIPPER=NOCTOWL
RALTS=NATU KIRLIA=XATU GARDEVOIR=XATU SURSKIT=LEDYBA MASQUERAIN=LEDIAN
SHROOMISH=PARAS BRELOOM=PARASECT SLAKOTH=TEDDIURSA VIGOROTH=URSARING SLAKING=SNORLAX
NINCADA=SPINARAK NINJASK=ARIADOS WHISMUR=SNUBBULL LOUDRED=GRANBULL EXPLOUD=GRANBULL
MAKUHITA=MACHOP HARIYAMA=MACHOKE AZURILL=MARILL NOSEPASS=ONIX SKITTY=MEOWTH DELCATTY=PERSIAN
SABLEYE=MISDREAVUS MAWILE=SNUBBULL ARON=LARVITAR LAIRON=PUPITAR AGGRON=TYRANITAR
MEDITITE=MANKEY MEDICHAM=PRIMEAPE ELECTRIKE=MAREEP MANECTRIC=FLAAFFY PLUSLE=PIKACHU MINUN=ELEKID
VOLBEAT=YANMA ILLUMISE=LEDIAN ROSELIA=GLOOM GULPIN=GRIMER CARVANHA=REMORAID SHARPEDO=OCTILLERY
WAILMER=CHINCHOU WAILORD=LANTURN NUMEL=PONYTA CAMERUPT=RAPIDASH TORKOAL=MAGCARGO
SPOINK=DROWZEE GRUMPIG=HYPNO SPINDA=AIPOM TRAPINCH=PHANPY CACNEA=SUNKERN CACTURNE=SUNFLORA
SWABLU=SPEAROW ALTARIA=DRAGONAIR ZANGOOSE=SNEASEL SEVIPER=ARBOK LUNATONE=CLEFAIRY SOLROCK=SUDOWOODO
BARBOACH=WOOPER WHISCASH=QUAGSIRE CORPHISH=KRABBY CRAWDAUNT=KINGLER BALTOY=EXEGGCUTE CLAYDOL=EXEGGUTOR
FEEBAS=HORSEA MILOTIC=KINGDRA CASTFORM=PORYGON KECLEON=SMEARGLE SHUPPET=GASTLY BANETTE=GENGAR
DUSKULL=MISDREAVUS DUSCLOPS=HAUNTER TROPIUS=GIRAFARIG CHIMECHO=XATU ABSOL=MURKROW WYNAUT=WOBBUFFET
SNORUNT=SWINUB SPHEAL=SEEL SEALEO=DEWGONG WALREIN=LAPRAS CLAMPERL=SHELLDER RELICANTH=QWILFISH
LUVDISC=CORSOLA BAGON=DRATINI SHELGON=DRAGONAIR BELDUM=MAGNEMITE
'''.split())

def swap(text):
    return re.sub(r'SPECIES_(\w+)', lambda m: 'SPECIES_' + SUB.get(m.group(1), m.group(1)), text)

for f in ['src/data/wild_encounters.json', 'src/data/trainer_parties.h']:
    p = root + '/' + f
    text = swap(open(p).read())
    open(p, 'w').write(text)
print('species ok')

# Story mons hardcoded in C: the intro mon, the professor's chaser, Wally's borrowed mon and his catch
for f, old, new in [
    ('src/battle_controllers.c', 'CreateMon(&gEnemyParty[0], SPECIES_ZIGZAGOON, 2,', 'CreateMon(&gEnemyParty[0], SPECIES_SENTRET, 2,'),
    ('src/field_specials.c', 'CreateMon(&gPlayerParty[0], SPECIES_ZIGZAGOON, 7,', 'CreateMon(&gPlayerParty[0], SPECIES_SENTRET, 7,'),
    ('src/main_menu.c', 'CreatePokeballSpriteToReleaseMon(spriteId, gSprites[spriteId].oam.paletteNum, 112, 58, 0, 0, 32, PALETTES_BG, SPECIES_LOTAD);',
     'CreatePokeballSpriteToReleaseMon(spriteId, gSprites[spriteId].oam.paletteNum, 112, 58, 0, 0, 32, PALETTES_BG, SPECIES_MARILL);'),
    ('src/main_menu.c', 'CreateMonPicSprite_Affine(SPECIES_LOTAD,', 'CreateMonPicSprite_Affine(SPECIES_MARILL,'),
    ('src/battle_setup.c', 'CreateMaleMon(&gEnemyParty[0], SPECIES_RALTS, 5);', 'CreateMaleMon(&gEnemyParty[0], SPECIES_NATU, 5);'),
]:
    p = root + '/' + f
    text = open(p).read()
    if old in text:
        open(p, 'w').write(text.replace(old, new))
    assert new in open(p).read(), f

# Johto mons live outside the Hoenn dex, so the National Dex is on from the start
p = root + '/src/new_game.c'
text = open(p).read()
hook = '    ResetContestLinkResults();\n}'
if 'EnableNationalPokedex();' not in text:
    text = text.replace(hook, '    ResetContestLinkResults();\n    // Johto mons live outside the Hoenn dex, so the National Dex is on from the start\n    EnableNationalPokedex();\n}')
    open(p, 'w').write(text)
assert 'EnableNationalPokedex();' in open(p).read()
print('story species ok')
