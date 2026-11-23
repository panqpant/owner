--!strict
-- Builds the Costa Verde terrain as Roblox voxels (4-stud resolution) from the world generator, with
-- detailed material rules: dune grass on beaches, mud in mangroves, sawgrass marsh, white sandy scrub,
-- crop rows on farms, rock on steep ground, limestone on the Keys, seagrass under shallow water, lawns
-- and paving in town. Roads and buildings are placed separately (grey for now).
-- Pure logic (`columns`) runs in Lune too, so tools/export-terrain.luau previews exactly what is built.
-- Studio: require(game.ReplicatedStorage.Shared.TerrainBuilder).build() from the command bar (edit mode, then save).
local Gen = require("./Gen")
local SegIndex = require("./Gen/SegIndex")

local Config, Terrain, Districts, Hash = Gen.Config, Gen.Terrain, Gen.Districts, Gen.Hash

local TerrainBuilder = {}

local RES = 4 -- Roblox voxel size
local SAMPLE = 16 -- generator samples every 16 studs; 4-stud columns interpolate between them
TerrainBuilder.OFFSET = -Config.SIZE / 2 -- world is centred on the origin (Roblox terrain limit)

-- Florida palette (sRGB 0-255) for Terrain.MaterialColors; the Blender preview uses the same values.
TerrainBuilder.PALETTE = {
	Grass = { 112, 132, 66 }, LeafyGrass = { 68, 98, 48 }, Ground = { 128, 104, 74 }, Mud = { 84, 78, 58 },
	Sand = { 228, 216, 182 }, Rock = { 126, 122, 112 }, Limestone = { 208, 200, 172 }, Pavement = { 134, 134, 130 },
	Sandstone = { 196, 170, 126 }, Salt = { 232, 228, 214 }, Concrete = { 170, 168, 160 },
}
TerrainBuilder.WATER = { color = { 38, 150, 160 }, transparency = 0.55, reflectance = 0.6, waveSize = 0.08, waveSpeed = 8 }

-- smooth value noise in [0, 1] at a given scale (studs)
local function vnoise(x: number, z: number, scale: number, seed: number): number
	local gx, gz = x / scale, z / scale
	local ix, iz = math.floor(gx), math.floor(gz)
	local fx, fz = gx - ix, gz - iz
	fx, fz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
	local a, b = Hash.float(ix, iz, seed), Hash.float(ix + 1, iz, seed)
	local c, d = Hash.float(ix, iz + 1, seed), Hash.float(ix + 1, iz + 1, seed)
	return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fz
end

local ROADSIDE = { county = true, state = true, collector = true, arterial = true, freeway = true, access = true, street = true }
local PAVED = { tower = true, midrise = true, warehouse = true }

-- Material for one column. s: generator sample (nearest 16-stud), h/water: interpolated, slope: rise per stud.
local function material(s: any, h: number, water: number?, slope: number, x: number, z: number, built: boolean, style: string?): string
	local big, fine = vnoise(x, z, 110, 11), vnoise(x, z, 22, 12)
	if water and h < water - 0.5 then -- under water
		local depth = water - h
		if s.biome == "lake" or s.wet > 0.3 then
			return "Mud"
		elseif depth < 14 and big > 0.58 then
			return "LeafyGrass" -- seagrass beds, seen through the shallows
		end
		return if depth < 24 or fine > 0.4 then "Sand" else "Mud"
	end
	if slope > 0.9 then
		return "Rock"
	elseif slope > 0.55 then
		return if s.shape == "key" then "Limestone" else "Ground"
	end
	if water and h < water + 1.2 then -- the waterline
		return if s.biome == "mangrove" or s.biome == "wetland" then "Mud" elseif s.shape == "key" and fine < 0.45 then "Limestone" else "Sand"
	end
	if built then
		if style and PAVED[style] then
			return "Pavement" -- plazas, car parks; roads and buildings are parts on top
		end
		return if big > 0.75 then "LeafyGrass" else "Grass" -- lawns, darker under street trees
	end
	local b = s.biome
	if b == "beach" then
		return if fine > 0.72 and big > 0.4 then "LeafyGrass" else "Sand" -- dune grass and sea oats
	elseif b == "mangrove" then
		return if fine < 0.28 then "Mud" else "LeafyGrass"
	elseif b == "hammock" then
		return "LeafyGrass"
	elseif b == "wetland" then -- sawgrass with open mud and darker sloughs
		return if big < 0.3 then "Mud" elseif fine > 0.75 then "LeafyGrass" else "Grass"
	elseif b == "scrub" then -- palmetto and wiregrass with occasional bare white sand
		return if big < 0.22 and fine < 0.45 then "Sand" elseif big > 0.6 then "LeafyGrass" else "Grass"
	elseif b == "farm" and s.material == "Ground" then -- ploughed crop rows, ~12 studs apart
		return if (x // 12) % 2 == 0 then "Ground" else "Sandstone"
	elseif s.shape == "key" and fine < 0.2 then
		return "Limestone"
	end
	return s.material
end

-- Columns for a w x d stud area starting at (x0, z0) in generator coordinates. Returns flat arrays
-- h, water (false = dry), material, plus nx, nz. Heights are bilinear between 16-stud samples plus fine
-- relief off-road (none in town, so streets stay flat). `roads` (SegIndex with kind tags) adds the
-- earthworks and wear that follow roads: ditches / canals, worn verges, dirt tracks.
function TerrainBuilder.columns(x0: number, z0: number, w: number, d: number, roads: any?, buildings: any?)
	local sx0, sz0 = x0 // SAMPLE - 2, z0 // SAMPLE - 2
	local sw, sd = math.ceil(w / SAMPLE) + 5, math.ceil(d / SAMPLE) + 5
	local S, built, style = {}, {}, {}
	for j = 0, sd - 1 do
		for i = 0, sw - 1 do
			local x, z = (sx0 + i) * SAMPLE, (sz0 + j) * SAMPLE
			local s = Terrain.sample(x, z)
			local k = j * sw + i + 1
			S[k] = s
			built[k] = not s.water and s.land > 20 and (s.shape == "barrier" or ((s.shape == "main" or s.shape == "key") and Districts.urban(x, z) > 0))
			if built[k] then
				local dd = Districts.byId[Districts.at(x, z, s)]
				style[k] = dd and dd.style
			end
		end
	end
	-- sample-level earthworks: levees (farm beside wetland, raised 4 studs) and seawalls (town beside water)
	local lift, wall = table.create(sw * sd, 0), {}
	for j = 1, sd - 2 do
		for i = 1, sw - 2 do
			local k = j * sw + i + 1
			local s = S[k]
			for _, o in { -1, 1, -sw, sw } do
				local n = S[k + o]
				if s.biome == "farm" and not s.water and n.biome == "wetland" then
					lift[k] = 4
				end
				if built[k] and n.water then
					wall[k] = n.water
				end
			end
		end
	end
	local function lerp(arr: { number }, fx: number, fz: number): number
		local i, j = math.floor(fx), math.floor(fz)
		local tx, tz = fx - i, fz - j
		local b = j * sw + i + 1
		return (arr[b] * (1 - tx) + arr[b + 1] * tx) * (1 - tz) + (arr[b + sw] * (1 - tx) + arr[b + sw + 1] * tx) * tz
	end
	local H16 = table.create(sw * sd)
	for k, s in S do
		H16[k] = s.h
	end
	local function waterAt(fx: number, fz: number): number?
		local b = math.floor(fz) * sw + math.floor(fx) + 1
		return S[b].water or S[b + 1].water or S[b + sw].water or S[b + sw + 1].water -- levels are flat per water body
	end
	local nx, nz = w // RES, d // RES
	local H, Wt, M, Bi = table.create(nx * nz), table.create(nx * nz), table.create(nx * nz), table.create(nx * nz)
	local hgrid, extra = {}, {}
	for j = -1, nz do -- one-column border for slopes
		for i = -1, nx do
			local x, z = x0 + (i + 0.5) * RES, z0 + (j + 0.5) * RES
			local fx, fz = x / SAMPLE - sx0, z / SAMPLE - sz0
			local k = math.round(fz) * sw + math.round(fx) + 1
			local h = lerp(H16, fx, fz) + lerp(lift, fx, fz)
			local water = waterAt(fx, fz)
			local tag: string? = nil
			if not built[k] and not S[k].water then
				h += (vnoise(x, z, 14, 13) - 0.5) * 0.8 -- small bumps, hummocks, furrows
			end
			-- backyard canals: in about a third of suburban neighbourhoods (1200-stud blocks), ground well
			-- away from streets and houses is dug out as a water channel (South Florida canal suburbs)
			if built[k] and style[k] == "house" and roads and buildings and Hash.int(x // 1200, z // 1200, Config.SEED + 77) % 100 < 35
				and roads.nearest(x, z, 26) > 24 and buildings.clear(x, z, 9) then
				water = h - 1.5
				h -= 7
				tag = "canal"
			elseif wall[k] and h > wall[k] - 1 then
				h, tag = wall[k] + 2.5, "seawall" -- vertical concrete edge, not a beach
			elseif roads and not built[k] and not S[k].water then
				local e, kind = roads.nearest(x, z, 16)
				if kind == "drive" and e < 0 then
					tag = "track" -- driveways and farm lanes are dirt, part of the terrain
				elseif kind and ROADSIDE[kind] and e >= 0 then
					if e < 4 and (kind == "county" or kind == "collector" or kind == "access") then
						tag = "verge"
					elseif e < 14 then -- roadside ditch; in the wetlands a water-filled canal
						local prof = math.sin((e - 4) / 10 * math.pi)
						if S[k].biome == "wetland" or S[k].biome == "mangrove" then
							water = h - 0.8
							h -= 5 * prof
							tag = "canal"
						else
							h -= 2.2 * prof
							tag = "ditch"
						end
					end
				end
			end
			local q = (j + 1) * (nx + 2) + (i + 1)
			hgrid[q], extra[q] = h, { water, tag }
		end
	end
	for j = 0, nz - 1 do
		for i = 0, nx - 1 do
			local x, z = x0 + (i + 0.5) * RES, z0 + (j + 0.5) * RES
			local fx, fz = x / SAMPLE - sx0, z / SAMPLE - sz0
			local k = math.round(fz) * sw + math.round(fx) + 1
			local g = function(a: number, b: number): number
				return hgrid[(j + 1 + b) * (nx + 2) + (i + 1 + a)]
			end
			local h = g(0, 0)
			local slope = math.max(math.abs(g(1, 0) - g(-1, 0)), math.abs(g(0, 1) - g(0, -1))) / (2 * RES)
			local ex = extra[(j + 1) * (nx + 2) + (i + 1)]
			local water, tag = ex[1], ex[2]
			local fine = vnoise(x, z, 22, 12)
			local m
			if tag == "seawall" then
				m = "Concrete"
			elseif tag == "track" then
				m = "Ground"
			elseif tag == "verge" then
				m = if fine < 0.55 then "Ground" else "Grass" -- worn, patchy shoulders
			elseif tag == "canal" then
				m = "Mud"
			elseif tag == "ditch" then
				m = if fine < 0.3 then "Mud" else "Grass"
			elseif lerp(lift, fx, fz) > 2.5 and slope < 0.4 then
				m = "Grass" -- mowed levee top
			elseif water and h >= water - 0.5 and h < water + 0.6 and S[k].biome ~= "mangrove" and S[k].biome ~= "wetland" and not built[k] then
				m = "Sandstone" -- wet sand at the waterline
			else
				m = material(S[k], h, water, slope, x, z, built[k], style[k])
			end
			table.insert(H, h)
			table.insert(Wt, water or false)
			table.insert(M, m)
			table.insert(Bi, if built[k] then "town" elseif tag then "road" else S[k].biome) -- for Vegetation
		end
	end
	return { nx = nx, nz = nz, h = H, water = Wt, material = M, biome = Bi }
end

-- Building footprints as circles (for canal and plant clearance).
function TerrainBuilder.buildingIndex(buildings: { any }): any
	local idx = SegIndex.new()
	for _, b in buildings do
		idx.add(b.x, b.z, b.x, b.z, math.max(b.w, b.d) / 2)
	end
	return idx
end

-- Road index for `columns`, from the generator's road list ({ ax, az, bx, bz, width, kind }).
function TerrainBuilder.roadIndex(roads: { any }): any
	local idx = SegIndex.new()
	for _, r in roads do
		if not r.bridge then
			idx.add(r.ax, r.az, r.bx, r.bz, (r.width or 20) / 2, r.kind)
		end
	end
	return idx
end

-- Self-check (Lune): materials are all in the palette, heights finite.
function TerrainBuilder.selfCheck()
	local c = TerrainBuilder.columns(Config.SIZE * 0.5, Config.SIZE * 0.5, 256, 256)
	for k = 1, #c.h do
		assert(c.h[k] == c.h[k], "NaN height")
		assert(TerrainBuilder.PALETTE[c.material[k]], "material not in palette: " .. tostring(c.material[k]))
	end
	return true
end

-- Roblox: write the whole map (or a sub-area) into workspace.Terrain in 256-stud chunks.
-- `roads`: the generator's road list; if omitted the road network is generated here (one-off, slow).
function TerrainBuilder.build(area: { x0: number, z0: number, w: number, d: number }?, world: any?)
	local a = area or { x0 = 0, z0 = 0, w = Config.SIZE, d = Config.SIZE }
	local wd = world
	if not wd then
		local city = Gen.City.generate()
		Gen.Rural.generate(city.roads, city.buildings, city.shared)
		wd = city
	end
	local ridx, bidx = TerrainBuilder.roadIndex(wd.roads), TerrainBuilder.buildingIndex(wd.buildings)
	local terrain = (workspace :: any).Terrain
	for name, c in TerrainBuilder.PALETTE do
		terrain:SetMaterialColor((Enum.Material :: any)[name], Color3.fromRGB(c[1], c[2], c[3]))
	end
	local wtr = TerrainBuilder.WATER
	terrain.WaterColor = Color3.fromRGB(wtr.color[1], wtr.color[2], wtr.color[3])
	terrain.WaterTransparency, terrain.WaterReflectance = wtr.transparency, wtr.reflectance
	terrain.WaterWaveSize, terrain.WaterWaveSpeed = wtr.waveSize, wtr.waveSpeed
	terrain.Decoration = true -- animated grass on Grass
	local CH, BOTTOM = 256, -80
	local done, total = 0, math.ceil(a.w / CH) * math.ceil(a.d / CH)
	local t0 = os.clock()
	for cz = a.z0, a.z0 + a.d - 1, CH do
		for cx = a.x0, a.x0 + a.w - 1, CH do
			local c = TerrainBuilder.columns(cx, cz, CH, CH, ridx, bidx)
			local top = BOTTOM
			for k = 1, #c.h do
				top = math.max(top, c.h[k], c.water[k] or -math.huge)
			end
			local ny = math.ceil((top + 8 - BOTTOM) / RES)
			local mats, occ = table.create(c.nx), table.create(c.nx)
			for i = 1, c.nx do
				mats[i], occ[i] = table.create(ny), table.create(ny)
				for y = 1, ny do
					mats[i][y], occ[i][y] = table.create(c.nz, Enum.Material.Air), table.create(c.nz, 0)
				end
			end
			for j = 1, c.nz do
				for i = 1, c.nx do
					local k = (j - 1) * c.nx + i
					local h, water = c.h[k], c.water[k]
					local mat = (Enum.Material :: any)[c.material[k]]
					for y = 1, ny do
						local y0 = BOTTOM + (y - 1) * RES
						local fill = math.clamp((h - y0) / RES, 0, 1)
						if fill > 0 then
							mats[i][y][j], occ[i][y][j] = mat, fill
						elseif water and y0 < water then
							mats[i][y][j], occ[i][y][j] = Enum.Material.Water, math.clamp((water - y0) / RES, 0, 1)
						end
					end
				end
			end
			local o = TerrainBuilder.OFFSET
			local region = Region3.new(Vector3.new(cx + o, BOTTOM, cz + o), Vector3.new(cx + o + c.nx * RES, BOTTOM + ny * RES, cz + o + c.nz * RES))
			terrain:WriteVoxels(region, RES, mats, occ)
			done += 1
			if done % 50 == 0 then
				print(string.format("terrain %d/%d chunks (%.0fs)", done, total, os.clock() - t0))
				task.wait()
			end
		end
	end
	print(string.format("terrain done: %d chunks in %.0fs", total, os.clock() - t0))
end

return TerrainBuilder
