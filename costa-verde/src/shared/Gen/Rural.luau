--!strict
-- Countryside: section-line county roads (US-style ~1 mile grid), farmsteads with driveways onto
-- those roads, crossroads hamlets, and Easter egg points of interest placed by biome rules.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Hash = require("./Hash")
local Streets = require("./Streets")
local StreetStyles = require("./StreetStyles")

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

-- Rural roads grow with the style trained on real county road networks, joining the city network.
function Rural.generate(roads: { any }, buildings: { any }, shared: Streets.Shared?)
	local rng = Hash.rng(Config.SEED + 500)
	local net = Streets.grow(StreetStyles.rural, ruralOk, W / 2, W / 2, W / 2, 0, Config.SEED + 503, 2500, shared)
	local segs = {}
	local uses: { [number]: number } = {}
	local function vkey(x: number, z: number): number
		return math.round(x) * 100000 + math.round(z)
	end
	for _, r in net do
		local pts = r.pts
		for i = 1, #pts - 3, 2 do
			local sg = { ax = pts[i], az = pts[i + 1], bx = pts[i + 2], bz = pts[i + 3] }
			table.insert(segs, sg)
			table.insert(roads, { ax = sg.ax, az = sg.az, bx = sg.bx, bz = sg.bz, width = if r.kind == "arterial" then Config.ROAD_W else Config.COUNTY_W, kind = "county", bridge = false })
		end
		-- junction degree: endpoints count once, interior vertices twice
		for i = 1, #pts - 1, 2 do
			local k = vkey(pts[i], pts[i + 1])
			uses[k] = (uses[k] or 0) + (if i == 1 or i == #pts - 1 then 1 else 2)
		end
	end

	-- Farmsteads: house + barn + silo set back from a road, joined by a driveway.
	local spacing = 0
	for _, sg in segs do
		local len = math.sqrt((sg.bx - sg.ax) ^ 2 + (sg.bz - sg.az) ^ 2)
		spacing += len
		if spacing > 500 and rng:next() < 0.5 then
			spacing = 0
			local dx, dz = (sg.bx - sg.ax) / len, (sg.bz - sg.az) / len
			local side = if rng:next() < 0.5 then -1 else 1
			local ox, oz = -dz * side, dx * side -- perpendicular, away from the road
			local t = rng:range(0.2, 0.8) * len
			local rx, rz = sg.ax + dx * t, sg.az + dz * t
			local hx, hz = rx + ox * 90, rz + oz * 90
			if ruralOk(hx, hz) then
				local y = Terrain.sample(hx, hz).h
				local rot = math.deg(math.atan2(dz, dx))
				table.insert(roads, { ax = rx + ox * Config.COUNTY_W / 2, az = rz + oz * Config.COUNTY_W / 2, bx = hx, bz = hz, width = 10, kind = "drive", bridge = false })
				table.insert(buildings, { x = hx + ox * 18, z = hz + oz * 18, y = y, w = 34, d = 26, h = 16, rot = rot, style = "farmhouse", district = "rural", variant = rng:int(1, 8) })
				table.insert(buildings, { x = hx + dx * 60 + ox * 30, z = hz + dz * 60 + oz * 30, y = y, w = 40, d = 56, h = 26, rot = rot, style = "barn", district = "rural", variant = rng:int(1, 8) })
				if rng:next() < 0.6 then
					table.insert(buildings, { x = hx - dx * 45 + ox * 40, z = hz - dz * 45 + oz * 40, y = y, w = 14, d = 14, h = 44, rot = 0, style = "silo", district = "rural", variant = 1 })
				end
			end
		end
	end

	-- Hamlets at real junctions (3+ roads), spaced apart.
	local settlements: { Settlement } = {}
	local names = table.clone(Config.HAMLET_NAMES)
	for k, n in uses do
		if n >= 3 and #names > 0 and Hash.float(k % 99991, math.floor(k / 99991), Config.SEED + 502) < 0.12 then
			local x, z = math.floor(k / 100000 + 0.5), k - math.floor(k / 100000 + 0.5) * 100000
			local far = true
			for _, st in settlements do
				if (st.x - x) ^ 2 + (st.z - z) ^ 2 < 2500 ^ 2 then
					far = false
					break
				end
			end
			if far and ruralOk(x, z) then
				local y = Terrain.sample(x, z).h
				local name = table.remove(names, rng:int(1, #names)) :: string
				local size = rng:int(5, 12)
				table.insert(settlements, { x = x, z = z, name = name, size = size })
				local anchor = rng:pick({ "store", "gas", "church", "diner" })
				table.insert(buildings, { x = x + 45, z = z + 45, y = y, w = 40, d = 30, h = 14, rot = 0, style = anchor, district = "hamlet", variant = 1 })
				for _ = 1, size do
					local a = rng:range(0, math.pi * 2)
					local dist = rng:range(70, 380)
					local hx, hz = x + math.cos(a) * dist, z + math.sin(a) * dist
					if ruralOk(hx, hz) then
						table.insert(buildings, { x = hx, z = hz, y = Terrain.sample(hx, hz).h, w = 22, d = 18, h = 12, rot = math.deg(a), style = if rng:next() < 0.3 then "trailer" else "house", district = "hamlet", variant = rng:int(1, 8) })
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
