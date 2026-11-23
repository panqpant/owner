# World audit

## Road network
total road length 458 km in 1 pieces
- [PASS] connected network: 100.0% of all road length is one connected network (target > 97%)
  disconnected pieces: 0, total 0.0 km, largest 0.00 km
dead ends by kind: {'freeway': 1, 'state': 3, 'arterial': 3, 'collector': 34, 'street': 82, 'county': 21, 'drive': 147}
- [PASS] major roads don't just stop: 7 loose major-road ends: 5 at the coast or map edge, 2 inland [('state', 6963, 6144), ('state', 4915, 4096)]
- [PASS] city dead ends like real cities: 6% of city street junctions are dead ends (real US: 12-27%, mostly cul-de-sacs)

## Land use
- [PASS] built-up land reached by roads: 97.6% of built-up land is within 150 studs of a road
- [PASS] built-up land has buildings: 94.2% of built-up land has a building within 130 studs

## Water
- [PASS] no roads driving through water: 0.00 km of road over water without a bridge (exact terrain); by kind (studs) {}

## Buildings
- [PASS] buildings not on roads: 43 of 7355 buildings (0.58%) overlap a road
- [PASS] buildings not overlapping: 6 overlapping pairs
buildings by district: {'northshore': 1553, 'palmgrove': 1463, 'gulftown': 1162, 'westside': 849, 'calle': 465, 'rural': 385, 'beach': 363, 'downtown': 334, 'university': 324, 'midtown': 280, 'docks': 60, 'hamlet': 59, 'swamptown': 32, 'truckstop': 26}

## Street patterns vs real data (2.4 km windows at district centres)
  downtown   (tower    ) density_ 14.84/12.48  block_me 160.24/260.85  straight 0.97/0.98  dead_end 0.11/0.16  t_frac 0.51/0.44  cross_fr 0.38/0.40  orientat 0.98/0.83
  midtown    (midrise  ) density_ 21.66/15.04  block_me 160.00/278.01  straight 0.98/0.99  dead_end 0.01/0.10  t_frac 0.59/0.51  cross_fr 0.40/0.39  orientat 0.99/0.98
  calle      (stucco   ) density_ 12.97/12.67  block_me 239.95/296.93  straight 0.98/0.99  dead_end 0.09/0.17  t_frac 0.61/0.44  cross_fr 0.30/0.39  orientat 0.98/0.99
  docks      (warehouse) density_ 8.94/6.60  block_me 210.62/441.04  straight 0.95/0.95  dead_end 0.13/0.24  t_frac 0.48/0.63  cross_fr 0.39/0.13  orientat 0.83/0.87
  northshore (house    ) density_ 10.50/10.07  block_me 194.04/293.33  straight 0.98/0.96  dead_end 0.12/0.27  t_frac 0.66/0.64  cross_fr 0.21/0.09  orientat 0.70/0.66
  westside   (house    ) density_ 13.08/10.07  block_me 181.08/293.33  straight 0.98/0.96  dead_end 0.12/0.27  t_frac 0.64/0.64  cross_fr 0.24/0.09  orientat 0.59/0.66
  palmgrove  (house    ) density_ 18.24/10.07  block_me 184.74/293.33  straight 0.99/0.96  dead_end 0.07/0.27  t_frac 0.67/0.64  cross_fr 0.26/0.09  orientat 0.64/0.66
  university (campus   ) density_ 15.30/11.75  block_me 200.00/298.52  straight 0.99/0.97  dead_end 0.09/0.20  t_frac 0.69/0.66  cross_fr 0.22/0.14  orientat 0.82/0.81
  gulftown   (stucco   ) density_ 11.24/12.67  block_me 280.00/296.93  straight 0.98/0.99  dead_end 0.15/0.17  t_frac 0.47/0.44  cross_fr 0.37/0.39  orientat 1.00/0.99

## Transit
- [PASS] stations reachable from a road: 0 of 33 stations have no road within ~150 studs
lines: {'Coastline Railway': 843, 'Gulf Line': 649, 'Citrus Freight': 351, 'Metro Green': 450, 'Metro Orange': 150}

all checks passed
