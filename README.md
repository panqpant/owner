# Sky Obby

A Roblox obstacle course that builds itself. One server script generates a 12-stage sky course with
checkpoints, kill bricks, moving platforms, spinning bars, collectible coins, and a win pad. Player
progress (Stage, Coins, Wins) shows on the leaderboard and is saved between sessions.

## Put it in Roblox Studio (easiest)

1. Open Roblox Studio and create a new **Baseplate** place.
2. In the Explorer, right-click **ServerScriptService** → **Insert Object** → **Script**.
3. Delete the default `print("Hello world!")` and paste in everything from
   [`src/server/Obby.server.luau`](src/server/Obby.server.luau).
4. Press **Play**. You'll spawn on the START pad.

To save progress while testing in Studio: **Home → Game Settings → Security → Enable Studio Access to API
Services** (the place must be published first). Without it the game still works; it just won't save.

## Or sync with Rojo

```sh
rojo serve
```

Then connect from the Rojo plugin in Studio.

## Tweaking

The constants at the top of the script control the game:

| Constant      | What it does                       |
| ------------- | ---------------------------------- |
| `STAGE_COUNT` | Number of stages                   |
| `GAP`         | Distance between checkpoints       |
| `COIN_VALUE`  | Coins per coin pickup              |
| `WIN_BONUS`   | Coins awarded for finishing        |

To add a new obstacle type, add a function to the `obstacles` table. It receives the checkpoint's `z`,
the height `y`, and the stage color.
