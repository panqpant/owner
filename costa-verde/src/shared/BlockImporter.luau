--!strict
-- Places the detailed test block (tools/blender/export_block_roblox.py) in Roblox.
-- Setup in Studio:
--   1. 3D-import build/roblox_block/*.fbx into a Folder ReplicatedStorage.BlockAssets (keep the names, e.g. b674).
--   2. Bulk-upload build/roblox_block/*.png and paste each id into BlockTextures.luau (b674 = "rbxassetid://...").
--   3. Command bar: require(game.ReplicatedStorage.Shared.BlockImporter).place()   then save the place.
-- Night lights run from ServerScriptService.Server.BlockLights.
local HttpService = game:GetService("HttpService")
local Manifest = HttpService:JSONDecode(require(script.Parent.BlockManifest))
local Textures = require(script.Parent.BlockTextures)

local BlockImporter = {}

BlockImporter.MAX_LIGHTS = 6 -- real lights per building; the rest of a lit building glows through its Neon fittings

local function style(part: BasePart, role: string, id: string)
	part.Anchored = true
	if role == "glass" then
		part.Material, part.Transparency, part.Color = Enum.Material.Glass, 0.55, Color3.fromRGB(200, 215, 220)
		part.CanCollide = true
	elseif role == "lamp" then
		part.Material, part.Color = Enum.Material.SmoothPlastic, Color3.fromRGB(240, 236, 226) -- BlockLights turns these Neon at night
		part.CanCollide = false
	else
		local tex = Textures[id]
		if tex and tex ~= "" then
			local sa = Instance.new("SurfaceAppearance")
			sa.ColorMap = tex
			sa.Parent = part
		end
	end
end

function BlockImporter.place()
	local assets = game:GetService("ReplicatedStorage"):WaitForChild("BlockAssets")
	local root = workspace:FindFirstChild("Block") or Instance.new("Folder")
	root.Name = "Block"
	root.Parent = workspace
	local missing = {}
	for _, b in Manifest.buildings do
		local src = assets:FindFirstChild(b.id)
		if not src then
			table.insert(missing, b.id)
			continue
		end
		local model = src:Clone()
		for _, part in model:GetDescendants() do
			if part:IsA("BasePart") then
				local role = string.match(part.Name, "_(%a+)$") or "opaque"
				local info = b.parts[role]
				if info then
					part.Position = Vector3.new(info.center[1], info.center[2], info.center[3])
				end
				style(part, role, b.id)
			end
		end
		model:SetAttribute("lights", HttpService:JSONEncode(b.lights))
		model.Name = b.id
		model.Parent = root
	end
	print(string.format("block placed: %d buildings, %d missing %s", #Manifest.buildings - #missing, #missing, table.concat(missing, " ")))
end

-- At night a share of each building's rooms light up (stable per night); off by day.
function BlockImporter.setNight(on: boolean, night: number)
	local root = workspace:FindFirstChild("Block")
	if not root then
		return
	end
	for _, model in root:GetChildren() do
		local lit = 0
		for _, old in model:GetChildren() do
			if old.Name == "RoomLight" then
				old:Destroy()
			end
		end
		if on then
			local pts = HttpService:JSONDecode(model:GetAttribute("lights") or "[]")
			local rng = Random.new(#model.Name * 7919 + night)
			for _, p in pts do
				if lit < BlockImporter.MAX_LIGHTS and rng:NextNumber() < 0.4 then
					local a = Instance.new("Part")
					a.Name, a.Anchored, a.CanCollide, a.CanQuery, a.Transparency = "RoomLight", true, false, false, 1
					a.Size, a.Position = Vector3.new(0.5, 0.5, 0.5), Vector3.new(p[1], p[2] - 0.6, p[3])
					local l = Instance.new("PointLight")
					l.Color, l.Brightness, l.Range, l.Shadows = Color3.fromRGB(255, 214, 160), 1.4, 18, false
					l.Parent = a
					a.Parent = model
					lit += 1
				end
			end
		end
		for _, part in model:GetDescendants() do
			if part:IsA("BasePart") and string.match(part.Name, "_lamp$") then
				part.Material = if on and lit > 0 then Enum.Material.Neon else Enum.Material.SmoothPlastic
			end
		end
	end
end

return BlockImporter
