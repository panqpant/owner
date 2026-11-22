"""Download USGS National Map orthoimagery (US public domain) for reference regions.
Usage: python tools/fetch_refs.py  -> refs/<name>.jpg + screenshots/refs_contact.jpg
Used to study real layouts (coasts, cities, farms); nothing is traced or copied into the map."""
import math
import os
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFont

URL = ("https://basemap.nationalmap.gov/arcgis/rest/services/USGSImageryOnly/MapServer/export"
       "?bbox={w},{s},{e},{n}&bboxSR=4326&imageSR=3857&size=1024,1024&format=jpg&f=image")

# name, lat, lon, span (km), what to learn from it
REGIONS = [
    ("bay_metro_barrier", 25.80, -80.20, 30, "metro on a bay behind a barrier island"),
    ("downtown_bayfront", 25.775, -80.19, 5, "downtown skyline meeting the bay, port island"),
    ("barrier_beach_strip", 25.83, -80.125, 6, "hotel strip on a barrier island"),
    ("venetian_islands", 25.79, -80.16, 4, "causeway with small residential islands"),
    ("inlet_jetties", 26.10, -80.11, 4, "inlet cutting a barrier island, jetties"),
    ("finger_canals", 26.12, -80.12, 5, "residential finger canals"),
    ("coastal_suburb_grid", 26.35, -80.10, 12, "suburb grid with lakes and golf courses"),
    ("suburban_lakes", 26.05, -80.35, 10, "western suburbs with dug lakes"),
    ("everglades_edge", 25.75, -80.48, 14, "hard edge where suburbs meet wetland"),
    ("sawgrass_prairie", 25.85, -80.75, 20, "sawgrass with tree islands and flow lines"),
    ("tree_islands", 25.70, -80.80, 8, "teardrop tree islands"),
    ("mangrove_coast", 25.35, -81.10, 15, "mangrove coast and rivers"),
    ("ten_thousand_islands", 25.85, -81.55, 18, "fragmented mangrove islets"),
    ("florida_bay", 25.05, -80.75, 30, "shallow bay with mudbanks"),
    ("upper_keys", 25.05, -80.48, 14, "keys with highway and marinas"),
    ("seven_mile_bridge", 24.70, -81.17, 14, "long bridge between keys"),
    ("key_town", 24.555, -81.78, 5, "dense old town on a key"),
    ("lower_keys", 24.66, -81.45, 18, "lower keys islet field"),
    ("gulf_barrier_islands", 27.30, -82.58, 15, "gulf barrier islands and passes"),
    ("gulf_city_bay", 27.95, -82.50, 20, "city at head of a gulf bay"),
    ("causeway_bay", 27.97, -82.65, 14, "causeways across a bay"),
    ("gulf_beach_town", 26.14, -81.80, 8, "gulf beach town grid"),
    ("estuary_river", 26.53, -81.95, 16, "river estuary and canal city"),
    ("cape_canal_city", 26.62, -81.98, 10, "massive canal-grid suburb"),
    ("big_lake", 26.95, -80.80, 60, "big shallow lake with farm rim"),
    ("sugarcane_fields", 26.62, -80.65, 14, "huge rectangular cane fields"),
    ("citrus_groves", 27.55, -81.60, 8, "citrus grove rows"),
    ("sinkhole_lakes", 28.05, -81.75, 20, "central lakes district"),
    ("cattle_ranch", 27.35, -81.20, 12, "ranchland and scrub"),
    ("small_town_grid", 27.20, -81.85, 5, "small rural town on a highway"),
    ("theme_park_area", 28.40, -81.55, 10, "resort district, big roads"),
    ("rocket_coast", 28.55, -80.62, 25, "cape with lagoons and launch area"),
    ("lagoon_barrier", 28.10, -80.60, 15, "long lagoon behind barrier island"),
    ("airport_major", 28.43, -81.31, 8, "major airport layout"),
    ("airport_coastal", 25.80, -80.29, 5, "airport inside the city"),
    ("container_port", 25.77, -80.165, 3, "port and cruise terminals"),
    ("industrial_port", 29.73, -95.10, 10, "ship channel industry"),
    ("interstate_interchange", 26.10, -80.20, 3, "big highway interchange"),
    ("gulf_marsh", 29.25, -89.40, 25, "river delta marsh"),
    ("bayou_town", 29.60, -90.70, 15, "bayou with ribbon towns"),
    ("gulf_coast_casino_strip", 30.39, -88.90, 10, "beach highway strip"),
    ("houston_downtown", 29.76, -95.37, 5, "downtown with freeways ring"),
    ("houston_sprawl", 29.85, -95.65, 20, "suburban sprawl and arterials"),
    ("galveston_island", 29.27, -94.83, 15, "barrier island city"),
    ("south_beach_detail", 25.78, -80.13, 2.5, "close-up beachfront blocks"),
    ("golf_community", 26.38, -80.18, 6, "gated golf communities"),
    ("swamp_highway", 26.15, -81.10, 15, "dead-straight highway across swamp"),
    ("trailer_parks", 26.68, -80.70, 4, "small farm town, trailer parks"),
    ("charleston_harbor", 32.77, -79.93, 15, "historic harbor city"),
    ("outer_banks", 35.55, -75.47, 20, "thin barrier island chain"),
]


def bbox(lat, lon, km):
    dlat = km / 2 / 111.0
    dlon = km / 2 / (111.0 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def fetch(r):
    name, lat, lon, km, _ = r
    path = f"refs/{name}.jpg"
    if not os.path.exists(path):
        w, s, e, n = bbox(lat, lon, km)
        urllib.request.urlretrieve(URL.format(w=w, s=s, e=e, n=n), path)
    return path


os.makedirs("refs", exist_ok=True)
with ThreadPoolExecutor(6) as ex:
    paths = list(ex.map(fetch, REGIONS))

# contact sheet
T, COLS = 300, 10
rows = math.ceil(len(paths) / COLS)
sheet = Image.new("RGB", (COLS * T, rows * (T + 22)), (20, 20, 22))
d = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("DejaVuSans.ttf", 13)
except OSError:
    font = ImageFont.load_default()
for i, (p, r) in enumerate(zip(paths, REGIONS)):
    x, y = (i % COLS) * T, (i // COLS) * (T + 22)
    sheet.paste(Image.open(p).convert("RGB").resize((T, T)), (x, y))
    d.text((x + 4, y + T + 3), f"{r[0]} ({r[3]:g} km)", fill=(230, 230, 230), font=font)
sheet.save("screenshots/refs_contact.jpg", quality=85)
print(len(paths), "regions -> refs/, contact sheet -> screenshots/refs_contact.jpg")
