# World audit

## Road network
total road length 521 km in 1 pieces
- [PASS] connected network: 100.0% of all road length is one connected network (target > 97%)
  disconnected pieces: 0, total 0.0 km, largest 0.00 km
dead ends by kind: {'access': 164, 'collector': 85, 'street': 88, 'county': 6, 'drive': 114}
- [PASS] major roads don't just stop: 0 loose major-road ends, 0 outside Key Marisol: []
rural county-road dead ends: 6 of 183 county junctions/ends (3%; real rural networks: 34%)
- [PASS] freeways are grade-separated: 0 places where a surface road meets a freeway mid-span at grade (should only connect via ramps)
interchange ramps: 2208 segments
- [PASS] city dead ends like real cities: 9% of city street junctions are dead ends (real US: 12-27%, mostly cul-de-sacs)

## Land use
- [PASS] built-up land reached by roads: 97.8% of built-up land is within 150 studs of a road
- [PASS] built-up land has buildings: 97.3% of built-up land has a building within 130 studs

## Water
- [PASS] no roads driving through water: 0.02 km of road over water without a bridge (exact terrain); by kind (studs) {'county': 40}

## Buildings
- [PASS] buildings not on roads: 4 of 12369 buildings (0.03%) overlap a road
- [PASS] every building has a real shape: 0 without parts, 0 part corners outside their lot
- [PASS] building shapes clear of roads: 3 buildings (0.02%) with a part corner on a road
building types: 25 kinds; top: {'shopfronts': 2979, 'ranch': 1416, 'l_ranch': 1198, 'courtyard': 1098, 'colonial': 1009, 'duplex': 745, 'art deco': 635, 'townhouses': 536, 'midrise': 499, 'Fast food': 425, 'split_level': 406, 'tower': 363}

## Building footprints vs real (FEMA USA Structures)
| style | n | area m² p10/p50/p90 gen (real) | long×short m p50 | plain boxes | end-on | setback m p50 | gap m p50 |
|---|---|---|---|---|---|---|---|
| campus | 347 | 68/450/2854 (92/698/3238) | 32×18 (41×20) | 0.49 (0.42) | 0.51 (0.45) | 11 (21) | 4.7 (7.5) |
| deco | 733 | 62/223/1193 (76/271/1253) | 20×13 (23×14) | 0.39 (0.40) | 0.49 (0.53) | 11 (18) | 3.1 (3.8) |
| house | 6526 | 121/263/429 (156/288/426) | 19×15 (20×16) | 0.58 (0.51) | 0.49 (0.47) | 13 (16) | 3.1 (4.8) |
| midrise | 564 | 58/198/1728 (74/240/2197) | 19×12 (22×12) | 0.59 (0.55) | 0.48 (0.58) | 11 (13) | 2.7 (4.9) |
| shack | 486 | 55/153/450 (67/174/556) | 16×10 (17×11) | 0.65 (0.68) | 0.55 (0.56) | 13 (16) | 3.6 (6.0) |
| stucco | 2965 | 63/185/660 (76/195/667) | 18×11 (19×11) | 0.65 (0.60) | 0.61 (0.73) | 13 (15) | 2.6 (3.7) |
| tower | 404 | 66/394/3606 (86/822/5842) | 26×15 (42×24) | 0.43 (0.38) | 0.51 (0.53) | 11 (11) | 5.7 (9.5) |
| warehouse | 59 | 68/1098/4310 (92/1452/7033) | 39×23 (56×27) | 0.31 (0.34) | 0.56 (0.40) | 11 (33) | 6.1 (7.8) |
- [FAIL] footprints match real buildings: size, spread, shape, orientation, setback and gap within range of the real data; off: ['campus', 'tower', 'warehouse']
- [PASS] buildings not overlapping: 0 overlapping pairs
buildings by district: {'northshore': 2976, 'palmgrove': 2299, 'gulftown': 2081, 'westside': 1251, 'beach': 733, 'calle': 727, 'midtown': 564, 'downtown': 404, 'university': 347, 'swamptown': 266, 'rural': 264, 'truckstop': 220, 'keytown': 157, 'docks': 59, 'hamlet': 21}

## Street patterns vs real data (2.4 km windows at district centres)
  downtown   (tower    ) density_ 11.21/12.48  block_me 200.02/260.85  straight 0.94/0.98  dead_end 0.08/0.16  t_frac 0.50/0.44  cross_fr 0.42/0.40  orientat 1.00/0.83
  midtown    (midrise  ) density_ 16.84/15.04  block_me 240.00/278.01  straight 0.98/0.99  dead_end 0.05/0.10  t_frac 0.54/0.51  cross_fr 0.41/0.39  orientat 1.00/0.98
  calle      (stucco   ) density_ 11.31/12.67  block_me 240.00/296.93  straight 0.96/0.99  dead_end 0.05/0.17  t_frac 0.69/0.44  cross_fr 0.26/0.39  orientat 0.99/0.99
  docks      (warehouse) density_ 7.15/6.60  block_me 237.02/441.04  straight 0.98/0.95  dead_end 0.18/0.24  t_frac 0.61/0.63  cross_fr 0.21/0.13  orientat 0.92/0.87
  northshore (house    ) density_ 9.74/10.07  block_me 200.00/293.33  straight 0.98/0.96  dead_end 0.17/0.27  t_frac 0.55/0.64  cross_fr 0.28/0.09  orientat 0.76/0.66
  westside   (house    ) density_ 11.38/10.07  block_me 165.02/293.33  straight 0.98/0.96  dead_end 0.09/0.27  t_frac 0.70/0.64  cross_fr 0.21/0.09  orientat 0.61/0.66
  palmgrove  (house    ) density_ 17.23/10.07  block_me 163.52/293.33  straight 0.99/0.96  dead_end 0.05/0.27  t_frac 0.69/0.64  cross_fr 0.26/0.09  orientat 0.73/0.66
  university (campus   ) density_ 10.01/11.75  block_me 239.58/298.52  straight 0.97/0.97  dead_end 0.05/0.20  t_frac 0.68/0.66  cross_fr 0.27/0.14  orientat 0.87/0.81
  gulftown   (stucco   ) density_ 12.05/12.67  block_me 277.05/296.93  straight 0.98/0.99  dead_end 0.17/0.17  t_frac 0.41/0.44  cross_fr 0.41/0.39  orientat 0.98/0.99

## Building uses
- [PASS] building uses match the real mix: top uses within 2x of real Florida shares
- [PASS] every building has a use: 0 without a use
map markers: {'car_dealer': 4, 'clothing': 10, 'pawn': 3, 'gas': 15, 'convenience': 12, 'barber': 6, 'bank': 4, 'gym': 3, 'tattoo': 5, 'food': 10, 'bar': 6, 'police': 6, 'arcade': 3, 'fire': 3, 'gun_store': 8, 'liquor': 5, 'mod_shop': 5, 'jewelry': 2, 'boat_dealer': 3}

## Landmarks
- [PASS] all 200 landmarks placed: 200 of 200 placed
- [PASS] landmarks on land (except offshore ones): 0 on water: []
- [PASS] no road through a landmark: 0 landmarks with a road through them: []
- [PASS] no ordinary building inside a landmark: 0 buildings inside landmark footprints
- [PASS] landmarks reachable by road (boat/air for islets and offshore): 0 with no road nearby: []
landmark sites: {'bridge': 2, 'open': 38, 'shore': 27, 'urban': 126, 'offshore': 4, 'islet': 3}

## Transit
- [PASS] stations reachable from a road: 0 of 33 stations have no road within ~150 studs
lines: {'Coastline Railway': 1028, 'Gulf Line': 654, 'Citrus Freight': 285, 'Metro Green': 450, 'Metro Orange': 150}

1 failed checks: ['footprints match real buildings']
