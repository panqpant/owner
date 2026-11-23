--!strict
-- Countryside: section-line county roads (US-style ~1 mile grid), farmsteads with driveways onto
-- those roads, crossroads hamlets, and Easter egg points of interest placed by biome rules.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Hash = require("./Hash")
local Streets = require("./Streets")
local StreetStyles = require("./StreetStyles")
local Roads = require("./Roads")
local Landmarks = require("./Landmarks")
local SegIndex = require("./SegIndex")

local Rural = {}

export type Poi = { x: number, z: number, y: number, kind: string, name: string }
export type Settlement = { x: number, z: number, name: string, size: number }

local W = Config.SIZE

local function ruralOk(x: number, z: number): boolean
	local s = Terrain.sample(x, z)
	if s.water or s.land < 80 or s.wet > 0.3 then
		return false
	end
	if s.biome ~= "farm" and s.biome ~= "scrub" then
		return false
	end
	return Districts.urban(x, z) <= 0 and not Landmarks.blocked(x, z)
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

-- Union-find over road endpoints; routes a connector from each cut-off piece to the main network.
local function connectIslands(roads: { any }, net: { any })
	local all = table.clone(roads)
	for _, r in net do
		local p = r.pts
		for i = 1, #p - 3, 2 do
			table.insert(all, { ax = p[i], az = p[i + 1], bx = p[i + 2], bz = p[i + 3], kind = "county" })
		end
	end
	local parent: { [string]: string } = {}
	local function key(x: number, z: number): string
		return math.round(x * 2) .. "," .. math.round(z * 2)
	end
	local function find(a: string): string
		while (parent[a] or a) ~= a do
			parent[a] = parent[parent[a]] or parent[a]
			a = parent[a]
		end
		return a
	end
	local pos: { [string]: { number } } = {}
	local len: { [string]: number } = {}
	for _, r in all do
		if r.kind ~= "runway" then
			local a, b = key(r.ax, r.az), key(r.bx, r.bz)
			pos[a], pos[b] = { r.ax, r.az }, { r.bx, r.bz }
			parent[find(a)] = find(b)
		end
	end
	for _, r in all do
		if r.kind ~= "runway" then
			local c = find(key(r.ax, r.az))
			len[c] = (len[c] or 0) + math.sqrt((r.bx - r.ax) ^ 2 + (r.bz - r.az) ^ 2)
		end
	end
	local main, best = nil, 0
	for c, l in len do
		if l > best then
			main, best = c, l
		end
	end
	local mainPts = {}
	local onFreeway: { [string]: boolean } = {}
	for _, r in all do
		if r.kind == "freeway" or r.kind == "ramp" then
			onFreeway[key(r.ax, r.az)], onFreeway[key(r.bx, r.bz)] = true, true
		end
	end
	for k, p in pos do
		if find(k) == main and not onFreeway[k] then -- connectors join surface roads, never a freeway mid-span
			table.insert(mainPts, p)
		end
	end
	for c in len do
		if c ~= main then
			-- nearest few target points; keep the first route that doesn't cross a landmark
			local cands = {}
			for k, p in pos do
				if find(k) == c then
					for q = 1, #mainPts, 7 do -- every 7th main vertex is plenty to find the nearest area
						local m = mainPts[q]
						table.insert(cands, { (m[1] - p[1]) ^ 2 + (m[2] - p[2]) ^ 2, p, m })
					end
				end
			end
			table.sort(cands, function(a, b)
				return a[1] < b[1]
			end)
			local chosen = nil
			for t = 1, math.min(#cands, 60), 6 do -- spread the tries over different targets
				local from, to = cands[t][2], cands[t][3]
				local route = Roads.route({ { from[1] / W, from[2] / W }, { to[1] / W, to[2] / W } }, "connector")
				route[1], route[2], route[#route - 1], route[#route] = from[1], from[2], to[1], to[2] -- exact junctions
				local crosses = false
				for i = 1, #route - 3, 2 do
					crosses = crosses or Landmarks.crosses(route[i], route[i + 1], route[i + 2], route[i + 3])
				end
				chosen = chosen or route -- shortcut: if every try crosses a landmark the first is used; the audit flags it
				if not crosses then
					chosen = route
					break
				end
			end
			if chosen then
				local route = chosen
				for i = 1, #route - 3, 2 do
					local wet = Terrain.sample((route[i] + route[i + 2]) / 2, (route[i + 1] + route[i + 3]) / 2).water ~= nil
					table.insert(roads, { ax = route[i], az = route[i + 1], bx = route[i + 2], bz = route[i + 3], width = Config.COUNTY_W, kind = "county", bridge = wet })
				end
			end
		end
	end
end

-- Rural roads grow with the style trained on real county road networks, joining the city network.
function Rural.generate(roads: { any }, buildings: { any }, shared: Streets.Shared?)
	local rng = Hash.rng(Config.SEED + 500)
	local net = Streets.grow(StreetStyles.rural, ruralOk, W / 2, W / 2, W / 2, 0, Config.SEED + 503, 2500, shared, nil, Landmarks.okLink)
	-- loose county-road ends join the nearest road (state road, city edge, another county road)
	-- two passes like the major roads: ahead first, then any direction for ends that found nothing
	local sh = shared or Streets.newShared()
	for _, anyDir in { false, true } do
		for _, link in Streets.stitch(sh, net, 1800, Landmarks.okLink, anyDir) do
			Streets.addExternal(sh, link.pts)
			table.insert(net, link)
		end
	end
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
			table.insert(roads, { ax = sg.ax, az = sg.az, bx = sg.bx, bz = sg.bz, width = if r.kind == "collector" then Config.ROAD_W else Config.COUNTY_W, kind = "county", bridge = false })
		end
		-- junction degree: endpoints count once, interior vertices twice
		for i = 1, #pts - 1, 2 do
			local k = vkey(pts[i], pts[i + 1])
			uses[k] = (uses[k] or 0) + (if i == 1 or i == #pts - 1 then 1 else 2)
		end
	end

	-- Every road piece joins the main network: pieces cut off (e.g. land ringed by marsh) get a
	-- connector routed over the terrain like a state road (bridging where it must).
	connectIslands(roads, net)

	-- every road so far (city + county), so farm buildings stay off all of them
	local roadIndex = SegIndex.new()
	for _, rd in roads do
		roadIndex.add(rd.ax, rd.az, rd.bx, rd.bz, (rd.width or 20) / 2)
	end
	local function place(b: any)
		if roadIndex.boxClear(b.x, b.z, b.w, b.d, b.rot) then
			table.insert(buildings, b)
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
			local rx, rz = sg.ax, sg.az -- a road vertex, so the driveway is a real junction
			local hx, hz = rx + ox * 90, rz + oz * 90
			if ruralOk(hx, hz) then
				local y = Terrain.sample(hx, hz).h
				local rot = math.deg(math.atan2(dz, dx))
				table.insert(roads, { ax = rx, az = rz, bx = hx, bz = hz, width = 10, kind = "drive", bridge = false })
				place({ x = hx + ox * 18, z = hz + oz * 18, y = y, w = 34, d = 26, h = 16, rot = rot, style = "farmhouse", district = "rural", variant = rng:int(1, 8) })
				place({ x = hx + dx * 60 + ox * 30, z = hz + dz * 60 + oz * 30, y = y, w = 40, d = 56, h = 26, rot = rot, style = "barn", district = "rural", variant = rng:int(1, 8) })
				if rng:next() < 0.6 then
					place({ x = hx - dx * 45 + ox * 40, z = hz - dz * 45 + oz * 40, y = y, w = 14, d = 14, h = 44, rot = 0, style = "silo", district = "rural", variant = 1 })
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
				place({ x = x + 45, z = z + 45, y = y, w = 40, d = 30, h = 14, rot = 0, style = anchor, district = "hamlet", variant = 1 })
				for _ = 1, size do
					local a = rng:range(0, math.pi * 2)
					local dist = rng:range(70, 380)
					local hx, hz = x + math.cos(a) * dist, z + math.sin(a) * dist
					if ruralOk(hx, hz) then
						place({ x = hx, z = hz, y = Terrain.sample(hx, hz).h, w = 22, d = 18, h = 12, rot = math.deg(a), style = if rng:next() < 0.3 then "trailer" else "house", district = "hamlet", variant = rng:int(1, 8) })
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
