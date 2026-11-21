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
    int flash;                           // lightning brightness 0-16 (thunderstorms)
    int gridX, gridY;                    // screen position of the grid's first metatile
    int gridWX, gridWY;                  // its map coordinates (world position = cell * 16)
    unsigned char grid[PC_GRID_H][PC_GRID_W]; // PC_CELL_* flags around the camera

    int numLights, numShadows;
    struct { short x, y, radius; } lights[PC_MAX_LIGHTS];   // GBA screen coords
    struct { short x, y, w; } shadows[PC_MAX_SHADOWS];      // feet position, width
};
extern struct PcFieldFx gPcFieldFx;
extern int gPcHdEffects; // renderer is drawing HD weather (hide the original sprites in HD layers)
void PcUpdateFieldFx(void);
#endif
