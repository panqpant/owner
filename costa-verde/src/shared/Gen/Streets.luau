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
}

export type Road = { kind: string, pts: { number } } -- flat x, z, x, z ...

local STEP = 40

export type Shared = { grid: { [number]: { { number } } }, nid: number }

function Streets.newShared(): Shared
	return { grid = {}, nid = 0 }
end

-- `shared` lets several districts grow into one network: later ones join onto earlier roads at borders.
function Streets.grow(p: Params, inside: (number, number) -> boolean, cx: number, cz: number, half: number, angle: number, seed: number, cap: number?, shared: Shared?): { Road }
	local rng = Hash.rng(seed)
	local roads: { Road } = {}
	local CELL = 64
	local state = shared or Streets.newShared()
	local grid = state.grid
	local function key(x: number, z: number): number
		return (math.floor(x / CELL) + 32768) * 65536 + (math.floor(z / CELL) + 32768)
	end
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
		return h + (axis - h) * p.order
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
		local turn = 0 -- curvature changes slowly: smooth arcs, not jitter
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
				break
			end
			-- reached another road -> join it (T junction) and stop
			if total > p.spacing * 0.3 then
				-- (a sibling grown back-to-back from the same seed is ignored for the first block)
				local jx, jz = nearest(nx, nz, p.connect * p.spacing, id, if total < p.spacing then hd.parent else nil)
				if jx then
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
			roads[slot] = { kind = if kind == "collector" then "arterial" else "street", pts = pts }
		else
			roads[slot] = { kind = "street", pts = {} }
		end
	end

	for c = 1, p.collectors do
		local a = angle + (if c % 2 == 0 then math.pi / 2 else 0) + rng:range(-0.15, 0.15) * (1 - p.order)
		local off = rng:range(-0.6, 0.6) * half
		local sx = cx - math.cos(a) * half + math.cos(a + math.pi / 2) * off
		local sz = cz - math.sin(a) * half + math.sin(a + math.pi / 2) * off
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

return Streets
