-- Pedestrians (client): locals stroll the pavement walks from art/map/walks.py around the player,
-- limbs swinging. Clip one at speed and they ragdoll and fly (and the server docks your parcel);
-- brush past fast without touching and it's a near miss (coins). These locals are each player's own:
-- no Humanoids, no network.
--
-- Customers on foot and parcel thieves are different: the server announces them ("Actor") with a path,
-- speed and server-clock start time, and every client draws them in the same place from that.
--
-- Models: ReplicatedStorage.PedAssets.Ped_* (import art/export/Ped_*.fbx there: six MeshParts each,
-- named Torso, Head, LArm, RArm, LLeg, RLeg, front facing -Z). Until then, block people stand in.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local WalkMath = require(Shared:WaitForChild("WalkMath"))
local remote = ReplicatedStorage:WaitForChild("KillTest") :: RemoteEvent
local player = Players.LocalPlayer
local camera = workspace.CurrentCamera

local MAX_PEDS = 36
local SPAWN_RADIUS = 240 -- spawn somewhere on a walk within this of the camera...
local SPAWN_MIN = 70 -- ...but not right under the player's nose
local DESPAWN_RADIUS = 320
local CELL = 120 -- spatial buckets for finding walks near the camera
local HIT_RADIUS = 4.5
local RAGDOLL_TIME = 6
local LIMBS = { "Torso", "Head", "LArm", "RArm", "LLeg", "RLeg" }

local city = workspace:WaitForChild("City")
local origin = (city:GetAttribute("Origin") :: Vector3?) or Vector3.zero

---------------------------------------------------------------------------- walks, bucketed

local walks = WalkMath.load(origin)
local buckets: { [number]: { WalkMath.Walk } } = {}

local function bucketKey(i: number, j: number): number
	return (i + 1000) * 10000 + (j + 1000) -- numbers, not Vector2: userdata keys compare by identity
end

for _, walk in walks do
	local seen = {}
	for _, p in walk.points do
		local key = bucketKey(math.floor(p.X / CELL), math.floor(p.Z / CELL))
		if not seen[key] then
			seen[key] = true
			buckets[key] = buckets[key] or {}
			table.insert(buckets[key], walk)
		end
	end
end

---------------------------------------------------------------------------- people

type Ped = {
	model: Model,
	parts: { BasePart },
	rest: { CFrame }, -- each part relative to the feet, standing still
	joints: { Vector3 }, -- each part's joint in the same frame (limbs hang from it)
	walk: WalkMath.Path,
	s: number,
	dir: number,
	speed: number,
	pause: number,
	phase: number,
	yaw: number,
	missed: boolean, -- a near miss already counted for this one
	hit: boolean,
}

local templates: { [string]: Model } = {}
local templateList: { Model } = {}
local folder = ReplicatedStorage:FindFirstChild("PedAssets")
if folder then
	for _, m in folder:GetChildren() do
		if m:IsA("Model") and m:FindFirstChild("Torso") then
			templates[m.Name] = m
			table.insert(templateList, m)
		end
	end
end

-- Block people for before the models are imported: same six parts, same proportions.
local SHIRTS = { "e8443a", "3a7bf0", "43b85c", "ffd23f", "f6a5c0", "8b5cf6", "f4f4f8", "ff9a2e" }
local SKINS = { "f2c9a0", "d9a066", "8d5a3b", "5c3a24" }
local function blockPerson(): Model
	local m = Instance.new("Model")
	m.Name = "Ped_Block"
	local shirt = Color3.fromHex(SHIRTS[math.random(#SHIRTS)])
	local skin = Color3.fromHex(SKINS[math.random(#SKINS)])
	local legs = Color3.fromHex(({ "23306b", "3a3d46", "8b5a3c" })[math.random(3)])
	local spec = {
		Torso = { Vector3.new(2, 2, 1), Vector3.new(0, 3, 0), shirt },
		Head = { Vector3.new(1.2, 1.2, 1.2), Vector3.new(0, 4.6, 0), skin },
		LArm = { Vector3.new(1, 2, 1), Vector3.new(-1.5, 3, 0), shirt },
		RArm = { Vector3.new(1, 2, 1), Vector3.new(1.5, 3, 0), shirt },
		LLeg = { Vector3.new(1, 2, 1), Vector3.new(-0.5, 1, 0), legs },
		RLeg = { Vector3.new(1, 2, 1), Vector3.new(0.5, 1, 0), legs },
	}
	for name, s in spec do
		local p = Instance.new("Part")
		p.Name = name
		p.Size = s[1]
		p.CFrame = CFrame.new(s[2])
		p.Color = s[3]
		p.TopSurface, p.BottomSurface = Enum.SurfaceType.Smooth, Enum.SurfaceType.Smooth
		p.Parent = m
	end
	return m
end

local live: { Ped } = {}
local pedFolder = Instance.new("Folder")
pedFolder.Name = "Pedestrians"
pedFolder.Parent = workspace

local function newPed(walk: WalkMath.Path, s: number, modelName: string?): Ped
	local template = if modelName then templates[modelName] else nil
	template = template or (if #templateList > 0 then templateList[math.random(#templateList)] else nil)
	local model = if template then template:Clone() else blockPerson()
	local box, size = model:GetBoundingBox()
	local feet = box * CFrame.new(0, -size.Y / 2, 0)
	local parts, rest, joints = {}, {}, {}
	for k, name in LIMBS do
		local p = model:FindFirstChild(name) :: BasePart
		p.Anchored = true
		p.CanCollide = false
		p.CanQuery = false -- suspension rays and cameras ignore walkers
		p.CanTouch = false
		p.CastShadow = true
		parts[k] = p
		rest[k] = feet:ToObjectSpace(p.CFrame)
		-- limbs hang from the top of their bounds, the head sits on the bottom of its bounds
		local up = if name == "Head" then -p.Size.Y / 2 else p.Size.Y / 2
		joints[k] = (rest[k] * CFrame.new(0, up, 0)).Position
	end
	model.Parent = pedFolder
	return {
		model = model,
		parts = parts,
		rest = rest,
		joints = joints,
		walk = walk,
		s = s,
		dir = if math.random() < 0.5 then 1 else -1,
		speed = 3.5 + math.random() * 2.5,
		pause = 0,
		phase = math.random() * math.pi * 2,
		yaw = 0,
		missed = false,
		hit = false,
	}
end

-- Feet at `here`, turning toward `face`, limbs swinging (legs and arms in opposition) while moving.
local moveParts: { BasePart } = {}
local moveCFrames: { CFrame } = {}
local function pose(ped: Ped, here: Vector3, face: Vector3, moving: boolean, dt: number)
	local targetYaw = math.atan2(-face.X, -face.Z)
	local turn = (targetYaw - ped.yaw + math.pi) % (2 * math.pi) - math.pi
	ped.yaw += turn * math.min(1, dt * 8)
	ped.phase += dt * (if moving then ped.speed * 1.7 else 0)
	local swing = math.sin(ped.phase) * (if moving then math.min(0.6, ped.speed * 0.09) else 0)
	local bob = if moving then math.abs(math.cos(ped.phase)) * 0.12 else 0
	local base = CFrame.new(here + Vector3.new(0, bob, 0)) * CFrame.Angles(0, ped.yaw, 0)
	local angles = { 0, 0, swing * 0.8, -swing * 0.8, -swing, swing }
	for k, p in ped.parts do
		local j = ped.joints[k]
		table.insert(moveParts, p)
		table.insert(moveCFrames, base * CFrame.new(j) * CFrame.Angles(angles[k], 0, 0) * CFrame.new(-j) * ped.rest[k])
	end
end

---------------------------------------------------------------------------- spawning locals

local function nearbyWalks(at: Vector3): { WalkMath.Walk }
	local out, seen = {}, {}
	local r = math.ceil(SPAWN_RADIUS / CELL)
	local cx, cz = math.floor(at.X / CELL), math.floor(at.Z / CELL)
	for i = cx - r, cx + r do
		for j = cz - r, cz + r do
			for _, w in buckets[bucketKey(i, j)] or {} do
				if not seen[w] then
					seen[w] = true
					table.insert(out, w)
				end
			end
		end
	end
	return out
end

local function trySpawn(at: Vector3)
	local options = nearbyWalks(at)
	if #options == 0 then
		return
	end
	local total = 0
	for _, w in options do
		total += w.weight
	end
	for _ = 1, 6 do -- a few tries to land in the ring between SPAWN_MIN and SPAWN_RADIUS
		local pick = math.random() * total
		local walk = options[#options]
		for _, w in options do
			pick -= w.weight
			if pick <= 0 then
				walk = w
				break
			end
		end
		local s = math.random() * walk.length
		local d = (WalkMath.at(walk, s) - at).Magnitude
		if d >= SPAWN_MIN and d <= SPAWN_RADIUS then
			table.insert(live, newPed(walk, s))
			return
		end
	end
end

---------------------------------------------------------------------------- ragdolls

local function ragdoll(ped: Ped, hitVelocity: Vector3)
	ped.hit = true
	local torso = ped.parts[1]
	for k, p in ped.parts do
		if k > 1 then
			-- a ball joint at each limb's joint, so they flop instead of scattering
			local world = torso.CFrame * (ped.rest[1]:Inverse() * CFrame.new(ped.joints[k]))
			local a0, a1 = Instance.new("Attachment"), Instance.new("Attachment")
			a0.CFrame = torso.CFrame:ToObjectSpace(world)
			a1.CFrame = p.CFrame:ToObjectSpace(world)
			a0.Parent, a1.Parent = torso, p
			local joint = Instance.new("BallSocketConstraint")
			joint.Attachment0, joint.Attachment1 = a0, a1
			joint.LimitsEnabled = true
			joint.UpperAngle = 70
			joint.Parent = p
		end
	end
	local fling = hitVelocity * 0.85 + Vector3.new(0, 22 + math.random() * 10, 0)
	local spin = Vector3.new(math.random() - 0.5, math.random() - 0.5, math.random() - 0.5) * 14
	for _, p in ped.parts do
		p.Anchored = false
		p.CanCollide = true
		p.AssemblyLinearVelocity = fling
		p.AssemblyAngularVelocity = spin
	end
	task.delay(RAGDOLL_TIME, function()
		for _, p in ped.parts do
			TweenService:Create(p, TweenInfo.new(0.6), { Transparency = 1 }):Play()
		end
		task.wait(0.7)
		ped.model:Destroy()
	end)
end

---------------------------------------------------------------------------- customers and thieves (from the server)

type Actor = { ped: Ped, path: WalkMath.Path, speed: number, t0: number, s0: number, dir: number, once: boolean }
local actors: { [number]: Actor } = {}

local function tag(model: Model, text: string, colour: Color3)
	local highlight = Instance.new("Highlight") -- an outline that shows through walls
	highlight.FillTransparency = 1
	highlight.OutlineColor = colour
	highlight.Parent = model
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromOffset(180, 44)
	gui.StudsOffset = Vector3.new(0, 4, 0)
	gui.AlwaysOnTop = true
	gui.MaxDistance = 600
	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = text
	label.TextScaled = true
	label.Font = Enum.Font.FredokaOne
	label.TextColor3 = colour
	label.TextStrokeTransparency = 0
	label.Parent = gui
	gui.Adornee = model:FindFirstChild("Head") :: BasePart
	gui.Parent = model
end

remote.OnClientEvent:Connect(function(kind: string, data: any)
	if kind == "Actor" then
		local path = WalkMath.path(data.points)
		local ped = newPed(path, data.s0, data.model)
		ped.speed = data.speed
		if data.kind == "thief" then
			tag(ped.model, "THIEF!", Color3.fromRGB(255, 70, 70))
		else
			tag(ped.model, "CUSTOMER", Color3.fromRGB(120, 255, 160))
		end
		actors[data.id] =
			{ ped = ped, path = path, speed = data.speed, t0 = data.t0, s0 = data.s0, dir = data.dir, once = data.once }
	elseif kind == "ActorGone" then
		local a = actors[data]
		if a then
			actors[data] = nil
			a.ped.model:Destroy()
		end
	end
end)

---------------------------------------------------------------------------- the loop

local spawnTimer = 0

RunService.Heartbeat:Connect(function(dt)
	local focus = camera.Focus.Position
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
	local riderPos = root and root.Position
	local riderVel = root and root.AssemblyLinearVelocity or Vector3.zero
	local speed = riderVel.Magnitude

	spawnTimer -= dt
	if spawnTimer <= 0 then
		spawnTimer = 0.25
		if #live < MAX_PEDS then
			trySpawn(focus)
		end
	end

	table.clear(moveParts)
	table.clear(moveCFrames)
	for i = #live, 1, -1 do
		local ped = live[i]
		local pos = WalkMath.at(ped.walk, ped.s)
		if (pos - focus).Magnitude > DESPAWN_RADIUS then
			ped.model:Destroy()
			table.remove(live, i)
			continue
		end
		if riderPos and math.abs(pos.Y - riderPos.Y) < 6 then
			local gap = (Vector3.new(pos.X, 0, pos.Z) - Vector3.new(riderPos.X, 0, riderPos.Z)).Magnitude
			if gap < HIT_RADIUS and speed >= Config.PedHitSpeed then
				table.remove(live, i)
				ragdoll(ped, riderVel)
				remote:FireServer("PedHit")
				continue
			elseif gap < Config.NearMissRange and speed >= Config.NearMissSpeed and not ped.missed then
				ped.missed = true -- counted when you pass, once per person (the server caps and checks it)
				task.delay(0.15, function()
					if not ped.hit then -- still standing: it really was a miss
						remote:FireServer("NearMiss")
					end
				end)
			end
		end

		-- walk, pause at the ends (and now and then), turn round
		local moving = ped.pause <= 0
		if moving then
			ped.s += ped.dir * ped.speed * dt
			if ped.s <= 0 or ped.s >= ped.walk.length then
				ped.s = math.clamp(ped.s, 0, ped.walk.length)
				ped.dir = -ped.dir
				ped.pause = 0.8 + math.random() * 2.5
			elseif math.random() < dt * 0.02 then
				ped.pause = 1.5 + math.random() * 3 -- stop to look at something
			end
		else
			ped.pause -= dt
		end
		local here, along = WalkMath.at(ped.walk, ped.s)
		pose(ped, here, along * ped.dir, moving, dt)
	end

	-- customers and thieves: where the server says they are now
	local now = workspace:GetServerTimeNow()
	for _, a in actors do
		local elapsed = math.max(0, now - a.t0)
		local s, dir = a.s0 + a.speed * elapsed, 1
		if a.once then
			s = math.min(s, a.path.length)
		else
			s, dir = WalkMath.pingPong(a.path.length, a.s0, a.dir, a.speed, elapsed)
		end
		local here, along = WalkMath.at(a.path, s)
		pose(a.ped, here, along * dir, not a.once or s < a.path.length, dt)
	end

	if #moveParts > 0 then
		workspace:BulkMoveTo(moveParts, moveCFrames, Enum.BulkMoveMode.FireCFrameChanged)
	end
end)
