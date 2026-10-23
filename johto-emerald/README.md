# Johto Emerald

Pokémon Emerald turned into the Johto region from HeartGold/SoulSilver, keeping Emerald's graphics.

## How to play it

You don't upload anything. The patch goes onto your own ROM on your own device.

1. You need your own **Pokémon Emerald (USA)** ROM. The correct one has SHA-1
   `f3ae088181bf583e55daf962a92bb46f4f1d07b7`.
2. Open an online patcher such as Rom Patcher JS (search "Rom Patcher JS"). Everything runs in your browser and nothing is uploaded.
3. For **ROM file**, pick your Emerald ROM. For **Patch file**, pick `patch/johto-emerald.xdelta`.
4. Click **Apply patch**, save the new `.gba`, and play it in any GBA emulator.

Start a **new game**. Old Emerald saves won't match.

## What's Johto already (phase 1)

| | Emerald | Now |
|---|---|---|
| Starters | Treecko / Torchic / Mudkip | **Chikorita / Cyndaquil / Totodile** |
| Professor | Birch (intro Pokémon: Lotad) | **Elm** (intro Pokémon: Marill) |
| Gym leaders | Roxanne … Juan | **Falkner, Bugsy, Whitney, Morty, Chuck, Jasmine, Pryce, Clair**, using their HGSS teams and movesets |
| Badges | Stone … Rain | **Zephyr, Hive, Plain, Fog, Storm, Mineral, Glacier, Rising** |
| Elite Four | Sidney, Phoebe, Glacia, Drake | **Will, Koga, Bruno, Karen** |
| Champion | Wallace | **Lance** |
| Post-game | Steven in Meteor Falls | **Red** (Pikachu, Espeon, Snorlax, Venusaur, Charizard, Blastoise) |
| Rival | May/Brendan | Johto starter + Silver's team (Gastly, Zubat, Magnemite, Sneasel lines) |
| Villains | Team Magma / Team Aqua | **Team Rocket** (Giovanni, Archer, Ariana, Proton, Petrel) |
| Wild Pokémon | Hoenn | HGSS route rosters on the main path (Route 29: Pidgey, Sentret, Rattata, Hoothoot…), Ice Path, Victory Road, Rocket Hideout; Johto/Kanto equivalents everywhere else |
| Trainers | Hoenn teams | Every Hoenn-only Pokémon swapped for a Johto/Kanto one with a similar role |
| Place names | Littleroot, Route 101… | New Bark Town, Route 29, Violet City, Ilex Forest, Union Cave, Dark Cave… |
| Pokédex | Hoenn dex until post-game | National Dex from the start, so Johto Pokémon register and evolve normally |

Levels follow Emerald's curve, so the difficulty stays balanced on the current maps.

## Not done yet (phase 2: the real Johto map)

The **towns and routes still have Hoenn's layouts**. They carry Johto names, Pokémon and trainers, but they're Hoenn's maps.
Rebuilding the actual Johto geography (New Bark → Cherrygrove → Violet … → Mt. Silver) with Emerald's tilesets is the next
phase, done town by town. Other known gaps:

- Story dialogue is still Emerald's plot with Johto names. For example, the Cianwood leader is still the player's dad, and Steven
  still appears in the main story.
- Leader and Elite Four sprites are still the Hoenn characters' sprites.
- Legendaries are still Emerald's (Groudon, Kyogre, Rayquaza, the Regis, Lati@s). They become Ho-Oh, Lugia, the beasts and Celebi
  when their maps are rebuilt.

## How it's built

There's no ROM in this repo. [pret/pokeemerald](https://github.com/pret/pokeemerald) is a source-code rebuild of Emerald.
`tools/` contains scripts that rewrite that source into Johto:

| Script | Changes |
|---|---|
| `johto_trainers.py` | Starters, gym leaders, Elite Four, champion, Red, rival teams |
| `johto_species.py` | Hoenn → Johto species swap in wild/trainer data, hardcoded story Pokémon, National Dex |
| `johto_wild.py` | HGSS route rosters for the story-path maps |
| `johto_text.py` | Renames places, people, teams and badges inside in-game text only |
| `johto_rewrap.py` | Re-wraps dialogue that no longer fits the text box after renaming (uses the real font widths) |

`./build.sh` clones pokeemerald at the commit in `UPSTREAM_COMMIT`, runs the scripts, builds, and regenerates the patch.
It first builds unmodified Emerald and checks that it matches retail byte-for-byte, so the patch works on a real ROM.
Build requirements: `git make gcc python3 libpng-dev binutils-arm-none-eabi xdelta3`.
