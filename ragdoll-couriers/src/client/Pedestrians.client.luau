-- Pedestrians (client only): locals stroll the pavement walks from art/map/walks.py around the player,
-- limbs swinging. Clip one at speed and they ragdoll and fly; a few seconds later they're recycled.
-- Everything is local to each player: no Humanoids, no network, a couple of hundred anchored parts.
--
-- Models: ReplicatedStorage.PedAssets.Ped_* (import art/export/Ped_*.fbx there: six MeshParts each,
-- named Torso, Head, LArm, RArm, LLeg, RLeg, front facing -Z). Until then, block people stand in.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Walks = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Walks"))
local player = Players.LocalPlayer
local camera = workspace.CurrentCamera

local MAX_PEDS = 36
local SPAWN_RADIUS = 240 -- spawn somewhere on a walk within this of the camera...
local SPAWN_MIN = 70 -- ...but not right under the player's nose
local DESPAWN_RADIUS = 320
local CELL = 120 -- spatial buckets for finding walks near the camera
local HIT_RADIUS = 4.5
local HIT_SPEED = 10 -- studs/s of rider speed needed to send someone flying
local RAGDOLL_TIME = 6
local LIMBS = { "Torso", "Head", "LArm", "RArm", "LLeg", "RLeg" }

local city = workspace:WaitForChild("City")
local origin = (city:GetAttribute("Origin") :: Vector3?) or Vector3.zero

---------------------------------------------------------------------------- walks, measured and bucketed

type Walk = { points: { Vector3 }, cum: { number }, length: number, weight: number }
local walks: { Walk } = {}
local buckets: { [number]: { Walk } } = {}

local function bucketKey(i: number, j: number): number
	return (i + 1000) * 10000 + (j + 1000) -- numbers, not Vector2: userdata keys compare by identity
end

for _, w in Walks.walks do
	local pts, cum = {}, { 0 }
	for k, p in w.p do
		pts[k] = origin + Vector3.new(p[1], p[2], p[3])
		if k > 1 then
			cum[k] = cum[k - 1] + (pts[k] - pts[k - 1]).Magnitude
		end
	end
	local walk: Walk = { points = pts, cum = cum, length = cum[#cum], weight = (Walks.density[w.d] or 1) * cum[#cum] }
	table.insert(walks, walk)
	local seen = {}
	for _, p in pts do
		local key = bucketKey(math.floor(p.X / CELL), math.floor(p.Z / CELL))
		if not seen[key] then
			seen[key] = true
			buckets[key] = buckets[key] or {}
			table.insert(buckets[key], walk)
		end
	end
end

local function pointAt(walk: Walk, s: number): (Vector3, Vector3)
	local cum, pts = walk.cum, walk.points
	for k = 2, #pts do
		if s <= cum[k] or k == #pts then
			local seg = cum[k] - cum[k - 1]
			local a = if seg > 0 then math.clamp((s - cum[k - 1]) / seg, 0, 1) else 0
			local dir = pts[k] - pts[k - 1]
			return pts[k - 1]:Lerp(pts[k], a), if dir.Magnitude > 0 then dir.Unit else Vector3.zAxis
		end
	end
	return pts[1], Vector3.zAxis
end

---------------------------------------------------------------------------- people

type Ped = {
	model: Model,
	parts: { BasePart },
	rest: { CFrame }, -- each part relative to the feet, standing still
	joints: { Vector3 }, -- each part's joint in the same frame (limbs hang from it)
	walk: Walk,
	s: number,
	dir: number,
	speed: number,
	pause: number,
	phase: number,
	yaw: number,
}

local templates: { Model } = {}
local folder = ReplicatedStorage:FindFirstChild("PedAssets")
if folder then
	for _, m in folder:GetChildren() do
		if m:IsA("Model") and m:FindFirstChild("Torso") then
			table.insert(templates, m)
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

local function newPed(walk: Walk, s: number): Ped
	local model = if #templates > 0 then templates[math.random(#templates)]:Clone() else blockPerson()
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
	}
end

---------------------------------------------------------------------------- spawning

local function nearbyWalks(at: Vector3): { Walk }
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
		local pos = pointAt(walk, s)
		local d = (pos - at).Magnitude
		if d >= SPAWN_MIN and d <= SPAWN_RADIUS then
			table.insert(live, newPed(walk, s))
			return
		end
	end
end

---------------------------------------------------------------------------- ragdolls

local function ragdoll(ped: Ped, hitVelocity: Vector3)
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

---------------------------------------------------------------------------- the loop

local spawnTimer = 0
local moveParts: { BasePart } = {}
local moveCFrames: { CFrame } = {}

RunService.Heartbeat:Connect(function(dt)
	local focus = camera.Focus.Position
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
	local riderPos = root and root.Position
	local riderVel = root and root.AssemblyLinearVelocity or Vector3.zero
	local fast = riderVel.Magnitude >= HIT_SPEED

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
		local pos = pointAt(ped.walk, ped.s)
		if (pos - focus).Magnitude > DESPAWN_RADIUS then
			ped.model:Destroy()
			table.remove(live, i)
			continue
		end
		if
			fast
			and riderPos
			and (Vector3.new(pos.X, 0, pos.Z) - Vector3.new(riderPos.X, 0, riderPos.Z)).Magnitude < HIT_RADIUS
			and math.abs(pos.Y - riderPos.Y) < 6
		then
			table.remove(live, i)
			ragdoll(ped, riderVel)
			continue
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
		local here, along = pointAt(ped.walk, ped.s)
		local face = along * ped.dir
		local targetYaw = math.atan2(-face.X, -face.Z)
		local turn = (targetYaw - ped.yaw + math.pi) % (2 * math.pi) - math.pi
		ped.yaw += turn * math.min(1, dt * 8)

		-- limbs: legs and arms swing in opposition while walking, settle while standing
		ped.phase += dt * (if moving then ped.speed * 1.7 else 0)
		local amount = if moving then 0.6 else 0
		local swing = math.sin(ped.phase) * amount
		local bob = if moving then math.abs(math.cos(ped.phase)) * 0.12 else 0
		local base = CFrame.new(here + Vector3.new(0, bob, 0)) * CFrame.Angles(0, ped.yaw, 0)
		local angles = { 0, 0, swing * 0.8, -swing * 0.8, -swing, swing }
		for k, p in ped.parts do
			local j = ped.joints[k]
			local cf = base * CFrame.new(j) * CFrame.Angles(angles[k], 0, 0) * CFrame.new(-j) * ped.rest[k]
			table.insert(moveParts, p)
			table.insert(moveCFrames, cf)
		end
	end
	if #moveParts > 0 then
		workspace:BulkMoveTo(moveParts, moveCFrames, Enum.BulkMoveMode.FireCFrameChanged)
	end
end)
