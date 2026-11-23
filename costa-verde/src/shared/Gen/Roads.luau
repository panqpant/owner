--!strict
-- Whole-map major road network, built top-down like a real region:
--   freeways and rail routed by A* over a terrain cost grid (curve around lakes, bridge water only
--   where needed), one continuous arterial grid over every built-up area (denser boulevards
--   downtown), a spine road along the barrier island, state roads linking towns, and every crossing
--   turned into a shared junction vertex (planarized) so the network is connected.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Streets = require("./Streets")
local Hash = require("./Hash")
local Landmarks = require("./Landmarks")

local Roads = {}

export type Major = { kind: string, width: number, pts: { number }, bridge: { boolean } }

local W = Config.SIZE
local R = Config.ROADS
local STEP = 40 -- vertex spacing on major roads (local streets snap to these)

-- Terrain cost grid for routing ------------------------------------------------------------------
local G = 256
local N = math.floor(W / G)
local costCache: { [string]: { number } } = {}

local function costGrid(profile: string): { number }
	if costCache[profile] then
		return costCache[profile]
	end
	local P = R.COST[profile]
	local c = table.create(N * N, 1)
	for j = 0, N - 1 do
		for i = 0, N - 1 do
			local s = Terrain.sample((i + 0.5) * G, (j + 0.5) * G)
			local v = 1
			if s.biome == "lake" then
				v = P.lake
			elseif s.water then
				v = if s.biome == "marsh" then P.wetland else P.water
			elseif s.biome == "wetland" or s.biome == "hammock" then
				v = P.wetland
			elseif s.biome == "mangrove" then
				v = P.mangrove
			elseif Districts.urban((i + 0.5) * G, (j + 0.5) * G) > 0 then
				v = P.urban
			end
			if P.landmark and (Landmarks.blocked((i + 0.5) * G, (j + 0.5) * G, G / 2) or Landmarks.blocked(i * G, j * G, 20)
				or Landmarks.blocked((i + 1) * G, j * G, 20) or Landmarks.blocked(i * G, (j + 1) * G, 20) or Landmarks.blocked((i + 1) * G, (j + 1) * G, 20)) then
				v = P.landmark -- connector roads (routed after landmarks exist) go around them
			end
			c[j * N + i + 1] = v
		end
	end
	costCache[profile] = c
	return c
end

-- A* on the cost grid (8-neighbour), returns cell-centre points from a to b (studs).
local function astar(ax: number, az: number, bx: number, bz: number, profile: string): { { number } }
	local c = costGrid(profile)
	local function cell(x: number, z: number): number
		return math.clamp(math.floor(z / G), 0, N - 1) * N + math.clamp(math.floor(x / G), 0, N - 1)
	end
	local start, goal = cell(ax, az), cell(bx, bz)
	local gi, gj = goal % N, goal // N
	local g: { [number]: number } = { [start] = 0 }
	local from: { [number]: number } = {}
	local heap: { { number } } = { { 0, start } }
	local function push(f: number, n: number)
		table.insert(heap, { f, n })
		local k = #heap
		while k > 1 and heap[k // 2][1] > heap[k][1] do
			heap[k], heap[k // 2] = heap[k // 2], heap[k]
			k //= 2
		end
	end
	local function pop(): { number }
		local top = heap[1]
		heap[1] = heap[#heap]
		table.remove(heap)
		local k = 1
		while true do
			local l, r, m = k * 2, k * 2 + 1, k
			if l <= #heap and heap[l][1] < heap[m][1] then
				m = l
			end
			if r <= #heap and heap[r][1] < heap[m][1] then
				m = r
			end
			if m == k then
				break
			end
			heap[k], heap[m] = heap[m], heap[k]
			k = m
		end
		return top
	end
	local closed: { [number]: boolean } = {}
	while #heap > 0 do
		local cur = pop()[2]
		if cur == goal then
			break
		end
		if not closed[cur] then
			closed[cur] = true
			local ci, cj = cur % N, cur // N
			for di = -1, 1 do
				for dj = -1, 1 do
					local ni, nj = ci + di, cj + dj
					if (di ~= 0 or dj ~= 0) and ni >= 0 and nj >= 0 and ni < N and nj < N then
						local nb = nj * N + ni
						local step = (if di ~= 0 and dj ~= 0 then 1.4142 else 1) * (c[cur + 1] + c[nb + 1]) / 2
						local ng = g[cur] + step
						if g[nb] == nil or ng < g[nb] then
							g[nb] = ng
							from[nb] = cur
							push(ng + math.sqrt((ni - gi) ^ 2 + (nj - gj) ^ 2), nb)
						end
					end
				end
			end
		end
	end
	local path = { { bx, bz } }
	local n = from[goal]
	while n and n ~= start do
		table.insert(path, 1, { (n % N + 0.5) * G, (n // N + 0.5) * G })
		n = from[n]
	end
	table.insert(path, 1, { ax, az })
	return path
end

-- Chaikin smoothing then even resampling: real roads curve gently between waypoints.
local function smoothResample(pts: { { number } }, iterations: number): { number }
	for _ = 1, iterations do
		local out = { pts[1] }
		for k = 1, #pts - 1 do
			local a, b = pts[k], pts[k + 1]
			table.insert(out, { a[1] * 0.75 + b[1] * 0.25, a[2] * 0.75 + b[2] * 0.25 })
			table.insert(out, { a[1] * 0.25 + b[1] * 0.75, a[2] * 0.25 + b[2] * 0.75 })
		end
		table.insert(out, pts[#pts])
		pts = out
	end
	local flat = { pts[1][1], pts[1][2] }
	local carry = 0
	for k = 1, #pts - 1 do
		local a, b = pts[k], pts[k + 1]
		local len = math.sqrt((b[1] - a[1]) ^ 2 + (b[2] - a[2]) ^ 2)
		local t = STEP - carry
		while t <= len do
			table.insert(flat, a[1] + (b[1] - a[1]) * t / len)
			table.insert(flat, a[2] + (b[2] - a[2]) * t / len)
			t += STEP
		end
		carry = len - (t - STEP)
	end
	local last = pts[#pts]
	if (flat[#flat - 1] - last[1]) ^ 2 + (flat[#flat] - last[2]) ^ 2 > 1 then
		table.insert(flat, last[1])
		table.insert(flat, last[2])
	end
	return flat
end

-- Route through normalized waypoints with A*; returns a flat polyline.
function Roads.route(waypoints: { { number } }, profile: string): { number }
	local cells = {}
	for k = 1, #waypoints - 1 do
		local a, b = waypoints[k], waypoints[k + 1]
		local p = astar(a[1] * W, a[2] * W, b[1] * W, b[2] * W, profile)
		for q = (if k == 1 then 1 else 2), #p do
			table.insert(cells, p[q])
		end
	end
	return smoothResample(cells, 3)
end

local function bridges(pts: { number }): { boolean }
	local out = {}
	for i = 1, #pts - 3, 2 do
		table.insert(out, Terrain.sample((pts[i] + pts[i + 2]) / 2, (pts[i + 1] + pts[i + 3]) / 2).water ~= nil)
	end
	return out
end

-- Arterial grid ----------------------------------------------------------------------------------
local function builtUp(x: number, z: number): boolean
	local s = Terrain.sample(x, z)
	if s.water or s.land < 20 then
		return false
	end
	return s.shape == "barrier" or ((s.shape == "main" or s.shape == "key") and Districts.urban(x, z) > 0)
end

-- One grid line (vertical if `alongZ`) at coordinate `c`: kept where built up, short water gaps bridged.
local function gridLine(c: number, alongZ: boolean, maxGap: number, kind: string, width: number, keep: ((number, number) -> boolean)?, out: { Major })
	local run: { number }? = nil
	local gap = 0
	local pending: { number } = {}
	local function flush()
		if run and #run >= 2 * 8 then -- at least ~300 studs
			table.insert(out, { kind = kind, width = width, pts = run, bridge = bridges(run) })
		end
		run, gap, pending = nil, 0, {}
	end
	for t = 0, W, STEP do
		local x, z = if alongZ then c else t, if alongZ then t else c
		local on = builtUp(x, z) and (keep == nil or keep(x, z))
		if on then
			if run then
				for _, v in pending do -- the gap was short enough: bridge it
					table.insert(run, v)
				end
			else
				run = {}
			end
			pending = {}
			gap = 0
			table.insert(run :: { number }, x)
			table.insert(run :: { number }, z)
		elseif run then
			gap += STEP
			if gap > maxGap then
				flush()
			else
				table.insert(pending, x)
				table.insert(pending, z)
			end
		end
	end
	flush()
end

-- Planarize: wherever two majors cross, insert the same junction vertex into both, except where a
-- freeway crosses a surface road: that is grade-separated (an overpass) and returned for interchanges.
local function planarize(majors: { Major }): { { number } }
	local crossings: { { number } } = {}
	local CELL = 256
	local grid: { [number]: { { number } } } = {}
	for ri, m in majors do
		local p = m.pts
		for i = 1, #p - 3, 2 do
			local x0, x1 = math.min(p[i], p[i + 2]), math.max(p[i], p[i + 2])
			local z0, z1 = math.min(p[i + 1], p[i + 3]), math.max(p[i + 1], p[i + 3])
			for gx = math.floor(x0 / CELL), math.floor(x1 / CELL) do
				for gz = math.floor(z0 / CELL), math.floor(z1 / CELL) do
					local k = gx * 4096 + gz
					grid[k] = grid[k] or {}
					table.insert(grid[k], { ri, i })
				end
			end
		end
	end
	local inserts: { [number]: { [number]: { { number } } } } = {}
	local seen: { [string]: boolean } = {}
	for _, list in grid do
		for a = 1, #list do
			for b = a + 1, #list do
				local ra, ia, rb, ib = list[a][1], list[a][2], list[b][1], list[b][2]
				local key = `{ra}:{ia}:{rb}:{ib}`
				if ra ~= rb and not seen[key] then
					seen[key] = true
					local p, q = majors[ra].pts, majors[rb].pts
					local x1, z1, x2, z2 = p[ia], p[ia + 1], p[ia + 2], p[ia + 3]
					local x3, z3, x4, z4 = q[ib], q[ib + 1], q[ib + 2], q[ib + 3]
					local den = (x2 - x1) * (z4 - z3) - (z2 - z1) * (x4 - x3)
					if math.abs(den) > 1e-6 then
						local t = ((x3 - x1) * (z4 - z3) - (z3 - z1) * (x4 - x3)) / den
						local u = ((x3 - x1) * (z2 - z1) - (z3 - z1) * (x2 - x1)) / den
						local fa, fb = majors[ra].kind == "freeway", majors[rb].kind == "freeway"
						if t > 1e-6 and t < 1 - 1e-6 and u > 1e-6 and u < 1 - 1e-6 and (fa or fb) then
							-- grade-separated: freeway over a surface road, or freeway over freeway (system)
							table.insert(crossings, { x1 + (x2 - x1) * t, z1 + (z2 - z1) * t, if fa then ra else rb, if fa then rb else ra, if fa and fb then 1 else 0 })
						elseif t > 1e-6 and t < 1 - 1e-6 and u > 1e-6 and u < 1 - 1e-6 then
							local x, z = x1 + (x2 - x1) * t, z1 + (z2 - z1) * t
							for _, ins in { { ra, ia, t }, { rb, ib, u } } do
								inserts[ins[1]] = inserts[ins[1]] or {}
								inserts[ins[1]][ins[2]] = inserts[ins[1]][ins[2]] or {}
								table.insert(inserts[ins[1]][ins[2]], { ins[3], x, z })
							end
						end
					end
				end
			end
		end
	end
	for ri, bySeg in inserts do
		local m = majors[ri]
		local p, out, br = m.pts, {}, {}
		for i = 1, #p - 1, 2 do
			table.insert(out, p[i])
			table.insert(out, p[i + 1])
			local list = bySeg[i]
			local b = m.bridge[(i + 1) // 2]
			if list then
				table.sort(list, function(a, c)
					return a[1] < c[1]
				end)
				for _, v in list do
					table.insert(br, b)
					table.insert(out, v[2])
					table.insert(out, v[3])
				end
			end
			if i < #p - 1 then
				table.insert(br, b)
			end
		end
		m.pts, m.bridge = out, br
	end
	return crossings
end

-- Interchange at each grade-separated crossing. The type is picked from the mix measured on real
-- Florida freeways (tools/interchange_stats.py, Config.ROADS.INTERCHANGE_MIX): urban or rural by where
-- it is; freeway-over-freeway crossings get a system interchange (cloverleaf geometry).
local function interchanges(majors: { Major }, crossings: { { number } })
	local function nearestIndex(p: { number }, x: number, z: number): number
		local best, bi = math.huge, 1
		for i = 1, #p - 1, 2 do
			local d = (p[i] - x) ^ 2 + (p[i + 1] - z) ^ 2
			if d < best then
				best, bi = d, i
			end
		end
		return bi
	end
	local function ramp(pts: { number })
		table.insert(majors, { kind = "ramp", width = R.RAMP_W, pts = pts, bridge = bridges(pts) })
	end
	local function pick(mix: { [string]: number }, x: number, z: number): string
		local roll, acc, last = Hash.float(math.round(x), math.round(z), Config.SEED + 700), 0, "diamond"
		for _, kind in { "diamond", "parclo", "clover", "spui" } do
			acc += mix[kind] or 0
			last = kind
			if roll < acc then
				return kind
			end
		end
		return last
	end
	local done: { [string]: boolean } = {}
	for _, c in crossings do
		local x, z = c[1], c[2]
		local k = math.round(x / 50) .. "," .. math.round(z / 50) -- one interchange per crossing
		if not done[k] then
			done[k] = true
			local fp, op = majors[c[3]].pts, majors[c[4]].pts
			local fi, oi = nearestIndex(fp, x, z), nearestIndex(op, x, z)
			local urban = Districts.urban(x, z) > 0
			local kind = if c[5] == 1 then "clover" else pick(if urban then R.INTERCHANGE_MIX.urban else R.INTERCHANGE_MIX.rural, x, z)
			local function vertex(p: { number }, i: number): (number?, number?)
				if i >= 1 and i < #p then
					return p[i], p[i + 1]
				end
				return nil, nil
			end
			-- outer ramp in quadrant (s, t): freeway vertex `fo` steps along, surface vertex `oo` steps along
			local function outer(s: number, t: number, fo: number, oo: number)
				local px, pz = vertex(fp, fi + s * fo * 2)
				local ax, az = vertex(op, oi + t * oo * 2)
				if px and ax then
					local cx, cz = px + ax - x, pz + az - z -- quadrant corner: the ramp bows outward
					local pts = {}
					for q = 0, 8 do
						local u = q / 8
						table.insert(pts, (1 - u) ^ 2 * px + 2 * (1 - u) * u * cx + u * u * ax)
						table.insert(pts, (1 - u) ^ 2 * pz + 2 * (1 - u) * u * cz + u * u * (az :: number))
					end
					ramp(pts)
				end
			end
			-- loop ramp in quadrant (s, t): leaves the freeway, turns ~270 degrees, joins the crossing road
			local function loop(s: number, t: number)
				local px, pz = vertex(fp, fi + s * 3 * 2)
				local ax, az = vertex(op, oi + t * 3 * 2)
				if px and ax then
					local fdx, fdz = (px - x), (pz - z)
					local odx, odz = (ax - x), (az :: number - z)
					local cx, cz = x + (fdx + odx) * 0.75, z + (fdz + odz) * 0.75 -- loop centre inside the quadrant
					local a0 = math.atan2(pz - cz, px - cx)
					local a1 = math.atan2(az :: number - cz, ax - cx)
					local d = (a1 - a0) % (2 * math.pi)
					-- turn whichever way round makes the loop closest to 270 degrees
					local alt = d - 2 * math.pi
					local sweep = if math.abs(math.abs(d) - 1.5 * math.pi) <= math.abs(math.abs(alt) - 1.5 * math.pi) then d else alt
					local r0 = math.sqrt((px - cx) ^ 2 + (pz - cz) ^ 2)
					local r1 = math.sqrt((ax - cx) ^ 2 + (az :: number - cz) ^ 2)
					local pts = {}
					for q = 0, 14 do
						local u = q / 14
						local a = a0 + sweep * u
						local rr = r0 + (r1 - r0) * u
						table.insert(pts, cx + math.cos(a) * rr)
						table.insert(pts, cz + math.sin(a) * rr)
					end
					pts[1], pts[2], pts[#pts - 1], pts[#pts] = px, pz, ax, az :: number -- exact junctions
					ramp(pts)
				end
			end
			if kind == "diamond" then
				for _, s in { -1, 1 } do
					for _, t in { -1, 1 } do
						outer(s, t, 7, 4)
					end
				end
			elseif kind == "spui" then -- all four ramps meet the crossing road at one signalised point
				for _, s in { -1, 1 } do
					for _, t in { -1, 1 } do
						outer(s, t, 7, 0)
					end
				end
			elseif kind == "parclo" then -- loops on one side of the crossing road, outer ramps on the other
				local side = if Hash.float(math.round(x), math.round(z), Config.SEED + 701) < 0.5 then 1 else -1
				for _, s in { -1, 1 } do
					loop(s, side)
					outer(s, -side, 7, 4)
				end
			else -- clover (and freeway-to-freeway systems): four loops plus four outer ramps
				for _, s in { -1, 1 } do
					for _, t in { -1, 1 } do
						loop(s, t)
						outer(s, t, 10, 7)
					end
				end
			end
		end
	end
end

-- Barrier island centre line (matches Terrain's barrier band).
local function beachSpine(out: { Major })
	local B = Config.BARRIER
	local pts = {}
	for z = B.v0 * W, B.v1 * W, STEP do
		local v = z / W
		local x = Terrain.barrierX(v) * W
		local s = Terrain.sample(x, z)
		if s.shape == "barrier" or s.water then -- inlets are bridged
			table.insert(pts, x)
			table.insert(pts, z)
		end
	end
	-- trim water off both ends
	while #pts > 2 and Terrain.sample(pts[1], pts[2]).water do
		table.remove(pts, 1)
		table.remove(pts, 1)
	end
	while #pts > 2 and Terrain.sample(pts[#pts - 1], pts[#pts]).water do
		table.remove(pts)
		table.remove(pts)
	end
	table.insert(out, { kind = "arterial", width = R.ARTERIAL_W, pts = pts, bridge = bridges(pts) })
end

function Roads.majors(): { Major }
	local out: { Major } = {}
	for _, f in R.FREEWAYS do
		local pts = Roads.route(f, "freeway")
		table.insert(out, { kind = "freeway", width = R.FREEWAY_W, pts = pts, bridge = bridges(pts) })
	end
	for _, s in R.STATE do
		local pts = Roads.route(s, "state")
		table.insert(out, { kind = "state", width = R.STATE_W, pts = pts, bridge = bridges(pts) })
	end
	local SP = R.ARTERIAL_SPACING
	for k = 1, math.floor(W / SP) do
		local c = k * SP
		local gap = if k % R.CAUSEWAY_EVERY == 0 then R.CAUSEWAY_GAP else R.BRIDGE_GAP
		gridLine(c, true, R.BRIDGE_GAP, "arterial", R.ARTERIAL_W, nil, out)
		gridLine(c, false, gap, "arterial", R.ARTERIAL_W, nil, out)
		-- downtown/midtown boulevards halfway between arterials
		local function core(x: number, z: number): boolean
			local id = Districts.at(x, z)
			return id == "downtown" or id == "midtown"
		end
		gridLine(c - SP / 2, true, R.BRIDGE_GAP, "boulevard", R.BOULEVARD_W, core, out)
		gridLine(c - SP / 2, false, R.BRIDGE_GAP, "boulevard", R.BOULEVARD_W, core, out)
	end
	beachSpine(out)
	-- Loose major-road ends join the nearest major ahead over land (short water gaps bridged),
	-- so arterials and boulevards run into the network instead of stopping at the edge of town.
	local shared = Streets.newShared()
	local asRoads = {}
	for _, m in out do
		if m.kind ~= "freeway" then -- nothing joins a freeway at grade
			Streets.addExternal(shared, m.pts)
		end
		table.insert(asRoads, { kind = m.kind, pts = m.pts })
	end
	local function passable(ax: number, az: number, bx: number, bz: number): boolean
		local n = math.ceil(math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2) / STEP)
		local wetRun = 0
		for k = 1, n do
			if Terrain.sample(ax + (bx - ax) * k / n, az + (bz - az) * k / n).water then
				wetRun += STEP
				if wetRun > R.BRIDGE_GAP then
					return false
				end
			else
				wetRun = 0
			end
		end
		return true
	end
	local links = Streets.stitch(shared, asRoads, R.MAJOR_STITCH, passable)
	for _, l in links do
		Streets.addExternal(shared, l.pts)
		table.insert(asRoads, l)
	end
	-- ends that found nothing ahead (edge of a small town, a freeway near the coast) take the nearest major in any direction
	for _, l in Streets.stitch(shared, asRoads, R.MAJOR_STITCH, passable, true) do
		table.insert(links, l)
	end
	for _, link in links do
		local a = link.pts
		local from = out[1] -- the major whose end this link continues
		for _, m in out do
			local p = m.pts
			if (p[1] == a[1] and p[2] == a[2]) or (p[#p - 1] == a[1] and p[#p] == a[2]) then
				from = m
				break
			end
		end
		local pts = { a[1], a[2] }
		local n = math.max(1, math.floor(math.sqrt((a[3] - a[1]) ^ 2 + (a[4] - a[2]) ^ 2) / STEP))
		for k = 1, n do
			table.insert(pts, a[1] + (a[3] - a[1]) * k / n)
			table.insert(pts, a[2] + (a[4] - a[2]) * k / n)
		end
		local kind = if from.kind == "freeway" then "state" else from.kind -- freeway ends continue as surface roads
		table.insert(out, { kind = kind, width = if kind == "state" then R.STATE_W else from.width, pts = pts, bridge = bridges(pts) })
	end
	interchanges(out, planarize(out))
	return out
end

return Roads
