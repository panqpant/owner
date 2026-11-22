// Wonder Trade replica (wondertrade.c game side, frontend overlay UI).
// Offline: the "trade partner" and the Pokémon they send are generated
// locally, then the game's own trade sequence plays.
#ifndef PC_WONDERTRADE_H
#define PC_WONDERTRADE_H

struct PcWt {
    // game -> UI (refreshed every overworld frame)
    int canOpen;                 // overworld, player free to act
    int count;
    char name[6][12];
    int level[6], egg[6], usable;
    // UI -> game
    int offerSlot;               // -1 none: start a search with this party slot
    int go;                      // the UI's search is over: start the trade scene
    // game -> UI
    int found;                   // a partner and their Pokémon are ready
    char partner[16], country[24];
    int busy;                    // trade scene running
    int done;                    // trade finished: result below
    char resultLine1[96], resultLine2[96], resultLine3[96];
    int shiny;
};
extern struct PcWt gPcWt;
void PcWonderTradeUpdate(void);  // game side, called every overworld frame

#endif
