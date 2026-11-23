--!strict
-- Greybox of the generated world in Roblox: roads (bridges raised, freeways on viaducts with pillars,
-- ramps climbing between), rail and the elevated metro, and every building and landmark at its real
-- footprint shape and height, with pitched roofs on houses. `pieces` is pure (runs in Lune, so the
-- Blender preview draws exactly the same pieces); `build` turns them into Parts in Roblox.
-- Studio (after TerrainBuilder and Vegetation): require(game.ReplicatedStorage.Shared.WorldBuilder).build()
local Gen = require("./Gen")
local TerrainBuilder = require("./TerrainBuilder")

local Terrain = Gen.Terrain

local WorldBuilder = {}

-- A piece: shape "box" | "wedge" (Roblox WedgePart: full height at +Z, slope down to -Z), centre p,
-- axes r (X), u (Y), b (Z) in Roblox space (Y up, generator x/z), size s, colour c (sRGB), group (chunk key).
export type Piece = { shape: string, p: { number }, r: { number }, u: { number }, b: { number }, s: { number }, c: { number }, g: string, t: number? }

local GREY = {
	street = { 70, 70, 74 }, collector = { 66, 66, 70 }, arterial = { 78, 78, 82 }, boulevard = { 82, 82, 86 }, state = { 76, 76, 80 },
	county = { 88, 86, 82 }, access = { 80, 80, 84 }, freeway = { 120, 120, 118 }, ramp = { 118, 118, 116 }, runway = { 60, 60, 62 },
	pillar = { 150, 150, 146 }, rail = { 60, 52, 46 }, metro = { 160, 160, 156 }, wall = { 200, 200, 196 }, roof = { 150, 150, 150 },
}
local SURFACE = { lot = { 96, 96, 98 }, field = { 92, 140, 70 }, stands = { 180, 180, 178 }, runway = { 56, 56, 58 }, deck = { 140, 120, 96 },
	tank = { 225, 225, 225 }, water = { 60, 150, 190 }, panel = { 50, 60, 90 }, wall = { 120, 120, 120 }, pit = { 170, 150, 115 } }
local FLATISH = { lot = true, field = true, runway = true, deck = true, panel = true, water = true }
local ELEV = 22 -- freeway viaduct height (studs above ground)
local METRO_ELEV = 30

local function sub(a: { number }, b: { number }): { number }
	return { a[1] - b[1], a[2] - b[2], a[3] - b[3] }
end
local function add(a: { number }, b: { number }): { number }
	return { a[1] + b[1], a[2] + b[2], a[3] + b[3] }
end
local function mul(a: { number }, k: number): { number }
	return { a[1] * k, a[2] * k, a[3] * k }
end
local function dot(a: { number }, b: { number }): number
	return a[1] * b[1] + a[2] * b[2] + a[3] * b[3]
end
local function cross(a: { number }, b: { number }): { number }
	return { a[2] * b[3] - a[3] * b[2], a[3] * b[1] - a[1] * b[3], a[1] * b[2] - a[2] * b[1] }
end
local function unit(a: { number }): { number }
	local l = math.sqrt(dot(a, a))
	return if l > 1e-9 then mul(a, 1 / l) else { 0, 0, 0 }
end

local function chunkKey(x: number, z: number): string
	return (x // 512) .. "_" .. (z // 512)
end

-- Ground (or water) height the generator says is at (x, z), and the water level there.
local function ground(x: number, z: number): (number, number?)
	local s = Terrain.sample(x, z)
	return s.h, s.water
end

-- Box between two points on the ground plane (a road / rail slab), top at ya / yb (sloped if they differ).
local function slab(out: { Piece }, ax: number, az: number, ya: number, bx: number, bz: number, yb: number, width: number, thick: number, c: { number }, g: string, ext: number)
	local d = { bx - ax, yb - ya, bz - az }
	local len = math.sqrt(dot(d, d))
	if len < 0.5 then
		return
	end
	local bvec = mul(d, 1 / len) -- along the road (Z axis of the part)
	local r = unit(cross({ 0, 1, 0 }, bvec))
	local u = cross(bvec, r)
	local mid = { (ax + bx) / 2, (ya + yb) / 2, (az + bz) / 2 }
	table.insert(out, { shape = "box", p = sub(mid, mul(u, thick / 2)), r = r, u = u, b = bvec, s = { width, thick, len + ext * 2 }, c = c, g = g })
end

-- Two wedges filling triangle a, b, c (Roblox technique), extruded `thick` along the triangle's normal.
local function triangle(out: { Piece }, a: { number }, b: { number }, c: { number }, thick: number, col: { number }, g: string)
	local ab, ac, bc = sub(b, a), sub(c, a), sub(c, b)
	local abd, acd, bcd = dot(ab, ab), dot(ac, ac), dot(bc, bc)
	if abd > acd and abd > bcd then
		c, a = a, c
	elseif acd > bcd and acd > abd then
		a, b = b, a
	end
	ab, ac, bc = sub(b, a), sub(c, a), sub(c, b)
	local right = unit(cross(ac, ab))
	local up = unit(cross(bc, right))
	local back = unit(bc)
	local height = math.abs(dot(ab, up))
	if height < 0.05 then
		return
	end
	table.insert(out, { shape = "wedge", p = mul(add(a, b), 0.5), r = right, u = up, b = back, s = { thick, height, math.abs(dot(ab, back)) }, c = col, g = g })
	table.insert(out, { shape = "wedge", p = mul(add(a, c), 0.5), r = mul(right, -1), u = up, b = mul(back, -1), s = { thick, height, math.abs(dot(ac, back)) }, c = col, g = g })
end

-- Ear-clipping triangulation of a simple polygon (flat x, z list), returns index triples.
local function earclip(xs: { number }, zs: { number }): { { number } }
	local n = #xs
	local idx = {}
	local area = 0
	for i = 1, n do
		local j = i % n + 1
		area += xs[i] * zs[j] - xs[j] * zs[i]
		idx[i] = i
	end
	local sign = if area > 0 then 1 else -1
	local tris = {}
	local guard = 0
	while #idx > 3 and guard < 500 do
		guard += 1
		local clipped = false
		for k = 1, #idx do
			local i0, i1, i2 = idx[(k - 2) % #idx + 1], idx[k], idx[k % #idx + 1]
			local cr = (xs[i1] - xs[i0]) * (zs[i2] - zs[i0]) - (zs[i1] - zs[i0]) * (xs[i2] - xs[i0])
			if cr * sign > 1e-9 then
				local inside = false
				for _, q in idx do
					if q ~= i0 and q ~= i1 and q ~= i2 then
						local function s(ax: number, az: number, bx: number, bz: number): number
							return (bx - ax) * (zs[q] - az) - (bz - az) * (xs[q] - ax)
						end
						local d1, d2, d3 = s(xs[i0], zs[i0], xs[i1], zs[i1]) * sign, s(xs[i1], zs[i1], xs[i2], zs[i2]) * sign, s(xs[i2], zs[i2], xs[i0], zs[i0]) * sign
						if d1 >= 0 and d2 >= 0 and d3 >= 0 then
							inside = true
							break
						end
					end
				end
				if not inside then
					table.insert(tris, { i0, i1, i2 })
					table.remove(idx, k)
					clipped = true
					break
				end
			end
		end
		if not clipped then
			break
		end
	end
	if #idx == 3 then
		table.insert(tris, { idx[1], idx[2], idx[3] })
	end
	return tris
end

-- One footprint part (world-space polygon) from y0 to y0 + h, plus its roof.
local function solid(out: { Piece }, xs: { number }, zs: { number }, y0: number, h: number, roof: string, col: { number }, g: string)
	local n = #xs
	local isRect = n == 4
	if isRect then
		local e1 = { xs[2] - xs[1], 0, zs[2] - zs[1] }
		local e2 = { xs[3] - xs[2], 0, zs[3] - zs[2] }
		isRect = math.abs(dot(unit(e1), unit(e2))) < 1e-3
		if isRect then
			local l1, l2 = math.sqrt(dot(e1, e1)), math.sqrt(dot(e2, e2))
			local r = unit(e1)
			local b = cross(r, { 0, 1, 0 })
			local cx, cz = (xs[1] + xs[3]) / 2, (zs[1] + zs[3]) / 2
			table.insert(out, { shape = "box", p = { cx, y0 + h / 2, cz }, r = r, u = { 0, 1, 0 }, b = b, s = { l1, h, l2 }, c = col, g = g })
			if roof == "hip" or roof == "gable" or roof == "gambrel" then -- ridge along the long side
				local ridge, across, L, W = r, b, l1, l2
				if l2 > l1 then
					ridge, across, L, W = b, r, l2, l1
				end
				local rh = math.min(W * 0.32, 14)
				for _, sgn in { 1, -1 } do
					local n2 = mul(across, sgn)
					local back = mul(n2, -1) -- full-height face at the ridge
					local right = cross({ 0, 1, 0 }, back)
					table.insert(out, { shape = "wedge", p = add({ cx, y0 + h + rh / 2, cz }, mul(n2, W / 4)), r = right, u = { 0, 1, 0 }, b = back, s = { L, rh, W / 2 }, c = GREY.roof, g = g })
				end
				_ = ridge
			end
			return
		end
	end
	local ym = y0 + h / 2
	for _, t in earclip(xs, zs) do
		triangle(out, { xs[t[1]], ym, zs[t[1]] }, { xs[t[2]], ym, zs[t[2]] }, { xs[t[3]], ym, zs[t[3]] }, h, col, g)
	end
end

-- Height of each road vertex above the ground: viaducts for freeways (sloping down over 300 studs to
-- ends that meet surface roads), ramps interpolated between their ends, bridges over water.
local function roadHeights(roads: { any }): { { number } }
	local function key(x: number, z: number): string
		return math.round(x * 2) .. "," .. math.round(z * 2)
	end
	local kinds: { [string]: { [string]: boolean } } = {}
	for _, r in roads do
		for _, k in { key(r.ax, r.az), key(r.bx, r.bz) } do
			kinds[k] = kinds[k] or {}
			kinds[k][r.kind] = true
		end
	end
	local function surfaceAt(k: string): boolean
		for kind in kinds[k] do
			if kind ~= "freeway" and kind ~= "ramp" then
				return true
			end
		end
		return false
	end
	local elev = table.create(#roads)
	local i = 1
	while i <= #roads do -- chains: consecutive segments of one kind joined end to start
		local j = i
		while j < #roads and roads[j + 1].kind == roads[i].kind and key(roads[j].bx, roads[j].bz) == key(roads[j + 1].ax, roads[j + 1].az) do
			j += 1
		end
		local kind = roads[i].kind
		local cum = { 0 }
		for q = i, j do
			local r = roads[q]
			table.insert(cum, cum[#cum] + math.sqrt((r.bx - r.ax) ^ 2 + (r.bz - r.az) ^ 2))
		end
		local total = cum[#cum]
		local k0, k1 = key(roads[i].ax, roads[i].az), key(roads[j].bx, roads[j].bz)
		local function at(dist: number): number
			if kind == "freeway" then
				local e = ELEV
				if surfaceAt(k0) then
					e = math.min(e, ELEV * dist / 300)
				end
				if surfaceAt(k1) then
					e = math.min(e, ELEV * (total - dist) / 300)
				end
				return e
			elseif kind == "ramp" then
				local e0 = if kinds[k0].freeway then ELEV else 0
				local e1 = if kinds[k1].freeway then ELEV else 0
				return e0 + (e1 - e0) * dist / math.max(total, 1)
			end
			return 0
		end
		for q = i, j do
			elev[q] = { at(cum[q - i + 1]), at(cum[q - i + 2]) }
		end
		i = j + 1
	end
	return elev
end

-- All pieces for the world (or those whose position falls in `area`).
function WorldBuilder.pieces(world: any, area: { x0: number, z0: number, w: number, d: number }?): { Piece }
	local out: { Piece } = {}
	local function inArea(x: number, z: number): boolean
		return not area or (x >= area.x0 and x < area.x0 + area.w and z >= area.z0 and z < area.z0 + area.d)
	end
	-- roads
	local elev = roadHeights(world.roads)
	for q, r in world.roads do
		if r.kind ~= "drive" and inArea((r.ax + r.bx) / 2, (r.az + r.bz) / 2) then -- drives are dirt terrain
			local ga, wa = ground(r.ax, r.az)
			local gb, wb = ground(r.bx, r.bz)
			local ya, yb = ga + elev[q][1], gb + elev[q][2]
			if wa then -- endpoint over water: bridge deck
				ya = math.max(ya, wa + 12)
			end
			if wb then
				yb = math.max(yb, wb + 12)
			end
			ya, yb = ya + 0.5, yb + 0.5
			local col = GREY[r.kind] or GREY.street
			local g = chunkKey(r.ax, r.az)
			slab(out, r.ax, r.az, ya, r.bx, r.bz, yb, r.width, if ya - ga > 3 or yb - gb > 3 then 3 else 1.2, col, g, math.min(r.width * 0.12, 4))
			local mx, mz = (r.ax + r.bx) / 2, (r.az + r.bz) / 2
			local gm, wm = ground(mx, mz)
			local base = math.max(gm, wm or gm)
			local top = (ya + yb) / 2 - 3
			if top - base > 6 then -- pillars under viaducts and bridges
				local len = math.sqrt((r.bx - r.ax) ^ 2 + (r.bz - r.az) ^ 2)
				local px, pz = -(r.bz - r.az) / len, (r.bx - r.ax) / len
				for _, off in (if r.width > 40 then { -r.width / 3, r.width / 3 } else { 0 }) :: { number } do
					table.insert(out, { shape = "box", p = { mx + px * off, (top + base - 4) / 2, mz + pz * off }, r = { 1, 0, 0 }, u = { 0, 1, 0 }, b = { 0, 0, 1 },
						s = { 5, top - base + 4, 5 }, c = GREY.pillar, g = g })
				end
			end
		end
	end
	-- rail and metro
	for _, t in world.tracks or {} do
		if inArea((t.ax + t.bx) / 2, (t.az + t.bz) / 2) then
			local ga, wa = ground(t.ax, t.az)
			local gb, wb = ground(t.bx, t.bz)
			local e = if t.elevated or t.kind == "metro" then METRO_ELEV else 0
			local ya, yb = math.max(ga + e, if wa then wa + 12 else -math.huge) + 0.6, math.max(gb + e, if wb then wb + 12 else -math.huge) + 0.6
			local g = chunkKey(t.ax, t.az)
			slab(out, t.ax, t.az, ya, t.bx, t.bz, yb, if t.kind == "metro" then 12 else 9, if e > 0 then 3 else 1, if t.kind == "metro" then GREY.metro else GREY.rail, g, 2)
			if e > 0 then
				local mx, mz = (t.ax + t.bx) / 2, (t.az + t.bz) / 2
				local gm = ground(mx, mz)
				table.insert(out, { shape = "box", p = { mx, ((ya + yb) / 2 - 3 + gm - 4) / 2, mz }, r = { 1, 0, 0 }, u = { 0, 1, 0 }, b = { 0, 0, 1 },
					s = { 4, (ya + yb) / 2 - 3 - gm + 4, 4 }, c = GREY.pillar, g = g })
			end
		end
	end
	-- water variety (Roblox has one global water style): murky tint on swamp and lake water, white foam
	-- where the sea meets a beach. Scanned every 16 studs, merged into strips along x.
	local x0, z0 = if area then area.x0 else 0, if area then area.z0 else 0
	local x1, z1 = if area then area.x0 + area.w else Gen.Config.SIZE, if area then area.z0 + area.d else Gen.Config.SIZE
	local STEP = 16
	for z = z0 + STEP / 2, z1, STEP do
		local runKind, runStart, runLevel = nil :: string?, 0, 0
		local function flush(xEnd: number)
			if runKind then
				local col = if runKind == "murk" then { 92, 88, 52 } else { 245, 245, 240 }
				local tr = if runKind == "murk" then 0.35 else 0.55
				table.insert(out, { shape = "box", p = { (runStart + xEnd) / 2, runLevel + 0.08, z }, r = { 1, 0, 0 }, u = { 0, 1, 0 }, b = { 0, 0, 1 },
					s = { xEnd - runStart, 0.15, STEP }, c = col, g = chunkKey(runStart, z), t = tr })
			end
			runKind = nil
		end
		for x = x0 + STEP / 2, x1, STEP do
			local s = Terrain.sample(x, z)
			local kind: string? = nil
			if s.water and s.h < s.water - 0.3 then
				if s.biome == "lake" or s.wet > 0.3 or s.biome == "mangrove" or s.biome == "wetland" then
					kind = "murk"
				elseif s.water == 0 and s.h > -3 then -- the sea in the surf zone next to a beach
					local n = Terrain.sample(x + STEP, z)
					local n2 = Terrain.sample(x - STEP, z)
					if n.biome == "beach" or n2.biome == "beach" then
						kind = "foam"
					end
				end
			end
			if kind ~= runKind or (kind and math.abs((s.water or 0) - runLevel) > 0.01) then
				flush(x - STEP / 2)
				if kind then
					runKind, runStart, runLevel = kind, x - STEP / 2, s.water :: number
				end
			end
		end
		flush(x1)
	end
	-- buildings: each part from 4 studs below ground (no gaps on slopes) up to its height
	for bi, b in world.buildings do
		if inArea(b.x, b.z) then
			local c, sn = math.cos(math.rad(b.rot)), math.sin(math.rad(b.rot))
			local shade = 200 - (bi % 5) * 8 -- neighbouring buildings read apart
			local col = { shade, shade, shade - 4 }
			local g = "b" .. bi
			for _, p in b.parts or {} do
				local xs, zs = {}, {}
				for i = 1, #p.pts - 1, 2 do
					table.insert(xs, b.x + c * p.pts[i] - sn * p.pts[i + 1])
					table.insert(zs, b.z + sn * p.pts[i] + c * p.pts[i + 1])
				end
				local y0 = b.y + p.base - (if p.base == 0 then 4 else 0)
				solid(out, xs, zs, y0, p.h + (if p.base == 0 then 4 else 0), p.roof, if p.roof == "canopy" then GREY.wall else col, g)
			end
		end
	end
	-- landmarks: site-plan surfaces as thin slabs, buildings as solids
	for li, l in world.landmarks or {} do
		if l.parts and inArea(l.x, l.z) then
			local g = "l" .. li
			for _, p in l.parts do
				local xs, zs = {}, {}
				for i = 1, #p.pts - 1, 2 do
					table.insert(xs, l.x + p.pts[i])
					table.insert(zs, l.z + p.pts[i + 1])
				end
				local surf = SURFACE[p.roof]
				if FLATISH[p.roof] then
					solid(out, xs, zs, l.y - 1, 1.6 + (if p.roof == "lot" then 0 else 0.2), "flat", surf, g)
				else
					solid(out, xs, zs, l.y + p.base - 4, p.h + 4, "flat", surf or { 190, 190, 188 }, g)
				end
			end
		end
	end
	return out
end

-- Roblox: Parts in chunk folders; each building / landmark is an atomic Model so streaming loads it whole.
function WorldBuilder.build(world: any?)
	local w = world
	if not w then
		local city = Gen.City.generate()
		local settlements = Gen.Rural.generate(city.roads, city.buildings, city.shared)
		Gen.Uses.assign(city.buildings, Gen.Config.SEED + 800)
		Gen.Shapes.assign(city.buildings, Gen.Config.SEED + 802)
		Gen.Shapes.landmarks(city.landmarks, Gen.Config.SEED + 803)
		local tracks = Gen.Transit.generate(settlements, city.roads)
		w = { roads = city.roads, buildings = city.buildings, landmarks = city.landmarks, tracks = tracks }
	end
	local ws = workspace :: any
	ws.StreamingEnabled = true
	ws.StreamingTargetRadius = 2048
	ws.StreamingMinRadius = 512
	local root = Instance.new("Folder")
	root.Name = "World"
	local o, t0 = TerrainBuilder.OFFSET, os.clock()
	local groups: { [string]: Instance } = {}
	local roadsFolder = Instance.new("Folder")
	roadsFolder.Name = "Roads"
	roadsFolder.Parent = root
	local n = 0
	for _, pc in WorldBuilder.pieces(w) do
		local part: BasePart = if pc.shape == "wedge" then Instance.new("WedgePart") else Instance.new("Part")
		part.Anchored = true
		part.Material = Enum.Material.SmoothPlastic
		part.Size = Vector3.new(pc.s[1], pc.s[2], pc.s[3])
		part.CFrame = CFrame.fromMatrix(Vector3.new(pc.p[1] + o, pc.p[2], pc.p[3] + o), Vector3.new(pc.r[1], pc.r[2], pc.r[3]),
			Vector3.new(pc.u[1], pc.u[2], pc.u[3]), Vector3.new(pc.b[1], pc.b[2], pc.b[3]))
		part.Color = Color3.fromRGB(pc.c[1], pc.c[2], pc.c[3])
		part.TopSurface, part.BottomSurface = Enum.SurfaceType.Smooth, Enum.SurfaceType.Smooth
		if pc.t then -- water tint / foam: see-through, nothing collides with it
			part.Transparency, part.CanCollide, part.CanQuery, part.CastShadow = pc.t, false, false, false
		end
		local grp = groups[pc.g]
		if not grp then
			if string.sub(pc.g, 1, 1) == "b" or string.sub(pc.g, 1, 1) == "l" then
				local m = Instance.new("Model")
				m.Name = pc.g;
				(m :: any).ModelStreamingMode = Enum.ModelStreamingMode.Atomic
				m.Parent = root
				grp = m
			else
				local f = Instance.new("Model")
				f.Name = "roads_" .. pc.g
				f.Parent = roadsFolder
				grp = f
			end
			groups[pc.g] = grp
		end
		part.Parent = grp
		n += 1
		if n % 5000 == 0 then
			task.wait()
		end
	end
	root.Parent = workspace
	print(string.format("world greybox: %d parts in %.0fs", n, os.clock() - t0))
end

return WorldBuilder
