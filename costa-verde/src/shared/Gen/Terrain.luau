--!strict
-- Height, surface and biome for any point. v2: rules taken from real Florida coast data —
-- smooth high-energy Atlantic coast, ragged mangrove Gulf coast that fragments into islets,
-- barrier islands with inlets over a shallow bay, keys on one smooth arc, flow-aligned wetlands,
-- sinkhole lakes and field grids inland.
local Config = require("./Config")
local Noise = require("./Noise")
local Hash = require("./Hash")

local Terrain = {}

export type Sample = {
	h: number, -- ground height, studs
	ltype: string, -- dominant learned terrain type: "farm" | "scrub" | "coast" | "wetland"
	water: number?, -- water surface if submerged (sea = 0; lakes and marsh sit at their own level)
	land: number, -- signed distance to shore, studs (+ on land)
	shape: string, -- "main" | "barrier" | "key" | "islet" | "lake" | "sea" | "bay"
	biome: string, -- "sea" | "bay" | "beach" | "mangrove" | "wetland" | "hammock" | "farm" | "scrub" | "lake"
	wet: number, -- 0..1 wetlands strength
	rough: number, -- 0..1 coast roughness here (0 = Atlantic, 1 = Gulf mangrove)
	material: string, -- Roblox Enum.Material name
}

local S = Config.SEED
local W = Config.SIZE
local COAST = Config.COAST

local function clamp01(x: number): number
	return math.clamp(x, 0, 1)
end

-- Signed distance (normalized, + inside) to the hand-drawn outline, plus interpolated roughness.
local function outline(u: number, v: number): (number, number)
	local inside = false
	local best, rough = math.huge, 0
	local n = #COAST
	for i = 1, n do
		local a, b = COAST[i], COAST[i % n + 1]
		local ax, ay, bx, by = a[1], a[2], b[1], b[2]
		if (ay > v) ~= (by > v) and u < ax + (v - ay) / (by - ay) * (bx - ax) then
			inside = not inside
		end
		local dx, dy = bx - ax, by - ay
		local t = math.clamp(((u - ax) * dx + (v - ay) * dy) / (dx * dx + dy * dy), 0, 1)
		local d = (u - ax - dx * t) ^ 2 + (v - ay - dy * t) ^ 2
		if d < best then
			best, rough = d, a[3] + (b[3] - a[3]) * t
		end
	end
	local d = math.sqrt(best)
	return if inside then d else -d, rough
end

-- Keys: islands stretched along a quadratic arc, denser toward the far end.
local function keys(u: number, v: number): number
	local K = Config.KEYS_ARC
	local best = -math.huge
	for i = 0, K.count - 1 do
		local t = (i + 0.5 * Hash.float(i, 7, S)) / K.count
		t = t ^ 0.8
		local mt = 1 - t
		local px = mt * mt * K.a[1] + 2 * mt * t * K.c[1] + t * t * K.b[1]
		local py = mt * mt * K.a[2] + 2 * mt * t * K.c[2] + t * t * K.b[2]
		local tx = 2 * mt * (K.c[1] - K.a[1]) + 2 * t * (K.b[1] - K.c[1])
		local ty = 2 * mt * (K.c[2] - K.a[2]) + 2 * t * (K.b[2] - K.c[2])
		local tl = math.sqrt(tx * tx + ty * ty)
		tx, ty = tx / tl, ty / tl
		local along = (u - px) * tx + (v - py) * ty
		local across = -(u - px) * ty + (v - py) * tx
		local len = 0.005 + 0.012 * Hash.float(i, 3, S)
		local wid = 0.003 + 0.003 * Hash.float(i, 5, S) + 0.003 * t
		local d = 1 - math.sqrt((along / len) ^ 2 + (across / wid) ^ 2)
		best = math.max(best, d * wid)
	end
	return best + 0.0012 * Noise.fbm(u * 300, v * 300, S + 21)
end

-- Barrier island chain: a band parallel to the coast (from coast distance), cut by inlets.
local function barrier(u: number, v: number, coastDist: number): number
	local B = Config.BARRIER
	if u < 0.6 or v < B.v0 - 0.02 or v > B.v1 + 0.02 or coastDist > 0 then -- Atlantic side only
		return -1
	end
	local off = -coastDist -- distance out to sea
	local width = B.width * (0.7 + 0.6 * clamp01(Noise.fbm(v * 9, 0.3, S + 30) + 0.5))
	local d = width - math.abs(off - B.offset - 0.004 * Noise.fbm(v * 14, 1.7, S + 31))
	-- taper ends, cut inlets
	d = math.min(d, (v - B.v0) * 0.3, (B.v1 - v) * 0.3)
	for _, iv in B.inlets do
		d = math.min(d, math.abs(v - iv) - 0.0025)
	end
	return d
end

function Terrain.sample(x: number, z: number): Sample
	local u, v = x / W, z / W
	local coast, rough = outline(u, v)
	-- Rough coasts get large, multi-scale wiggles; Atlantic side stays smooth.
	local wiggle = Noise.fbm(u * 18, v * 18, S + 1, 5) * (0.004 + 0.016 * rough)
	local fine = Noise.fbm(u * 140, v * 140, S + 2, 3) * (0.0008 + 0.004 * rough)
	local d = coast + wiggle + fine
	local shape = "main"
	-- Mangrove fragmentation: just offshore of rough coasts, noise pokes up islets.
	if d < 0 and d > -0.03 * rough then
		local f = Noise.fbm(u * 90, v * 90, S + 3, 3) - (-d / (0.03 * rough + 1e-6)) * 0.6
		if f > 0.12 then
			d, shape = (f - 0.12) * 0.01, "islet"
		end
	end
	local seaD = d -- depth is measured from mainland/islets/keys, not the barrier chain (avoids seams)
	local bd = barrier(u, v, coast)
	if bd > d then
		d, shape = bd, "barrier"
	end
	local kd = keys(u, v)
	if kd > d then
		d, shape = kd, "key"
	end
	seaD = math.max(seaD, kd)

	local landStuds = d * W
	local T = Config.TERRAIN
	local VERT = Config.VERT
	local north = clamp01((0.5 - v) * 3)

	-- Continuous land-type weights (no seams): wetland, coast, farm/ridge, scrub.
	local WL = Config.WETLANDS
	local wd = math.sqrt(((u - WL[1]) / WL[3]) ^ 2 + ((v - WL[2]) / WL[4]) ^ 2)
	local wet = if shape == "main" then clamp01((1 - wd * (1 + 0.4 * Noise.fbm(u * 6, v * 6, S + 50))) * 3) else 0
	local coastW = clamp01(1 - math.max(landStuds, 0) / 3000)
	local farmMask = clamp01((north + 0.35 * Noise.fbm(u * 10, v * 10, S + 11) - 0.2) * 3)
	-- Regional elevation changes slowly (10+ km in the real data), so heights use smooth weights;
	-- farmMask only decides where fields go.
	local farmR = clamp01((north + 0.3 * Noise.fbm(u * 2.5, v * 2.5, S + 13) - 0.2) * 4)
	local wW = clamp01((wet - 0.1) * 5) -- wide flat plateau, short rise at the edge (as in real wetland DEMs)
	local wC = (1 - wW) * coastW
	local wF = (1 - wW) * (1 - coastW) * farmR
	local wS = (1 - wW) * (1 - coastW) * (1 - farmR)
	local ltype = "wetland"
	local best = wW
	if wC > best then
		ltype, best = "coast", wC
	end
	if wF > best then
		ltype, best = "farm", wF
	end
	if wS > best then
		ltype = "scrub"
	end

	-- Learned elevation: mean per type + noise at each measured wavelength (tools/terrain_stats.py).
	local meanM = wW * T.mean.wetland + wC * T.mean.coast + wF * T.mean.farm + wS * T.mean.scrub
	local amps = table.create(#T.bands_m)
	for i in T.bands_m do
		amps[i] = wW * T.amps.wetland[i] * T.cal.wetland[i] + wC * T.amps.coast[i] * T.cal.coast[i]
			+ wF * T.amps.farm[i] * T.cal.farm[i] + wS * T.amps.scrub[i] * T.cal.scrub[i]
	end
	local ramp = clamp01(math.max(landStuds, 0) / 700) -- ramps down to the beach
	-- Height (m) at any nearby point with this point's land-type weights (used for lake levels too).
	local function heightAt(px: number, pz: number): number
		local hh = meanM
		for i, lam in T.bands_m do
			local ls = lam * Config.STUD_PER_M
			hh += amps[i] * Noise.value(px / ls, pz / ls, S + 80 + i)
		end
		return 0.6 + (hh - 0.6) * ramp
	end
	local hM = heightAt(x, z)

	-- Sinkholes (dry hollows and lakes) cluster in ridge country; one big lake.
	local water: number? = nil
	local lakeBottom = math.huge
	if shape == "main" and d > 0.004 then
		local L = Config.BIG_LAKE
		local ld = L[3] * (1 + 0.3 * Noise.fbm(u * 25, v * 25, S + 40)) - math.sqrt((u - L[1]) ^ 2 + (v - L[2]) ^ 2)
		local bigLevel = (heightAt(L[1] * W, L[2] * W) - 1.5) * VERT
		if ld > 0 then
			water = bigLevel
			lakeBottom = bigLevel - math.min(ld * W * 0.02, 18)
		elseif ld > -0.012 then -- shore slopes down to the water instead of a cliff
			hM = math.min(hM, bigLevel / VERT + 0.3 + (hM - bigLevel / VERT) * clamp01(-ld / 0.012))
		end
		-- Real karst: sinkholes 100-600 m across, clustered in zones, often merging, irregular rims.
		local cs = 0.02
		local karst = clamp01(Noise.fbm(u * 4, v * 4, S + 47) * 1.5 + 0.2)
		local ci, cj = math.floor(u / cs), math.floor(v / cs)
		for di = -2, 2 do
			for dj = -2, 2 do
				local i, j = ci + di, cj + dj
				if Hash.float(i, j, S + 41) < (0.03 + 0.8 * wF * karst) * (1 - wW) then -- none in the wetlands
					local cx = (i + 0.15 + 0.7 * Hash.float(i, j, S + 42)) * cs
					local cy = (j + 0.15 + 0.7 * Hash.float(i, j, S + 43)) * cs
					local r = 0.004 + 0.012 * Hash.float(i, j, S + 44) ^ 2
					local t = math.sqrt((u - cx) ^ 2 + (v - cy) ^ 2) / r * (1 + 0.18 * Noise.fbm(u * 60, v * 60, S + i * 13 + j))
					if t < 1.5 then
						local level = heightAt(cx * W, cy * W) - 0.8 -- water sits just below the local ground
						local wetLake = Hash.float(i, j, S + 46) < 0.8
						if t < 1 and wetLake then
							local depthM = 2 + 6 * Hash.float(i, j, S + 45)
							water = math.max(water or -math.huge, level * VERT)
							lakeBottom = math.min(lakeBottom, (level - depthM * (1 - t * t) - 0.3) * VERT)
						elseif t < 1 then
							hM = math.min(hM, level - 3 * (1 - t * t)) -- dry sinkhole
						else
							hM = math.min(hM, level + 0.4 + (hM - level) * (t - 1) / 0.5) -- gentle shore
						end
					end
				end
			end
		end
	end

	local h, material, biome
	if landStuds <= 0 then
		-- Sea: shelf shallow and wide on the Gulf side, narrow then a drop-off on the Atlantic side.
		local shelf = 0.012 + 0.04 * rough
		local off = math.max(-seaD, 0)
		local Bc = Config.BARRIER
		local bayness = if u > 0.6 then math.clamp(math.min(v - Bc.v0, Bc.v1 - v) / 0.04, 0, 1) * math.clamp((Bc.offset - -coast) / 0.012, 0, 1) else 0
		if coast > 0 then
			h, biome, shape, water = -1.5, "marsh", "marsh", 0 -- tidal pools inside the outline
		else
			local sea = if off < shelf then -(2 + 18 * (off / shelf) ^ 1.5) else -math.min(20 + (off - shelf) * W * 0.08, 200)
			local bay = -math.min(3 + off * W * 0.004, 10)
			h = sea + (bay - sea) * bayness
			biome = if bayness > 0.5 then "bay" else "sea"
			shape, water = biome, 0
		end
		material = "Sand"
	elseif water then
		h, biome, shape, material = lakeBottom, "lake", "lake", "Mud"
		landStuds = -1 -- lakes count as water for districts/roads
	else
		h = hM * VERT
		biome, material = "scrub", "LeafyGrass"
		if landStuds < 90 + 140 * (1 - rough) and rough < 0.55 then
			biome, material = "beach", "Sand"
		elseif rough >= 0.55 and landStuds < 600 * rough then
			biome, material = "mangrove", "LeafyGrass"
			h = math.min(h, 1.2 * VERT)
		elseif wet > 0.15 then
			-- Flow runs NE -> SW: stretched noise gives sloughs (sheet water) and teardrop tree islands.
			local along = (u + v) * 0.7071
			local across = (u - v) * 0.7071
			local slough = Noise.fbm(along * 8, across * 90, S + 51, 3)
			local hammock = Noise.fbm(along * 30, across * 75, S + 52, 2)
			if slough > 0.38 and wet > 0.4 then
				biome, material, shape = "marsh", "Mud", "marsh"
				water = h + 0.4 * VERT
				landStuds = -1
			elseif hammock > 0.35 then
				h, biome, material = h + 0.4 * VERT, "hammock", "LeafyGrass"
			else
				biome, material = "wetland", "Grass"
			end
		elseif farmMask > 0.5 and Noise.fbm(u * 9, v * 9, S + 12) > -0.15 then
			-- Fields subdivide the road sections (so every field touches a county road), tracks between.
			local SEC = Config.SECTION
			local si, sj = math.floor(x / SEC), math.floor(z / SEC)
			local cols, rows = 2 + math.floor(Hash.float(si, sj, S + 62) * 3), 1 + math.floor(Hash.float(si, sj, S + 63) * 2)
			local fx, fz = (x - si * SEC) / (SEC / cols), (z - sj * SEC) / (SEC / rows)
			local edge = math.min(fx % 1, 1 - fx % 1) * SEC / cols < 6 or math.min(fz % 1, 1 - fz % 1) * SEC / rows < 6
			biome = "farm"
			if edge then
				material = "Ground"
			else
				local crop = Hash.float(si * 8 + math.floor(fx), sj * 8 + math.floor(fz), S + 60)
				material = if crop < 0.45 then "LeafyGrass" elseif crop < 0.75 then "Grass" else "Ground"
			end
		end
	end

	return { h = h, water = water, ltype = ltype, land = landStuds, shape = shape, biome = biome, wet = wet, rough = rough, material = material }
end

return Terrain
