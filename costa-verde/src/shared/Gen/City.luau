--!strict
-- One continuous street grid over all built-up land (like real sprawl), arterials every N blocks,
-- lots that thin out at the edges, dug lakes / golf in suburbs, plus highways and bridges.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Hash = require("./Hash")

local City = {}

export type Road = { ax: number, az: number, bx: number, bz: number, width: number, kind: string, bridge: boolean }
export type Building = { x: number, z: number, y: number, w: number, d: number, h: number, rot: number, style: string, district: string, variant: number }
export type Park = { x: number, z: number, y: number, w: number, d: number, district: string, kind: string }

local W = Config.SIZE
local B = Config.BLOCK

local Streets = require("./Streets")
local StreetStyles = require("./StreetStyles")

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

-- Districts grow their own street networks (tuned on real data), sharing one index so they join at
-- borders. Buildings then line the street frontage.
local function grid(roads: { Road }, buildings: { Building }, parks: { Park }, shared: Streets.Shared)
	local segs = segIndex()
	local placed: { [number]: { { number } } } = {}
	local function free(x: number, z: number, r: number): boolean
		local gx, gz = math.floor(x / 128), math.floor(z / 128)
		for i = -1, 1 do
			for j = -1, 1 do
				for _, b in placed[(gx + i + 4096) * 8192 + gz + j + 4096] or {} do
					if (b[1] - x) ^ 2 + (b[2] - z) ^ 2 < (b[3] + r) ^ 2 then
						return false
					end
				end
			end
		end
		return true
	end
	local function occupy(x: number, z: number, r: number)
		local k = (math.floor(x / 128) + 4096) * 8192 + math.floor(z / 128) + 4096
		placed[k] = placed[k] or {}
		table.insert(placed[k], { x, z, r })
	end

	-- Big districts first, so small ones join onto them.
	local order = {}
	for _, d in Config.DISTRICTS do
		if d.urban then
			table.insert(order, d)
		end
	end
	table.sort(order, function(a, b)
		return a.radius > b.radius
	end)
	local rng = Hash.rng(Config.SEED + 1)
	for di, d in order do
		local function inside(x: number, z: number): boolean
			local s = Terrain.sample(x, z)
			if s.water or s.land < 30 then
				return false
			end
			if d.id == "beach" then
				return s.shape == "barrier"
			end
			return s.shape == "main" and Districts.urban(x, z) > 0 and Districts.at(x, z, s) == d.id
		end
		local style = d.style :: string
		local params = StreetStyles[style] or StreetStyles.house
		local cx, cz = d.u * W, d.v * W
		local half = d.radius * W * 1.4
		local angle = Hash.float(di, 3, Config.SEED) * math.pi / 2
		if d.id == "beach" then -- the island runs north-south; follow it
			cx, cz, half, angle = 0.79 * W, 0.5 * W, 0.22 * W, math.pi / 2
		end
		local net = Streets.grow(params, inside, cx, cz, half, angle, Config.SEED + di * 101, 3000, shared)
		local lot = LOT[style] or LOT.house
		for _, r in net do
			local art = r.kind == "arterial"
			local width = if art then Config.ARTERIAL_W else Config.ROAD_W
			local pts = r.pts
			for i = 1, #pts - 3, 2 do
				table.insert(roads, { ax = pts[i], az = pts[i + 1], bx = pts[i + 2], bz = pts[i + 3], width = width, kind = r.kind, bridge = false })
				segs.add(pts[i], pts[i + 1], pts[i + 2], pts[i + 3], width / 2)
			end
		end
		-- Frontage lots: walk each street, both sides, face the road.
		for _, r in net do
			local width = if r.kind == "arterial" then Config.ARTERIAL_W else Config.ROAD_W
			local pts = r.pts
			local carry = 0
			for i = 1, #pts - 3, 2 do
				local ax, az, bx, bz = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
				local len = math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2)
				local dx, dz = (bx - ax) / len, (bz - az) / len
				local t = carry
				while t < len do
					local px, pz = ax + dx * t, az + dz * t
					for _, side in { 1, -1 } do
						local w = lot[1] * rng:range(0.8, 1.25)
						local dep = lot[2] * rng:range(0.8, 1.3)
						local off = width / 2 + lot[3] + dep / 2
						local x, z = px - dz * off * side, pz + dx * off * side
						local rad = math.max(w, dep) * 0.5
						if inside(x, z) and segs.clear(x, z, rad * 0.85) and free(x, z, rad * 0.9) then
							local s = Terrain.sample(x, z)
							local dens = if s.shape == "barrier" then 1 else Districts.urban(x, z)
							occupy(x, z, rad)
							if rng:next() < (d.parkChance or 0) * 0.5 then
								local suburb = style == "house" or style == "shack"
								local roll = rng:next()
								table.insert(parks, { x = x, z = z, y = s.h, w = w * 1.6, d = dep * 1.6, district = d.id,
									kind = if suburb and roll < 0.3 then "lake" elseif suburb and roll < 0.55 then "golf" else "park" })
							elseif rng:next() < dens * 1.6 then
								local centre = 1 - math.min(1, math.sqrt((x / W - d.u) ^ 2 + (z / W - d.v) ^ 2) / d.radius)
								local tt = rng:next() ^ 1.6
								if style == "tower" or style == "midrise" then
									tt *= 0.25 + 0.75 * centre ^ 1.5
								end
								local minH, maxH = d.minH :: number, d.maxH :: number
								table.insert(buildings, {
									x = x, z = z, y = s.h, w = w, d = dep,
									h = math.floor(minH + (maxH - minH) * tt),
									rot = math.deg(math.atan2(dz, dx)) + (if side == 1 then 0 else 180),
									style = style, district = d.id, variant = rng:int(1, 8),
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
end

-- Catmull-Rom smoothing so highways curve like real ones.
local function smooth(points: { { number } }): { { number } }
	if #points < 3 then
		return points
	end
	local out = {}
	for i = 1, #points - 1 do
		local p0, p1, p2, p3 = points[math.max(1, i - 1)], points[i], points[i + 1], points[math.min(#points, i + 2)]
		for k = 0, 7 do
			local t = k / 8
			local t2, t3 = t * t, t * t * t
			local function c(a: number, b: number, cc: number, d: number)
				return 0.5 * (2 * b + (-a + cc) * t + (2 * a - 5 * b + 4 * cc - d) * t2 + (-a + 3 * b - 3 * cc + d) * t3)
			end
			table.insert(out, { c(p0[1], p1[1], p2[1], p3[1]), c(p0[2], p1[2], p2[2], p3[2]) })
		end
	end
	table.insert(out, points[#points])
	return out
end

-- Highway polyline -> segments, split where it crosses water (bridges).
local function highway(points: { { number } }, roads: { Road })
	local STEP = 64
	points = smooth(points)
	for p = 1, #points - 1 do
		local ax, az = points[p][1] * W, points[p][2] * W
		local bx, bz = points[p + 1][1] * W, points[p + 1][2] * W
		local len = math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2)
		local n = math.max(1, math.floor(len / STEP))
		local function emit(k0: number, k1: number, bridge: boolean)
			local t0, t1 = k0 / n, k1 / n
			table.insert(roads, {
				ax = ax + (bx - ax) * t0,
				az = az + (bz - az) * t0,
				bx = ax + (bx - ax) * t1,
				bz = az + (bz - az) * t1,
				width = Config.HIGHWAY_W,
				kind = "highway",
				bridge = bridge,
			})
		end
		local runStart, runBridge = 0, Terrain.sample(ax, az).water ~= nil
		for k = 1, n do
			local wet = Terrain.sample(ax + (bx - ax) * k / n, az + (bz - az) * k / n).water ~= nil
			if wet ~= runBridge then
				emit(runStart, k, runBridge or wet) -- the step that crosses the shore is bridged
				runStart, runBridge = k, wet
			end
		end
		if runStart < n then
			emit(runStart, n, runBridge)
		end
	end
end

function City.generate(): { roads: { Road }, buildings: { Building }, parks: { Park }, shared: Streets.Shared }
	local roads, buildings, parks = {}, {}, {}
	local shared = Streets.newShared()
	grid(roads, buildings, parks, shared)
	for _, h in Config.HIGHWAYS do
		highway(h, roads)
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
