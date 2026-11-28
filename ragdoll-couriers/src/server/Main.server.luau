-- Ragdoll Couriers (server): jobs, crashes, parcel damage, payouts, pedestrians' effects on all of it.
-- The client only steers and reports pedestrian contact; everything worth money is decided here.
-- Note: the scooter is simulated on the rider's device, so a cheater can fake a smooth ride. The server
-- checks what it can see (speeds, times, distances).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local Formula = require(Shared.Formula)
local Services = script.Parent:WaitForChild("Services")
local remote = require(Services.Net)
local Data = require(Services.Data)
local World = require(Services.World)
local Actors = require(Services.Actors)
local Vehicles = require(Services.Vehicles)
local Ragdoll = require(Services.Ragdoll)
local parcelsFolder, part, DEPOT_Z, zoneCFrame, dropZoneAt, zones, citySpawn, walks, cityMode, flatDistance, friendly, pickAddress, pickWalk =
	World.parcelsFolder,
	World.part,
	World.DEPOT_Z,
	World.zoneCFrame,
	World.dropZoneAt,
	World.zones,
	World.citySpawn,
	World.walks,
	World.cityMode,
	World.flatDistance,
	World.friendly,
	World.pickAddress,
	World.pickWalk
local actors, actorData, addActor, removeActor, actorPos, getawayRoute =
	Actors.actors, Actors.actorData, Actors.addActor, Actors.removeActor, Actors.actorPos, Actors.getawayRoute
local buildScooter = Vehicles.buildScooter
local rigRagdoll, setRagdoll = Ragdoll.rigRagdoll, Ragdoll.setRagdoll
type Actor = Actors.Actor

---------------------------------------------------------------------------- state

type Job = {
	parcelId: string,
	from: string,
	to: string,
	startedAt: number,
	crashed: boolean,
	distance: number,
	zone: BasePart,
	label: string,
	kind: string, -- "address" or "customer"
	customer: Actor?,
	ownZone: boolean, -- a city zone made for this job (destroyed with it)
	nearMisses: number,
}
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
	thief: Actor?,
	lastPedHit: number,
	lastNearMiss: number,
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
	local p = part({
		Name = player.Name,
		Size = def.size,
		Color = def.color,
		Material = def.material,
		Parent = parcelsFolder,
	})
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

local function endJobExtras(state: State)
	local job = state.job
	if job and job.customer then
		removeActor(job.customer)
	end
	if job and job.ownZone then
		job.zone:Destroy()
	end
	if state.thief then
		removeActor(state.thief)
		state.thief = nil
	end
end

local function startJob(player: Player, state: State, from: string)
	endJobExtras(state)
	local parcelId = Config.JobOrder[(state.jobIndex - 1) % #Config.JobOrder + 1]
	local job: Job
	if cityMode then
		-- City: from wherever the rider is to an address, or every few jobs to a customer on foot.
		local body = state.vehicle and state.vehicle.PrimaryPart
		local fromPos = if body then body.Position else (citySpawn :: BasePart).Position
		local zone = dropZoneAt("Zone_" .. player.Name, fromPos)
		job = {
			parcelId = parcelId,
			from = "here",
			to = "",
			startedAt = os.clock(),
			crashed = false,
			distance = 0,
			zone = zone,
			label = "",
			kind = "address",
			ownZone = true,
			nearMisses = 0,
		}
		if #walks > 0 and state.jobIndex % Config.HandoffEvery == 0 then
			local walk = pickWalk(fromPos)
			job.customer = addActor(
				"customer",
				walk,
				Config.CustomerSpeed,
				math.random() * walk.length,
				if math.random() < 0.5 then 1 else -1,
				false
			)
			job.kind = "customer"
			job.label = "Customer on foot, " .. walk.district
			zone.Size = Vector3.new(0.4, 16, 16)
			zone.CFrame = zoneCFrame(actorPos(job.customer :: Actor))
		else
			local address = pickAddress(fromPos)
			job.label = friendly(address:GetAttribute("Building") :: string?)
				.. ", "
				.. tostring(address:GetAttribute("District") or "City")
			zone.CFrame = zoneCFrame(address.Position)
		end
		job.to = job.kind
		job.distance = flatDistance(zone.Position, fromPos)
	else
		local to = if from == "depot" then "house" else "depot"
		job = {
			parcelId = parcelId,
			from = from,
			to = to,
			startedAt = os.clock(),
			crashed = false,
			distance = (zones[to].Position - zones[from].Position).Magnitude,
			zone = zones[to],
			label = if to == "house" then "House" else "Depot",
			kind = "address",
			ownZone = false,
			nearMisses = 0,
		}
	end
	state.job = job
	makeParcel(player, state, parcelId)
	remote:FireClient(
		player,
		"Job",
		{ parcelId = parcelId, to = job.to, label = job.label, kind = job.kind, zone = job.zone }
	)
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
	Data.bump(player, "crashes")
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
		if cityMode and #walks > 0 and not state.thief and math.random() < Config.ThiefChance then
			task.delay(1.2, function() -- once the parcel has landed
				local parcel, body = state.parcel, state.vehicle and state.vehicle.PrimaryPart
				if
					states[player] ~= state
					or state.thief
					or not state.job
					or not parcel
					or not body
					or parcelAttached(state)
				then
					return
				end
				local route = getawayRoute(parcel.Position, body.Position)
				if not route then
					return
				end
				state.thief = addActor("thief", route, Config.ThiefSpeed, 0, 1, true)
				parcel.Anchored = true -- carried over the thief's head from here (see the Heartbeat)
				remote:FireClient(player, "Lost", "THIEF! Catch them!")
			end)
		end
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
	local result =
		Formula.payout(def.pay, state.condition, seconds, par, job.crashed, Config.SpeedBonus, Config.CleanBonus)
	local handoffBonus = if job.kind == "customer" then math.floor(result.base * Config.HandoffBonus + 0.5) else 0
	result.total += handoffBonus
	-- shortcut: crude speed sanity check; real anti-cheat (position sampling, flags) comes with the full game.
	local fastest = job.distance / (Config.Presets[1].maxSpeed * 1.5)
	if seconds < fastest then
		warn(player.Name, "delivered impossibly fast; no pay")
		result.total = 0
	end
	Data.addCoins(player, result.total)
	local profile = Data.get(player)
	if profile then
		profile.deliveries += 1
		profile.stats.bestCondition = math.max(profile.stats.bestCondition, math.floor(state.condition + 0.5))
		if job.kind == "customer" then
			profile.stats.customersServed += 1
		end
	end
	remote:FireClient(player, "Delivered", {
		name = def.name,
		condition = math.floor(state.condition + 0.5),
		seconds = seconds,
		par = par,
		base = result.base,
		speedBonus = result.speedBonus,
		cleanBonus = result.cleanBonus,
		handoffBonus = handoffBonus,
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
	endJobExtras(state)
	if state.vehicle then
		state.vehicle:Destroy()
	end
	if state.parcel then
		state.parcel:Destroy()
	end
end

local function onCharacter(player: Player, character: Model)
	if not Data.wait(player) then
		return -- left before their save loaded
	end
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
		lastPedHit = 0,
		lastNearMiss = 0,
	}
	states[player] = state
	local at = CFrame.lookAt(Vector3.new(0, 3, DEPOT_Z + 6), Vector3.new(0, 3, DEPOT_Z + 100))
	if cityMode then
		at = (citySpawn :: BasePart).CFrame * CFrame.new(0, 3, 0)
		pcall(function()
			player:RequestStreamAroundAsync(at.Position) -- load the depot before dropping them into it
		end)
	end
	state.vehicle = buildScooter(player, at)
	root.CFrame = at + Vector3.new(0, 3, 0)
	task.wait(0.2)
	sitDown(player, state)
	startJob(player, state, "depot")
end

local function onPlayerAdded(player: Player)
	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local coins = Instance.new("IntValue")
	coins.Name = "Coins"
	coins.Parent = stats
	stats.Parent = player
	task.spawn(function()
		coins.Value = Data.load(player).coins
	end)
	for _, a in actors do
		remote:FireClient(player, "Actor", actorData(a))
	end
	player.CharacterAdded:Connect(function(character)
		onCharacter(player, character)
	end)
	if player.Character then
		task.spawn(onCharacter, player, player.Character)
	end
end
Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in Players:GetPlayers() do -- anyone who joined while the modules were loading
	task.spawn(onPlayerAdded, player)
end

Players.PlayerRemoving:Connect(function(player)
	local state = states[player]
	if state then
		cleanup(state)
		states[player] = nil
	end
end)

local lastReset: { [Player]: number } = {}

-- Pedestrians live on each client, so hits and near misses are reported by the client.
-- A hit only costs the reporter. shortcut: near misses are trusted within limits (rider speed checked
-- here, rate and per-job cap); at 4 coins x 6 a job a faker gains little. Revisit if coins get real value.
local function onPedHit(player: Player, state: State)
	local job, parcel, body = state.job, state.parcel, state.vehicle and state.vehicle.PrimaryPart
	local now = os.clock()
	if not cityMode or not job or not parcel or not body or state.ragdolled or now - state.lastPedHit < 0.5 then
		return
	end
	state.lastPedHit = now
	job.crashed = true -- no clean bonus
	state.condition = math.max(0, state.condition - Config.PedHitDamage)
	parcel:SetAttribute("Condition", math.floor(state.condition + 0.5))
	remote:FireClient(player, "Hit", Config.PedHitDamage)
	remote:FireClient(player, "Lost", "Watch it! -" .. Config.PedHitDamage .. "%")
end

local function onNearMiss(player: Player, state: State)
	local job, body = state.job, state.vehicle and state.vehicle.PrimaryPart
	local now = os.clock()
	if
		not cityMode
		or not job
		or not body
		or state.ragdolled
		or now - state.lastNearMiss < 0.8
		or job.nearMisses >= Config.NearMissMaxPerJob
	then
		return
	end
	if body.AssemblyLinearVelocity.Magnitude < Config.NearMissSpeed * 0.8 then
		return -- the server doesn't see them going fast enough
	end
	state.lastNearMiss = now
	job.nearMisses += 1
	Data.addCoins(player, Config.NearMissCoins)
	Data.bump(player, "nearMisses")
	remote:FireClient(player, "Bonus", "Near miss! +" .. Config.NearMissCoins)
end

remote.OnServerEvent:Connect(function(player, kind)
	local state = states[player]
	if not state then
		return
	end
	if kind == "PedHit" then
		onPedHit(player, state)
		return
	elseif kind == "NearMiss" then
		onNearMiss(player, state)
		return
	end
	if kind ~= "Reset" or state.ragdolled then
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

		-- A thief has the parcel: it rides over their head until you catch them or they get away.
		local thief = state.thief
		if thief then
			local at = actorPos(thief)
			parcel.CFrame = CFrame.new(at + Vector3.new(0, 6.5, 0))
			if
				not state.ragdolled
				and flatDistance(body.Position, at) < Config.ThiefCatchRange
				and math.abs(body.Position.Y - at.Y) < 8
			then
				removeActor(thief)
				state.thief = nil
				parcel.Anchored = false
				attachParcel(state)
				parcel:SetNetworkOwner(player)
				Data.addCoins(player, Config.ThiefCatchCoins)
				Data.bump(player, "thievesCaught")
				remote:FireClient(player, "Bonus", "Caught the thief! +" .. Config.ThiefCatchCoins)
			elseif workspace:GetServerTimeNow() - thief.t0 > thief.path.length / thief.speed + 0.5 then
				failJob(player, state, "The thief got away!")
			end
			continue
		end

		-- Parcel damage from every jolt it takes, in or out of the box.
		local pv = parcel.AssemblyLinearVelocity
		local def = Config.Parcels[job.parcelId]
		local hit =
			Formula.impactDamage((pv - state.lastParcelV).Magnitude, def.fragility, def.tolerance, Config.DamageScale)
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

		-- Delivery: ride into the green circle with the parcel in the box. A customer's circle walks with them.
		local customer = job.customer
		if customer then
			local at = actorPos(customer)
			job.zone.CFrame = zoneCFrame(at)
			local handOver = flatDistance(body.Position, at) < Config.HandoffRange
				and body.AssemblyLinearVelocity.Magnitude < Config.HandoffMaxSpeed
			if parcelAttached(state) and handOver and not state.ragdolled then
				deliver(player, state)
			end
		elseif
			parcelAttached(state)
			and flatDistance(body.Position, job.zone.Position) < 12
			and not state.ragdolled
		then
			deliver(player, state)
		end
	end
end)
