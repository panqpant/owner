// Overworld lighting data (fieldfx.c), read by the renderer.
#ifndef PC_FIELDFX_H
#define PC_FIELDFX_H
#define PC_MAX_LIGHTS 24
#define PC_MAX_SHADOWS 32
#define PC_WATER_ROWS 13
enum { PC_WEATHER_NONE, PC_WEATHER_RAIN, PC_WEATHER_DOWNPOUR, PC_WEATHER_SANDSTORM };
struct PcFieldFx {
    int outdoors;
    int weather;                         // PC_WEATHER_*: redrawn in HD by the renderer
    int hideTileStart[2], hideTileCount[2]; // OBJ tiles of the original weather sprites
    int waterX, waterY, waterCols;       // screen position of the water grid's first metatile
    int water[PC_WATER_ROWS];            // bit per metatile column: water

    int numLights, numShadows;
    struct { short x, y, radius; } lights[PC_MAX_LIGHTS];   // GBA screen coords
    struct { short x, y, w; } shadows[PC_MAX_SHADOWS];      // feet position, width
};
extern struct PcFieldFx gPcFieldFx;
extern int gPcHdEffects; // renderer is drawing HD weather (hide the original sprites in HD layers)
void PcUpdateFieldFx(void);
#endif
