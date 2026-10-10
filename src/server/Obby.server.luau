--!strict
-- Sky Obby: a self-building obstacle course.
-- Drop this Script into ServerScriptService and press Play. It builds the whole
-- map, tracks each player's stage and coins, and saves progress between sessions.

local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local TweenService = game:GetService("TweenService")
local RunService = game:GetService("RunService")

local STAGE_COUNT = 12
local GAP = 14 -- studs between stage starts
local BASE_HEIGHT = 40
local COIN_VALUE = 5
local WIN_BONUS = 100

local store = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore("SkyObby_v1")
	end)
	if ok then
		store = result
	else
		warn("DataStore unavailable (enable Studio API access to save progress):", result)
	end
end

local map = Instance.new("Folder")
map.Name = "SkyObby"
map.Parent = workspace

local checkpoints: { [number]: BasePart } = {}

local STAGE_COLORS = {
	Color3.fromRGB(85, 170, 255),
	Color3.fromRGB(120, 220, 120),
	Color3.fromRGB(255, 200, 80),
	Color3.fromRGB(255, 130, 90),
	Color3.fromRGB(200, 120, 255),
	Color3.fromRGB(255, 110, 170),
}

local function part(props: { [string]: any }): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Material = Enum.Material.SmoothPlastic
	for key, value in props do
		(p :: any)[key] = value
	end
	p.Parent = props.Parent or map
	return p
end

local function addLabel(target: BasePart, text: string)
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromOffset(200, 50)
	gui.StudsOffset = Vector3.new(0, 4, 0)
	gui.AlwaysOnTop = true
	gui.MaxDistance = 60
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = text
	label.TextScaled = true
	label.Font = Enum.Font.FredokaOne
	label.TextColor3 = Color3.new(1, 1, 1)
	label.TextStrokeTransparency = 0
	label.Parent = gui
	gui.Parent = target
end

local function getHumanoid(hit: BasePart): Humanoid?
	local model = hit:FindFirstAncestorOfClass("Model")
	return model and model:FindFirstChildOfClass("Humanoid")
end

local function getPlayer(hit: BasePart): Player?
	local model = hit:FindFirstAncestorOfClass("Model")
	return model and Players:GetPlayerFromCharacter(model)
end

local function killBrick(cf: CFrame, size: Vector3, parent: Instance?): Part
	local p = part({
		Name = "KillBrick",
		Size = size,
		CFrame = cf,
		Color = Color3.fromRGB(255, 40, 40),
		Material = Enum.Material.Neon,
		Parent = parent,
	})
	p.Touched:Connect(function(hit)
		local humanoid = getHumanoid(hit)
		if humanoid and humanoid.Health > 0 then
			humanoid.Health = 0
		end
	end)
	return p
end

local function coin(position: Vector3)
	local c = part({
		Name = "Coin",
		CFrame = CFrame.new(position) * CFrame.Angles(0, 0, math.rad(90)),
		Color = Color3.fromRGB(255, 215, 0),
		Material = Enum.Material.Neon,
		CanCollide = false,
	})
	c.Shape = Enum.PartType.Cylinder
	c.Size = Vector3.new(0.4, 2, 2)
	local collected: { [Player]: boolean } = {}
	c.Touched:Connect(function(hit)
		local player = getPlayer(hit)
		if not player or collected[player] then
			return
		end
		collected[player] = true
		local stats = player:FindFirstChild("leaderstats")
		local coins = stats and stats:FindFirstChild("Coins") :: IntValue?
		if coins then
			coins.Value += COIN_VALUE
		end
	end)
	-- Each player can grab each coin once per server session.
	Players.PlayerRemoving:Connect(function(player)
		collected[player] = nil
	end)
	TweenService:Create(
		c,
		TweenInfo.new(2, Enum.EasingStyle.Linear, Enum.EasingDirection.InOut, -1),
		{ CFrame = c.CFrame * CFrame.Angles(math.rad(360), 0, 0) }
	):Play()
end

local function movingPlatform(from: Vector3, to: Vector3, size: Vector3, color: Color3)
	local p = part({ Name = "MovingPlatform", Size = size, Position = from, Color = color })
	TweenService:Create(
		p,
		TweenInfo.new(2.5, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true),
		{ Position = to }
	):Play()
end

local function spinner(center: Vector3, length: number, speed: number)
	local bar = killBrick(CFrame.new(center), Vector3.new(length, 1, 1))
	local angle = 0
	RunService.Heartbeat:Connect(function(dt)
		angle += dt * speed
		bar.CFrame = CFrame.new(center) * CFrame.Angles(0, angle, 0)
	end)
end

-- Obstacle builders. Each one fills the space between a checkpoint at z and the
-- next one at z + GAP, at height y.
local obstacles: { (z: number, y: number, color: Color3) -> () } = {
	-- Stepping stones
	function(z, y, color)
		for i = 1, 3 do
			part({ Size = Vector3.new(3, 1, 3), Position = Vector3.new((i % 2 == 0) and 3 or -3, y, z + i * 3.5), Color = color })
		end
	end,
	-- Narrow beam with a coin
	function(z, y, color)
		part({ Size = Vector3.new(1, 1, GAP - 4), Position = Vector3.new(0, y, z + GAP / 2), Color = color })
		coin(Vector3.new(0, y + 3, z + GAP / 2))
	end,
	-- Lava floor with stepping pads
	function(z, y, color)
		killBrick(CFrame.new(0, y - 0.4, z + GAP / 2), Vector3.new(10, 0.2, GAP - 4))
		for i = 1, 2 do
			part({ Size = Vector3.new(2.5, 1, 2.5), Position = Vector3.new(0, y + 0.5, z + 2 + i * 3.3), Color = color })
		end
	end,
	-- Moving platform
	function(z, y, color)
		movingPlatform(Vector3.new(-6, y, z + GAP / 2), Vector3.new(6, y, z + GAP / 2), Vector3.new(5, 1, 5), color)
		coin(Vector3.new(0, y + 3, z + GAP / 2))
	end,
	-- Staircase up
	function(z, y, color)
		for i = 1, 4 do
			part({ Size = Vector3.new(4, 1, 2), Position = Vector3.new(0, y + i * 1.2, z + 2 + i * 2), Color = color })
		end
	end,
	-- Spinning kill bar over a platform
	function(z, y, color)
		part({ Size = Vector3.new(12, 1, GAP - 4), Position = Vector3.new(0, y, z + GAP / 2), Color = color })
		spinner(Vector3.new(0, y + 1.5, z + GAP / 2), 11, 2)
		coin(Vector3.new(0, y + 5, z + GAP / 2)) -- jump over the bar to grab it
	end,
}

local function buildCheckpoint(stage: number, position: Vector3, color: Color3)
	local pad = part({
		Name = "Checkpoint" .. stage,
		Size = Vector3.new(8, 1, 6),
		Position = position,
		Color = color,
		Material = Enum.Material.Neon,
	})
	addLabel(pad, stage == 1 and "START" or ("Stage " .. stage))
	if stage == 1 then
		-- Default spawn, so nobody lands on the kill floor before their data loads.
		local spawnPad = Instance.new("SpawnLocation")
		spawnPad.Anchored = true
		spawnPad.Size = Vector3.new(4, 1, 4)
		spawnPad.Position = position - Vector3.new(0, 0, 6)
		spawnPad.Duration = 0
		spawnPad.Parent = map
	end
	pad.Touched:Connect(function(hit)
		local player = getPlayer(hit)
		local humanoid = getHumanoid(hit)
		if not player or not humanoid or humanoid.Health <= 0 then
			return
		end
		local stats = player:FindFirstChild("leaderstats")
		local stageValue = stats and stats:FindFirstChild("Stage") :: IntValue?
		if stageValue and stageValue.Value == stage - 1 then
			stageValue.Value = stage
		end
	end)
	checkpoints[stage] = pad
end

-- Build the course. Stage heights rise slowly so the course climbs into the sky.
local height = BASE_HEIGHT
for stage = 1, STAGE_COUNT do
	local z = (stage - 1) * GAP
	local color = STAGE_COLORS[(stage - 1) % #STAGE_COLORS + 1]
	buildCheckpoint(stage, Vector3.new(0, height, z), color)
	if stage < STAGE_COUNT then
		local build = obstacles[(stage - 1) % #obstacles + 1]
		build(z, height, color)
		if build == obstacles[5] then
			height += 4.8 -- the staircase climbs, so the next checkpoint does too
		end
	end
end

-- Win pad after the last stage.
local winZ = STAGE_COUNT * GAP
part({ Size = Vector3.new(1, 1, GAP - 6), Position = Vector3.new(0, height, winZ - GAP / 2), Color = Color3.new(1, 1, 1) })
local winPad = part({
	Name = "WinPad",
	Size = Vector3.new(14, 1, 14),
	Position = Vector3.new(0, height, winZ + 4),
	Color = Color3.fromRGB(255, 215, 0),
	Material = Enum.Material.Neon,
})
addLabel(winPad, "🏆 YOU WIN! 🏆")

local winners: { [Player]: number } = {}
winPad.Touched:Connect(function(hit)
	local player = getPlayer(hit)
	if not player then
		return
	end
	local now = os.clock()
	if winners[player] and now - winners[player] < 10 then
		return
	end
	local stats = player:FindFirstChild("leaderstats")
	local stageValue = stats and stats:FindFirstChild("Stage") :: IntValue?
	local wins = stats and stats:FindFirstChild("Wins") :: IntValue?
	local coins = stats and stats:FindFirstChild("Coins") :: IntValue?
	if not (stageValue and wins and coins) or stageValue.Value < STAGE_COUNT then
		return
	end
	winners[player] = now
	wins.Value += 1
	coins.Value += WIN_BONUS
	-- Send them back to the start for another run.
	stageValue.Value = 1
	task.delay(2, function()
		if player.Parent then
			player:LoadCharacter()
		end
	end)
end)

-- Skybox-ish ground far below so falling looks like falling.
killBrick(CFrame.new(0, 0, winZ / 2), Vector3.new(400, 1, winZ + 200))

-- Player data
local function load(player: Player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"

	local stage = Instance.new("IntValue")
	stage.Name = "Stage"
	stage.Value = 1
	stage.Parent = stats

	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Parent = stats

	local wins = Instance.new("IntValue")
	wins.Name = "Wins"
	wins.Parent = stats

	if store then
		local ok, data = pcall(function()
			return store:GetAsync("player_" .. player.UserId)
		end)
		if ok and type(data) == "table" then
			stage.Value = math.clamp(tonumber(data.Stage) or 1, 1, STAGE_COUNT)
			coins.Value = tonumber(data.Coins) or 0
			wins.Value = tonumber(data.Wins) or 0
		end
	end

	stats.Parent = player

	local function placeAtCheckpoint(character: Model)
		local root = character:WaitForChild("HumanoidRootPart") :: BasePart
		local pad = checkpoints[stage.Value] or checkpoints[1]
		task.wait() -- let the default spawn finish before moving them
		root.CFrame = pad.CFrame + Vector3.new(0, 4, 0)
	end
	player.CharacterAdded:Connect(placeAtCheckpoint)
	if player.Character then
		task.spawn(placeAtCheckpoint, player.Character)
	end
end

local function save(player: Player)
	local stats = player:FindFirstChild("leaderstats")
	if not store or not stats then
		return
	end
	local data = {
		Stage = (stats:FindFirstChild("Stage") :: IntValue).Value,
		Coins = (stats:FindFirstChild("Coins") :: IntValue).Value,
		Wins = (stats:FindFirstChild("Wins") :: IntValue).Value,
	}
	local ok, err = pcall(function()
		store:SetAsync("player_" .. player.UserId, data)
	end)
	if not ok then
		warn("Failed to save", player.Name, err)
	end
end

Players.PlayerAdded:Connect(load)
for _, player in Players:GetPlayers() do
	task.spawn(load, player)
end

Players.PlayerRemoving:Connect(function(player)
	winners[player] = nil
	save(player)
end)

game:BindToClose(function()
	for _, player in Players:GetPlayers() do
		save(player)
	end
end)
