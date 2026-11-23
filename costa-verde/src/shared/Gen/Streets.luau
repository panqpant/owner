--!strict
-- Street network growth. Collector streets cross the area; side streets branch off at junctions,
-- drift/curve, join existing roads (T-junctions), cross through (crossroads) or stop (cul-de-sacs).
-- Parameters per district style are tuned against real US networks (tools/train_streets.py).
local Hash = require("./Hash")

local Streets = {}

export type Params = {
	spacing: number, -- target distance between junctions (studs)
	order: number, -- 0 = free headings, 1 = snapped to a 2-axis grid
	curve: number, -- heading drift per 100 studs (radians)
	branch: number, -- chance of a side street at each junction, per side
	cross: number, -- chance a side street continues across (makes a crossroads)
	deadEnd: number, -- chance a street stops at a junction (cul-de-sac)
	connect: number, -- snap distance to join another road, as a fraction of spacing
	maxLen: number, -- longest a side street grows, in blocks
	collectors: number, -- number of collector streets seeded through the area
	aspect: number?, -- block length / block width (real grids ~1.5-3); junctions sit on a shared lattice
	seedEvery: number?, -- studs between side streets started from a bounding major road
}

export type Road = { kind: string, pts: { number }, cul: boolean? } -- flat x, z, ...; cul = ends in a cul-de-sac on purpose

local STEP = 40

export type Shared = { grid: { [number]: { { number } } }, nid: number }

function Streets.newShared(): Shared
	return { grid = {}, nid = 0 }
end

local CELL = 64
local function key(x: number, z: number): number
	return (math.floor(x / CELL) + 32768) * 65536 + (math.floor(z / CELL) + 32768)
end

-- Register an existing road (flat x, z, ...) so streets can join it; returns its id.
function Streets.addExternal(shared: Shared, pts: { number }): number
	shared.nid += 1
	local id = shared.nid
	for i = 1, #pts - 1, 2 do
		local k = key(pts[i], pts[i + 1])
		shared.grid[k] = shared.grid[k] or {}
		table.insert(shared.grid[k], { pts[i], pts[i + 1], id })
	end
	return id
end

export type Seed = { x: number, z: number, h: number, parent: number }

-- Candidate side-street starts along a road: every `step` studs, with the road's left normal.
-- `idx` counts along the road so both sides (and both neighbouring blocks) pick the same points.
function Streets.frontSeeds(pts: { number }, id: number, step: number): { { number } }
	local out, acc, idx = {}, 0, 0
	for i = 3, #pts - 3, 2 do
		acc += math.sqrt((pts[i] - pts[i - 2]) ^ 2 + (pts[i + 1] - pts[i - 1]) ^ 2)
		if acc >= step then
			acc = 0
			idx += 1
			local dx, dz = pts[i + 2] - pts[i - 2], pts[i + 3] - pts[i - 1]
			local l = math.sqrt(dx * dx + dz * dz)
			table.insert(out, { pts[i], pts[i + 1], -dz / l, dx / l, id, idx, (i + 1) // 2 })
		end
	end
	return out
end

-- Seeds for one block: candidates every `every`-th point, heading into the block on either side.
function Streets.blockSeeds(cands: { { number } }, every: number, inside: (number, number) -> boolean): { Seed }
	local seeds = {}
	for _, c in cands do
		if c[6] % every == 0 then
			for _, side in { 1, -1 } do
				local hx, hz = c[3] * side, c[4] * side
				if inside(c[1] + hx * 60, c[2] + hz * 60) then
					table.insert(seeds, { x = c[1], z = c[2], h = math.atan2(hz, hx), parent = c[5] })
				end
			end
		end
	end
	return seeds
end

-- `shared` lets several districts grow into one network: later ones join onto earlier roads at borders.
-- `seeds`: start streets from these points (on existing roads) instead of seeding collectors.
-- `link`: may a joining step from (ax, az) to (bx, bz) be built (e.g. not across water)? default: yes.
function Streets.grow(p: Params, inside: (number, number) -> boolean, cx: number, cz: number, half: number, angle: number, seed: number, cap: number?, shared: Shared?, seeds: { Seed }?, link: ((number, number, number, number) -> boolean)?): { Road }
	local canLink = link or function()
		return true
	end
	local rng = Hash.rng(seed)
	local roads: { Road } = {}
	local state = shared or Streets.newShared()
	local grid = state.grid
	local function addVertex(x: number, z: number, road: number)
		local k = key(x, z)
		local list = grid[k]
		if not list then
			list = {}
			grid[k] = list
		end
		table.insert(list, { x, z, road })
	end
	-- nearest vertex of another road within r (excluding road `self`)
	local function nearest(x: number, z: number, r: number, self: number, also: number?): (number?, number?)
		local bx, bz, bd = nil, nil, r * r
		local cr = math.ceil(r / CELL)
		local gx, gz = math.floor(x / CELL), math.floor(z / CELL)
		for i = -cr, cr do
			for j = -cr, cr do
				local list = grid[(gx + i + 32768) * 65536 + (gz + j + 32768)]
				if list then
					for _, v in list do
						if v[3] ~= self and v[3] ~= also then
							local d = (v[1] - x) ^ 2 + (v[2] - z) ^ 2
							if d < bd then
								bx, bz, bd = v[1], v[2], d
							end
						end
					end
				end
			end
		end
		return bx, bz
	end
	local function snapHeading(h: number): number
		local axis = angle + math.round((h - angle) / (math.pi / 2)) * (math.pi / 2)
		return h + (axis - h) * p.order ^ 4 -- per-step pull: mid values still allow real curves
	end

	type Head = { x: number, z: number, h: number, depth: number, parent: number }
	local queue: { Head } = {}
	local limit = cap or 4000

	-- Grow one street from a head; returns nothing, pushes branch heads.
	local function grow(hd: Head, kind: string, maxBlocks: number)
		local slot = #roads + 1
		local id = state.nid + slot
		local pts = { hd.x, hd.z }
		local x, z, h = hd.x, hd.z, hd.h
		local sinceJunction = 0
		local nextJunction = p.spacing * rng:range(0.75, 1.25)
		local blocks = 0
		local total = 0
		-- side streets bend in a steady arc (suburban loops); curvature then changes slowly, never jitters
		local turn = if kind == "collector" then 0 else rng:range(-1, 1) * p.curve * STEP / 100
		local stub = -1 -- > 0 while finishing a cul-de-sac
		-- Lattice: on grid-like styles junctions fall on shared lines, so parallel streets make neat blocks.
		local useLattice = p.order >= 0.6
		local function cellOf(px: number, pz: number): number
			local along = if math.abs(math.cos(h - angle)) >= math.abs(math.sin(h - angle)) then angle else angle + math.pi / 2
			local spacingAxis = if along == angle then p.spacing * (p.aspect or 1) else p.spacing
			return math.floor(((px - cx) * math.cos(along) + (pz - cz) * math.sin(along)) / spacingAxis)
		end
		local lastCell = cellOf(x, z)
		while true do
			turn = math.clamp(turn + rng:range(-1, 1) * p.curve * 0.03, -p.curve * STEP / 100, p.curve * STEP / 100)
			h = snapHeading(h + turn)
			if stub == 0 then
				break
			elseif stub > 0 then
				stub -= 1
			end
			local nx, nz = x + math.cos(h) * STEP, z + math.sin(h) * STEP
			if not inside(nx, nz) or math.max(math.abs(nx - cx), math.abs(nz - cz)) > half then
				-- leaving the area: join the nearest road out there (e.g. the bounding arterial), not a dead end
				local jx, jz = nearest(nx, nz, p.spacing * 0.75, id, if total < p.spacing then hd.parent else nil)
				if jx and total > 0 and canLink(x, z, jx, jz :: number) then
					table.insert(pts, jx)
					table.insert(pts, jz :: number)
				end
				break
			end
			-- reached another road -> join it (T junction) and stop
			if total > p.spacing * 0.3 then
				-- (a sibling grown back-to-back from the same seed is ignored for the first block)
				local jx, jz = nearest(nx, nz, p.connect * p.spacing, id, if total < p.spacing then hd.parent else nil)
				if jx and canLink(x, z, jx, jz :: number) then
					table.insert(pts, jx)
					table.insert(pts, jz :: number)
					break
				end
			end
			x, z = nx, nz
			total += STEP
			sinceJunction += STEP
			table.insert(pts, x)
			table.insert(pts, z)
			addVertex(x, z, id)
			local atJunction
			if useLattice then
				local c = cellOf(x, z)
				atJunction = c ~= lastCell
				lastCell = c
			else
				atJunction = sinceJunction >= nextJunction
			end
			if atJunction and stub < 0 then
				sinceJunction = 0
				nextJunction = p.spacing * rng:range(0.75, 1.25)
				blocks += 1
				-- decide first: a street that ends here runs on a short stub to a cul-de-sac, no branches
				if kind ~= "collector" and (blocks >= maxBlocks or rng:next() < p.deadEnd) then
					stub = math.max(1, math.floor(p.spacing * 0.4 / STEP))
				elseif hd.depth < 6 and #roads + #queue < limit then
					local left = rng:next() < p.branch
					local right = rng:next() < p.branch or (left and rng:next() < p.cross)
					if left then
						table.insert(queue, { x = x, z = z, h = h + math.pi / 2, depth = hd.depth + 1, parent = id })
					end
					if right then
						table.insert(queue, { x = x, z = z, h = h - math.pi / 2, depth = hd.depth + 1, parent = id })
					end
				end
			end
		end
		if #pts >= 4 then
			roads[slot] = { kind = kind, pts = pts, cul = stub == 0 }
		else
			roads[slot] = { kind = "street", pts = {} }
		end
	end

	-- On grid styles, move a seed sideways onto the lattice line its street will run along, so every
	-- road shares the lattice (and rural fields, which use the same lattice, sit between roads).
	local function onLattice(x: number, z: number, a: number): (number, number)
		if p.order < 0.6 then
			return x, z
		end
		local alongAngle = math.abs(math.cos(a - angle)) >= math.abs(math.sin(a - angle))
		local nx, nz = -math.sin(a), math.cos(a)
		local sp = if alongAngle then p.spacing else p.spacing * (p.aspect or 1)
		local q = (x - cx) * nx + (z - cz) * nz
		local dq = math.round(q / sp) * sp - q
		return x + nx * dq, z + nz * dq
	end

	for _, sd in seeds or {} do
		if #roads + #queue >= limit then
			break
		end
		grow({ x = sd.x, z = sd.z, h = sd.h, depth = 0, parent = sd.parent }, "collector", math.huge)
	end
	for c = 1, if seeds then 0 else p.collectors do
		local a = angle + (if c % 2 == 0 then math.pi / 2 else 0) + rng:range(-0.15, 0.15) * (1 - p.order)
		local off = rng:range(-0.6, 0.6) * half
		local sx = cx - math.cos(a) * half + math.cos(a + math.pi / 2) * off
		local sz = cz - math.sin(a) * half + math.sin(a + math.pi / 2) * off
		sx, sz = onLattice(sx, sz, a)
		-- walk the start point inward until it is inside the area
		for _ = 1, 100 do
			if inside(sx, sz) then
				break
			end
			sx += math.cos(a) * STEP
			sz += math.sin(a) * STEP
		end
		grow({ x = sx, z = sz, h = a, depth = 0, parent = -1 }, "collector", math.huge)
	end
	local qi = 1
	local function drain()
		while qi <= #queue and #roads < limit do
			local hd = queue[qi]
			qi += 1
			grow(hd, "street", p.maxLen)
		end
	end
	drain()
	-- Coverage: irregular areas (between lakes, coast, levee) get new collectors wherever no road
	-- reached yet, grown both ways from the seed.
	local stepC = p.spacing * 1.5
	for pass = 1, 3 do
		for gx = cx - half, cx + half, stepC do
			for gz = cz - half, cz + half, stepC do
				if #roads >= limit then
					break
				end
				local x = gx + rng:range(-0.3, 0.3) * stepC
				local z = gz + rng:range(-0.3, 0.3) * stepC
				if inside(x, z) and not nearest(x, z, p.spacing * 1.1, -1) then
					local a = angle + (if rng:next() < 0.5 then 0 else math.pi / 2)
					x, z = onLattice(x, z, a)
					local first = state.nid + #roads + 1
					grow({ x = x, z = z, h = a, depth = 0, parent = -1 }, "collector", math.huge)
					grow({ x = x, z = z, h = a + math.pi, depth = 0, parent = first }, "collector", math.huge)
					drain()
				end
			end
		end
	end
	state.nid += #roads
	local out = {}
	for _, r in roads do
		if #r.pts >= 4 then
			table.insert(out, r)
		end
	end
	return out
end

-- Stitch: every street end that is neither joined to another road nor a deliberate cul-de-sac gets
-- linked to the nearest road vertex within `reach` (if `ok` allows the link, e.g. not over water).
-- Returns the new link roads.
-- `anyDirection`: also link backwards/sideways (a fallback for ends that found nothing ahead).
function Streets.stitch(shared: Shared, roads: { Road }, reach: number, ok: (number, number, number, number) -> boolean, anyDirection: boolean?): { Road }
	local ahead = if anyDirection then -math.huge else 0.3
	local grid = shared.grid
	-- nearest other-road vertex ahead of the end (dx, dz = direction of travel), or whether it's already joined
	local function others(x: number, z: number, dx: number, dz: number, r: number, self: { number }): (number?, number?, boolean)
		local bx, bz, bd, joined = nil, nil, r * r, false
		local cr = math.ceil(r / CELL)
		local gx, gz = math.floor(x / CELL), math.floor(z / CELL)
		for i = -cr, cr do
			for j = -cr, cr do
				for _, v in grid[(gx + i + 32768) * 65536 + (gz + j + 32768)] or {} do
					local d = (v[1] - x) ^ 2 + (v[2] - z) ^ 2
					if d < 0.25 and not self[v[3]] then
						joined = true
					elseif d < bd and d > 0.25 and not self[v[3]] and (v[1] - x) * dx + (v[2] - z) * dz > ahead * math.sqrt(d) then
						bx, bz, bd = v[1], v[2], d
					end
				end
			end
		end
		return bx, bz, joined
	end
	-- which grid ids belong to a road: look up its own vertices
	local links: { Road } = {}
	for _, r in roads do
		local p = r.pts
		if #p >= 4 then
			local self: { [number]: boolean } = {}
			for _, v in grid[key(p[3], p[4])] or {} do
				if v[1] == p[3] and v[2] == p[4] then
					self[v[3]] = true
				end
			end
			local ends = { { p[1], p[2], p[1] - p[3], p[2] - p[4] } }
			if not r.cul then
				table.insert(ends, { p[#p - 1], p[#p], p[#p - 1] - p[#p - 3], p[#p] - p[#p - 2] })
			end
			for _, e in ends do
				local l = math.max(math.sqrt(e[3] ^ 2 + e[4] ^ 2), 1e-6)
				local bx, bz, joined = others(e[1], e[2], e[3] / l, e[4] / l, reach, self :: any)
				if not joined and bx and ok(e[1], e[2], bx, bz :: number) then
					table.insert(links, { kind = "street", pts = { e[1], e[2], bx, bz :: number } })
				end
			end
		end
	end
	return links
end

return Streets
