-- Grow a street network in an open square from a params file and write it in the training-data format.
-- Usage: lune run tools/gen-streets.luau <params.json> <out.json>
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local process = require("@lune/process")
local Streets = require("../src/shared/Gen/Streets")

local args = process.args
local cfg = serde.decode("json", fs.readFile(args[1]))
local half = cfg.half or 4000
local roads = Streets.grow(cfg.params, function()
	return true
end, 0, 0, half, cfg.angle or 0.3, cfg.seed or 7)
local out = {}
for _, r in roads do
	local pts = {}
	for i = 1, #r.pts, 2 do
		table.insert(pts, { r.pts[i], r.pts[i + 1] })
	end
	table.insert(out, { kind = r.kind, pts = pts })
end
fs.writeFile(args[2], serde.encode("json", { half = half, roads = out }))
