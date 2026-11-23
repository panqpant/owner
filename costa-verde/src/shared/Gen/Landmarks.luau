--!strict
-- Places the 200 unique landmarks (LandmarkData.luau) after the major roads exist and before local
-- streets, so streets, lots and farmsteads grow around them. Each landmark samples spots in its district
-- and takes the first that fits its siting rule, misses other landmarks and major roads, then gets an
-- access road to the nearest road over land (built by City.luau).
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Hash = require("./Hash")
local Data = require("./LandmarkData")

local Landmarks = {}

export type Landmark = { name: string, district: string, site: string, x: number, z: number, y: number, w: number, d: number, h: number }

local W = Config.SIZE
local placed: { Landmark } = {}
local CELL = 512
local buckets: { [number]: { Landmark } } = {} -- landmarks by 512-stud cell (each footprint in every cell it touches)
local MAXHALF = 800 -- largest landmark half-size + default margin; bounds the cells to search

-- Is (x, z) inside a placed landmark's footprint (plus margin)? Streets, lots and farms stay out.
function Landmarks.blocked(x: number, z: number, margin: number?): boolean
	local m = margin or 15
	local r = (MAXHALF + m) // CELL + 1
	local gx, gz = x // CELL, z // CELL
	for i = -r, r do
		for j = -r, r do
			for _, l in buckets[(gx + i) * 4096 + gz + j] or {} do
				if math.abs(x - l.x) < l.w / 2 + m and math.abs(z - l.z) < l.d / 2 + m then
					return true
				end
			end
		end
	end
	return false
end

-- Would a straight link from a to b cross a landmark's footprint? (joining links must go around)
function Landmarks.crosses(ax: number, az: number, bx: number, bz: number): boolean
	local n = math.max(1, math.ceil(math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2) / 20))
	for k = 1, n - 1 do
		if Landmarks.blocked(ax + (bx - ax) * k / n, az + (bz - az) * k / n, 0) then
			return true
		end
	end
	return false
end

-- A link may be built if it stays on land and goes around landmarks.
function Landmarks.okLink(ax: number, az: number, bx: number, bz: number): boolean
	return Terrain.dryLink(ax, az, bx, bz) and not Landmarks.crosses(ax, az, bx, bz)
end

local function districtOk(want: string, got: string): boolean
	return got == want or (want == "keys" and got == "keytown")
end

-- Candidate centre near the district (special shapes: barrier island, keys arc, the open sea).
local function candidate(district: string, site: string, rng: Hash.Rng): (number, number)
	if site == "islet" or site == "offshore" then
		return rng:range(0.05, 0.95) * W, rng:range(0.05, 0.97) * W
	elseif district == "beach" then
		local v = rng:range(Config.BARRIER.v0, Config.BARRIER.v1)
		return Terrain.barrierX(v) * W + rng:range(-400, 400), v * W
	elseif district == "keys" and rng:next() < 0.5 then -- half the tries on Key Marisol's island
		local T = Config.TOWN_KEY
		return (T[1] + rng:range(-1, 1) * T[3]) * W, (T[2] + rng:range(-1, 1) * T[4]) * W
	elseif district == "keys" then
		local K = Config.KEYS_ARC
		local t = rng:next()
		local mt = 1 - t
		return (mt * mt * K.a[1] + 2 * mt * t * K.c[1] + t * t * K.b[1]) * W + rng:range(-400, 400),
			(mt * mt * K.a[2] + 2 * mt * t * K.c[2] + t * t * K.b[2]) * W + rng:range(-400, 400)
	end
	local d = Districts.byId[district]
	local a, r = rng:range(0, 2 * math.pi), math.sqrt(rng:next()) * d.radius * W
	return d.u * W + math.cos(a) * r, d.v * W + math.sin(a) * r
end

local function fits(l: { [string]: any }, x: number, z: number): boolean
	local s = Terrain.sample(x, z)
	local site = l.site
	if site == "offshore" then
		if l.name == "Stilt Shacks" then -- stilt houses stand in the shallow bay
			return s.water ~= nil and s.biome == "bay" and s.h < -3
		end
		-- diveable shelf: deep enough to float a ship, shallow enough to dive a wreck (real reefs 3-40 m)
		return s.water ~= nil and s.biome == "sea" and s.h < -8 and s.h > -140
	elseif site == "islet" then
		return s.shape == "islet" and not s.water
	end
	if s.water or not districtOk(l.district, Districts.at(x, z, s)) then
		return false
	end
	if site == "open" and Districts.urban(x, z) > 0 then
		return false
	end
	-- footprint corners on land (shore sites may reach over the water: piers, marinas, terminals)
	local wetCorners = 0
	for _, c in { { -1, -1 }, { 1, -1 }, { 1, 1 }, { -1, 1 } } do
		if Terrain.sample(x + c[1] * l.w / 2, z + c[2] * l.d / 2).water then
			wetCorners += 1
		end
	end
	if site == "shore" then
		if wetCorners > 2 then
			return false
		end
		local reach = math.max(l.w, l.d) / 2 + 150
		for k = 0, 7 do
			local a = k * math.pi / 4
			if Terrain.sample(x + math.cos(a) * reach, z + math.sin(a) * reach).water then
				return true
			end
		end
		return false
	end
	return wetCorners == 0
end

-- `clear(x, z, r)`: no major road within r. `bridges`: bridge runs on the road network {x, z, len}, for
-- landmarks that are a bridge (the longest in their district, else the nearest). Access roads are built
-- by the caller afterwards.
function Landmarks.place(clear: (number, number, number) -> boolean, bridges: { { number } }): { Landmark }
	table.clear(placed)
	table.clear(buckets)
	local missing = {}
	local usedBridge: { [number]: boolean } = {}
	for _, l in Data do
		if l.site == "bridge" then
			local d = Districts.byId[l.district]
			local best, bi = -math.huge, nil
			for i, b in bridges do
				if not usedBridge[i] then
					local inDistrict = districtOk(l.district, Districts.at(b[1], b[2]))
					local score = if inDistrict then b[3] else -math.sqrt((b[1] - d.u * W) ^ 2 + (b[2] - d.v * W) ^ 2)
					if (inDistrict and score > best) or (best < 0 and not inDistrict and score > best) then
						best, bi = score, i
					end
				end
			end
			if bi then
				usedBridge[bi] = true
				local b = bridges[bi]
				table.insert(placed, { name = l.name, district = l.district, site = l.site, x = b[1], z = b[2], y = 0, w = l.w, d = l.d, h = l.h })
			else
				table.insert(missing, `{l.name} (no bridge on the map)`)
			end
		end
	end
	for i, l in Data do
		if l.site == "bridge" then
			continue
		end
		local rng = Hash.rng(Config.SEED + 900 + i)
		local ok = false
		local why = { edge = 0, landmark = 0, road = 0, terrain = 0 }
		for _ = 1, 3000 do
			local x, z = candidate(l.district, l.site, rng)
			local half = math.sqrt(l.w ^ 2 + l.d ^ 2) / 2
			local good = false
			if not (x > half and z > half and x < W - half and z < W - half) then
				why.edge += 1
			elseif Landmarks.blocked(x, z, half) then
				why.landmark += 1
			elseif not (l.site == "offshore" or clear(x, z, half + 10)) then
				why.road += 1
			elseif not fits(l, x, z) then
				why.terrain += 1
			else
				good = true
			end
			if good then
				local lm = { name = l.name, district = l.district, site = l.site, x = x, z = z, y = Terrain.sample(x, z).h, w = l.w, d = l.d, h = l.h }
				table.insert(placed, lm)
				for gx = (x - l.w / 2) // CELL, (x + l.w / 2) // CELL do
					for gz = (z - l.d / 2) // CELL, (z + l.d / 2) // CELL do
						local k = gx * 4096 + gz
						buckets[k] = buckets[k] or {}
						table.insert(buckets[k], lm)
					end
				end
				ok = true
				break
			end
		end
		if not ok then
			table.insert(missing, `{l.name} (rejected: {why.landmark} by landmarks, {why.road} by roads, {why.terrain} by terrain)`)
		end
	end
	if #missing > 0 then
		warn(`Landmarks not placed ({#missing}): {table.concat(missing, "; ")}`)
	end
	return table.clone(placed)
end

return Landmarks
