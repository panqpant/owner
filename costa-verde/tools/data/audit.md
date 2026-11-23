# World audit

## Road network
total road length 524 km in 1 pieces
- [PASS] connected network: 100.0% of all road length is one connected network (target > 97%)
  disconnected pieces: 0, total 0.0 km, largest 0.00 km
dead ends by kind: {'state': 3, 'arterial': 3, 'access': 148, 'collector': 99, 'street': 98, 'county': 13, 'drive': 109}
- [PASS] major roads don't just stop: 6 loose major-road ends: 4 at the coast or map edge, 2 inland [('state', 28672, 4096), ('state', 4915, 4096)]
- [PASS] freeways are grade-separated: 0 places where a surface road meets a freeway mid-span at grade (should only connect via ramps)
interchange ramps: 2204 segments
- [PASS] city dead ends like real cities: 9% of city street junctions are dead ends (real US: 12-27%, mostly cul-de-sacs)

## Land use
- [PASS] built-up land reached by roads: 98.0% of built-up land is within 150 studs of a road
- [PASS] built-up land has buildings: 96.6% of built-up land has a building within 130 studs

## Water
- [PASS] no roads driving through water: 0.02 km of road over water without a bridge (exact terrain); by kind (studs) {'collector': 40}

## Buildings
- [PASS] buildings not on roads: 29 of 7233 buildings (0.40%) overlap a road
- [PASS] buildings not overlapping: 5 overlapping pairs
buildings by district: {'northshore': 1707, 'palmgrove': 1317, 'gulftown': 1142, 'westside': 718, 'calle': 400, 'beach': 333, 'university': 311, 'downtown': 296, 'rural': 283, 'midtown': 261, 'swamptown': 194, 'truckstop': 159, 'keytown': 61, 'docks': 38, 'hamlet': 13}

## Street patterns vs real data (2.4 km windows at district centres)
  downtown   (tower    ) density_ 15.92/12.48  block_me 161.04/260.85  straight 0.98/0.98  dead_end 0.07/0.16  t_frac 0.54/0.44  cross_fr 0.39/0.40  orientat 0.97/0.83
  midtown    (midrise  ) density_ 20.28/15.04  block_me 160.01/278.01  straight 0.97/0.99  dead_end 0.06/0.10  t_frac 0.54/0.51  cross_fr 0.41/0.39  orientat 0.99/0.98
  calle      (stucco   ) density_ 13.02/12.67  block_me 200.00/296.93  straight 0.98/0.99  dead_end 0.06/0.17  t_frac 0.61/0.44  cross_fr 0.33/0.39  orientat 0.98/0.99
  docks      (warehouse) density_ 8.70/6.60  block_me 200.19/441.04  straight 0.94/0.95  dead_end 0.11/0.24  t_frac 0.53/0.63  cross_fr 0.36/0.13  orientat 0.84/0.87
  northshore (house    ) density_ 9.41/10.07  block_me 199.86/293.33  straight 0.98/0.96  dead_end 0.18/0.27  t_frac 0.56/0.64  cross_fr 0.26/0.09  orientat 0.79/0.66
  westside   (house    ) density_ 11.36/10.07  block_me 162.65/293.33  straight 0.98/0.96  dead_end 0.09/0.27  t_frac 0.71/0.64  cross_fr 0.20/0.09  orientat 0.61/0.66
  palmgrove  (house    ) density_ 17.19/10.07  block_me 184.59/293.33  straight 0.99/0.96  dead_end 0.05/0.27  t_frac 0.68/0.64  cross_fr 0.27/0.09  orientat 0.73/0.66
  university (campus   ) density_ 12.70/11.75  block_me 200.09/298.52  straight 0.99/0.97  dead_end 0.11/0.20  t_frac 0.62/0.66  cross_fr 0.27/0.14  orientat 0.77/0.81
  gulftown   (stucco   ) density_ 10.41/12.67  block_me 280.00/296.93  straight 0.98/0.99  dead_end 0.27/0.17  t_frac 0.32/0.44  cross_fr 0.41/0.39  orientat 1.00/0.99

## Building uses
- [PASS] building uses match the real mix: top uses within 2x of real Florida shares
- [PASS] every building has a use: 0 without a use
map markers: {'tattoo': 5, 'clothing': 10, 'liquor': 5, 'hospital': 3, 'gas': 15, 'convenience': 12, 'barber': 6, 'bar': 6, 'car_dealer': 4, 'bank': 4, 'gym': 3, 'pawn': 3, 'jewelry': 2, 'gun_store': 8, 'food': 10, 'cinema': 3, 'arcade': 2, 'police': 6, 'mod_shop': 5, 'fire': 3, 'boat_dealer': 3}

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
