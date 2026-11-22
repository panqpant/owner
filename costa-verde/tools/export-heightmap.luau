-- Heightmap only (fast path for tools/train_terrain.py). Usage: lune run tools/export-heightmap.luau
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local Gen = require("../src/shared/Gen")
if not fs.isDir("build") then
	fs.writeDir("build")
end
fs.writeFile("build/heightmap.json", serde.encode("json", Gen.heightmap(Gen.Config.CELL)))
