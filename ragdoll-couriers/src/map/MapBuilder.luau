--!strict
-- Builds the city designed in Blender (art/map) into workspace.City.
--
-- Run it once in Studio's command bar (edit mode, not Play), then save the place:
--     require(game.ServerStorage.Map.MapBuilder).build()
--
-- Imported models go in ServerStorage.CityAssets, each named like its FBX (House_A, Road_Straight...).
-- Anything not imported yet is drawn as a block of the right size and colour, so the whole
-- layout can be driven around from day one and models drop in as they're imported.

local HttpService = game:GetService("HttpService")
local ServerStorage = game:GetService("ServerStorage")

type Asset = { size: { number }, centre: { number }, paint: boolean }
type Item = { a: string, p: { number }, r: number, c: string?, d: string }

local MapBuilder = {}

local function v3(t: { number }): Vector3
	return Vector3.new(t[1], t[2], t[3])
end

-- Moves a freshly imported model so its bounding box lands where Blender put the asset,
-- whatever pivot the importer gave it.
local function placeModel(model: Model, target: CFrame, centre: Vector3)
	local box = model:GetBoundingBox()
	model:PivotTo((target * CFrame.new(centre)) * box:Inverse() * model:GetPivot())
end

local function recolour(model: Instance, hex: string?)
	if not hex then
		return
	end
	for _, d in model:GetDescendants() do
		if d:IsA("MeshPart") and d.Name == "Paint" then
			local look = d:FindFirstChildOfClass("SurfaceAppearance")
			if look then
				look:Destroy() -- Paint parts are coloured, not textured
			end
			d.Color = Color3.fromHex(hex)
		end
	end
end

local function block(name: string, size: Vector3, cf: CFrame, colour: Color3): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.Size = size
	p.CFrame = cf
	p.Color = colour
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	return p
end

-- Puts each sign's image on an invisible board just in front of the model's sign. Images come from
-- DecalIds (filled in after uploading art/export/textures); signs without an ID yet are skipped.
local function addDecals(layout, ids, counters, item: Item, target: CFrame, folder: Instance)
	local slots = layout.slots[item.a]
	if not slots then
		return
	end
	for _, slot in slots do
		local name = slot.d
		if name == "shop" then
			counters.shop = counters.shop % 7 + 1 -- shops 1-7; 8 is the fish market's
			name = "sign_shop_" .. counters.shop
		elseif name == "ad" then
			counters.ad = counters.ad % #layout.ads + 1
			name = layout.ads[counters.ad]
		end
		local id = ids[name]
		if id and id ~= "" then
			local board = block(
				"Sign_" .. name,
				Vector3.new(slot.s[1], slot.s[2], 0.05),
				target * CFrame.new(v3(slot.c)),
				Color3.new(1, 1, 1)
			)
			board.Transparency = 1
			board.CanCollide = false
			board.CanQuery = false
			board.CanTouch = false
			local decal = Instance.new("Decal")
			decal.Face = Enum.NormalId.Front
			decal.Texture = id
			decal.Parent = board
			board.Parent = folder
		end
	end
end

-- Sets Lighting's sky from DecalIds (sky_<mood>_Ft and so on) once all six faces have IDs.
local function applySky(ids, mood: string)
	local faces = { "Bk", "Dn", "Ft", "Lf", "Rt", "Up" }
	for _, face in faces do
		local id = ids["sky_" .. mood .. "_" .. face]
		if not id or id == "" then
			return false
		end
	end
	local Lighting = game:GetService("Lighting")
	local old = Lighting:FindFirstChildOfClass("Sky")
	if old then
		old:Destroy()
	end
	local sky = Instance.new("Sky")
	for _, face in faces do
		(sky :: any)["Skybox" .. face] = ids["sky_" .. mood .. "_" .. face]
	end
	sky.Parent = Lighting
	return true
end

function MapBuilder.build(offset: Vector3?, mood: string?)
	local layout = HttpService:JSONDecode(require(script.Parent.Layout))
	local ids = {}
	local idModule = script.Parent:FindFirstChild("DecalIds")
	if idModule then
		local ok, loaded = pcall(require, idModule)
		if ok and type(loaded) == "table" then
			ids = loaded
		end
	end
	local counters = { shop = 0, ad = 0 }
	local origin = CFrame.new(offset or Vector3.zero)
	local templates = ServerStorage:FindFirstChild("CityAssets")

	local old = workspace:FindFirstChild("City")
	if old then
		old:Destroy()
	end
	local city = Instance.new("Folder")
	city.Name = "City"

	-- Water everywhere at sea level: the terrain covers it except in the sea and the lake.
	-- Parts max out at 2048 studs, so the sheet is four tiles.
	local groundFolder = Instance.new("Folder")
	groundFolder.Name = "Ground"
	groundFolder.Parent = city
	local half = layout.extent / 2
	for _, q in { { -1, -1 }, { -1, 1 }, { 1, -1 }, { 1, 1 } } do
		local water = block(
			"Water",
			Vector3.new(layout.extent, 1, layout.extent),
			origin * CFrame.new(q[1] * half, layout.water - 0.5, q[2] * half),
			Color3.fromHex("3f9be0")
		)
		water.Material = Enum.Material.Glass
		water.Transparency = 0.2
		water.CanCollide = false -- ride off the quay and the parcel is lost
		water.Parent = groundFolder
	end

	-- Until the terrain is imported, flat district-coloured ground stands in for it.
	local hasTerrain = templates ~= nil and templates:FindFirstChild("Terrain_NW") ~= nil
	if not hasTerrain then
		local layer = 0
		for _, name in { "Outskirts", "Hub", "Suburbs", "OldTown", "Docks", "Downtown", "Mountain" } do
			local r = layout.districts[name].rect
			layer += 1
			local g = block(
				name,
				Vector3.new(r[3] - r[1], 1, r[4] - r[2]),
				origin * CFrame.new((r[1] + r[3]) / 2, -0.6 + layer * 0.002, (r[2] + r[4]) / 2),
				Color3.fromHex(layout.districts[name].colour)
			)
			g.Material = Enum.Material.Grass
			g.Parent = groundFolder
		end
	end

	-- Every placed piece, grouped by district so the map streams and selects sensibly.
	local districts: { [string]: Folder } = {}
	local missing: { [string]: boolean } = {}
	local imported = 0
	for _, item: Item in layout.items do
		local folder = districts[item.d]
		if not folder then
			folder = Instance.new("Folder")
			folder.Name = item.d
			folder.Parent = city
			districts[item.d] = folder
		end
		local asset: Asset = layout.assets[item.a]
		local target = origin * CFrame.new(v3(item.p)) * CFrame.Angles(0, math.rad(item.r), 0)
		local template = templates and templates:FindFirstChild(item.a)
		if template and template:IsA("Model") then
			local model = template:Clone()
			for _, d in model:GetDescendants() do
				if d:IsA("BasePart") then
					d.Anchored = true
				end
			end
			placeModel(model, target, v3(asset.centre))
			recolour(model, item.c)
			addDecals(layout, ids, counters, item, target, model)
			if item.d == "Wires" then
				for _, d in model:GetDescendants() do
					if d:IsA("BasePart") then
						d.CanCollide = false -- riders pass under the cables
						d.CanQuery = false
					end
				end
			end
			if item.d == "Terrain" or item.d == "Roads" then
				for _, d in model:GetDescendants() do
					if d:IsA("MeshPart") then
						d.CollisionFidelity = Enum.CollisionFidelity.PreciseConvexDecomposition -- hills need real collision, not a box
					end
				end
			else
				-- Cheap physics for the thousands of static props: nothing on the map listens for Touched,
				-- small props collide as boxes, tiny ones cast no shadow, birds are scenery only.
				-- Road tiles, ramps and buildings keep Default collision (kerbs and slopes must be right).
				local biggest = math.max(asset.size[1], asset.size[2], asset.size[3])
				local isRoad = string.sub(item.a, 1, 5) == "Road_" or item.a == "Ramp" or item.a == "SpeedBump"
				for _, d in model:GetDescendants() do
					if d:IsA("BasePart") then
						d.CanTouch = false
						if string.sub(item.a, 1, 5) == "Bird_" then
							d.CanCollide = false
							d.CanQuery = false
						end
						if biggest < 3 then
							d.CastShadow = false
						end
						if d:IsA("MeshPart") and biggest <= 6 and not isRoad then
							d.CollisionFidelity = Enum.CollisionFidelity.Box
						end
					end
				end
			end
			model.Parent = folder
			imported += 1
		elseif item.d == "Terrain" or item.d == "Roads" or item.d == "Wires" then
			missing[item.a] = true -- no stand-in block: flat ground covers for terrain; roads get centreline blocks below
		else
			missing[item.a] = true
			local colour = if item.c then Color3.fromHex(item.c) else Color3.fromRGB(170, 170, 180)
			local stand = block(item.a, v3(asset.size), target * CFrame.new(v3(asset.centre)), colour)
			stand.Parent = folder
			addDecals(layout, ids, counters, item, target, folder)
		end
	end

	-- Free-form roads (mountain switchbacks, causeway, roundabout) not imported yet: drivable blocks
	-- along their centrelines, so the whole network works from day one.
	local roadAsset = { Mountain = "Road_Mountain", Causeway = "Road_Causeway" }
	for _, road in layout.freeRoads do
		local assetName = roadAsset[road.n] or "Road_Roundabout"
		if templates and templates:FindFirstChild(assetName) then
			continue
		end
		local folder = Instance.new("Folder")
		folder.Name = road.n
		folder.Parent = city
		local pts = road.p
		local count = if road.c then #pts else #pts - 1
		for k = 1, count do
			local a, b = v3(pts[k]), v3(pts[k % #pts + 1])
			local mid = (a + b) / 2
			local seg = block(
				"Road",
				Vector3.new(road.w, 1, (b - a).Magnitude + 1),
				origin * CFrame.lookAt(mid, b) * CFrame.new(0, -0.5, 0),
				Color3.fromRGB(64, 66, 74)
			)
			seg.Material = Enum.Material.Asphalt
			seg.Parent = folder
		end
	end

	-- Delivery addresses: invisible markers the job system will read.
	local addressFolder = Instance.new("Folder")
	addressFolder.Name = "Addresses"
	addressFolder.Parent = city
	for k, a in layout.addresses do
		local p = block("Address" .. k, Vector3.new(4, 1, 4), origin * CFrame.new(v3(a.p)), Color3.new(0, 1, 0))
		p.Transparency = 1
		p.CanCollide = false
		p.CanQuery = false
		p:SetAttribute("District", a.d)
		p:SetAttribute("Building", a.b)
		p.Parent = addressFolder
	end

	local spawn = Instance.new("SpawnLocation")
	spawn.Name = "CitySpawn"
	spawn.Anchored = true
	spawn.Size = Vector3.new(8, 1, 8)
	spawn.Transparency = 1
	spawn.CanCollide = false
	spawn.CFrame = origin * CFrame.new(v3(layout.spawn.p)) * CFrame.Angles(0, math.rad(layout.spawn.r), 0)
	spawn.Parent = city

	city.Parent = workspace
	if applySky(ids, mood or "day") then
		print(`Sky set to {mood or "day"}.`)
	end
	local names = {}
	for name in missing do
		table.insert(names, name)
	end
	table.sort(names)
	print(`City built: {#layout.items} pieces, {imported} from CityAssets, {#layout.addresses} addresses.`)
	if #names > 0 then
		print(`Shown as blocks until imported into ServerStorage.CityAssets: {table.concat(names, ", ")}`)
	end
	return city
end

return MapBuilder
