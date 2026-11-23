# Costa Verde: buildings the map needs

What every building on the map is for, worked out from real data rather than guesswork. Two kinds:

1. **Feature buildings**: places the player uses, shown as map markers (gun stores, mod shops, clothes
   shops, banks to rob and so on). GTA V and GTA VI were used to see *which kinds* of features an
   open-world crime game on a real-style US map has. Names and designs here are original.
2. **Everything else**: the buildings that make a city feel real without being markers (power plants,
   substations, schools, churches, warehouses, car dealers, dentists...). The full checklist is the American
   Planning Association's land-use classification; the counts come from real Florida counties.

## How the numbers were worked out

- **Checklist of building types:** the APA's Land Based Classification Standards, Function dimension:
  367 categories, saved in `tools/data/lbcs_function.txt`. Every category there is a building or land
  use a real US city has.
- **How many of each:** US Census County Business Patterns 2022 (every business establishment by type,
  per county) and Census 2023 population estimates, via `tools/building_stats.py`.
  - Urban rate: Miami-Dade, Broward, Palm Beach, Hillsborough and Orange counties.
  - Rural rate: Hendry, Highlands, Glades, DeSoto and Hardee counties.
  - Keys rate: Monroe County (shown for reference; the Keys towns need their own row of shops).
- **Scaling to the map:** the generator currently places 3,037 commercial buildings in the metro
  and 438 in the rural towns. That matches the business count of a real Florida population
  of about **239,642 (metro) + 59,868 (rural towns)**. Every count below
  is the real per-person rate at that size, so the map keeps real proportions (for example, there are about
  as many dentists as gas stations in a real Florida metro, and the map will have the same).
- **Government and civic buildings** aren't in the business data, so they use national totals from the
  sources named in their table. Where no reliable source turned up, the row says so instead of guessing.

## 1. Feature buildings (map markers)

Columns: what the player does there, the GTA reference that shows the feature belongs in this kind of game,
and how many real ones of that type the map should hold. The marker column is a design choice: which share of
the real ones are playable. The rest stay as ordinary buildings of that type.

| Feature | Player use | GTA reference | Real ones on the map | Markers (design choice) |
|---|---|---|---|---|
| Gun store (some with a shooting range) | Buy weapons, ammo, armour | GTA V: Ammu-Nation, "plenty of locations" [1] | 17 sporting-goods stores (gun shops are a subset) | 8 |
| Mod / body shop | Upgrade, repair, respray cars | GTA V: 4 Los Santos Customs [2] | 28 body/paint shops | 5 |
| Car dealership | Buy cars | GTA V/VI: vehicle shops | 16 new + 30 used | 4 |
| Boat dealer / marina | Buy and store boats | GTA VI: boat yard in the Leonida Keys (fan-reported, unconfirmed) [3] | 10 boat dealers, 4 marinas | 3 |
| Clothing store (budget, mid, luxury) | Buy outfits | GTA V: several clothing chains [4] | 98 clothing + 19 shoe | 10 |
| Barber / hair salon | Haircuts | GTA V: barbers, one high-end salon [5] | 11 barbers, 98 salons | 6 |
| Tattoo parlour | Tattoos | GTA V: 6 tattoo parlours [2] | part of 37 "other personal care" | 5 |
| Convenience store | Snacks; robbable | GTA V: robbable stores | 52 | 12 |
| Gas station | Refuel; robbable | GTA V | 77 | 15 |
| Liquor store | Robbable | GTA V | 20 | 5 |
| Bank branch | Heists, money | GTA V heists | 65 banks, 10 credit unions | 4 |
| Jewelry store | Heist | GTA V jewel store heist | 27 | 2 |
| Pawn shop | Sell stolen goods | Common GTA mechanic | part of 30 check-cashing/pawn | 3 |
| Restaurant / fast food | Eat, heal | GTA V/VI | 235 restaurants, 205 fast food | 10 |
| Bar / nightclub | Social, missions | GTA VI: Nine1Nine club, seen in Trailer 2 (fan-reported) [3] | 19 | 6 |
| Gym | Raise stats | GTA San Andreas-style mechanic | 38 | 3 |
| Cinema, arcade, bowling | Activities | GTA V cinemas | 3 cinemas, 3 arcades, 1 bowling | all |
| Golf course | Activity | GTA V golf club | 7 | 2 |
| Hospital | Respawn after death | GTA V/VI | 6 private (+ public, see civic table) | all |
| Police station | Respawn after arrest | GTA V/VI | not sourced (see civic notes) | 6 |
| Fire station | Firefighter missions | GTA V | see civic table | 3 |
| Airport / hangar, helipads | Planes, helicopters | GTA VI: Vice City International (trailer 1) [3] | 1 international airport (map), 15 airport businesses | all |
| Prison | Story, breakouts | GTA VI: Leonida Penitentiary (trailer 1) [3] | state prison (1, story landmark) | 1 |
| Arena / stadium | Events | GTA VI: Sahara Arena (fan-reported) [3] | 1 (landmark) | 1 |
| Strip / casino-style venues | Activities | GTA V/VI | casinos: 0 in the business data, see note | design |
| Safe houses / properties | Save, store cars | GTA V/VI | real estate offices: 270 | design |

**Casino note:** the business data shows 0 casinos in these counties because Florida's casinos are run by
the Seminole Tribe, a tribal government, which the business count excludes. They do exist in real South
Florida, so 1 resort casino is realistic.

## 2. Everything else, by type (real counts for the map)

These are ordinary buildings: no marker, but each needs a recognisable look (sign, shape, car park). Counts are
real per-person rates at the map's size.


#### Vehicles

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Gas station | 22.6 / 39.0 / 57.6 | 54 | 23 |
| New car dealer | 5.8 / 3.6 / 4.9 | 14 | 2 |
| Used car dealer | 10.9 / 6.3 / 0.0 | 26 | 4 |
| Boat dealer | 4.3 / 0.0 / 44.1 | 10 | 0 |
| Motorcycle / ATV dealer | 2.2 / 2.3 / 3.7 | 5 | 1 |
| Tire shop | 7.2 / 5.4 / 0.0 | 17 | 3 |
| Auto parts store | 11.1 / 16.3 / 7.4 | 27 | 10 |
| Auto repair (general) | 24.2 / 20.0 / 24.5 | 58 | 12 |
| Body / paint shop | 10.4 / 4.5 / 8.6 | 25 | 3 |
| Car wash | 7.6 / 0.0 / 6.1 | 18 | 0 |
| Towing | 3.2 / 4.5 / 6.1 | 8 | 3 |
| Car rental | 6.2 / 1.4 / 9.8 | 15 | 1 |

#### Shopping

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Supermarket / grocery | 20.4 / 16.8 / 35.5 | 49 | 10 |
| Convenience store | 16.5 / 20.4 / 20.8 | 40 | 12 |
| Liquor store | 7.3 / 2.7 / 13.5 | 18 | 2 |
| Pharmacy | 14.5 / 8.6 / 18.4 | 35 | 5 |
| Department store | 0.8 / 0.0 / 0.0 | 2 | 0 |
| Supercenter / warehouse club | 2.0 / 0.0 / 0.0 | 5 | 0 |
| Dollar / variety store | 10.4 / 26.8 / 20.8 | 25 | 16 |
| Home centre / hardware | 4.4 / 7.3 / 14.7 | 11 | 4 |
| Furniture store | 8.6 / 2.7 / 12.3 | 21 | 2 |
| Electronics store | 6.5 / 1.8 / 0.0 | 16 | 1 |
| Clothing store | 39.2 / 6.3 / 123.7 | 94 | 4 |
| Shoe store | 7.4 / 1.4 / 4.9 | 18 | 1 |
| Jewelry store | 11.3 / 0.0 / 28.2 | 27 | 0 |
| Sporting goods (incl. gun shops) | 6.7 / 2.3 / 49.0 | 16 | 1 |
| Florist | 2.9 / 3.2 / 12.3 | 7 | 2 |
| Pet store | 4.1 / 1.4 / 9.8 | 10 | 1 |
| Thrift / used goods | 4.9 / 4.5 / 12.3 | 12 | 3 |
| Tobacco / vape shop | 6.9 / 1.8 / 9.8 | 16 | 1 |

#### Food & nightlife

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Full-service restaurant | 86.1 / 47.6 / 303.9 | 206 | 29 |
| Fast food | 74.0 / 46.3 / 91.9 | 177 | 28 |
| Coffee shop / snack bar | 22.9 / 9.1 / 34.3 | 55 | 5 |
| Bar / nightclub | 7.1 / 2.7 / 57.6 | 17 | 2 |

#### Personal services

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Barber shop | 4.6 / 0.0 / 0.0 | 11 | 0 |
| Beauty salon | 37.9 / 11.3 / 38.0 | 91 | 7 |
| Nail salon | 7.5 / 3.6 / 11.0 | 18 | 2 |
| Other personal care (incl. tattoo) | 14.8 / 2.3 / 14.7 | 36 | 1 |
| Laundromat | 4.2 / 2.7 / 7.4 | 10 | 2 |
| Dry cleaner | 6.1 / 1.4 / 6.1 | 15 | 1 |
| Funeral home | 2.5 / 2.3 / 0.0 | 6 | 1 |
| Cemetery / crematory | 0.8 / 1.4 / 0.0 | 2 | 1 |
| Parking lot / garage | 9.0 / 0.0 / 0.0 | 21 | 0 |
| Child day care | 24.2 / 29.0 / 18.4 | 58 | 17 |
| Veterinarian | 11.1 / 8.6 / 17.2 | 27 | 5 |

#### Money & offices

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Bank branch | 23.7 / 14.1 / 47.8 | 57 | 8 |
| Credit union | 3.3 / 2.7 / 11.0 | 8 | 2 |
| Check cashing / pawn / payday | 10.8 / 6.3 / 0.0 | 26 | 4 |
| Insurance agency | 58.1 / 26.3 / 46.6 | 139 | 16 |
| Real estate office | 105.0 / 30.8 / 240.1 | 252 | 18 |
| Self-storage | 7.3 / 2.3 / 11.0 | 18 | 1 |
| Law office | 122.2 / 20.4 / 82.1 | 293 | 12 |

#### Health

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Hospital (private) | 1.5 / 4.1 / 3.7 | 4 | 2 |
| Doctor's office | 98.0 / 56.2 / 94.3 | 235 | 34 |
| Dentist | 50.6 / 14.5 / 36.8 | 121 | 9 |
| Urgent care / outpatient centre | 14.7 / 6.8 / 6.1 | 35 | 4 |
| Nursing home | 4.0 / 5.0 / 3.7 | 10 | 3 |
| Assisted living | 8.2 / 2.7 / 0.0 | 20 | 2 |

#### Lodging & leisure

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Hotel / motel | 16.2 / 11.3 / 160.5 | 39 | 7 |
| RV park / campground | 0.4 / 7.7 / 15.9 | 1 | 5 |
| Fitness centre / gym | 14.9 / 4.1 / 18.4 | 36 | 2 |
| Golf course / country club | 2.0 / 4.1 / 4.9 | 5 | 2 |
| Marina | 1.8 / 0.0 / 47.8 | 4 | 0 |
| Bowling centre | 0.3 / 0.0 / 0.0 | 1 | 0 |
| Arcade | 1.2 / 0.0 / 0.0 | 3 | 0 |
| Casino | 0.0 / 0.0 / 0.0 | 0 | 0 |
| Amusement / theme park | 0.5 / 0.0 / 0.0 | 1 | 0 |
| Cinema | 1.0 / 1.4 / 6.1 | 2 | 1 |
| Museum | 1.1 / 1.4 / 17.2 | 3 | 1 |
| Zoo / botanical garden | 0.4 / 0.0 / 3.7 | 1 | 0 |
| Nature park / attraction | 0.1 / 0.0 / 4.9 | 0 | 0 |
| Theatre / performing arts | 0.8 / 0.0 / 4.9 | 2 | 0 |

#### Community

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Religious congregation (private) | 33.2 / 77.6 / 45.3 | 80 | 46 |
| Civic / social club | 3.7 / 8.2 / 15.9 | 9 | 5 |
| Private school | 8.9 / 2.7 / 7.4 | 21 | 2 |
| College / university | 1.7 / 0.0 / 0.0 | 4 | 0 |
| Driving school | 0.7 / 0.0 / 0.0 | 2 | 0 |
| Flight school | 0.8 / 0.0 / 0.0 | 2 | 0 |

#### Industry & logistics

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Warehouse / distribution | 5.9 / 0.0 / 0.0 | 14 | 0 |
| Trucking company | 42.8 / 34.0 / 20.8 | 103 | 20 |
| Port / marine cargo | 0.6 / 0.0 / 0.0 | 2 | 0 |
| Airport services | 6.0 / 1.4 / 12.3 | 14 | 1 |
| Boat building / repair | 1.1 / 0.0 / 3.7 | 3 | 0 |
| Concrete plant | 1.2 / 1.4 / 0.0 | 3 | 1 |
| Sugar mill / refinery | 0.1 / 0.0 / 0.0 | 0 | 0 |
| Fruit & vegetable processing | 0.1 / 0.0 / 0.0 | 0 | 0 |
| Brewery | 0.8 / 0.0 / 0.0 | 2 | 0 |

#### Utilities

| Building | Real rate per 100k (urban FL / rural FL / Keys) | Metro | Rural towns |
|---|---|---|---|
| Power plant (private / utility) | 0.5 / 0.0 / 0.0 | 1 | 0 |
| Power transmission / substation op. | 1.9 / 0.0 / 0.0 | 4 | 0 |
| Water supply | 0.9 / 1.8 / 3.7 | 2 | 1 |
| Sewage treatment | 0.0 / 1.4 / 0.0 | 0 | 1 |
| Waste collection | 2.1 / 1.4 / 12.3 | 5 | 1 |
| Landfill | 0.3 / 0.0 / 0.0 | 1 | 0 |
| Recycling / materials recovery | 0.3 / 0.0 / 0.0 | 1 | 0 |
| Scrap yard | 2.1 / 0.0 / 0.0 | 5 | 0 |

## 3. Civic, government and infrastructure

The business data doesn't include government, so these use national totals per 100,000 people.

| Facility | Real rate per 100k (US) | In Costa Verde | Source |
|---|---|---|---|
| Fire station | 15.6 | 47 | USFA National Fire Department Registry, Jan 2023 |
| Public elementary school | 15.7 | 47 | NCES via Education Week |
| Public middle school | 4.9 | 15 | NCES via Education Week |
| Public high school | 7.1 | 21 | NCES via Education Week |
| Post office (USPS-run) | 9.3 | 28 | USPS Postal Facts |
| Hospital (all) | 1.8 | 5 | AHA Fast Facts 2024 |
| Religious congregation (all) | 107.0 | 320 | U.S. Religion Census 2020 |
| Municipal landfill | 0.5 | 1 | EREF (2013 data), via Waste Dive |

**Needed, but no reliable national count found yet** (each listed in the APA checklist):
- Police stations
- Courthouses
- City hall and county government centre
- Public libraries
- Water treatment plants
- Wastewater treatment plants
- Electrical substations
- Cell towers
- Bus depots
- Rail yards
- Water towers
- Prisons and jails
- Military base (the map already has Fort Calusa)

Florida-specific power facts: natural gas makes about 75% of Florida's electricity, from about 50 utility-scale
gas plants (EIA, 2019 count) and 2 nuclear plants. At Costa Verde's size that's 1 gas-fired power plant. There
should also be solar farms in the farm belt, since about 75% of Florida's solar capacity is utility-scale.

## 4. What the map still needs to place these

- **Lot types:** big-box stores, malls and supercenters need large footprints with car parks. Gas
  stations need corner lots with canopies, car dealers need display lots, warehouses need loading
  yards, and power plants, landfills and water plants need large industrial sites. Today the generator
  only makes plain frontage lots.
- **Placement rules from real data:** where each type sits (gas stations at junctions and interchanges,
  big-box stores near freeway exits, schools inside neighbourhoods, industry near the port and rail). The
  next step is to measure these from real data the same way the roads were, not to write them by hand.
- **Rural and Keys mixes:** rural towns use the rural rates (more gas stations, dollar stores and
  churches per person). The Keys need their own small towns, with many hotels, marinas, bars and boat
  dealers per person.

## Sources

1. GameGrin, "5 awesome things to do in Los Santos": https://gamegrin.com/articles/5-awesome-things-to-do-in-los-santos
2. GamePressure GTA V guide (4 Los Santos Customs, 6 tattoo parlours): https://www.gamepressure.com/gtav/shopping-1/z154bf
3. GTA VI locations: Rockstar's official site names Vice City, the Leonida Keys, Grassrivers, Port Gellhorn,
   Ambrosia and Mount Kalaga; individual venues come from fan sites and are unconfirmed:
   https://rockstarreport.com/features/gta-6-map-locations-confirmed-leaked-rumoured-leonida ,
   https://www.gtasixmap.com/guides/all-gta-6-locations
4. Supercheats GTA V business guide: https://www.supercheats.com/grand-theft-auto-5/wiki/business-yellow-pages-guide
5. GTA Wiki (Bob Mulét salon): https://gta.fandom.com/wiki/File:FcEIIMQ.png
6. APA Land Based Classification Standards: https://planning.org/lbcs/standards/function/
7. US Census County Business Patterns 2022: https://www2.census.gov/programs-surveys/cbp/datasets/2022/
8. US Census county population estimates 2023: https://www2.census.gov/programs-surveys/popest/datasets/2020-2023/counties/totals/
9. Census 2020 urban areas (Miami–Fort Lauderdale): https://www.census.gov/programs-surveys/geography/guidance/geo-areas/urban-rural/2020-ua-facts.html
10. USFA fire department registry: https://www.usfa.fema.gov/downloads/pdf/registry-summary-2023.pdf
11. NCES public schools: https://nces.ed.gov/fastfacts/display.asp?id=84 , Education Week explainer: https://www.edweek.org/ew/issues/education-statistics/index.html
12. USPS Postal Facts: https://facts.usps.com/size
13. AHA Fast Facts on US Hospitals 2024: https://www.aha.org/statistics/fast-facts-us-hospitals
14. U.S. Religion Census 2020: https://usreligioncensus.org/node/1641
15. Landfills (EREF via Waste Dive): https://www.wastedive.com/news/eref-sees-new-comprehensive-facility-list-as-first-step-in-analyzing-bigger/507062/
16. EIA Florida electricity profile: https://www.eia.gov/electricity/state/florida/ , EIA natural gas plants note: https://www.eia.gov/todayinenergy/detail.php?id=41233
17. Interchange mix (diamonds ~61% nationally): https://www.tandfonline.com/doi/abs/10.1080/00330124.2021.1949730
