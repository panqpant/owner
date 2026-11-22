// Overworld lighting data (fieldfx.c), read by the renderer.
#ifndef PC_FIELDFX_H
#define PC_FIELDFX_H
#define PC_MAX_LIGHTS 24
#define PC_MAX_SHADOWS 32
#define PC_GRID_W 36
#define PC_GRID_H 16
// Per-metatile flags in the field grid.
enum {
    PC_CELL_SOLID = 1,   // impassable scenery (buildings, trees, rocks, walls): casts shadows
    PC_CELL_WATER = 2,
    PC_CELL_GRASS = 4,   // tall or long grass: sways
    PC_CELL_SAND  = 8,   // sand, deep sand, ash
    PC_CELL_LEDGE = 16,
    PC_CELL_PUDDLE = 32, // puddles and shallow water: rain ripples, reflections
};
enum { PC_WEATHER_NONE, PC_WEATHER_RAIN, PC_WEATHER_DOWNPOUR, PC_WEATHER_SANDSTORM };
struct PcFieldFx {
    int outdoors;
    int weather;                         // PC_WEATHER_*: redrawn in HD by the renderer
    int hideTileStart[2], hideTileCount[2]; // OBJ tiles of the original weather sprites
    int mapType;
    int flash;
    int ash;                             // volcanic ash falling (Route 113)
    int heat;
    int mood;                            // area atmosphere: 0 none, 1 rainforest, 2 desert, 3 Fortree canopy, 4 Sootopolis, 5 Mt. Pyre mist, 6 Lavaridge steam, 7 open ocean                            // heat haze (Mt. Chimney, Fiery Path, Magma Hideout)
    int playerX, playerY;                // player's feet, GBA screen coords (-999 if none)                           // lightning brightness 0-16 (thunderstorms)
    int gridX, gridY;                    // screen position of the grid's first metatile
    int gridWX, gridWY;                  // its map coordinates (world position = cell * 16)
    unsigned char grid[PC_GRID_H][PC_GRID_W]; // PC_CELL_* flags around the camera
    float wake[12][3];                   // swimming: [0] the player now, [1..] trail; world px x, y, game frame (-1 unused)

    int numLights, numShadows;
    struct { short x, y, radius; } lights[PC_MAX_LIGHTS];   // GBA screen coords
    struct { short x, y, w; } shadows[PC_MAX_SHADOWS];      // feet position, width
};
extern struct PcFieldFx gPcFieldFx;

// Ambient soundscape inputs (fieldfx.c), read by the audio mixer.
struct PcAmbient {
    float waterL, waterR;   // nearby water on each side (0-1)
    float trees;            // nearby trees and bushes
    float open;             // open outdoor area (wind)
    float rain, lava, cave, town;
    int active;             // overworld visible
};
extern struct PcAmbient gPcAmbient;


// Following Pokémon (fieldfx.c): the lead party Pokémon walks behind the
// player, drawn by the renderer from the game's own animated party icon.
struct PcFollower {
    int show;
    int species, iconVersion;          // iconVersion changes when the image changes
    int x, y;                          // icon top-left, GBA screen coords
    int flip, frame;
    int feetY;                         // for draw order against the player
    unsigned int rgba[64][32];         // two 32x32 frames, 0xAABBGGRR
    unsigned short col[64][32];        // the same in BGR555, bit 15 = opaque
    int prio, playerFeetY;
    float fadeMul[3], fadeAdd[3];      // the screen's current palette fade, applied to the icon
};
extern struct PcFollower gPcFollower;

enum { PC_BSCENE_ROUTE, PC_BSCENE_TOWN, PC_BSCENE_SEA, PC_BSCENE_POND, PC_BSCENE_SAND,
       PC_BSCENE_MOUNTAIN, PC_BSCENE_CAVE, PC_BSCENE_INDOOR, PC_BSCENE_UNDERWATER, PC_BSCENE_TALLGRASS };
// Battle scene data for the renderer (fieldfx.c, filled each battle frame).
struct PcBattleFx {
    int outdoors;
    int scene;   // new backdrop: -1 keep the game's, else PC_BSCENE_*
    int count;
    int boss;            // CINE_* style of a boss battle (0 = ordinary)
    int anim;            // a move animation is playing
    int attacker, target, moveType;
    float shake;         // 0-1: a hit just landed
    struct { short x, y, w, h; unsigned short tile; unsigned char side, visible; } mon[4]; // sprite rects (GBA screen coords), first OBJ tile
};
extern struct PcBattleFx gPcBattleFx;

// Cinematic story moments (fieldfx.c): letterbox, camera push, colour grade.
enum { CINE_NONE, CINE_SPOTTED, CINE_GYM, CINE_VILLAIN, CINE_LEGEND_RED, CINE_LEGEND_BLUE, CINE_LEGEND_GREEN,
       CINE_ANCIENT, CINE_MYSTIC, CINE_E4_SIDNEY, CINE_E4_PHOEBE, CINE_E4_GLACIA, CINE_E4_DRAKE, CINE_CHAMPION,
       CINE_HALL_OF_FAME, CINE_STORY, CINE_RIVAL, CINE_COUNT };
struct PcCine {
    int want;            // a cinematic moment is happening now
    int style;           // CINE_*
    int mapStyle;        // the current map's own style (also used for its battles)
    short fx, fy;        // camera focus, GBA screen coords
    float zoom;          // target zoom (1 = none)
};
extern struct PcCine gPcCine;
int PcBattleBoss(void);  // style for the current battle (0 = ordinary)
void PcUpdateBattleFx(void);
extern int gPcHdEffects; // renderer is drawing HD weather (hide the original sprites in HD layers)
void PcUpdateFieldFx(void);
#endif

// HD party screen (fieldfx.c): each slot's window rect and HP bar, GBA px
// (without the widescreen margin). state: 1 present, 2 cursor, 4 fainted, 8 picked to move.
struct PcPartyCard { float x, y, w, h, barX, barY, barW, hp; int state; };
int PcPartyUi(struct PcPartyCard out[6]);   // number of slot windows (0: not the party screen)
