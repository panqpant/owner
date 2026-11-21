// Stand-ins for assembly-only parts of the GBA build that have no PC
// meaning: the crt0 interrupt trampoline, GameCube link boot, ROM header.
#include <stdint.h>
#include <string.h>

typedef uint8_t u8; typedef uint32_t u32;

// crt0.s: the game copies IntrMain into IWRAM and points the BIOS vector at
// it. The PC frame loop dispatches gIntrTable directly instead.
void IntrMain(void) {}

// rom_header.s
const u8 RomHeaderGameCode[4] = { 'B', 'P', 'E', 'E' };
const u8 RomHeaderSoftwareVersion = 0;

// libgcnmultiboot.s: GameCube-to-GBA boot, never connected on PC.
struct GcmbStruct;
void GameCubeMultiBoot_Init(struct GcmbStruct *s) { (void)s; }
void GameCubeMultiBoot_Main(struct GcmbStruct *s) { (void)s; }
void GameCubeMultiBoot_ExecuteProgram(struct GcmbStruct *s) { (void)s; }
void GameCubeMultiBoot_HandleSerialInterrupt(struct GcmbStruct *s) { (void)s; }
void GameCubeMultiBoot_Quit(void) {}
