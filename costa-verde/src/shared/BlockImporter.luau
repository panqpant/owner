--!strict
-- Places the detailed test block (tools/blender/export_block_roblox.py) in Roblox.
-- Setup in Studio:
--   1. 3D-import assets/roblox/block/*.fbx into a Folder ReplicatedStorage.BlockAssets (keep the names, e.g. b674).
--   2. Bulk-upload assets/roblox/block/*.jpg and paste each id into BlockTextures.luau (b674 = "rbxassetid://...").
--   3. Street level: 3D-import build/roblox_block/env/*.fbx into ReplicatedStorage.BlockEnvAssets; upload env/leaf.png
--      and paste its id as BlockTextures.leaf.
--   4. Command bar: require(game.ReplicatedStorage.Shared.BlockImporter).place()   then save the place.
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
					if info.size and part:IsA("MeshPart") then -- undo any unit-scale mix-up from the importer
						part.Size = Vector3.new(info.size[1], info.size[2], info.size[3])
					end
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
	BlockImporter.placeEnv()
end

-- Street level: surfaces (Roblox materials) and every prop / plant / tree / car from the placement list.
function BlockImporter.placeEnv()
	local env = HttpService:JSONDecode(require(script.Parent.BlockEnvManifest))
	local assets = game:GetService("ReplicatedStorage"):WaitForChild("BlockEnvAssets")
	local root = workspace:FindFirstChild("BlockEnv") or Instance.new("Folder")
	root.Name = "BlockEnv"
	root.Parent = workspace
	local missing = {}
	for _, sf in env.surfaces do
		local src = assets:FindFirstChild(sf.name)
		if not src then
			table.insert(missing, sf.name)
			continue
		end
		local m = src:Clone()
		for _, part in m:GetDescendants() do
			if part:IsA("BasePart") then
				if sf.size and part:IsA("MeshPart") then
					part.Size = Vector3.new(sf.size[1], sf.size[2], sf.size[3])
				end
				part.Anchored, part.Position = true, Vector3.new(sf.center[1], sf.center[2], sf.center[3])
				part.Material = (Enum.Material :: any)[sf.material]
				part.Color = Color3.fromRGB(sf.color[1], sf.color[2], sf.color[3])
				if sf.material == "Glass" then
					part.Transparency, part.Reflectance = 0.25, 0.3 -- puddles
				end
			end
		end
		m.Parent = root
	end
	local leaf = Textures.leaf
	for _, pl in env.placements do
		local src = assets:FindFirstChild(pl.model)
		local info = env.models[pl.model]
		if not src or not info then
			table.insert(missing, pl.model)
			continue
		end
		local m = src:Clone()
		if not m:IsA("Model") then
			local wrap = Instance.new("Model")
			m.Parent = wrap
			m = wrap
		end
		for _, part in m:GetDescendants() do
			if part:IsA("BasePart") then
				part.Anchored = true
				part.CanCollide = part.Size.Magnitude > 6
				if info.leaf and leaf and leaf ~= "" and string.find(string.lower(part.Name), "leaf") then
					local sa = Instance.new("SurfaceAppearance")
					sa.ColorMap, sa.AlphaMode = leaf, Enum.AlphaMode.Transparency
					sa.Parent = part
				end
			end
		end
		local _, ext = m:GetBoundingBox()
		local fix = if info.size and ext.Y > 0 then info.size[2] / ext.Y else 1 -- undo importer unit scale
		if pl.scale * fix ~= 1 then
			m:ScaleTo(m:GetScale() * pl.scale * fix)
		end
		-- put the model's bounding-box centre where the placement says (pivot-independent)
		local rot = CFrame.Angles(0, pl.yaw, 0)
		local o = info.offset
		local target = Vector3.new(pl.pos[1], pl.pos[2], pl.pos[3]) + rot:VectorToWorldSpace(Vector3.new(o[1], o[2], o[3]) * pl.scale)
		local box = m:GetBoundingBox()
		m:PivotTo(CFrame.new(target) * rot * box.Rotation:Inverse() * (box:Inverse() * m:GetPivot()))
		m.Parent = root
	end
	print(string.format("street level placed: %d surfaces, %d placements; missing: %s", #env.surfaces, #env.placements,
		if #missing > 0 then table.concat(missing, " ") else "none"))
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
