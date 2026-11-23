--!strict
-- Trees, plants and shoreline props, placed per biome on the same 4-stud columns the terrain is built
-- from (so every model sits exactly on the ground). Models come from tools/blender/make_assets.py
-- (assets/roblox/*.fbx), imported into ReplicatedStorage.Assets with the same names.
-- Studio (after TerrainBuilder.build): require(game.ReplicatedStorage.Shared.Vegetation).build()
local Gen = require("./Gen")
local TerrainBuilder = require("./TerrainBuilder")

local Config, Hash = Gen.Config, Gen.Hash

local Vegetation = {}

Vegetation.DENSITY = 1 -- global multiplier; lower it if the device budget needs it

-- Material colours of the models (sRGB), same as make_assets.py COLORS.
Vegetation.COLORS = {
	trunk = { 112, 92, 70 }, palm_leaf = { 86, 128, 52 }, oak_leaf = { 52, 84, 40 }, pine_leaf = { 70, 96, 50 },
	mangrove_leaf = { 46, 78, 38 }, palmetto_leaf = { 98, 130, 70 }, sawgrass = { 150, 150, 86 }, seaoats = { 206, 190, 140 },
	root = { 96, 82, 64 }, wood = { 140, 112, 80 }, rock = { 150, 146, 136 }, buoy_red = { 200, 50, 40 }, buoy_white = { 235, 235, 230 },
	coconut = { 110, 90, 40 },
}

-- Plants per biome: { model, count per 10,000 square studs, clearance from buildings (studs) }.
-- Densities follow the real communities: dense hammock canopy, mangrove thickets, sparse pine scrub.
local RULES: { [string]: { { any } } } = {
	hammock = { { "LiveOak", 9, 12 }, { "PalmCabbage", 6, 6 }, { "Palmetto", 4, 3 } },
	mangrove = { { "Mangrove", 28, 8 } },
	wetland = { { "Sawgrass", 8, 2 }, { "PalmCabbage", 0.6, 6 } },
	scrub = { { "Palmetto", 6, 3 }, { "SlashPine", 2.5, 8 }, { "LiveOak", 0.6, 12 } },
	farm = { { "LiveOak", 0.25, 12 }, { "PalmCabbage", 0.3, 6 } },
	beach = { { "SeaOats", 10, 2 }, { "PalmCoconut", 1.5, 6 } },
	town = { { "PalmCoconut", 1.8, 8 }, { "PalmCabbage", 1.0, 8 }, { "LiveOak", 0.6, 14 } },
}
-- tree islands in the marsh (darker patches) and dune grass get their own mix
local ISLAND = { { "LiveOak", 7, 12 }, { "PalmCabbage", 9, 6 }, { "Palmetto", 3, 3 } }
local NO_PLANTS = { Pavement = true, Concrete = true, Ground = true, Rock = true }

-- Items for one columns() result at (x0, z0): { model, x, z, y, rot (deg), scale }.
-- `buildings`: SegIndex of building footprints (circles); `roads`: TerrainBuilder.roadIndex.
function Vegetation.place(c: any, x0: number, z0: number, roads: any?, buildings: any?): { { any } }
	local out = {}
	local nx, nz = c.nx, c.nz
	local cellArea = 16 * Vegetation.DENSITY / 10000
	local function col(i: number, j: number): number
		return j * nx + i + 1
	end
	for j = 0, nz - 1 do
		for i = 0, nx - 1 do
			local k = col(i, j)
			local h, water, mat, biome = c.h[k], c.water[k], c.material[k], c.biome[k]
			local x, z = x0 + (i + 0.5) * 4, z0 + (j + 0.5) * 4
			local gx, gz = math.floor(x / 4), math.floor(z / 4)
			local r1, r2 = Hash.float(gx, gz, Config.SEED + 900), Hash.float(gx, gz, Config.SEED + 901)
			local jx, jz = (r2 - 0.5) * 3.5, (Hash.float(gx, gz, Config.SEED + 902) - 0.5) * 3.5
			local under = water and h < water - 0.3
			-- shoreline props on seawalls: docks reaching into the water, riprap at the toe
			if mat == "Concrete" then
				for _, o in { { 1, 0 }, { -1, 0 }, { 0, 1 }, { 0, -1 } } do
					local a, b = i + o[1] * 2, j + o[2] * 2
					if a >= 0 and b >= 0 and a < nx and b < nz then
						local n = col(a, b)
						local wl = c.water[n]
						if wl and c.h[n] < wl - 1 then
							local rot = math.deg(math.atan2(o[1], o[2]))
							if r1 < 0.03 then -- a dock every ~130 studs of seawall, 22 studs out
								table.insert(out, { "DockSection", x + o[1] * 22, z + o[2] * 22, wl, rot, 1 })
								table.insert(out, { "Piling", x + o[1] * 44 + o[2] * 8, z + o[2] * 44 + o[1] * 8, wl, 0, 1 })
							elseif r1 > 0.86 then
								table.insert(out, { "Riprap", x + o[1] * 6, z + o[2] * 6, wl - 1, rot + 90, 0.8 + r2 * 0.5 })
							end
							break
						end
					end
				end
				continue
			end
			if under then
				local depth = water - h
				if biome == "mangrove" and depth < 3 and r1 < 28 * cellArea then
					table.insert(out, { "Mangrove", x + jx, z + jz, h, r2 * 360, 0.8 + r2 * 0.4 }) -- roots in the shallows
				elseif depth > 10 and depth < 30 and r1 < 0.0006 * Vegetation.DENSITY then
					table.insert(out, { "Buoy", x, z, water, 0, 1 })
				end
				continue
			end
			if NO_PLANTS[mat] or biome == "road" then
				continue
			end
			local rules = RULES[biome]
			if biome == "wetland" and mat == "LeafyGrass" then
				rules = ISLAND
			elseif biome == "beach" and mat == "Sand" then
				rules = { { "PalmCoconut", 0.6, 6 } } -- open sand: the odd palm only; sea oats on the dune grass
			end
			if rules then
				local acc = 0
				for _, rule in rules do
					acc += rule[2] * cellArea
					if r1 < acc then
						local px, pz = x + jx, z + jz
						local clearRoad = not roads or roads.nearest(px, pz, 6) > 3
						local clearBld = not buildings or buildings.clear(px, pz, rule[3])
						if clearRoad and clearBld then
							table.insert(out, { rule[1], px, pz, h, r2 * 360, 0.8 + Hash.float(gx, gz, Config.SEED + 903) * 0.45 })
						end
						break
					end
				end
			end
		end
	end
	return out
end

Vegetation.buildingIndex = TerrainBuilder.buildingIndex

-- Roblox: colour the imported template MeshParts from their material names (the importer keeps them).
local function prepare(template: Instance)
	for _, p in template:GetDescendants() do
		if p:IsA("MeshPart") then
			for name, c in Vegetation.COLORS do
				if string.find(string.lower(p.Name), name, 1, true) or (p.MaterialVariant ~= "" and string.find(string.lower(p.MaterialVariant), name, 1, true)) then
					p.Color = Color3.fromRGB(c[1], c[2], c[3])
				end
			end
			p.Anchored, p.CanCollide, p.CastShadow = true, p.Size.Magnitude > 20, true
		end
	end
end

-- Roblox: place everything, in 256-stud chunk folders under workspace.Vegetation (streams with the map).
function Vegetation.build(area: { x0: number, z0: number, w: number, d: number }?, world: any?)
	local a = area or { x0 = 0, z0 = 0, w = Config.SIZE, d = Config.SIZE }
	local w = world
	if not w then
		local city = Gen.City.generate()
		Gen.Rural.generate(city.roads, city.buildings, city.shared)
		w = city
	end
	local ridx, bidx = TerrainBuilder.roadIndex(w.roads), Vegetation.buildingIndex(w.buildings)
	local assets = (game :: any).ReplicatedStorage:WaitForChild("Assets")
	for _, t in assets:GetChildren() do
		prepare(t)
	end
	local root = Instance.new("Folder")
	root.Name = "Vegetation"
	root.Parent = workspace
	local o, n, t0 = TerrainBuilder.OFFSET, 0, os.clock()
	for cz = a.z0, a.z0 + a.d - 1, 256 do
		for cx = a.x0, a.x0 + a.w - 1, 256 do
			local c = TerrainBuilder.columns(cx, cz, 256, 256, ridx, bidx)
			local items = Vegetation.place(c, cx, cz, ridx, bidx)
			if #items > 0 then
				local chunk = Instance.new("Model")
				chunk.Name = cx .. "_" .. cz
				for _, it in items do
					local t = assets:FindFirstChild(it[1])
					if t then
						local m = t:Clone()
						if m:IsA("Model") then
							m:ScaleTo(it[6])
							m:PivotTo(CFrame.new(it[2] + o, it[4], it[3] + o) * CFrame.Angles(0, math.rad(it[5]), 0))
						else
							(m :: any).CFrame = CFrame.new(it[2] + o, it[4], it[3] + o) * CFrame.Angles(0, math.rad(it[5]), 0)
						end
						m.Parent = chunk
						n += 1
					end
				end
				chunk.Parent = root
			end
		end
		task.wait()
	end
	print(string.format("vegetation: %d models in %.0fs", n, os.clock() - t0))
end

return Vegetation
