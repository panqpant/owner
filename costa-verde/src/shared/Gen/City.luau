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
local Landmarks = require("./Landmarks")
local SegIndex = require("./SegIndex")
local segIndex = SegIndex.new
local StreetStyles = require("./StreetStyles")
local Footprints = require("./FootprintData")

local City = {}

export type Road = { ax: number, az: number, bx: number, bz: number, width: number, kind: string, bridge: boolean }
export type Building = { x: number, z: number, y: number, w: number, d: number, h: number, rot: number, style: string, district: string, variant: number }
export type Park = { x: number, z: number, y: number, w: number, d: number, district: string, kind: string }

local W = Config.SIZE
local SP = Config.ROADS.ARTERIAL_SPACING

-- Embedded in the whole-map network these styles came out with blocks shorter than real ones (audit:
-- block median, 2.4 km windows), too small for real-size office blocks, campus halls and warehouses.
-- One-step correction = real / generated block median.
local BLOCK_FIX: { [string]: number } = { tower = 1.6, midrise = 1.7, campus = 1.5, warehouse = 2.2 }

-- Value at uniform u from a real 10/25/50/75/90% quantile table (FootprintData); tails extend 1.6x.
local QU = { 0, 0.1, 0.25, 0.5, 0.75, 0.9, 1 }
local function quantile(t: { number }, u: number, logScale: boolean?): number
	local v = { t[1] / 1.6, t[1], t[2], t[3], t[4], t[5], t[5] * 1.6 }
	for i = 2, #QU do
		if u <= QU[i] then
			local f = (u - QU[i - 1]) / (QU[i] - QU[i - 1])
			if logScale then
				return math.exp(math.log(v[i - 1]) + (math.log(v[i]) - math.log(v[i - 1])) * f)
			end
			return v[i - 1] + (v[i] - v[i - 1]) * f
		end
	end
	return v[#v]
end

-- One real-sized building footprint: width along the street, depth back from it, setback, side gap.
local function footprint(style: string, rng: Hash.Rng, shrink: number): (number, number, number, number)
	local f = Footprints[style] or Footprints.house
	local area = quantile(f.area, rng:next(), true) * shrink
	local aspect = math.max(1, quantile(f.aspect, rng:next()))
	local long = math.sqrt(area * aspect)
	local short = area / long
	local w, d = long, short
	if rng:next() < f.endon then
		w, d = short, long
	end
	return w, d, quantile(f.setback, rng:next(), true), quantile(f.gap, rng:next(), true)
end

-- Built-up land a local street or lot may use, and the urban district there (nil if none).
local function urbanDistrict(x: number, z: number): Config.District?
	local s = Terrain.sample(x, z)
	if s.water or s.land < 30 then
		return nil
	end
	if s.shape ~= "barrier" and ((s.shape ~= "main" and s.shape ~= "key") or Districts.urban(x, z) <= 0) then
		return nil
	end
	local d = Districts.byId[Districts.at(x, z, s)]
	return if d and d.urban then d else nil
end

function City.generate(): { roads: { Road }, buildings: { Building }, parks: { Park }, shared: Streets.Shared, landmarks: { Landmarks.Landmark } }
	local roads, buildings, parks = {}, {}, {}
	local shared = Streets.newShared()
	local segs = segIndex()
	local rng = Hash.rng(Config.SEED + 1)

	local function addRoad(pts: { number }, width: number, kind: string, bridge: { boolean }?, rid: number?)
		for i = 1, #pts - 3, 2 do
			table.insert(roads, { ax = pts[i], az = pts[i + 1], bx = pts[i + 2], bz = pts[i + 3], width = width, kind = kind, bridge = if bridge then bridge[(i + 1) // 2] else false, rid = rid })
			segs.add(pts[i], pts[i + 1], pts[i + 2], pts[i + 3], width / 2)
		end
	end

	-- 1. Major network; register it so local streets join it.
	local majors = Roads.majors()
	local onFreeway = Roads.freewayPoints(majors)
	local SEED_STEP = Config.ROADS.SEED_STEP
	local seedBucket: { [number]: { { number } } } = {} -- superblock -> candidate seed points on majors
	for mi, m in majors do
		addRoad(m.pts, m.width, m.kind, m.bridge, mi) -- rid: which major road a segment belongs to
		-- freeways and ramps are grade-separated: no street, driveway or lot joins them
		if m.kind ~= "freeway" and m.kind ~= "ramp" then
			local id = Streets.addExternal(shared, m.pts, onFreeway)
			for _, c in Streets.frontSeeds(m.pts, id, SEED_STEP) do
				if not m.bridge[c[7]] and not onFreeway(c[1], c[2]) then
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

	-- 1b. Landmarks claim their ground before local streets; each gets an access road to the nearest
	-- surface major road (vertices bucketed in 512-stud cells for the search).
	local majorPts: { [number]: { { number } } } = {}
	for _, m in majors do
		if m.kind ~= "freeway" and m.kind ~= "ramp" then
			for i = 1, #m.pts - 1, 2 do
				if onFreeway(m.pts[i], m.pts[i + 1]) then
					continue -- never link onto a freeway point
				end
				local k = (m.pts[i] // 512) * 4096 + m.pts[i + 1] // 512
				majorPts[k] = majorPts[k] or {}
				table.insert(majorPts[k], { m.pts[i], m.pts[i + 1] })
			end
		end
	end
	local function accessRoad(l: Landmarks.Landmark): boolean
		-- nearest road points first; the first one reachable over land wins
		local cands = {}
		for _, e in { { l.x, l.z - l.d / 2 }, { l.x, l.z + l.d / 2 }, { l.x - l.w / 2, l.z }, { l.x + l.w / 2, l.z } } do
			local gx, gz = e[1] // 512, e[2] // 512
			for i = -12, 12 do
				for j = -12, 12 do
					for _, p in majorPts[(gx + i) * 4096 + gz + j] or {} do
						table.insert(cands, { (p[1] - e[1]) ^ 2 + (p[2] - e[2]) ^ 2, e, p })
					end
				end
			end
		end
		table.sort(cands, function(a, b)
			return a[1] < b[1]
		end)
		local best, from, to = math.huge, nil, nil
		for k = 1, math.min(#cands, 40) do
			local c = cands[k]
			if Terrain.dryLink(c[2][1], c[2][2], c[3][1], c[3][2]) and not Landmarks.crosses(c[2][1], c[2][2], c[3][1], c[3][2]) then
				best, from, to = c[1], c[2], c[3]
				break
			end
		end
		-- none over dry land (wetland sites): the nearest, as a park road on a causeway, if it isn't too long
		if not from then
			for k = 1, math.min(#cands, 40) do
				local c = cands[k]
				if c[1] < 6000 ^ 2 and not Landmarks.crosses(c[2][1], c[2][2], c[3][1], c[3][2]) then
					best, from, to = c[1], c[2], c[3]
					break
				end
			end
		end
		-- still none: route around the other landmarks over the terrain (A*, landmarks cost 500)
		local routed: { number }? = nil
		-- the A* grid (256 studs) can't see small sites, so check each route and keep the first that's clear
		for k = 1, math.min(#cands, 40), 4 do
			local c = cands[k]
			if from or c[1] >= 6000 ^ 2 then
				break
			end
			local route = Roads.route({ { c[2][1] / W, c[2][2] / W }, { c[3][1] / W, c[3][2] / W } }, "connector")
			route[1], route[2], route[#route - 1], route[#route] = c[2][1], c[2][2], c[3][1], c[3][2]
			local clear = true
			for i = 1, #route - 3, 2 do
				clear = clear and not Landmarks.crosses(route[i], route[i + 1], route[i + 2], route[i + 3])
			end
			if clear then
				best, from, to, routed = c[1], c[2], c[3], route
			end
		end
		if from and to then
			local pts = {}
			if routed then
				pts = routed
				pts[1], pts[2] = from[1], from[2]
			else
				local n = math.max(1, math.ceil(math.sqrt(best) / 40))
				for k = 0, n do
					table.insert(pts, from[1] + (to[1] - from[1]) * k / n)
					table.insert(pts, from[2] + (to[2] - from[2]) * k / n)
				end
			end
			pts[#pts - 1], pts[#pts] = to[1], to[2] -- exact junction
			Streets.addExternal(shared, pts)
			for k = 1, #pts - 1, 2 do -- later landmarks may link to this road (a park-road network)
				local key = (pts[k] // 512) * 4096 + pts[k + 1] // 512
				majorPts[key] = majorPts[key] or {}
				table.insert(majorPts[key], { pts[k], pts[k + 1] })
			end
			local wet = {}
			for k = 1, #pts - 3, 2 do
				table.insert(wet, Terrain.sample((pts[k] + pts[k + 2]) / 2, (pts[k + 1] + pts[k + 3]) / 2).water ~= nil)
			end
			addRoad(pts, Config.ROAD_W, "access", wet)
			return true
		end
		return false
	end
	-- bridge runs on surface-and-freeway majors (midpoint and length), for bridge landmarks
	local bridgeRuns = {}
	for _, m in majors do
		local runStart: number? = nil
		for k = 1, #m.bridge + 1 do
			local on = m.bridge[k] == true
			if on and not runStart then
				runStart = k
			elseif not on and runStart then
				local a, b = runStart * 2 - 1, k * 2 - 1
				local len = math.sqrt((m.pts[b] - m.pts[a]) ^ 2 + (m.pts[b + 1] - m.pts[a + 1]) ^ 2)
				local mid = ((runStart + k) // 2) * 2 - 1
				table.insert(bridgeRuns, { m.pts[mid], m.pts[mid + 1], len })
				runStart = nil
			end
		end
	end
	local landmarks = Landmarks.place(segs.clear, bridgeRuns)
	-- access roads in passes: a site that reaches nothing at first may reach another landmark's road later
	local pending = {}
	for _, l in landmarks do
		if l.site ~= "offshore" and l.site ~= "islet" and l.site ~= "bridge" then
			table.insert(pending, l)
		end
	end
	for _ = 1, 3 do
		local still = {}
		for _, l in pending do
			if not accessRoad(l) then
				table.insert(still, l)
			end
		end
		pending = still
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
				local fix = BLOCK_FIX[style]
				if fix then
					params = table.clone(params)
					params.spacing *= fix
					params.seedEvery = (params.seedEvery or 240) * fix
				end
				local function inside(x: number, z: number): boolean
					return x > x0 + 20 and x < x0 + SP - 20 and z > z0 + 20 and z < z0 + SP - 20 and urbanDistrict(x, z) ~= nil and not Landmarks.blocked(x, z)
				end
				local every = math.max(1, math.round((params.seedEvery or 240) / SEED_STEP))
				local seeds = Streets.blockSeeds(seedBucket[i * 4096 + j] or {}, every, inside)
				local net = Streets.grow(params, inside, x0 + SP / 2, z0 + SP / 2, SP / 2, 0, Config.SEED + i * 977 + j, 400, shared, seeds, Landmarks.okLink)
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
	for _, link in Streets.stitch(shared, allLocal, 300, Landmarks.okLink) do
		if onFreeway(link.pts[1], link.pts[2]) or onFreeway(link.pts[3], link.pts[4]) then
			continue -- a freeway's end is never a street junction
		end
		Streets.addExternal(shared, link.pts)
		addRoad(link.pts, Config.ROAD_W, "street")
	end
	-- Major roads that still end loose (e.g. at a lake shore) join the nearest street, any direction.
	local surfaceMajors = {}
	for _, m in majors do
		if m.kind ~= "freeway" and m.kind ~= "ramp" then
			table.insert(surfaceMajors, { kind = m.kind, pts = m.pts })
		end
	end
	for _, link in Streets.stitch(shared, surfaceMajors, 600, Landmarks.okLink, true) do
		if onFreeway(link.pts[1], link.pts[2]) or onFreeway(link.pts[3], link.pts[4]) then
			continue -- a freeway's end is never a street junction
		end
		Streets.addExternal(shared, link.pts)
		addRoad(link.pts, Config.ROAD_W, "street")
	end

	-- 3. Buildings on the frontage of every street and major road (majors become commercial strips).
	-- placed footprints as rotated boxes, bucketed on a 128-stud grid by their bounding box
	local placed: { [number]: { { number } } } = {}
	local function cells(x: number, z: number, w: number, d: number, rot: number, fn: (number) -> boolean?): boolean
		local c, sn = math.abs(math.cos(math.rad(rot))), math.abs(math.sin(math.rad(rot)))
		local ex, ez = (w * c + d * sn) / 2, (w * sn + d * c) / 2
		for gx = (x - ex) // 128, (x + ex) // 128 do
			for gz = (z - ez) // 128, (z + ez) // 128 do
				if fn((gx + 4096) * 8192 + gz + 4096) == false then
					return false
				end
			end
		end
		return true
	end
	local function overlap(a: { number }, b: { number }, pad: number): boolean -- separating-axis test
		for _, o in { a, b } do
			for k = 0, 1 do
				local ang = math.rad(o[5]) + k * math.pi / 2
				local ux, uz = math.cos(ang), math.sin(ang)
				local function half(r: { number }): number
					local rc, rs = math.cos(math.rad(r[5])), math.sin(math.rad(r[5]))
					return (math.abs(ux * rc + uz * rs) * r[3] + math.abs(-ux * rs + uz * rc) * r[4]) / 2
				end
				if math.abs((b[1] - a[1]) * ux + (b[2] - a[2]) * uz) >= half(a) + half(b) + pad then
					return false
				end
			end
		end
		return true
	end
	local function free(box: { number }, pad: number): boolean
		return cells(box[1], box[2], box[3], box[4], box[5], function(k)
			for _, o in placed[k] or {} do
				if overlap(box, o, pad) then
					return false
				end
			end
			return nil
		end)
	end
	-- Frontage candidates: real-sized footprints drawn along both sides of every street at real gaps.
	local cands = {}
	local function frontage(pts: { number }, width: number)
		local carry = { [1] = 0, [-1] = 0 }
		for i = 1, #pts - 3, 2 do
			local ax, az, bx, bz = pts[i], pts[i + 1], pts[i + 2], pts[i + 3]
			local len = math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2)
			if len > 1e-3 then
				local dx, dz = (bx - ax) / len, (bz - az) / len
				local d = urbanDistrict((ax + bx) / 2, (az + bz) / 2)
				local style0 = d and d.style or "house"
				for _, side in { 1, -1 } do
					local t = carry[side]
					while t < len do
						local fw, fd, setback, gap = footprint(style0, rng, 1)
						table.insert(cands, { ax = ax, az = az, dx = dx, dz = dz, width = width, t = t, side = side, w = fw, d = fd, setback = setback })
						t += fw + gap
					end
					carry[side] = t - len
				end
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
	-- Biggest first (a big building takes its block, smaller ones fill around it); each slides along
	-- the street, then shrinks, until it fits.
	table.sort(cands, function(p, q)
		return p.w * p.d > q.w * q.d
	end)
	for _, c in cands do
		local ang = math.deg(math.atan2(c.dz, c.dx))
		local w, dep, x, z, ld = 0, 0, 0, 0, nil :: Config.District?
		local ok = false
		-- { area scale, slide along the street, turn sideways, build to the sidewalk }
		for _, try in { { 1, 0 }, { 1, 15 }, { 1, -15 }, { 1, 30 }, { 1, 0, true }, { 1, 0, false, true }, { 1, 0, true, true },
			{ 1, 20, true, true }, { 0.6, 0 }, { 0.6, 0, true, true }, { 0.35, 0 } } do
			local k = math.sqrt(try[1])
			w, dep = c.w * k, c.d * k
			if try[3] then
				w, dep = dep, w
			end
			local off = (if try[4] then c.width / 2 + 4 else math.max(c.setback, c.width / 2 + 4)) + dep / 2
			local at = c.t + try[2] + w / 2
			local px, pz = c.ax + c.dx * at, c.az + c.dz * at
			x, z = px - c.dz * off * c.side, pz + c.dx * off * c.side
			ld = urbanDistrict(x, z)
			if ld and segs.boxClear(x, z, w, dep, ang) and free({ x, z, w, dep, ang }, 1.5)
				and not Landmarks.blocked(x, z, math.max(w, dep) / 2) then
				ok = true
				break
			end
		end
		if ok and ld then
			local style = ld.style :: string
			local s = Terrain.sample(x, z)
			local box = { x, z, w, dep, ang }
			cells(x, z, w, dep, ang, function(k)
				placed[k] = placed[k] or {}
				table.insert(placed[k], box)
				return nil
			end)
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
					-- slenderness cap: real buildings are rarely taller than ~7x their narrow side
					h = math.floor(math.min(minH + (maxH - minH) * tt, math.max(minH, 7 * math.min(w, dep)))),
					rot = ang + (if c.side == 1 then 0 else 180),
					style = style, district = ld.id, variant = rng:int(1, 8),
				})
			end
		end
	end

	-- Grade separation, last word: where a freeway passes through a point (the same freeway on both sides),
	-- no surface segment may touch it; any that does (a stray link) is dropped. Freeway ends may meet roads.
	local through: { [string]: number } = {}
	local function vk(x: number, z: number): string
		return math.round(x * 2) .. "," .. math.round(z * 2)
	end
	for _, r in roads do
		if r.kind == "freeway" then
			for _, p in { { r.ax, r.az }, { r.bx, r.bz } } do
				local k = vk(p[1], p[2]) .. "#" .. r.rid
				through[k] = (through[k] or 0) + 1
			end
		end
	end
	local passThrough: { [string]: boolean } = {}
	for k, n in through do
		if n >= 2 then
			passThrough[string.split(k, "#")[1]] = true
		end
	end
	for i = #roads, 1, -1 do
		local r = roads[i]
		if r.kind ~= "freeway" and r.kind ~= "ramp" and (passThrough[vk(r.ax, r.az)] or passThrough[vk(r.bx, r.bz)]) then
			table.remove(roads, i)
		end
	end

	-- Airport runways (landmark, hand-placed)
	local a = Districts.byId.airport
	for _, off in { -200, 200 } do
		local x, z = a.u * W, a.v * W + off
		table.insert(roads, { ax = x - 1100, az = z, bx = x + 1100, bz = z, width = 110, kind = "runway", bridge = false })
	end
	return { roads = roads, buildings = buildings, parks = parks, shared = shared, landmarks = landmarks }
end

return City
