-- The world the game runs in: the kill-test road (always built, near the origin) and, when
-- workspace.City exists (art/README.md), the city's addresses, spawn and pedestrian walks.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local WalkMath = require(Shared.WalkMath)

---------------------------------------------------------------------------- map

local map = Instance.new("Folder")
map.Name = "Map"
map.Parent = workspace
local vehiclesFolder = Instance.new("Folder")
vehiclesFolder.Name = "Vehicles"
vehiclesFolder.Parent = workspace
local parcelsFolder = Instance.new("Folder")
parcelsFolder.Name = "Parcels"
parcelsFolder.Parent = workspace

local function part(props: { [string]: any }, class: string?): BasePart
	local p = Instance.new(class or "Part") :: BasePart
	p.Anchored = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Material = Enum.Material.SmoothPlastic
	for key, value in props do
		if key ~= "Parent" then
			(p :: any)[key] = value
		end
	end
	p.Parent = props.Parent or map
	return p
end

local function sign(parent: BasePart, text: string, offsetY: number)
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromOffset(260, 70)
	gui.StudsOffset = Vector3.new(0, offsetY, 0)
	gui.MaxDistance = 400
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = text
	label.TextScaled = true
	label.Font = Enum.Font.FredokaOne
	label.TextColor3 = Color3.new(1, 1, 1)
	label.TextStrokeTransparency = 0
	label.Parent = gui
	gui.Parent = parent
end

local ROAD_W = 30
local DEPOT_Z, HOUSE_Z = -20, 590

part({
	Name = "Ground",
	Size = Vector3.new(1000, 2, 1400),
	Position = Vector3.new(0, -1, 300),
	Material = Enum.Material.Grass,
	Color = Color3.fromRGB(90, 170, 80),
})
part({
	Name = "Road",
	Size = Vector3.new(ROAD_W, 1, 680),
	Position = Vector3.new(0, -0.4, 290),
	Color = Color3.fromRGB(55, 55, 60),
	Material = Enum.Material.Asphalt,
})

-- Depot (start) and house (address)
local depot = part({
	Name = "Depot",
	Size = Vector3.new(50, 14, 14),
	Position = Vector3.new(0, 7, DEPOT_Z - 28),
	Color = Color3.fromRGB(255, 170, 60),
})
sign(depot, "DEPOT", 10)
local spawn = Instance.new("SpawnLocation")
spawn.Anchored = true
spawn.Size = Vector3.new(10, 1, 10)
spawn.Position = Vector3.new(-25, 0, DEPOT_Z)
spawn.Transparency = 1
spawn.CanCollide = false
spawn.Duration = 0
spawn.Parent = map
local house = part({
	Name = "House",
	Size = Vector3.new(30, 18, 20),
	Position = Vector3.new(0, 9, HOUSE_Z + 26),
	Color = Color3.fromRGB(230, 120, 120),
})
part({
	Name = "Roof",
	Size = Vector3.new(32, 8, 22),
	CFrame = house.CFrame * CFrame.new(0, 13, 0),
	Color = Color3.fromRGB(120, 60, 50),
}, "WedgePart")
sign(house, "42 FRAGILE LANE", 16)

-- Destinations live in a persistent model: with streaming on, the client always has them for its guide beam.
local zonesModel = Instance.new("Model")
zonesModel.Name = "Zones"
zonesModel.ModelStreamingMode = Enum.ModelStreamingMode.Persistent
zonesModel.Parent = workspace

local function zoneCFrame(at: Vector3): CFrame
	return CFrame.new(at + Vector3.new(0, 0.15, 0)) * CFrame.Angles(0, 0, math.rad(90))
end

local function dropZoneAt(name: string, at: Vector3): BasePart
	return part({
		Name = name,
		Parent = zonesModel,
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.4, 24, 24),
		CFrame = zoneCFrame(at),
		Color = Color3.fromRGB(80, 255, 120),
		Material = Enum.Material.Neon,
		Transparency = 0.4,
		CanCollide = false,
		CanQuery = false,
	})
end
local zones = {
	depot = dropZoneAt("DepotZone", Vector3.new(0, 0, DEPOT_Z + 6)),
	house = dropZoneAt("HouseZone", Vector3.new(0, 0, HOUSE_Z)),
}

-- Speed bumps: half-buried cylinders, smooth to ride over, rough on a TV at speed.
for z = 70, 130, 20 do
	part({
		Name = "SpeedBump",
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(ROAD_W, 2.6, 2.6),
		Position = Vector3.new(0, -0.5, z),
		Color = Color3.fromRGB(240, 200, 40),
	})
end

-- Loose crates to smash through (unanchored, so they scatter).
for i = 0, 9 do
	local p = part({
		Name = "Crate",
		Size = Vector3.new(3, 3, 3),
		Position = Vector3.new(8 + (i % 2) * 3.2, 1.5 + math.floor(i / 2) * 3.1, 160),
		Color = Color3.fromRGB(170, 120, 70),
		Material = Enum.Material.WoodPlanks,
	})
	p.Anchored = false
end

-- Ramp: the first run almost guarantees a funny crash (the pillow survives it).
part({
	Name = "Ramp",
	Size = Vector3.new(18, 1, 26),
	CFrame = CFrame.new(-4, 3, 210) * CFrame.Angles(math.rad(-15), 0, 0),
	Color = Color3.fromRGB(255, 120, 40),
})

-- Cobbles: lots of small uneven stones.
local rng = Random.new(7)
for z = 270, 340, 3.2 do
	for x = -13.5, 13.5, 3 do
		part({
			Name = "Cobble",
			Size = Vector3.new(2.8, 1, 3),
			Position = Vector3.new(x, -0.3 + rng:NextNumber(0, 0.55), z),
			Color = Color3.fromRGB(130 + rng:NextInteger(-15, 15), 125, 115),
			Material = Enum.Material.Cobblestone,
		})
	end
end

-- Narrow alley: walls pinch the road to 10 studs. Hit a wall, fly off.
for _, s in { -1, 1 } do
	part({
		Name = "AlleyWall",
		Size = Vector3.new(10, 12, 50),
		Position = Vector3.new(s * 10, 6, 405),
		Color = Color3.fromRGB(180, 170, 150),
		Material = Enum.Material.Brick,
	})
end

-- Hill with a crest you can get air off.
part({
	Name = "HillUp",
	Size = Vector3.new(ROAD_W, 1, 34),
	CFrame = CFrame.new(0, 3.6, 470) * CFrame.Angles(math.rad(-12), 0, 0),
	Color = Color3.fromRGB(70, 70, 75),
})
part({
	Name = "HillDown",
	Size = Vector3.new(ROAD_W, 1, 34),
	CFrame = CFrame.new(0, 3.6, 502) * CFrame.Angles(math.rad(12), 0, 0),
	Color = Color3.fromRGB(70, 70, 75),
})

---------------------------------------------------------------------------- the city (when it's built)

-- With workspace.City built (art/README.md), riders start at the Hub depot and deliver to the city's
-- addresses, to customers on foot, and chase parcel thieves. Without it, the test road above is used.
local city = workspace:FindFirstChild("City")
local cityOrigin = city and city:GetAttribute("Origin") :: Vector3?
local cityAddresses: { BasePart } = {}
local citySpawn = city and city:FindFirstChild("CitySpawn") :: BasePart?
local walks: { WalkMath.Walk } = {}
if city and cityOrigin then
	local folder = city:FindFirstChild("Addresses")
	for _, a in if folder then folder:GetChildren() else {} do
		if a:IsA("BasePart") then
			table.insert(cityAddresses, a)
		end
	end
	walks = WalkMath.load(cityOrigin)
end
local cityMode = #cityAddresses > 0 and citySpawn ~= nil

local function flatDistance(a: Vector3, b: Vector3): number
	return ((a - b) * Vector3.new(1, 0, 1)).Magnitude
end

-- "Docks_FishMarket" -> "Fish Market", "OldTown_TownhouseLow" -> "Townhouse", "House_C" -> "House"
local function friendly(building: string?): string
	if not building then
		return "Address"
	end
	if string.sub(building, 1, 5) == "House" then
		return "House"
	end
	local rest = string.match(building, "^[^_]+_(.+)$") or building
	for _, suffix in { "Low", "Short", "Tall" } do
		rest = string.gsub(rest, suffix .. "$", "")
	end
	return (string.gsub(rest, "(%l)(%u)", "%1 %2"))
end

local function pickAddress(from: Vector3): BasePart
	local options = {}
	for _, a in cityAddresses do
		local d = flatDistance(a.Position, from)
		if d >= Config.JobMinDistance and d <= Config.JobMaxDistance then
			table.insert(options, a)
		end
	end
	local list = if #options > 0 then options else cityAddresses
	return list[math.random(#list)]
end

local function pickWalk(from: Vector3): WalkMath.Walk
	local options, total = {}, 0
	for _, w in walks do
		local d = flatDistance(WalkMath.at(w, w.length / 2), from)
		if d >= Config.JobMinDistance and d <= Config.JobMaxDistance then
			table.insert(options, w)
			total += w.weight
		end
	end
	if #options == 0 then
		return walks[math.random(#walks)]
	end
	local pick = math.random() * total
	for _, w in options do
		pick -= w.weight
		if pick <= 0 then
			return w
		end
	end
	return options[#options]
end

return {
	vehiclesFolder = vehiclesFolder,
	parcelsFolder = parcelsFolder,
	part = part,
	sign = sign,
	ROAD_W = ROAD_W,
	DEPOT_Z = DEPOT_Z,
	zonesModel = zonesModel,
	zoneCFrame = zoneCFrame,
	dropZoneAt = dropZoneAt,
	zones = zones,
	citySpawn = citySpawn,
	walks = walks,
	cityMode = cityMode,
	flatDistance = flatDistance,
	friendly = friendly,
	pickAddress = pickAddress,
	pickWalk = pickWalk,
}
