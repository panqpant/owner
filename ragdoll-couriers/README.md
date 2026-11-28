# Ragdoll Couriers: kill test

The week-1 test from the plan (`docs/`): does riding a wobbly scooter with a fragile parcel feel fun on a
phone? If not, we switch to Flip It before building anything else.

## What's in it
- A test road from the **Depot** to **42 Fragile Lane**: speed bumps, loose crates, a ramp, cobbles, a narrow
  alley and a hill.
- A scooter with a cargo box. The parcel shifts around inside it.
- Crash into something or land badly and you ragdoll off; you're back on the scooter in under 2 seconds.
- Parcels cycle: Pillow → TV → Vase → Fish Tank. Pay = parcel value × condition, +20% if fast, +25% if you didn't crash.
- If you drop the parcel, ride next to it to scoop it up, or it comes back by itself after 20 seconds (−15%).
- **Feel** button: cycles three driving presets (Twitchy / Balanced / Heavy). **Reset** (or R) stands the scooter back up.

## Run it
1. Install [Rojo](https://rojo.space) (the Studio plugin and the CLI).
2. From this folder: `rojo serve`, then in Studio open a new **Baseplate**, delete the Baseplate part, and
   click **Connect** in the Rojo plugin.
3. Press **Play**. Controls: W/S or the arrow keys to go and brake, A/D to steer. On a phone you get the
   thumbstick plus big GO / STOP buttons.
4. To test on your phone: **File → Publish to Roblox**, then open the game on your phone. Device emulation in
   Studio is not the same thing.

## What to judge (the kill test)
Play 10 minutes on your phone, then answer:
1. Is the first crash funny?
2. Do you slow down for the TV without being told twice?
3. Does steering feel fine, or does it fight you? Which **Feel** preset is best?
4. Do you want "one more delivery"?

Two clear "no"s → switch to Flip It. Otherwise, tell me what felt off and I'll tune it.

## Tuning
Every number is in `src/shared/Config.luau`: driving presets, how hard a hit has to be to throw you off
(`CrashDeltaV`), parcel fragility, and pay.

## Tests
`lune run tests/formula.spec.luau` checks the damage and payout maths.
