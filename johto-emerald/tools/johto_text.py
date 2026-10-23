"""Rename Hoenn places, people, teams and badges to their Johto counterparts.
Only text inside in-game strings is touched (.string "...", _("..."), map section names),
never labels or constants."""
import re, sys, pathlib
root = pathlib.Path(sys.argv[1])

# Hoenn town -> Johto town. Gym towns follow the leader who now lives there.
TOWNS = [
 ('LITTLEROOT TOWN', 'NEW BARK TOWN'), ('OLDALE TOWN', 'CHERRYGROVE CITY'),
 ('RUSTBORO CITY', 'VIOLET CITY'), ('DEWFORD TOWN', 'AZALEA TOWN'),
 ('MAUVILLE CITY', 'GOLDENROD CITY'), ('LAVARIDGE TOWN', 'ECRUTEAK CITY'),
 ('PETALBURG CITY', 'CIANWOOD CITY'), ('FORTREE CITY', 'OLIVINE CITY'),
 ('MOSSDEEP CITY', 'MAHOGANY TOWN'), ('SOOTOPOLIS CITY', 'BLACKTHORN CITY'),
 ('EVER GRANDE CITY', 'INDIGO PLATEAU'), ('SLATEPORT CITY', 'VERMILION CITY'),
 ('VERDANTURF TOWN', 'NATIONAL PARK'), ('FALLARBOR TOWN', 'LAKE OF RAGE'),
 ('PACIFIDLOG TOWN', 'WHIRL ISLANDS'), ('LILYCOVE CITY', 'CELADON CITY'),
]
PLACES = [
 ('PETALBURG WOODS', 'ILEX FOREST'), ('NEW MAUVILLE', 'POWER PLANT'),
 ('GRANITE CAVE', 'DARK CAVE'), ('RUSTURF TUNNEL', 'UNION CAVE'),
 ('MT. PYRE', 'SPROUT TOWER'), ('METEOR FALLS', 'MT. SILVER'),
 ('SHOAL CAVE', 'ICE PATH'), ('SEAFLOOR CAVERN', 'WHIRL ISLANDS'),
 ('SKY PILLAR', 'BELL TOWER'), ('CAVE OF ORIGIN', "DRAGON'S DEN"),
 ('MT. CHIMNEY', 'MT. MORTAR'), ('JAGGED PASS', 'MT. MORTAR'),
 ('FIERY PATH', 'BURNED TOWER'), ('ABANDONED SHIP', 'S.S. AQUA'),
 ('SEALED CHAMBER', 'RUINS OF ALPH'),
 ('{AQUA} HIDEOUT', 'ROCKET HIDEOUT'), ('AQUA HIDEOUT', 'ROCKET HIDEOUT'),
 ('MAGMA HIDEOUT', 'ROCKET HIDEOUT'),
]
# Bare town names ("back to OLDALE") follow the full names
BARE = [(old.rsplit(' ', 1)[0], new.rsplit(' ', 1)[0] if new.endswith((' TOWN', ' CITY')) else new)
        for old, new in TOWNS]
ROUTES = {101:29, 102:31, 103:30, 104:32, 105:40, 106:41, 107:41, 108:40, 109:40, 110:34,
          111:36, 112:37, 113:38, 114:39, 115:43, 116:33, 117:35, 118:42, 119:44, 120:45,
          121:46, 122:47, 123:48, 124:40, 125:41, 126:41, 127:41, 128:26, 129:27, 130:27,
          131:21, 132:20, 133:19, 134:19}
WORDS = [
 ('HOENN', 'JOHTO'), ('BIRCH', 'ELM'),
 ('TEAM AQUA', 'TEAM ROCKET'), ('TEAM MAGMA', 'TEAM ROCKET'),
 ('TEAM {AQUA}', 'TEAM ROCKET'), ('TEAM {MAGMA}', 'TEAM ROCKET'),
 ('AQUA ADMIN', 'ROCKET ADMIN'), ('MAGMA ADMIN', 'ROCKET ADMIN'),
 ('AQUA LEADER', 'ROCKET BOSS'), ('MAGMA LEADER', 'ROCKET BOSS'),
 ('ROXANNE', 'FALKNER'), ('BRAWLY', 'BUGSY'), ('WATTSON', 'WHITNEY'), ('FLANNERY', 'MORTY'),
 ('WINONA', 'JASMINE'), ('TATE&LIZA', 'PRYCE'), ('TATE and LIZA', 'PRYCE'), ('JUAN', 'CLAIR'),
 ('SIDNEY', 'WILL'), ('PHOEBE', 'KOGA'), ('GLACIA', 'BRUNO'), ('DRAKE', 'KAREN'), ('WALLACE', 'LANCE'),
 ('ARCHIE', 'ARCHER'), ('MAXIE', 'GIOVANNI'), ('MATT', 'PROTON'), ('TABITHA', 'PETREL'),
 ('SHELLY', 'ARIANA'), ('COURTNEY', 'ARIANA'),
 ('STONE BADGE', 'ZEPHYRBADGE'), ('KNUCKLE BADGE', 'HIVEBADGE'), ('DYNAMO BADGE', 'PLAINBADGE'),
 ('HEAT BADGE', 'FOGBADGE'), ('BALANCE BADGE', 'STORMBADGE'), ('FEATHER BADGE', 'MINERALBADGE'),
 ('MIND BADGE', 'GLACIERBADGE'), ('RAIN BADGE', 'RISINGBADGE'),
]
PAIRS = TOWNS + PLACES + WORDS + BARE
PATTERNS = [(re.compile(r'(?<![A-Za-z])' + re.escape(o) + r'(?![A-Za-z])'), n) for o, n in PAIRS]
ROUTE_RE = re.compile(r'ROUTE (1[0-3]\d)\b')

def johtoify(s):
    for pat, new in PATTERNS:
        s = pat.sub(new, s)
    return ROUTE_RE.sub(lambda m: 'ROUTE %d' % ROUTES.get(int(m.group(1)), int(m.group(1))), s)

STRING_RE = re.compile(r'(\.string\s+"|_\("|COMPOUND_STRING\(")((?:[^"\\]|\\.)*)(")')
changed = 0
files = list(root.glob('data/**/*.inc')) + list(root.glob('src/**/*.c')) + list(root.glob('src/**/*.h'))
for f in files:
    t = f.read_text()
    n = STRING_RE.sub(lambda m: m.group(1) + johtoify(m.group(2)) + m.group(3), t)
    if n != t:
        f.write_text(n); changed += 1

rm = root / 'src/data/region_map/region_map_sections.json'
t = rm.read_text()
rm.write_text(re.sub(r'("name": ")([^"]*)(")', lambda m: m.group(1) + johtoify(m.group(2)) + m.group(3), t))
# {AQUA}/{MAGMA} placeholders both expand to ROCKET
st = root / 'src/strings.c'
t = st.read_text()
t = t.replace('gText_ExpandedPlaceholder_Aqua[] = _("AQUA")', 'gText_ExpandedPlaceholder_Aqua[] = _("ROCKET")')
t = t.replace('gText_ExpandedPlaceholder_Magma[] = _("MAGMA")', 'gText_ExpandedPlaceholder_Magma[] = _("ROCKET")')
st.write_text(t)

# Pryce runs the Mahogany gym alone
gym = root / 'data/maps/MossdeepCity_Gym/scripts.inc'
t = gym.read_text()
t = re.sub(r'\.string "(?:TATE|LIZA): ', '.string "PRYCE: ', t).replace("LIZA AND TATE'S CERTIFIED", "PRYCE'S CERTIFIED")
gym.write_text(t)
print('text ok, files changed:', changed + 1)
