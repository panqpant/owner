-- Grow a street network from a params file, in the same setting the game uses, and write it in the
-- training-data format. mode "blocks" (city): an arterial grid every ROADS.ARTERIAL_SPACING, each block
-- filled from seeds on its arterials, then stitched, exactly like City.luau. mode "open" (rural):
-- free growth over an open square, like Rural.luau.
-- Usage: lune run tools/gen-streets.luau <params.json> <out.json>
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local process = require("@lune/process")
local Config = require("../src/shared/Gen/Config")
local Streets = require("../src/shared/Gen/Streets")

local cfg = serde.decode("json", fs.readFile(process.args[1]))
local half = cfg.half or 4000
local p = cfg.params
local out = {}
local function emit(kind, pts)
	local list = {}
	for i = 1, #pts, 2 do
		table.insert(list, { pts[i], pts[i + 1] })
	end
	table.insert(out, { kind = kind, pts = list })
end

if cfg.mode == "open" then
	for _, r in Streets.grow(p, function()
		return true
	end, 0, 0, half, cfg.angle or 0, cfg.seed or 7) do
		emit(r.kind, r.pts)
	end
else
	local SP = Config.ROADS.ARTERIAL_SPACING
	local STEP = Config.ROADS.SEED_STEP
	local shared = Streets.newShared()
	local bucket = {}
	local k0, k1 = math.floor(-half / SP), math.ceil(half / SP)
	for k = k0, k1 do
		for _, vertical in { true, false } do
			local pts = {}
			for t = -half, half, 40 do
				table.insert(pts, if vertical then k * SP else t)
				table.insert(pts, if vertical then t else k * SP)
			end
			local id = Streets.addExternal(shared, pts)
			emit("arterial", pts)
			for _, c in Streets.frontSeeds(pts, id, STEP) do
				local done = {}
				for _, o in { { 1, 1 }, { -1, -1 }, { 1, -1 }, { -1, 1 } } do
					local key = math.floor((c[1] + o[1]) / SP) * 4096 + math.floor((c[2] + o[2]) / SP)
					if not done[key] then
						done[key] = true
						bucket[key] = bucket[key] or {}
						table.insert(bucket[key], c)
					end
				end
			end
		end
	end
	local all = {}
	for i = k0, k1 - 1 do
		for j = k0, k1 - 1 do
			local x0, z0 = i * SP, j * SP
			local function inside(x, z)
				return x > x0 + 20 and x < x0 + SP - 20 and z > z0 + 20 and z < z0 + SP - 20
			end
			local every = math.max(1, math.round((p.seedEvery or 240) / STEP))
			local seeds = Streets.blockSeeds(bucket[(i - 0) * 4096 + j] or {}, every, inside)
			for _, r in Streets.grow(p, inside, x0 + SP / 2, z0 + SP / 2, SP / 2, 0, (cfg.seed or 7) + i * 977 + j, 400, shared, seeds) do
				table.insert(all, r)
				emit(r.kind, r.pts)
			end
		end
	end
	for _, link in Streets.stitch(shared, all, 300, function()
		return true
	end) do
		Streets.addExternal(shared, link.pts)
		emit("street", link.pts)
	end
end
fs.writeFile(process.args[2], serde.encode("json", { half = half, roads = out }))
