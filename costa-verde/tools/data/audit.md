# World audit

## Road network
total road length 547 km in 1 pieces
- [PASS] connected network: 100.0% of all road length is one connected network (target > 97%)
  disconnected pieces: 0, total 0.0 km, largest 0.00 km
dead ends by kind: {'access': 148, 'collector': 89, 'street': 94, 'county': 7, 'drive': 145}
- [PASS] major roads don't just stop: 0 loose major-road ends, 0 outside Key Marisol: []
rural county-road dead ends: 7 of 229 county junctions/ends (3%; real rural networks: 34%)
- [PASS] freeways are grade-separated: 0 places where a surface road meets a freeway mid-span at grade (should only connect via ramps)
interchange ramps: 2208 segments
- [PASS] city dead ends like real cities: 8% of city street junctions are dead ends (real US: 12-27%, mostly cul-de-sacs)

## Land use
- [PASS] built-up land reached by roads: 98.1% of built-up land is within 150 studs of a road
- [PASS] built-up land has buildings: 96.5% of built-up land has a building within 130 studs

## Water
- [PASS] no roads driving through water: 0.00 km of road over water without a bridge (exact terrain); by kind (studs) {}

## Buildings
- [PASS] buildings not on roads: 47 of 7383 buildings (0.64%) overlap a road
- [PASS] buildings not overlapping: 2 overlapping pairs
buildings by district: {'northshore': 1708, 'palmgrove': 1310, 'gulftown': 1160, 'westside': 750, 'calle': 409, 'rural': 376, 'beach': 337, 'university': 316, 'downtown': 295, 'midtown': 251, 'swamptown': 181, 'truckstop': 150, 'keytown': 68, 'docks': 38, 'hamlet': 34}

## Street patterns vs real data (2.4 km windows at district centres)
  downtown   (tower    ) density_ 16.18/12.48  block_me 160.30/260.85  straight 0.98/0.98  dead_end 0.05/0.16  t_frac 0.55/0.44  cross_fr 0.40/0.40  orientat 0.96/0.83
  midtown    (midrise  ) density_ 20.32/15.04  block_me 160.00/278.01  straight 0.98/0.99  dead_end 0.06/0.10  t_frac 0.54/0.51  cross_fr 0.40/0.39  orientat 0.98/0.98
  calle      (stucco   ) density_ 13.35/12.67  block_me 200.00/296.93  straight 0.98/0.99  dead_end 0.04/0.17  t_frac 0.62/0.44  cross_fr 0.35/0.39  orientat 0.98/0.99
  docks      (warehouse) density_ 8.70/6.60  block_me 200.19/441.04  straight 0.94/0.95  dead_end 0.11/0.24  t_frac 0.53/0.63  cross_fr 0.36/0.13  orientat 0.84/0.87
  northshore (house    ) density_ 9.74/10.07  block_me 200.00/293.33  straight 0.98/0.96  dead_end 0.17/0.27  t_frac 0.55/0.64  cross_fr 0.28/0.09  orientat 0.76/0.66
  westside   (house    ) density_ 11.38/10.07  block_me 165.02/293.33  straight 0.98/0.96  dead_end 0.09/0.27  t_frac 0.70/0.64  cross_fr 0.21/0.09  orientat 0.61/0.66
  palmgrove  (house    ) density_ 17.10/10.07  block_me 181.14/293.33  straight 0.99/0.96  dead_end 0.05/0.27  t_frac 0.68/0.64  cross_fr 0.27/0.09  orientat 0.73/0.66
  university (campus   ) density_ 12.70/11.75  block_me 200.09/298.52  straight 0.99/0.97  dead_end 0.11/0.20  t_frac 0.62/0.66  cross_fr 0.27/0.14  orientat 0.77/0.81
  gulftown   (stucco   ) density_ 12.05/12.67  block_me 277.05/296.93  straight 0.98/0.99  dead_end 0.17/0.17  t_frac 0.41/0.44  cross_fr 0.41/0.39  orientat 0.98/0.99

## Building uses
- [PASS] building uses match the real mix: top uses within 2x of real Florida shares
- [PASS] every building has a use: 0 without a use
map markers: {'liquor': 5, 'food': 10, 'gun_store': 8, 'clothing': 10, 'hospital': 8, 'gas': 15, 'barber': 6, 'bar': 6, 'pawn': 3, 'tattoo': 5, 'car_dealer': 4, 'fire': 3, 'convenience': 12, 'bank': 4, 'boat_dealer': 3, 'mod_shop': 5, 'jewelry': 2, 'cinema': 2, 'police': 6, 'gym': 3}

## Landmarks
- [PASS] all 200 landmarks placed: 200 of 200 placed
- [PASS] landmarks on land (except offshore ones): 0 on water: []
- [PASS] no road through a landmark: 0 landmarks with a road through them: []
- [PASS] no ordinary building inside a landmark: 0 buildings inside landmark footprints
- [PASS] landmarks reachable by road (boat/air for islets and offshore): 0 with no road nearby: []
landmark sites: {'bridge': 2, 'open': 38, 'shore': 27, 'urban': 126, 'offshore': 4, 'islet': 3}

## Transit
- [PASS] stations reachable from a road: 0 of 33 stations have no road within ~150 studs
lines: {'Coastline Railway': 841, 'Gulf Line': 654, 'Citrus Freight': 364, 'Metro Green': 450, 'Metro Orange': 150}

all checks passed
