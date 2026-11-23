--!strict
-- The city, top-down: the whole-map major network (Roads.luau) first, then every superblock between
-- arterials is filled with local streets grown from its surrounding major roads in the district's
-- trained style (Streets.luau), then buildings line the frontage of locals and major roads alike.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Hash = require("./Hash")
local Roads = require("./Roads")
local Streets = require("./Streets")
local StreetStyles = require("./StreetStyles")

local City = {}

export type Road = { ax: number, az: number, bx: number, bz: number, width: number, kind: string, bridge: boolean }
export type Building = { x: number, z: number, y: number, w: number, d: number, h: number, rot: number, style: string, district: string, variant: number }
export type Park = { x: number, z: number, y: number, w: number, d: number, district: string, kind: string }

local W = Config.SIZE
local SP = Config.ROADS.ARTERIAL_SPACING

-- Lot sizes along the frontage per style: width along the street, depth back from it, setback.
local LOT = {
	tower = { 70, 90, 6 }, midrise = { 60, 80, 6 }, deco = { 55, 70, 8 }, stucco = { 40, 50, 8 },
	house = { 42, 55, 16 }, shack = { 34, 40, 14 }, warehouse = { 110, 120, 12 }, campus = { 80, 70, 20 },
}

-- Spatial hash of road segments, to keep buildings off the road.
local function segIndex()
	local cells: { [number]: { { number } } } = {}
	local CELL = 128
	local idx = {}
	function idx.add(ax: number, az: number, bx: number, bz: number, hw: number)
		for gx = math.floor((math.min(ax, bx) - hw) / CELL), math.floor((math.max(ax, bx) + hw) / CELL) do
			for gz = math.floor((math.min(az, bz) - hw) / CELL), math.floor((math.max(az, bz) + hw) / CELL) do
				local k = (gx + 4096) * 8192 + gz + 4096
				cells[k] = cells[k] or {}
				table.insert(cells[k], { ax, az, bx, bz, hw })
			end
		end
	end
	function idx.clear(x: number, z: number, r: number): boolean
		local gx, gz = math.floor(x / CELL), math.floor(z / CELL)
		for i = -1, 1 do
			for j = -1, 1 do
				for _, sg in cells[(gx + i + 4096) * 8192 + gz + j + 4096] or {} do
					local dx, dz = sg[3] - sg[1], sg[4] - sg[2]
					local t = math.clamp(((x - sg[1]) * dx + (z - sg[2]) * dz) / math.max(dx * dx + dz * dz, 1e-6), 0, 1)
					if (x - sg[1] - dx * t) ^ 2 + (z - sg[2] - dz * t) ^ 2 < (r + sg[5]) ^ 2 then
						return false
					end
				end
			end
		end
		return true
	end
	return idx
end

-- Built-up land a local street or lot may use, and the urban district there (nil if none).
local function urbanDistrict(x: number, z: number): Config.District?
	local s = Terrain.sample(x, z)
	if s.water or s.land < 30 then
		return nil
	end
	if s.shape ~= "barrier" and (s.shape ~= "main" or Districts.urban(x, z) <= 0) then
		return nil
	end
	local d = Districts.byId[Districts.at(x, z, s)]
	return if d and d.urban then d else nil
end

function City.generate(): { roads: { Road }, buildings: { Building }, parks: { Park }, shared: Streets.Shared }
	local roads, buildings, parks = {}, {}, {}
	local shared = Streets.newShared()
	local segs = segIndex()
	local rng = Hash.rng(Config.SEED + 1)

	local function addRoad(pts: { number }, width: number, kind: string, bridge: { boolean }?)
		for i = 1, #pts - 3, 2 do
			table.insert(roads, { ax = pts[i], az = pts[i + 1], bx = pts[i + 2], bz = pts[i + 3], width = width, kind = kind, bridge = if bridge then bridge[(i + 1) // 2] else false })
			segs.add(pts[i], pts[i + 1], pts[i + 2], pts[i + 3], width / 2)
		end
	end

	-- 1. Major network; register it so local streets join it.
	local majors = Roads.majors()
	local SEED_STEP = Config.ROADS.SEED_STEP
	local seedBucket: { [number]: { { number } } } = {} -- superblock -> candidate seed points on majors
	for _, m in majors do
		addRoad(m.pts, m.width, m.kind, m.bridge)
		-- freeways and ramps are grade-separated: no street, driveway or lot joins them
		if m.kind ~= "freeway" and m.kind ~= "ramp" then
			local id = Streets.addExternal(shared, m.pts)
			for _, c in Streets.frontSeeds(m.pts, id, SEED_STEP) do
				if not m.bridge[c[7]] then
					-- a point on a superblock edge belongs to the cells on both sides
					local done: { [number]: boolean } = {}
					for _, o in { { 1, 1 }, { -1, -1 }, { 1, -1 }, { -1, 1 } } do
						local k = math.floor((c[1] + o[1]) / SP) * 4096 + math.floor((c[2] + o[2]) / SP)
						if not done[k] then
							done[k] = true
							seedBucket[k] = seedBucket[k] or {}
							table.insert(seedBucket[k], c)
						end
					end
				end
			end
		end
	end

	-- 2. Local streets per superblock, grown from the majors around it.
	local localNets: { { net: { Streets.Road }, d: Config.District } } = {}
	for i = 0, math.floor(W / SP) - 1 do
		for j = 0, math.floor(W / SP) - 1 do
			local x0, z0 = i * SP, j * SP
			local counts: { [string]: number } = {}
			local best: Config.District? = nil
			for a = 1, 5 do -- 5x5 samples: small towns (Gator Hollow, Mile 88) are only a few hundred studs across
				for b = 1, 5 do
					local d = urbanDistrict(x0 + a * SP / 6, z0 + b * SP / 6)
					if d then
						counts[d.id] = (counts[d.id] or 0) + 1
						if not best or counts[d.id] > counts[best.id] then
							best = d
						end
					end
				end
			end
			if best then
				local d = best
				local style = d.style :: string
				local params = StreetStyles[style] or StreetStyles.house
				local function inside(x: number, z: number): boolean
					return x > x0 + 20 and x < x0 + SP - 20 and z > z0 + 20 and z < z0 + SP - 20 and urbanDistrict(x, z) ~= nil
				end
				local every = math.max(1, math.round((params.seedEvery or 240) / SEED_STEP))
				local seeds = Streets.blockSeeds(seedBucket[i * 4096 + j] or {}, every, inside)
				local net = Streets.grow(params, inside, x0 + SP / 2, z0 + SP / 2, SP / 2, 0, Config.SEED + i * 977 + j, 400, shared, seeds, Terrain.dryLink)
				for _, r in net do
					addRoad(r.pts, Config.ROAD_W, if r.kind == "collector" then "collector" else "street")
				end
				table.insert(localNets, { net = net, d = d })
			end
		end
	end

	-- Stitch: loose street ends join the nearest road unless they are deliberate cul-de-sacs.
	local allLocal = {}
	for _, ln in localNets do
		for _, rd in ln.net do
			table.insert(allLocal, rd)
		end
	end
	for _, link in Streets.stitch(shared, allLocal, 300, Terrain.dryLink) do
		Streets.addExternal(shared, link.pts)
		addRoad(link.pts, Config.ROAD_W, "street")
	end

	-- 3. Buildings on the frontage of every street and major road (majors become commercial strips).
	local placed: { [number]: { { number } } } = {}
	local function free(x: number, z: number, r: number): boolean
		local gx, gz = math.floor(x / 128), math.floor(z / 128)
		for a = -1, 1 do
			for b = -1, 1 do
				for _, o in placed[(gx + a + 4096) * 8192 + gz + b + 4096] or {} do
					if (o[1] - x) ^ 2 + (o[2] - z) ^ 2 < (o[3] + r) ^ 2 then
						return false
					end
				end
			end
		end
		return true
	end
	local function frontage(pts: { number }, width: number)
		local carry = 0
		for i = 1, #pts - 3, 2 do
			local ax, az, bx, bz = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
			local len = math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2)
			if len > 1e-3 then
				local dx, dz = (bx - ax) / len, (bz - az) / len
				local t = carry
				local d = urbanDistrict((ax + bx) / 2, (az + bz) / 2)
				local lot = LOT[d and d.style or "house"] or LOT.house
				while t < len do
					local px, pz = ax + dx * t, az + dz * t
					for _, side in { 1, -1 } do
						local w = lot[1] * rng:range(0.8, 1.25)
						local dep = lot[2] * rng:range(0.8, 1.3)
						local off = width / 2 + lot[3] + dep / 2
						local x, z = px - dz * off * side, pz + dx * off * side
						local rad = math.max(w, dep) * 0.5
						local ld = urbanDistrict(x, z)
						if ld and segs.clear(x, z, rad * 0.85) and free(x, z, rad * 0.9) then
							local style = ld.style :: string
							local s = Terrain.sample(x, z)
							local k = (math.floor(x / 128) + 4096) * 8192 + math.floor(z / 128) + 4096
							placed[k] = placed[k] or {}
							table.insert(placed[k], { x, z, rad })
							if rng:next() < (ld.parkChance or 0) * 0.5 then
								local suburb = style == "house" or style == "shack"
								local roll = rng:next()
								table.insert(parks, { x = x, z = z, y = s.h, w = w * 1.6, d = dep * 1.6, district = ld.id,
									kind = if suburb and roll < 0.3 then "lake" elseif suburb and roll < 0.55 then "golf" else "park" })
							else
								local centre = 1 - math.min(1, math.sqrt((x / W - ld.u) ^ 2 + (z / W - ld.v) ^ 2) / ld.radius)
								local tt = rng:next() ^ 1.6
								if style == "tower" or style == "midrise" then
									tt *= 0.25 + 0.75 * centre ^ 1.5
								end
								local minH, maxH = ld.minH :: number, ld.maxH :: number
								table.insert(buildings, {
									x = x, z = z, y = s.h, w = w, d = dep,
									h = math.floor(minH + (maxH - minH) * tt),
									rot = math.deg(math.atan2(dz, dx)) + (if side == 1 then 0 else 180),
									style = style, district = ld.id, variant = rng:int(1, 8),
								})
							end
						end
					end
					t += lot[1] * rng:range(0.9, 1.15)
				end
				carry = t - len
			end
		end
	end
	for _, m in majors do
		if m.kind ~= "freeway" and m.kind ~= "ramp" then
			frontage(m.pts, m.width)
		end
	end
	for _, ln in localNets do
		for _, r in ln.net do
			frontage(r.pts, Config.ROAD_W)
		end
	end

	-- Airport runways (landmark, hand-placed)
	local a = Districts.byId.airport
	for _, off in { -200, 200 } do
		local x, z = a.u * W, a.v * W + off
		table.insert(roads, { ax = x - 1100, az = z, bx = x + 1100, bz = z, width = 110, kind = "runway", bridge = false })
	end
	return { roads = roads, buildings = buildings, parks = parks, shared = shared }
end

return City
