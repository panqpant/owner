# HD texture packs

You can replace any of the game's 8×8 tiles (map tiles, characters, Pokémon, UI) with
hand-drawn high-resolution art. Replacements are drawn at your screen's full resolution.
Anything without a replacement keeps the automatic xBR upscale.

## Making a replacement

1. Start the game and press **F6**. The window title shows that tiles are being dumped.
   Walk around or open the screens whose art you want to redraw. Every tile that appears
   is saved once to `hd/dump/<hash>.png` (8×8, transparent where the game draws nothing).
2. Press **F6** again to stop.
3. Redraw a tile at a larger size, square and a multiple of 8 (32×32 is 4× detail,
   64×64 is 8×). Keep the same file name.
4. Put it in `hd/tiles/<hash>.png` next to the game and restart.

All replacements in a pack should use the same scale. The first one loaded sets the scale,
and others are resized to match.

## How tiles are matched

The 16-hex-digit hash covers the tile's pixels and the palette colours it uses. The same
drawing in a different palette, such as another colour variant, is a different tile.
Matching uses the game's unfaded palette, so replacements stay in place during screen
fades, and the fade is re-applied to your art automatically.

Rotated or scaled sprites (some battle animations) always use the automatic upscale.

## Tips

- A large object is made of several tiles. Draw the whole object at high resolution,
  then cut it into 8×8-cell pieces (32×32 at 4×), each saved under its tile's hash.
- Alpha is respected: semi-transparent edges blend smoothly over what's behind them.
