"""Real establishment rates for Costa Verde's buildings, from Census County Business Patterns 2022
(www2.census.gov, public domain) and Census 2023 county population estimates.
Usage: python tools/building_stats.py  (needs tools/data/census/cbp22co.txt, pop.csv and build/world.json)
-> tools/data/building_rates.json: per category, establishments per 100k people in real urban and
   rural Florida counties, and the in-game count: real rates applied at the population whose real
   establishments match the commercial buildings the generator places (so proportions stay real)."""
import csv
import json
from collections import defaultdict

URBAN = {"086": "Miami-Dade", "011": "Broward", "099": "Palm Beach", "057": "Hillsborough", "095": "Orange"}
RURAL = {"051": "Hendry", "055": "Highlands", "043": "Glades", "027": "DeSoto", "049": "Hardee"}
KEYS = {"087": "Monroe (the Keys)"}

# category: (NAICS codes, group). CBP covers private businesses only (no government, no farms).
CATS = {
    # vehicles
    "Gas station": (["447110", "447190"], "Vehicles"),
    "New car dealer": (["441110"], "Vehicles"),
    "Used car dealer": (["441120"], "Vehicles"),
    "Boat dealer": (["441222"], "Vehicles"),
    "Motorcycle / ATV dealer": (["441228"], "Vehicles"),
    "Tire shop": (["441320"], "Vehicles"),
    "Auto parts store": (["441310"], "Vehicles"),
    "Auto repair (general)": (["811111"], "Vehicles"),
    "Body / paint shop": (["811121"], "Vehicles"),
    "Car wash": (["811192"], "Vehicles"),
    "Towing": (["488410"], "Vehicles"),
    "Car rental": (["532111"], "Vehicles"),
    # food and everyday shopping
    "Supermarket / grocery": (["445110"], "Shopping"),
    "Convenience store": (["445120", "445131"], "Shopping"),
    "Liquor store": (["445310", "445320"], "Shopping"),
    "Pharmacy": (["446110", "456110"], "Shopping"),
    "Department store": (["452210", "455110"], "Shopping"),
    "Supercenter / warehouse club": (["452311", "455211"], "Shopping"),
    "Dollar / variety store": (["452319", "455219"], "Shopping"),
    "Home centre / hardware": (["444110", "444130", "444140"], "Shopping"),
    "Furniture store": (["442110", "449110"], "Shopping"),
    "Electronics store": (["443142", "449210"], "Shopping"),
    "Clothing store": (["448110", "448120", "448130", "448140", "448150", "448190", "458110"], "Shopping"),
    "Shoe store": (["448210", "458210"], "Shopping"),
    "Jewelry store": (["448310", "458310"], "Shopping"),
    "Sporting goods (incl. gun shops)": (["451110", "459110"], "Shopping"),
    "Florist": (["453110", "459310"], "Shopping"),
    "Pet store": (["453910", "459910"], "Shopping"),
    "Thrift / used goods": (["453310", "459510"], "Shopping"),
    "Tobacco / vape shop": (["453991", "459991"], "Shopping"),
    # food service and nightlife
    "Full-service restaurant": (["722511"], "Food & nightlife"),
    "Fast food": (["722513"], "Food & nightlife"),
    "Coffee shop / snack bar": (["722515"], "Food & nightlife"),
    "Bar / nightclub": (["722410"], "Food & nightlife"),
    # personal services
    "Barber shop": (["812111"], "Personal services"),
    "Beauty salon": (["812112"], "Personal services"),
    "Nail salon": (["812113"], "Personal services"),
    "Other personal care (incl. tattoo)": (["812199"], "Personal services"),
    "Laundromat": (["812310"], "Personal services"),
    "Dry cleaner": (["812320"], "Personal services"),
    "Funeral home": (["812210"], "Personal services"),
    "Cemetery / crematory": (["812220"], "Personal services"),
    "Parking lot / garage": (["812930"], "Personal services"),
    "Child day care": (["624410"], "Personal services"),
    "Veterinarian": (["541940"], "Personal services"),
    # money
    "Bank branch": (["522110"], "Money & offices"),
    "Credit union": (["522130"], "Money & offices"),
    "Check cashing / pawn / payday": (["522390", "522298"], "Money & offices"),
    "Insurance agency": (["524210"], "Money & offices"),
    "Real estate office": (["531210"], "Money & offices"),
    "Self-storage": (["531130"], "Money & offices"),
    "Law office": (["541110"], "Money & offices"),
    # health
    "Hospital (private)": (["622110", "622210", "622310"], "Health"),
    "Doctor's office": (["621111"], "Health"),
    "Dentist": (["621210"], "Health"),
    "Urgent care / outpatient centre": (["621493", "621498"], "Health"),
    "Nursing home": (["623110"], "Health"),
    "Assisted living": (["623311", "623312"], "Health"),
    # lodging and leisure
    "Hotel / motel": (["721110"], "Lodging & leisure"),
    "RV park / campground": (["721211"], "Lodging & leisure"),
    "Fitness centre / gym": (["713940"], "Lodging & leisure"),
    "Golf course / country club": (["713910"], "Lodging & leisure"),
    "Marina": (["713930"], "Lodging & leisure"),
    "Bowling centre": (["713950"], "Lodging & leisure"),
    "Arcade": (["713120"], "Lodging & leisure"),
    "Casino": (["713210"], "Lodging & leisure"),
    "Amusement / theme park": (["713110"], "Lodging & leisure"),
    "Cinema": (["512131"], "Lodging & leisure"),
    "Museum": (["712110"], "Lodging & leisure"),
    "Zoo / botanical garden": (["712130"], "Lodging & leisure"),
    "Nature park / attraction": (["712190"], "Lodging & leisure"),
    "Theatre / performing arts": (["711110"], "Lodging & leisure"),
    "Religious congregation (private)": (["813110"], "Community"),
    "Civic / social club": (["813410"], "Community"),
    "Private school": (["611110"], "Community"),
    "College / university": (["611310"], "Community"),
    "Driving school": (["611692"], "Community"),
    "Flight school": (["611512"], "Community"),
    # industry, logistics, utilities
    "Warehouse / distribution": (["493110", "493120", "493190"], "Industry & logistics"),
    "Trucking company": (["484110", "484121", "484122"], "Industry & logistics"),
    "Port / marine cargo": (["488310", "488320"], "Industry & logistics"),
    "Airport services": (["488119", "488190"], "Industry & logistics"),
    "Boat building / repair": (["336612", "336611"], "Industry & logistics"),
    "Concrete plant": (["327320"], "Industry & logistics"),
    "Sugar mill / refinery": (["311314"], "Industry & logistics"),
    "Fruit & vegetable processing": (["311411", "311421"], "Industry & logistics"),
    "Brewery": (["312120"], "Industry & logistics"),
    "Power plant (private / utility)": (["221112", "221113", "221114", "221117", "221118"], "Utilities"),
    "Power transmission / substation op.": (["221121", "221122"], "Utilities"),
    "Water supply": (["221310"], "Utilities"),
    "Sewage treatment": (["221320"], "Utilities"),
    "Waste collection": (["562111"], "Utilities"),
    "Landfill": (["562212"], "Utilities"),
    "Recycling / materials recovery": (["562920"], "Utilities"),
    "Scrap yard": (["423930"], "Utilities"),
}

# Government and civic facilities aren't in CBP; national totals from the sources named.
US_POP = 333_287_557  # Census 2022 estimate (pop.csv national row is used if present)
CIVIC = {
    "Police station": (17_541, "BJS Census of State and Local Law Enforcement Agencies, 2018 (agencies, as a floor for stations)"),
    "Fire station": (52_007, "USFA National Fire Department Registry, Jan 2023"),
    "Public elementary school": (52_474, "NCES via Education Week"),
    "Public middle school": (16_298, "NCES via Education Week"),
    "Public high school": (23_810, "NCES via Education Week"),
    "Post office (USPS-run)": (31_123, "USPS Postal Facts"),
    "Hospital (all)": (6_120, "AHA Fast Facts 2024"),
    "Religious congregation (all)": (356_642, "U.S. Religion Census 2020"),
    "Municipal landfill": (1_540, "EREF (2013 data), via Waste Dive"),
}


def load():
    est = defaultdict(lambda: defaultdict(int))
    with open("tools/data/census/cbp22co.txt") as f:
        for row in csv.DictReader(f):
            if row["fipstate"] == "12":
                est[row["fipscty"]][row["naics"]] = int(row["est"])
    pop = {}
    us = US_POP
    with open("tools/data/census/pop.csv", encoding="latin-1") as f:
        for row in csv.DictReader(f):
            if row["STATE"] == "12" and row["COUNTY"] != "000":
                pop[row["COUNTY"]] = int(row["POPESTIMATE2022"])
            if row["SUMLEV"] == "010":
                us = int(row["POPESTIMATE2022"])
    return est, pop, us


def rate(est, pop, counties, codes):
    n = sum(est[c][code] for c in counties for code in codes)
    p = sum(pop[c] for c in counties)
    return 1e5 * n / p, n


RURAL_STYLES = {"shack", "store", "gas", "diner"}
URBAN_STYLES = {"tower", "midrise", "deco", "stucco", "warehouse", "campus"}


def costa_verde():
    """Commercial buildings the generator places, split metro vs rural towns."""
    w = json.load(open("build/world.json"))
    urban = sum(1 for b in w["buildings"] if b["style"] in URBAN_STYLES)
    rural = sum(1 for b in w["buildings"] if b["style"] in RURAL_STYLES)
    return urban, rural, len(w["buildings"])


if __name__ == "__main__":
    est, pop, us = load()
    n_urban, n_rural, n_bld = costa_verde()
    rows = {}
    for name, (codes, group) in CATS.items():
        ru, _ = rate(est, pop, URBAN, codes)
        rr, _ = rate(est, pop, RURAL, codes)
        rk, _ = rate(est, pop, KEYS, codes)
        rows[name] = {"group": group, "naics": codes, "urban_per_100k": ru, "rural_per_100k": rr, "keys_per_100k": rk}
    # The population whose real establishments match the commercial buildings the map has (metro and
    # rural towns separately). Real per-person rates at that size give every count, so the whole map
    # keeps real proportions.
    p_urban = 1e5 * n_urban / sum(r["urban_per_100k"] for r in rows.values())
    p_rural = 1e5 * n_rural / sum(r["rural_per_100k"] for r in rows.values())
    for r in rows.values():
        r["metro"] = round(r["urban_per_100k"] * p_urban / 1e5)
        r["rural_towns"] = round(r["rural_per_100k"] * p_rural / 1e5)
        r["in_game"] = r["metro"] + r["rural_towns"]
    civic = {}
    for name, (n, src) in CIVIC.items():
        per = 1e5 * n / us
        civic[name] = {"per_100k": per, "source": src, "in_game": round(per * (p_urban + p_rural) / 1e5)}
    out = {"costa_verde": {"buildings": n_bld, "metro_commercial": n_urban, "rural_commercial": n_rural,
                           "represented_population_metro": p_urban, "represented_population_rural": p_rural},
           "counties": {"urban": URBAN, "rural": RURAL, "keys": KEYS}, "business": rows, "civic": civic}
    json.dump(out, open("tools/data/building_rates.json", "w"), indent=1)
    # Luau data for the generator: real use mixes (per 100k weights) and the playable marker picks
    # (design numbers from BUILDINGS.md section 1).
    MARKERS = [("gun_store", "Sporting goods (incl. gun shops)", 8), ("mod_shop", "Body / paint shop", 5),
               ("car_dealer", "New car dealer", 4), ("boat_dealer", "Boat dealer", 3), ("clothing", "Clothing store", 10),
               ("barber", "Barber shop", 6), ("tattoo", "Other personal care (incl. tattoo)", 5), ("convenience", "Convenience store", 12),
               ("gas", "Gas station", 15), ("liquor", "Liquor store", 5), ("bank", "Bank branch", 4), ("jewelry", "Jewelry store", 2),
               ("pawn", "Check cashing / pawn / payday", 3), ("food", "Fast food", 10), ("bar", "Bar / nightclub", 6),
               ("gym", "Fitness centre / gym", 3), ("cinema", "Cinema", 99), ("arcade", "Arcade", 99), ("bowling", "Bowling centre", 99),
               ("hospital", "Hospital (private)", 99), ("fire", "Fire station", 3), ("police", "Police station", 6)]
    def mix(key):
        lines = [f'\t\t{{ use = {json.dumps(n)}, group = "{r["group"]}", w = {r[key]:.2f} }},' for n, r in rows.items() if r[key] > 0]
        civ_w = {"urban_per_100k": 1, "rural_per_100k": 1, "keys_per_100k": 1}[key]
        lines += [f'\t\t{{ use = {json.dumps(n)}, group = "Civic", w = {c["per_100k"] * civ_w:.2f} }},' for n, c in civic.items()
                  if not n.startswith("Religious") and not n.startswith("Hospital") and not n.startswith("Municipal")]
        return "\n".join(lines)
    with open("src/shared/Gen/BuildingUses.luau", "w") as fh:
        fh.write("-- Generated by tools/building_stats.py from Census County Business Patterns 2022 and national civic\n"
                 "-- totals: real use mixes (weights = establishments per 100k people). Do not edit.\nreturn {\n")
        for name, key in (("metro", "urban_per_100k"), ("rural", "rural_per_100k"), ("keys", "keys_per_100k")):
            fh.write(f"\t{name} = {{\n{mix(key)}\n\t}},\n")
        fh.write("\tmarkers = {\n" + "\n".join(f'\t\t{{ feature = "{f}", use = {json.dumps(u)}, count = {c} }},' for f, u, c in MARKERS) + "\n\t},\n}\n")
    print(f"{n_bld} buildings; commercial: metro {n_urban}, rural towns {n_rural} -> represents a real population of "
          f"{p_urban:,.0f} (metro) + {p_rural:,.0f} (rural)")
    for name, r in rows.items():
        print(f"  {r['group'][:12]:12s} {name:38s} urban {r['urban_per_100k']:6.1f} rural {r['rural_per_100k']:6.1f} keys {r['keys_per_100k']:6.1f}  metro {r['metro']:4d} rural {r['rural_towns']:3d}")
    for name, r in civic.items():
        print(f"  {'Civic':12s} {name:38s} per100k {r['per_100k']:6.1f}  in-game {r['in_game']:4d}")
