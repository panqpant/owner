// melonDS links "onecore" on Windows but looks up the functions it needs (VirtualAlloc2,
// MapViewOfFile3) at runtime, so an empty library is enough where the toolchain has none.
int b2o_onecore_stub;
