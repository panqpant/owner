# World audit

## Road network
total road length 534 km in 1 pieces
- [PASS] connected network: 100.0% of all road length is one connected network (target > 97%)
  disconnected pieces: 0, total 0.0 km, largest 0.00 km
dead ends by kind: {'freeway': 1, 'state': 3, 'arterial': 3, 'collector': 50, 'street': 92, 'county': 30, 'drive': 200}
- [PASS] major roads don't just stop: 7 loose major-road ends: 5 at the coast or map edge, 2 inland [('state', 6963, 6144), ('state', 4915, 4096)]
- [PASS] freeways are grade-separated: 0 places where a surface road meets a freeway mid-span at grade (should only connect via ramps)
interchange ramps: 2188 segments
- [PASS] city dead ends like real cities: 6% of city street junctions are dead ends (real US: 12-27%, mostly cul-de-sacs)

## Land use
- [PASS] built-up land reached by roads: 97.9% of built-up land is within 150 studs of a road
- [PASS] built-up land has buildings: 97.2% of built-up land has a building within 130 studs

## Water
- [PASS] no roads driving through water: 0.02 km of road over water without a bridge (exact terrain); by kind (studs) {'collector': 40}

## Buildings
- [PASS] buildings not on roads: 52 of 8116 buildings (0.64%) overlap a road
- [PASS] buildings not overlapping: 4 overlapping pairs
buildings by district: {'northshore': 1836, 'palmgrove': 1398, 'gulftown': 1201, 'westside': 819, 'rural': 527, 'calle': 443, 'beach': 376, 'university': 348, 'downtown': 334, 'midtown': 281, 'swamptown': 249, 'truckstop': 185, 'hamlet': 65, 'docks': 54}

## Street patterns vs real data (2.4 km windows at district centres)
  downtown   (tower    ) density_ 16.66/12.48  block_me 160.25/260.85  straight 0.98/0.98  dead_end 0.02/0.16  t_frac 0.58/0.44  cross_fr 0.40/0.40  orientat 0.96/0.83
  midtown    (midrise  ) density_ 21.89/15.04  block_me 160.01/278.01  straight 0.98/0.99  dead_end 0.01/0.10  t_frac 0.58/0.51  cross_fr 0.41/0.39  orientat 0.99/0.98
  calle      (stucco   ) density_ 13.61/12.67  block_me 200.02/296.93  straight 0.98/0.99  dead_end 0.02/0.17  t_frac 0.65/0.44  cross_fr 0.33/0.39  orientat 0.97/0.99
  docks      (warehouse) density_ 9.26/6.60  block_me 200.46/441.04  straight 0.95/0.95  dead_end 0.00/0.24  t_frac 0.60/0.63  cross_fr 0.40/0.13  orientat 0.82/0.87
  northshore (house    ) density_ 10.57/10.07  block_me 194.04/293.33  straight 0.98/0.96  dead_end 0.12/0.27  t_frac 0.67/0.64  cross_fr 0.21/0.09  orientat 0.70/0.66
  westside   (house    ) density_ 13.01/10.07  block_me 166.88/293.33  straight 0.98/0.96  dead_end 0.08/0.27  t_frac 0.70/0.64  cross_fr 0.22/0.09  orientat 0.64/0.66
  palmgrove  (house    ) density_ 17.77/10.07  block_me 184.74/293.33  straight 0.99/0.96  dead_end 0.03/0.27  t_frac 0.71/0.64  cross_fr 0.26/0.09  orientat 0.68/0.66
  university (campus   ) density_ 15.33/11.75  block_me 200.00/298.52  straight 0.99/0.97  dead_end 0.03/0.20  t_frac 0.68/0.66  cross_fr 0.29/0.14  orientat 0.73/0.81
  gulftown   (stucco   ) density_ 11.61/12.67  block_me 280.00/296.93  straight 0.98/0.99  dead_end 0.13/0.17  t_frac 0.51/0.44  cross_fr 0.36/0.39  orientat 1.00/0.99

## Transit
- [PASS] stations reachable from a road: 0 of 34 stations have no road within ~150 studs
lines: {'Coastline Railway': 841, 'Gulf Line': 654, 'Citrus Freight': 364, 'Metro Green': 450, 'Metro Orange': 150}

all checks passed
