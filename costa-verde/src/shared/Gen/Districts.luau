--!strict
local Config = require("./Config")
local Terrain = require("./Terrain")
local Noise = require("./Noise")

local Districts = {}

local byId: { [string]: Config.District } = {}
for _, d in Config.DISTRICTS do
	byId[d.id] = d
end
Districts.byId = byId

-- Built-up density 0..1: union of sprawl cores with ragged edges, cut by the levee line.
function Districts.urban(x: number, z: number): number
	local u, v = x / Config.SIZE, z / Config.SIZE
	local U = Config.URBAN
	local best = 0
	for _, c in U.cores do
		if not (c[1] > U.levee and u < U.levee and v > 0.3) then
			local d = math.sqrt((u - c[1]) ^ 2 + (v - c[2]) ^ 2) / c[3]
			best = math.max(best, 1 - d * (1 + 0.35 * Noise.fbm(u * 20, v * 20, Config.SEED + 70)))
		end
	end
	return math.clamp(best * 2.5, 0, 1)
end

-- District id for a point (Voronoi of district seeds, noisy edges), given its terrain sample.
function Districts.at(x: number, z: number, s: Terrain.Sample?): string
	local sample = s or Terrain.sample(x, z)
	if sample.shape == "barrier" then
		return "beach"
	elseif sample.shape == "key" then
		return if Districts.urban(x, z) > 0 then "keytown" else "keys"
	elseif sample.shape == "islet" then
		return "islets"
	elseif sample.land <= 0 then
		return "water"
	end
	local u, v = x / Config.SIZE, z / Config.SIZE
	local bestId, bestScore = "rural", math.huge
	local town = Districts.urban(x, z) > 0
	for i, d in Config.DISTRICTS do
		if not d.special and not (town and d.landscape) then
			local score = math.sqrt((u - d.u) ^ 2 + (v - d.v) ^ 2) / d.radius * (1 + 0.3 * Noise.fbm(u * 30, v * 30, Config.SEED + i * 7))
			if score < bestScore then
				bestId, bestScore = d.id, score
			end
		end
	end
	return bestId
end

return Districts
