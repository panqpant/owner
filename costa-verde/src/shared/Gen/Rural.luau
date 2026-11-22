--!strict
-- Countryside: section-line county roads (US-style ~1 mile grid), farmsteads with driveways onto
-- those roads, crossroads hamlets, and Easter egg points of interest placed by biome rules.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Hash = require("./Hash")

local Rural = {}

export type Poi = { x: number, z: number, y: number, kind: string, name: string }
export type Settlement = { x: number, z: number, name: string, size: number }

local W = Config.SIZE
local SEC = Config.SECTION

local function ruralOk(x: number, z: number): boolean
	local s = Terrain.sample(x, z)
	if s.water or s.land < 80 or s.wet > 0.3 then
		return false
	end
	if s.biome ~= "farm" and s.biome ~= "scrub" then
		return false
	end
	return Districts.urban(x, z) <= 0
end

-- A road segment is usable if every 200 studs along it is dry rural land.
local function segmentOk(ax: number, az: number, bx: number, bz: number): boolean
	local n = math.ceil(math.max(math.abs(bx - ax), math.abs(bz - az)) / 200)
	for k = 0, n do
		if not ruralOk(ax + (bx - ax) * k / n, az + (bz - az) * k / n) then
			return false
		end
	end
	return true
end

function Rural.generate(roads: { any }, buildings: { any })
	local rng = Hash.rng(Config.SEED + 500)
	local n = math.floor(W / SEC)
	local kept: { [string]: boolean } = {}
	local segs = {}
	-- Section-line roads: each section edge exists if dry, with a few randomly missing (real grids have gaps).
	for i = 0, n do
		for j = 0, n do
			for _, dir in { { 1, 0 }, { 0, 1 } } do
				local ax, az = i * SEC, j * SEC
				local bx, bz = ax + dir[1] * SEC, az + dir[2] * SEC
				if bx <= W and bz <= W and Hash.float(i, j * 2 + dir[1], Config.SEED + 501) < 0.8 and segmentOk(ax, az, bx, bz) then
					kept[`{i},{j},{dir[1]}`] = true
					table.insert(segs, { ax = ax, az = az, bx = bx, bz = bz, i = i, j = j, horiz = dir[1] == 1 })
					table.insert(roads, { ax = ax, az = az, bx = bx, bz = bz, width = Config.COUNTY_W, kind = "county", bridge = false })
				end
			end
		end
	end

	-- Farmsteads: house + barn + silo set back from a county road, joined by a driveway.
	for _, sgm in segs do
		if rng:next() < 0.55 then
			local t = rng:range(0.2, 0.8)
			local side = if rng:next() < 0.5 then -1 else 1
			local rx, rz = sgm.ax + (sgm.bx - sgm.ax) * t, sgm.az + (sgm.bz - sgm.az) * t
			local ox, oz = if sgm.horiz then 0 else side, if sgm.horiz then side else 0
			local hx, hz = rx + ox * 90, rz + oz * 90
			if ruralOk(hx, hz) then
				local y = Terrain.sample(hx, hz).h
				table.insert(roads, { ax = rx + ox * Config.COUNTY_W / 2, az = rz + oz * Config.COUNTY_W / 2, bx = hx, bz = hz, width = 10, kind = "drive", bridge = false })
				local px, pz = if sgm.horiz then 1 else 0, if sgm.horiz then 0 else 1
				table.insert(buildings, { x = hx, z = hz + oz * 18, y = y, w = 34, d = 26, h = 16, rot = 0, style = "farmhouse", district = "rural", variant = rng:int(1, 8) })
				table.insert(buildings, { x = hx + px * 60, z = hz + pz * 60 + oz * 30, y = y, w = 40, d = 56, h = 26, rot = 0, style = "barn", district = "rural", variant = rng:int(1, 8) })
				if rng:next() < 0.6 then
					table.insert(buildings, { x = hx - px * 45, z = hz - pz * 45 + oz * 40, y = y, w = 14, d = 14, h = 44, rot = 0, style = "silo", district = "rural", variant = 1 })
				end
			end
		end
	end

	-- Hamlets at crossroads with 3+ roads.
	local settlements: { Settlement } = {}
	local names = table.clone(Config.HAMLET_NAMES)
	for i = 1, n - 1 do
		for j = 1, n - 1 do
			local deg = (if kept[`{i},{j},1`] then 1 else 0) + (if kept[`{i - 1},{j},1`] then 1 else 0)
				+ (if kept[`{i},{j},0`] then 1 else 0) + (if kept[`{i},{j - 1},0`] then 1 else 0)
			if deg >= 3 and #names > 0 and Hash.float(i, j, Config.SEED + 502) < 0.16 then
				local x, z = i * SEC, j * SEC
				local y = Terrain.sample(x, z).h
				local name = table.remove(names, rng:int(1, #names)) :: string
				local size = rng:int(5, 12)
				table.insert(settlements, { x = x, z = z, name = name, size = size })
				local anchor = rng:pick({ "store", "gas", "church", "diner" })
				table.insert(buildings, { x = x + 45, z = z + 45, y = y, w = 40, d = 30, h = 14, rot = 0, style = anchor, district = "hamlet", variant = 1 })
				for k = 1, size do
					local along = rng:range(70, 380) * (if rng:next() < 0.5 then -1 else 1)
					local off = 40 * (if rng:next() < 0.5 then -1 else 1)
					local horiz = rng:next() < 0.5
					local hx, hz = x + (if horiz then along else off), z + (if horiz then off else along)
					if ruralOk(hx, hz) then
						table.insert(buildings, { x = hx, z = hz, y = Terrain.sample(hx, hz).h, w = 22, d = 18, h = 12, rot = 0, style = if rng:next() < 0.3 then "trailer" else "house", district = "hamlet", variant = rng:int(1, 8) })
					end
				end
			end
		end
	end
	return settlements
end

-- Easter eggs: each kind has biome rules; placed by rejection sampling.
function Rural.pois(): { Poi }
	local rng = Hash.rng(Config.SEED + 600)
	local out: { Poi } = {}
	for _, egg in Config.EASTER_EGGS do
		local placed, tries = 0, 0
		while placed < egg.count and tries < 4000 do
			tries += 1
			local x, z = rng:range(0, W), rng:range(0, W)
			local s = Terrain.sample(x, z)
			local ok = table.find(egg.biomes, s.biome) ~= nil
			if ok and s.h < -25 then -- underwater secrets stay diveable
				ok = false
			end
			if ok and egg.rural and Districts.urban(x, z) > 0 then
				ok = false
			end
			if ok then
				for _, p in out do
					if (p.x - x) ^ 2 + (p.z - z) ^ 2 < 600 ^ 2 then
						ok = false
						break
					end
				end
			end
			if ok then
				placed += 1
				table.insert(out, { x = x, z = z, y = s.h, kind = egg.kind, name = egg.name })
			end
		end
	end
	return out
end

return Rural
