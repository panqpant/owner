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

local function lots(d: Config.District, x: number, z: number, y: number, dens: number, centre: number, rng: Hash.Rng, buildings: { Building }, parks: { Park })
	local inset = Config.ROAD_W / 2 + 10
	local size = B - inset * 2
	local suburb = d.style == "house" or d.style == "shack"
	local roll = rng:next()
	if roll < (d.parkChance or 0) then
		local kind = if suburb and roll < (d.parkChance or 0) * 0.35 then "lake" elseif suburb and roll < (d.parkChance or 0) * 0.6 then "golf" else "park"
		table.insert(parks, { x = x, z = z, y = y, w = size, d = size, district = d.id, kind = kind })
		return
	end
	local cols = if suburb then 4 elseif d.style == "warehouse" then 1 else rng:int(1, 2)
	local rows = if suburb then 2 else cols
	local lw, ld = size / cols, size / rows
	for a = 0, cols - 1 do
		for b = 0, rows - 1 do
			if rng:next() < dens * 1.6 then -- edges of the sprawl thin out
				local setback = if suburb then 10 else 5
				local t = rng:next() ^ 1.6
				if d.style == "tower" or d.style == "midrise" then
					t *= 0.25 + 0.75 * centre ^ 1.5
				end
				local minH, maxH = d.minH :: number, d.maxH :: number
				table.insert(buildings, {
					x = x - size / 2 + (a + 0.5) * lw,
					z = z - size / 2 + (b + 0.5) * ld,
					y = y,
					w = lw - setback * 2,
					d = ld - setback * 2,
					h = math.floor(minH + (maxH - minH) * t),
					rot = if suburb and b == 0 then 180 else 0,
					style = d.style :: string,
					district = d.id,
					variant = rng:int(1, 8),
				})
			end
		end
	end
end

local function grid(roads: { Road }, buildings: { Building }, parks: { Park })
	local n = math.floor(W / B)
	local inBlock: { [number]: boolean } = {}
	local rng = Hash.rng(Config.SEED + 1)
	for i = 0, n - 1 do
		for j = 0, n - 1 do
			local x, z = (i + 0.5) * B, (j + 0.5) * B
			local s = Terrain.sample(x, z)
			if s.land > 40 and s.h > 0 then
				local dens = if s.shape == "barrier" then 1 else Districts.urban(x, z)
				if dens > 0 then
					local id = Districts.at(x, z, s)
					local d = Districts.byId[id]
					if d and d.urban then
						inBlock[i * 4096 + j] = true
						local centre = 1 - math.min(1, math.sqrt((x / W - d.u) ^ 2 + (z / W - d.v) ^ 2) / d.radius)
						lots(d, x, z, s.h, dens, centre, rng, buildings, parks)
					end
				end
			end
		end
	end
	-- Roads along every grid edge that touches a block, merged into straight runs.
	local function run(horizontal: boolean)
		for line = 0, n do
			local start: number? = nil
			for step = 0, n do
				local touches
				if horizontal then
					touches = inBlock[step * 4096 + line - 1] or inBlock[step * 4096 + line]
				else
					touches = inBlock[(line - 1) * 4096 + step] or inBlock[line * 4096 + step]
				end
				if touches and not start then
					start = step
				elseif not touches and start then
					local art = line % Config.ARTERIAL_EVERY == 0
					local s0, s1 = (start :: number) * B, step * B
					local p = line * B
					table.insert(roads, {
						ax = if horizontal then s0 else p,
						az = if horizontal then p else s0,
						bx = if horizontal then s1 else p,
						bz = if horizontal then p else s1,
						width = if art then Config.ARTERIAL_W else Config.ROAD_W,
						kind = if art then "arterial" else "street",
						bridge = false,
					})
					start = nil
				end
			end
		end
	end
	run(true)
	run(false)
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
		local runStart, runBridge = 0, Terrain.sample(ax, az).h <= 0
		for k = 1, n do
			local wet = Terrain.sample(ax + (bx - ax) * k / n, az + (bz - az) * k / n).h <= 0
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

function City.generate(): { roads: { Road }, buildings: { Building }, parks: { Park } }
	local roads, buildings, parks = {}, {}, {}
	grid(roads, buildings, parks)
	for _, h in Config.HIGHWAYS do
		highway(h, roads)
	end
	-- Airport runways (landmark, hand-placed)
	local a = Districts.byId.airport
	for _, off in { -200, 200 } do
		local x, z = a.u * W, a.v * W + off
		table.insert(roads, { ax = x - 1100, az = z, bx = x + 1100, bz = z, width = 110, kind = "runway", bridge = false })
	end
	return { roads = roads, buildings = buildings, parks = parks }
end

return City
