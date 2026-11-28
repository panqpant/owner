-- Ragdoll Couriers kill test (server).
-- Builds a test road, gives every player a scooter with a parcel, and decides everything
-- worth money: crashes, parcel damage and payouts. The client only steers.
-- Note: the scooter is simulated on the rider's device, so a cheater can fake a smooth ride.
-- The server can only check what it sees (speeds, times); good enough for a kill test.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Formula = require(Shared.Formula)

local remote = Instance.new("RemoteEvent")
remote.Name = "KillTest"
remote.Parent = ReplicatedStorage

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

part({ Name = "Ground", Size = Vector3.new(1000, 2, 1400), Position = Vector3.new(0, -1, 300), Material = Enum.Material.Grass, Color = Color3.fromRGB(90, 170, 80) })
part({ Name = "Road", Size = Vector3.new(ROAD_W, 1, 680), Position = Vector3.new(0, -0.4, 290), Color = Color3.fromRGB(55, 55, 60), Material = Enum.Material.Asphalt })

-- Depot (start) and house (address)
local depot = part({ Name = "Depot", Size = Vector3.new(50, 14, 14), Position = Vector3.new(0, 7, DEPOT_Z - 28), Color = Color3.fromRGB(255, 170, 60) })
sign(depot, "DEPOT", 10)
local spawn = Instance.new("SpawnLocation")
spawn.Anchored = true
spawn.Size = Vector3.new(10, 1, 10)
spawn.Position = Vector3.new(-25, 0, DEPOT_Z)
spawn.Transparency = 1
spawn.CanCollide = false
spawn.Duration = 0
spawn.Parent = map
local house = part({ Name = "House", Size = Vector3.new(30, 18, 20), Position = Vector3.new(0, 9, HOUSE_Z + 26), Color = Color3.fromRGB(230, 120, 120) })
part({ Name = "Roof", Size = Vector3.new(32, 8, 22), CFrame = house.CFrame * CFrame.new(0, 13, 0), Color = Color3.fromRGB(120, 60, 50) }, "WedgePart")
sign(house, "42 FRAGILE LANE", 16)

local function dropZone(name: string, z: number): BasePart
	return part({
		Name = name,
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.4, 24, 24),
		CFrame = CFrame.new(0, 0.15, z) * CFrame.Angles(0, 0, math.rad(90)),
		Color = Color3.fromRGB(80, 255, 120),
		Material = Enum.Material.Neon,
		Transparency = 0.4,
		CanCollide = false,
		CanQuery = false,
	})
end
local zones = { depot = dropZone("DepotZone", DEPOT_Z + 6), house = dropZone("HouseZone", HOUSE_Z) }

-- Speed bumps: half-buried cylinders, smooth to ride over, rough on a TV at speed.
for z = 70, 130, 20 do
	part({ Name = "SpeedBump", Shape = Enum.PartType.Cylinder, Size = Vector3.new(ROAD_W, 2.6, 2.6), Position = Vector3.new(0, -0.5, z), Color = Color3.fromRGB(240, 200, 40) })
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
part({ Name = "Ramp", Size = Vector3.new(18, 1, 26), CFrame = CFrame.new(-4, 3, 210) * CFrame.Angles(math.rad(-15), 0, 0), Color = Color3.fromRGB(255, 120, 40) })

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
	part({ Name = "AlleyWall", Size = Vector3.new(10, 12, 50), Position = Vector3.new(s * 10, 6, 405), Color = Color3.fromRGB(180, 170, 150), Material = Enum.Material.Brick })
end

-- Hill with a crest you can get air off.
part({ Name = "HillUp", Size = Vector3.new(ROAD_W, 1, 34), CFrame = CFrame.new(0, 3.6, 470) * CFrame.Angles(math.rad(-12), 0, 0), Color = Color3.fromRGB(70, 70, 75) })
part({ Name = "HillDown", Size = Vector3.new(ROAD_W, 1, 34), CFrame = CFrame.new(0, 3.6, 502) * CFrame.Angles(math.rad(12), 0, 0), Color = Color3.fromRGB(70, 70, 75) })

---------------------------------------------------------------------------- vehicle

local function weld(a: BasePart, b: BasePart)
	local w = Instance.new("WeldConstraint")
	w.Part0, w.Part1 = a, b
	w.Parent = a
end

local function buildScooter(owner: Player, at: CFrame): Model
	local model = Instance.new("Model")
	model.Name = owner.Name
	local body = part({ Name = "Body", Size = Vector3.new(2.4, 0.8, 5.6), CFrame = at, Color = Color3.fromRGB(255, 90, 60), Parent = model })
	body.Anchored = false
	body.CustomPhysicalProperties = PhysicalProperties.new(1.5, 0.3, 0.2)
	model.PrimaryPart = body

	local function piece(name: string, size: Vector3, offset: CFrame, color: Color3, props: { [string]: any }?): BasePart
		local p = part({ Name = name, Size = size, CFrame = at * offset, Color = color, Parent = model, CanCollide = false, Massless = true })
		p.Anchored = false
		for k, v in props or {} do
			(p :: any)[k] = v
		end
		weld(body, p)
		return p
	end

	local wheelColor = Color3.fromRGB(30, 30, 30)
	piece("FrontWheel", Vector3.new(0.6, 1.8, 1.8), CFrame.new(0, -0.9, -2.4), wheelColor, { Shape = Enum.PartType.Cylinder })
	piece("RearWheel", Vector3.new(0.6, 1.8, 1.8), CFrame.new(0, -0.9, 2.4), wheelColor, { Shape = Enum.PartType.Cylinder })
	piece("Stem", Vector3.new(0.4, 3.6, 0.4), CFrame.new(0, 1.8, -2.5), Color3.fromRGB(200, 200, 210))
	piece("Bars", Vector3.new(2.6, 0.3, 0.3), CFrame.new(0, 3.6, -2.5), Color3.fromRGB(40, 40, 40))

	-- Cargo box behind the rider. Walls collide so the parcel rattles around inside.
	local boxColor = Color3.fromRGB(250, 230, 120)
	local boxCenter = CFrame.new(0, 1.9, 1.6)
	piece("BoxFloor", Vector3.new(3, 0.3, 2.8), boxCenter * CFrame.new(0, -1.1, 0), boxColor, { CanCollide = true })
	piece("BoxBack", Vector3.new(3, 2, 0.3), boxCenter * CFrame.new(0, -0.1, 1.4), boxColor, { CanCollide = true })
	piece("BoxFront", Vector3.new(3, 2, 0.3), boxCenter * CFrame.new(0, -0.1, -1.4), boxColor, { CanCollide = true })
	piece("BoxLeft", Vector3.new(0.3, 2, 2.8), boxCenter * CFrame.new(-1.5, -0.1, 0), boxColor, { CanCollide = true })
	piece("BoxRight", Vector3.new(0.3, 2, 2.8), boxCenter * CFrame.new(1.5, -0.1, 0), boxColor, { CanCollide = true })
	local anchor = Instance.new("Attachment")
	anchor.Name = "ParcelAnchor"
	anchor.CFrame = boxCenter
	anchor.Parent = body

	local seat = Instance.new("Seat")
	seat.Name = "Seat"
	seat.Size = Vector3.new(2, 0.4, 1.6)
	seat.CFrame = at * CFrame.new(0, 0.6, -0.6)
	seat.Color = Color3.fromRGB(30, 30, 30)
	seat.Massless = true
	seat.TopSurface = Enum.SurfaceType.Smooth
	seat.Parent = model
	weld(body, seat)

	-- Suspension ray origins; the client raycasts down from these.
	for i, offset in { Vector3.new(-1, -0.4, -2.4), Vector3.new(1, -0.4, -2.4), Vector3.new(-1, -0.4, 2.4), Vector3.new(1, -0.4, 2.4) } do
		local a = Instance.new("Attachment")
		a.Name = "Ray" .. i
		a.Position = offset
		a.Parent = body
	end

	model.Parent = vehiclesFolder
	body:SetNetworkOwner(owner)
	return model
end

---------------------------------------------------------------------------- ragdoll

-- Ball sockets sit ready on every joint; a crash swaps the motors for them.
local function rigRagdoll(character: Model)
	local humanoid = character:FindFirstChildOfClass("Humanoid") :: Humanoid
	humanoid.BreakJointsOnDeath = false
	for _, motor in character:GetDescendants() do
		if motor:IsA("Motor6D") and motor.Name ~= "Root" and motor.Name ~= "RootJoint" and motor.Part0 and motor.Part1 then
			local a0 = Instance.new("Attachment")
			a0.Name = "RagA0"
			a0.CFrame = motor.C0
			a0.Parent = motor.Part0
			local a1 = Instance.new("Attachment")
			a1.Name = "RagA1"
			a1.CFrame = motor.C1
			a1.Parent = motor.Part1
			local socket = Instance.new("BallSocketConstraint")
			socket.Name = "RagSocket"
			socket.Attachment0, socket.Attachment1 = a0, a1
			socket.LimitsEnabled = true
			socket.UpperAngle = 50
			socket.TwistLimitsEnabled = true
			socket.TwistLowerAngle = -45
			socket.TwistUpperAngle = 45
			socket.Enabled = false
			socket.Parent = motor.Parent
		end
	end
end

local function setRagdoll(character: Model, on: boolean)
	for _, d in character:GetDescendants() do
		if d:IsA("Motor6D") and d.Name ~= "Root" and d.Name ~= "RootJoint" then
			d.Enabled = not on
		elseif d:IsA("BallSocketConstraint") and d.Name == "RagSocket" then
			d.Enabled = on
		end
	end
end

---------------------------------------------------------------------------- state

type Job = { parcelId: string, from: string, to: string, startedAt: number, crashed: boolean, distance: number }
type State = {
	vehicle: Model?,
	parcel: BasePart?,
	condition: number,
	job: Job?,
	jobIndex: number,
	lastV: Vector3,
	lastParcelV: Vector3,
	tiltSince: number?,
	ragdolled: boolean,
	detachedAt: number?,
	lastPos: Vector3?,
	lastPosAt: number,
}
local states: { [Player]: State } = {}

local function seatOf(state: State): Seat?
	return state.vehicle and state.vehicle:FindFirstChild("Seat") :: Seat?
end

local function parcelAttached(state: State): boolean
	local parcel = state.parcel
	return parcel ~= nil and (parcel:FindFirstChild("AlignPosition") :: AlignPosition).Enabled
end

local function attachParcel(state: State)
	local parcel, vehicle = state.parcel, state.vehicle
	if not parcel or not vehicle or not vehicle.PrimaryPart then
		return
	end
	local anchor = vehicle.PrimaryPart:FindFirstChild("ParcelAnchor") :: Attachment
	parcel.CFrame = anchor.WorldCFrame
	parcel.AssemblyLinearVelocity = vehicle.PrimaryPart.AssemblyLinearVelocity
	local ap = parcel:FindFirstChild("AlignPosition") :: AlignPosition
	local ao = parcel:FindFirstChild("AlignOrientation") :: AlignOrientation
	ap.Attachment1, ao.Attachment1 = anchor, anchor
	ap.Enabled, ao.Enabled = true, true
	state.detachedAt = nil
	state.lastParcelV = parcel.AssemblyLinearVelocity
end

local function detachParcel(state: State)
	local parcel = state.parcel
	if parcel and parcelAttached(state) then
		(parcel:FindFirstChild("AlignPosition") :: AlignPosition).Enabled = false
		(parcel:FindFirstChild("AlignOrientation") :: AlignOrientation).Enabled = false
		state.detachedAt = os.clock()
	end
end

local function makeParcel(player: Player, state: State, parcelId: string)
	if state.parcel then
		state.parcel:Destroy()
	end
	local def = Config.Parcels[parcelId]
	local p = part({ Name = player.Name, Size = def.size, Color = def.color, Material = def.material, Parent = parcelsFolder })
	p.Anchored = false
	p.CustomPhysicalProperties = PhysicalProperties.new(0.4, 0.5, 0.1)
	p:SetAttribute("ParcelId", parcelId)
	p:SetAttribute("Condition", 100)
	local a0 = Instance.new("Attachment")
	a0.Parent = p
	-- Soft hold: the parcel lags and shifts in the box instead of being glued in.
	local ap = Instance.new("AlignPosition")
	ap.Attachment0 = a0
	ap.MaxForce = p:GetMass() * workspace.Gravity * 8
	ap.Responsiveness = 25
	ap.Enabled = false
	ap.Parent = p
	local ao = Instance.new("AlignOrientation")
	ao.Attachment0 = a0
	ao.MaxTorque = p:GetMass() * 400
	ao.Responsiveness = 20
	ao.Enabled = false
	ao.Parent = p
	state.parcel = p
	state.condition = 100
	attachParcel(state)
	p:SetNetworkOwner(player)
end

local function startJob(player: Player, state: State, from: string)
	local parcelId = Config.JobOrder[(state.jobIndex - 1) % #Config.JobOrder + 1]
	local to = if from == "depot" then "house" else "depot"
	state.job = {
		parcelId = parcelId,
		from = from,
		to = to,
		startedAt = os.clock(),
		crashed = false,
		distance = (zones[to].Position - zones[from].Position).Magnitude,
	}
	makeParcel(player, state, parcelId)
	remote:FireClient(player, "Job", { parcelId = parcelId, to = to, zone = zones[to] })
end

local function placeVehicle(state: State, at: CFrame)
	local vehicle = state.vehicle
	if vehicle and vehicle.PrimaryPart then
		vehicle:PivotTo(at)
		vehicle.PrimaryPart.AssemblyLinearVelocity = Vector3.zero
		vehicle.PrimaryPart.AssemblyAngularVelocity = Vector3.zero
		state.lastV = Vector3.zero
		state.lastPos = nil
	end
end

local function sitDown(player: Player, state: State)
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local seat = seatOf(state)
	if humanoid and seat and humanoid.Health > 0 then
		seat.Disabled = false
		seat:Sit(humanoid)
	end
end

local function crash(player: Player, state: State, velocity: Vector3)
	if state.ragdolled then
		return
	end
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	local seat = seatOf(state)
	if not character or not humanoid or not seat then
		return
	end
	state.ragdolled = true
	state.tiltSince = nil
	if state.job then
		state.job.crashed = true
	end
	local weldToSeat = seat:FindFirstChild("SeatWeld")
	if weldToSeat then
		weldToSeat:Destroy()
	end
	seat.Disabled = true
	humanoid.Sit = false
	setRagdoll(character, true)
	local fling = velocity * 0.9 + Vector3.new(0, Config.LaunchUp, 0)
	remote:FireClient(player, "Ragdoll", fling)
	if state.parcel and parcelAttached(state) then
		detachParcel(state)
		state.parcel.AssemblyLinearVelocity = fling + Vector3.new(math.random(-8, 8), 6, math.random(-8, 8))
	end

	task.delay(Config.RagdollSeconds, function()
		if states[player] ~= state or player.Character ~= character then
			return
		end
		setRagdoll(character, false)
		remote:FireClient(player, "Recover")
		local root = character:FindFirstChild("HumanoidRootPart") :: BasePart?
		if root and state.vehicle and state.vehicle.PrimaryPart then
			-- Stand the scooter back up where the rider landed, facing the way it was going.
			local look = state.vehicle.PrimaryPart.CFrame.LookVector * Vector3.new(1, 0, 1)
			if look.Magnitude < 0.1 then
				look = Vector3.new(0, 0, 1)
			end
			local at = root.Position + Vector3.new(0, 2, 0)
			placeVehicle(state, CFrame.lookAt(at, at + look.Unit))
		end
		task.wait(0.15)
		state.ragdolled = false
		sitDown(player, state)
	end)
end

local function deliver(player: Player, state: State)
	local job = state.job :: Job
	local def = Config.Parcels[job.parcelId]
	local seconds = os.clock() - job.startedAt
	local par = job.distance / Config.ParSpeed
	local result = Formula.payout(def.pay, state.condition, seconds, par, job.crashed, Config.SpeedBonus, Config.CleanBonus)
	-- shortcut: crude speed sanity check; real anti-cheat (position sampling, flags) comes with the full game.
	local fastest = job.distance / (Config.Presets[1].maxSpeed * 1.5)
	if seconds < fastest then
		warn(player.Name, "delivered impossibly fast; no pay")
		result.total = 0
	end
	local coins = (player:FindFirstChild("leaderstats") :: Folder):FindFirstChild("Coins") :: IntValue
	coins.Value += result.total
	remote:FireClient(player, "Delivered", {
		name = def.name,
		condition = math.floor(state.condition + 0.5),
		seconds = seconds,
		par = par,
		base = result.base,
		speedBonus = result.speedBonus,
		cleanBonus = result.cleanBonus,
		total = result.total,
	})
	state.jobIndex += 1
	startJob(player, state, job.to)
end

local function failJob(player: Player, state: State, reason: string)
	local job = state.job :: Job
	remote:FireClient(player, "Lost", reason)
	state.jobIndex += 1
	startJob(player, state, job.from) -- try the same leg again with the next parcel
end

---------------------------------------------------------------------------- players

local function cleanup(state: State)
	if state.vehicle then
		state.vehicle:Destroy()
	end
	if state.parcel then
		state.parcel:Destroy()
	end
end

local function onCharacter(player: Player, character: Model)
	local old = states[player]
	if old then
		cleanup(old)
	end
	local root = character:WaitForChild("HumanoidRootPart") :: BasePart
	character:WaitForChild("Humanoid")
	rigRagdoll(character)
	local state: State = {
		condition = 100,
		jobIndex = if old then old.jobIndex else 1,
		lastV = Vector3.zero,
		lastParcelV = Vector3.zero,
		ragdolled = false,
		lastPosAt = os.clock(),
	}
	states[player] = state
	local at = CFrame.lookAt(Vector3.new(0, 3, DEPOT_Z + 6), Vector3.new(0, 3, DEPOT_Z + 100))
	state.vehicle = buildScooter(player, at)
	root.CFrame = at + Vector3.new(0, 3, 0)
	task.wait(0.2)
	sitDown(player, state)
	startJob(player, state, "depot")
end

Players.PlayerAdded:Connect(function(player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Parent = stats
	stats.Parent = player
	player.CharacterAdded:Connect(function(character)
		onCharacter(player, character)
	end)
end)

Players.PlayerRemoving:Connect(function(player)
	local state = states[player]
	if state then
		cleanup(state)
		states[player] = nil
	end
end)

local lastReset: { [Player]: number } = {}
remote.OnServerEvent:Connect(function(player, kind)
	local state = states[player]
	if kind ~= "Reset" or not state or state.ragdolled then
		return
	end
	if os.clock() - (lastReset[player] or 0) < 1 then
		return
	end
	lastReset[player] = os.clock()
	local root = player.Character and player.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
	if root and state.vehicle and state.vehicle.PrimaryPart then
		local look = root.CFrame.LookVector * Vector3.new(1, 0, 1)
		local at = root.Position + Vector3.new(0, 2, 0)
		placeVehicle(state, CFrame.lookAt(at, at + (if look.Magnitude > 0.1 then look.Unit else Vector3.new(0, 0, 1))))
		sitDown(player, state)
	end
end)

---------------------------------------------------------------------------- simulation watch

local cosTilt = math.cos(math.rad(Config.TiltCrashDegrees))

RunService.Heartbeat:Connect(function()
	local now = os.clock()
	for player, state in states do
		local vehicle, parcel, job = state.vehicle, state.parcel, state.job
		local body = vehicle and vehicle.PrimaryPart
		local seat = seatOf(state)
		if not body or not parcel or not job or not seat then
			continue
		end

		-- Crash: a sudden change of velocity (hit a wall, landed badly) or lying on its side.
		local v = body.AssemblyLinearVelocity
		if seat.Occupant and not state.ragdolled then
			if (v - state.lastV).Magnitude > Config.CrashDeltaV then
				crash(player, state, state.lastV)
			elseif body.CFrame.UpVector.Y < cosTilt then
				state.tiltSince = state.tiltSince or now
				if now - (state.tiltSince :: number) > Config.TiltCrashSeconds then
					crash(player, state, v)
				end
			else
				state.tiltSince = nil
			end
		end
		state.lastV = v

		-- Parcel damage from every jolt it takes, in or out of the box.
		local pv = parcel.AssemblyLinearVelocity
		local def = Config.Parcels[job.parcelId]
		local hit = Formula.impactDamage((pv - state.lastParcelV).Magnitude, def.fragility, def.tolerance, Config.DamageScale)
		state.lastParcelV = pv
		if hit > 0 then
			state.condition = math.max(0, state.condition - hit)
			parcel:SetAttribute("Condition", math.floor(state.condition + 0.5))
			if hit >= 1 then
				remote:FireClient(player, "Hit", hit)
			end
		end

		-- Dropped parcel: lost off the map, scooped up when you ride close, or comes back after a while.
		if parcel.Position.Y < Config.ParcelLostY then
			failJob(player, state, "Parcel lost!")
			continue
		end
		if not parcelAttached(state) and state.detachedAt then
			local near = (parcel.Position - body.Position).Magnitude < Config.ReloadDistance
			if not state.ragdolled and seat.Occupant and near and pv.Magnitude < 10 then
				attachParcel(state)
			elseif now - state.detachedAt > Config.ParcelRetrieveSeconds and not state.ragdolled then
				state.condition = math.max(0, state.condition - Config.ParcelRetrievePenalty)
				parcel:SetAttribute("Condition", math.floor(state.condition + 0.5))
				attachParcel(state)
				remote:FireClient(player, "Lost", "Parcel retrieved (-" .. Config.ParcelRetrievePenalty .. "%)")
			end
		end

		-- Delivery: ride into the green circle with the parcel in the box.
		local zone = zones[job.to]
		local flat = (body.Position - zone.Position) * Vector3.new(1, 0, 1)
		if parcelAttached(state) and flat.Magnitude < 12 and not state.ragdolled then
			deliver(player, state)
		end
	end
end)
