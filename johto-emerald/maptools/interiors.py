"""HGSS interiors as Emerald rooms: pick the matching Emerald interior for each HGSS room, keep HGSS's warp list
(order matters: warps refer to each other by index) and place each warp on the template's exit or stairs."""
import sys, os, json, glob, re, collections
sys.path.insert(0, os.path.dirname(__file__))
from emr import *
from hg import PHG

def vanilla_maps():
    out = {}
    for mj in glob.glob(ROOT + '/data/maps/*/map.json'):
        m = json.load(open(mj))
        if m['name'].startswith('HG_'): continue
        out.setdefault(m['layout'], m)
    return out

TEMPLATES = [  # (keyword regex on the HGSS map constant, Emerald layout)
    (r'POKECENTER_1F', 'LAYOUT_POKEMON_CENTER_1F'), (r'POKECENTER_2F', 'LAYOUT_POKEMON_CENTER_2F'),
    (r'POKECENTER_B1F', 'LAYOUT_POKEMON_CENTER_2F'),
    (r'DEPT_STORE_1F', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_1F'), (r'DEPT_STORE_2F', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_2F'),
    (r'DEPT_STORE_3F', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_3F'), (r'DEPT_STORE_4F', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_4F'),
    (r'DEPT_STORE_5F', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_5F'), (r'DEPT_STORE_6F', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_5F'),
    (r'DEPT_STORE_ROOF', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_ROOFTOP'), (r'DEPT_STORE_ELEVATOR', 'LAYOUT_LILYCOVE_CITY_DEPARTMENT_STORE_ELEVATOR'),
    (r'MART|SHOP|BOUTIQUE', 'LAYOUT_MART'),
    (r'PLAYER_HOUSE_1F', 'LAYOUT_LITTLEROOT_TOWN_BRENDANS_HOUSE_1F'), (r'PLAYER_HOUSE_2F', 'LAYOUT_LITTLEROOT_TOWN_BRENDANS_HOUSE_2F'),
    (r'RIVAL_HOUSE_1F', 'LAYOUT_LITTLEROOT_TOWN_MAYS_HOUSE_1F'), (r'RIVAL_HOUSE_2F', 'LAYOUT_LITTLEROOT_TOWN_MAYS_HOUSE_2F'),
    (r'LAB', 'LAYOUT_LITTLEROOT_TOWN_PROFESSOR_BIRCHS_LAB'),
    (r'GATE|GATEHOUSE', 'LAYOUT_ROUTE110_SEASIDE_CYCLING_ROAD_ENTRANCE'),
    (r'DAY_CARE|DAYCARE', 'LAYOUT_ROUTE117_POKEMON_DAY_CARE'),
    (r'GYM', 'LAYOUT_RUSTBORO_CITY_GYM'),
    (r'_2F|_3F|_4F', 'LAYOUT_RUSTBORO_CITY_FLAT1_2F'),
]
HOUSES_STAIRS = 'LAYOUT_RUSTBORO_CITY_FLAT1_1F'
HOUSES = ['LAYOUT_HOUSE1', 'LAYOUT_HOUSE2', 'LAYOUT_HOUSE3', 'LAYOUT_HOUSE4', 'LAYOUT_HOUSE_WITH_BED',
          'LAYOUT_PACIFIDLOG_TOWN_HOUSE1', 'LAYOUT_RUSTBORO_CITY_HOUSE', 'LAYOUT_ROUTE116_TUNNELERS_REST_HOUSE']

def pick_template(const, n_inner):
    for pat, lay in TEMPLATES:
        if re.search(pat, const): return lay
    if n_inner: return HOUSES_STAIRS
    return HOUSES[sum(map(ord, const)) % len(HOUSES)]   # vary houses town to town, stable per room

def template_warps(vmap):
    """Template warps split into exits (door mats at the bottom) and inner warps (stairs/escalators), in x order."""
    ws = vmap.get('warp_events', [])
    hmax = max(w['y'] for w in ws) if ws else 0
    exits = sorted([w for w in ws if w['y'] >= hmax - 1], key=lambda w: w['x'])
    inner = sorted([w for w in ws if w['y'] < hmax - 1], key=lambda w: (w['y'], w['x']))
    return exits, inner
