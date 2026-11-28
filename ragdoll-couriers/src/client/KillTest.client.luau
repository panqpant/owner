-- Ragdoll Couriers kill test (client): drives the scooter, plays the ragdoll, shows the HUD.
-- The scooter is a raycast "hover" vehicle: four suspension rays, arcade grip and steering.
-- That keeps the feel fully tunable from Config instead of fighting wheel constraints.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local ContextActionService = game:GetService("ContextActionService")
local TweenService = game:GetService("TweenService")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local remote = ReplicatedStorage:WaitForChild("Couriers") :: RemoteEvent
local player = Players.LocalPlayer
local controls = require(player:WaitForChild("PlayerScripts"):WaitForChild("PlayerModule")):GetControls()
local camera = workspace.CurrentCamera

local presetIndex = Config.DefaultPreset
local tune = Config.Presets[presetIndex]
local ragdolled = false
local gasHeld, brakeHeld = false, false
local job: { parcelId: string, to: string, zone: BasePart }? = nil
local cleanCombo = 0

---------------------------------------------------------------------------- UI helpers

local function make(class: string, props: { [string]: any }, children: { Instance }?): any
	local inst = Instance.new(class)
	for k, v in props do
		if k ~= "Parent" then
			(inst :: any)[k] = v
		end
	end
	for _, child in children or {} do
		child.Parent = inst
	end
	inst.Parent = props.Parent
	return inst
end

local function corner(r: number)
	return make("UICorner", { CornerRadius = UDim.new(0, r) })
end
local function stroke(t: number)
	return make(
		"UIStroke",
		{ Thickness = t, Color = Color3.new(0, 0, 0), ApplyStrokeMode = Enum.ApplyStrokeMode.Border }
	)
end

local function text(props: { [string]: any }): TextLabel
	props.BackgroundTransparency = props.BackgroundTransparency or 1
	props.Font = Enum.Font.FredokaOne
	props.TextColor3 = props.TextColor3 or Color3.new(1, 1, 1)
	props.TextStrokeTransparency = 0
	props.TextScaled = true
	return make("TextLabel", props)
end

local gui = make(
	"ScreenGui",
	{ Name = "KillTestHud", ResetOnSpawn = false, IgnoreGuiInset = false, Parent = player:WaitForChild("PlayerGui") }
)

local coinsLabel = text({
	Size = UDim2.fromOffset(260, 46),
	Position = UDim2.new(0.5, -130, 0, 8),
	Text = "COINS 0",
	TextColor3 = Color3.fromRGB(255, 220, 80),
	Parent = gui,
})

local card = make(
	"Frame",
	{
		Size = UDim2.fromOffset(250, 92),
		Position = UDim2.fromOffset(12, 60),
		BackgroundColor3 = Color3.fromRGB(30, 30, 45),
		BackgroundTransparency = 0.15,
		Parent = gui,
	},
	{ corner(12), stroke(3) }
)
local jobLabel = text({
	Size = UDim2.new(1, -16, 0, 30),
	Position = UDim2.fromOffset(8, 6),
	Text = "",
	TextXAlignment = Enum.TextXAlignment.Left,
	Parent = card,
})
local barBack = make(
	"Frame",
	{
		Size = UDim2.new(1, -16, 0, 22),
		Position = UDim2.fromOffset(8, 40),
		BackgroundColor3 = Color3.fromRGB(60, 20, 20),
		Parent = card,
	},
	{ corner(8) }
)
local barFill = make(
	"Frame",
	{ Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.fromRGB(90, 230, 110), Parent = barBack },
	{ corner(8) }
)
local condLabel = text({ Size = UDim2.fromScale(1, 1), Text = "100%", ZIndex = 2, Parent = barBack })
local distLabel = text({
	Size = UDim2.new(1, -16, 0, 20),
	Position = UDim2.fromOffset(8, 66),
	Text = "",
	TextXAlignment = Enum.TextXAlignment.Left,
	TextColor3 = Color3.fromRGB(200, 200, 220),
	Parent = card,
})

local popup = text({
	Size = UDim2.new(0.8, 0, 0, 90),
	Position = UDim2.new(0.1, 0, 0.22, 0),
	Text = "",
	Visible = false,
	Parent = gui,
})
local breakdown = text({
	Size = UDim2.new(0.6, 0, 0, 80),
	Position = UDim2.new(0.2, 0, 0.22, 95),
	Text = "",
	Visible = false,
	TextColor3 = Color3.fromRGB(230, 230, 240),
	Parent = gui,
})

local function button(label: string, color: Color3, size: UDim2, pos: UDim2): TextButton
	local b = make(
		"TextButton",
		{
			Size = size,
			Position = pos,
			BackgroundColor3 = color,
			Text = label,
			Font = Enum.Font.FredokaOne,
			TextScaled = true,
			TextColor3 = Color3.new(1, 1, 1),
			AutoButtonColor = true,
			Parent = gui,
		},
		{ corner(16), stroke(3) }
	)
	make(
		"UIPadding",
		{
			PaddingTop = UDim.new(0, 8),
			PaddingBottom = UDim.new(0, 8),
			PaddingLeft = UDim.new(0, 8),
			PaddingRight = UDim.new(0, 8),
			Parent = b,
		}
	)
	return b
end

local feelButton =
	button("Feel: " .. tune.name, Color3.fromRGB(110, 90, 220), UDim2.fromOffset(170, 44), UDim2.new(1, -182, 0, 60))
local resetButton =
	button("Reset (R)", Color3.fromRGB(90, 90, 110), UDim2.fromOffset(170, 44), UDim2.new(1, -182, 0, 112))
feelButton.Activated:Connect(function()
	presetIndex = presetIndex % #Config.Presets + 1
	tune = Config.Presets[presetIndex]
	feelButton.Text = "Feel: " .. tune.name
end)
resetButton.Activated:Connect(function()
	remote:FireServer("Reset")
end)
UserInputService.InputBegan:Connect(function(input, processed)
	if not processed and input.KeyCode == Enum.KeyCode.R then
		remote:FireServer("Reset")
	end
end)

-- Big thumb buttons on phones (plan: mobile first). Keyboard and gamepad use the normal move input.
if UserInputService.TouchEnabled then
	local gas = button("GO", Color3.fromRGB(60, 200, 90), UDim2.fromOffset(130, 130), UDim2.new(1, -150, 1, -170))
	local brake = button("STOP", Color3.fromRGB(220, 70, 70), UDim2.fromOffset(100, 100), UDim2.new(1, -270, 1, -140))
	gas.InputBegan:Connect(function(i)
		if i.UserInputType == Enum.UserInputType.Touch then
			gasHeld = true
		end
	end)
	gas.InputEnded:Connect(function(i)
		if i.UserInputType == Enum.UserInputType.Touch then
			gasHeld = false
		end
	end)
	brake.InputBegan:Connect(function(i)
		if i.UserInputType == Enum.UserInputType.Touch then
			brakeHeld = true
		end
	end)
	brake.InputEnded:Connect(function(i)
		if i.UserInputType == Enum.UserInputType.Touch then
			brakeHeld = false
		end
	end)
end

coinsLabel.Text = "COINS 0"
task.spawn(function()
	local coins = player:WaitForChild("leaderstats"):WaitForChild("Coins") :: IntValue
	local function show()
		coinsLabel.Text = "COINS " .. coins.Value
	end
	show()
	coins.Changed:Connect(show)
end)

---------------------------------------------------------------------------- juice

local function sound(id: string, speed: number?)
	local s = make("Sound", { SoundId = id, Volume = 0.8, PlaybackSpeed = speed or 1, Parent = gui })
	s:Play()
	s.Ended:Once(function()
		s:Destroy()
	end)
	task.delay(5, function()
		s:Destroy()
	end)
end

local shake = 0
RunService:BindToRenderStep("CourierShake", Enum.RenderPriority.Camera.Value + 1, function(dt)
	if shake > 0.01 then
		local r = Random.new()
		camera.CFrame *= CFrame.Angles(r:NextNumber(-1, 1) * shake * 0.03, r:NextNumber(-1, 1) * shake * 0.03, 0)
		shake = math.max(0, shake - dt * 4)
	end
end)

local popupToken = 0
local function showPopup(main: string, sub: string?, color: Color3?, seconds: number?)
	popupToken += 1
	local token = popupToken
	popup.Text = main
	popup.TextColor3 = color or Color3.new(1, 1, 1)
	popup.Visible = true
	popup.Size = UDim2.new(0.8, 0, 0, 40)
	TweenService:Create(popup, TweenInfo.new(0.25, Enum.EasingStyle.Back), { Size = UDim2.new(0.8, 0, 0, 90) }):Play()
	breakdown.Text = sub or ""
	breakdown.Visible = sub ~= nil
	task.delay(seconds or 2, function()
		if token == popupToken then
			popup.Visible = false
			breakdown.Visible = false
		end
	end)
end

local CRASH_WORDS = { "OOF!", "BONK!", "YEET!", "SPLAT!", "WHOOPS!" }

---------------------------------------------------------------------------- vehicle lookup

local function myVehicle(): (Model?, BasePart?, Seat?)
	local folder = workspace:FindFirstChild("Vehicles")
	local model = folder and folder:FindFirstChild(player.Name)
	if not model then
		return nil
	end
	return model, model:FindFirstChild("Body") :: BasePart?, model:FindFirstChild("Seat") :: Seat?
end

local function myHumanoid(): Humanoid?
	return player.Character and player.Character:FindFirstChildOfClass("Humanoid")
end

local function seated(): boolean
	local humanoid = myHumanoid()
	local _, _, seat = myVehicle()
	return humanoid ~= nil and seat ~= nil and humanoid.SeatPart == seat
end

-- Jumping out of the seat by accident ruins a run on a phone, so block it while riding.
ContextActionService:BindActionAtPriority("CourierNoJump", function()
	return if seated() and not ragdolled then Enum.ContextActionResult.Sink else Enum.ContextActionResult.Pass
end, false, Enum.ContextActionPriority.High.Value, Enum.PlayerActions.CharacterJump)
RunService.RenderStepped:Connect(function()
	local touchGui = player.PlayerGui:FindFirstChild("TouchGui")
	local jump = touchGui and touchGui:FindFirstChild("JumpButton", true)
	if jump then
		(jump :: GuiObject).Visible = not seated()
	end
end)

---------------------------------------------------------------------------- driving physics

local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Exclude

RunService.PreSimulation:Connect(function(dt)
	local model, body = myVehicle()
	if not model or not body or ragdolled or not seated() then
		return
	end
	rayParams.FilterDescendantsInstances =
		{ model, player.Character :: Instance, workspace:FindFirstChild("Parcels") :: Instance }

	local mass = body.AssemblyMass
	local g = workspace.Gravity
	local rh = Config.RideHeight
	local k = (mass * g / 4) / (0.4 * rh) * tune.stiffness -- per ray; rests at ~40% compression
	local c = tune.damping * 2 * math.sqrt(k * mass / 4)
	local cf = body.CFrame
	local up = cf.UpVector

	local grounded = 0
	local normal = Vector3.zero
	for i = 1, 4 do
		local a = body:FindFirstChild("Ray" .. i) :: Attachment
		local origin = a.WorldPosition
		local hit = workspace:Raycast(origin, -up * (rh + 0.6), rayParams)
		if hit then
			local compression = rh - hit.Distance
			if compression > 0 then
				local vUp = body:GetVelocityAtPosition(origin):Dot(up)
				local force = math.max(0, k * compression - c * vUp)
				body:ApplyImpulseAtPosition(up * force * dt, origin)
			end
			grounded += 1
			normal += hit.Normal
		end
	end

	local move = controls:GetMoveVector()
	local throttle = if gasHeld then 1 elseif brakeHeld then -1 else -move.Z
	local steer = move.X
	local v = body.AssemblyLinearVelocity
	local av = body.AssemblyAngularVelocity
	local look, right = cf.LookVector, cf.RightVector

	if grounded > 0 then
		local frac = grounded / 4
		local vf = v:Dot(look)
		local vl = v:Dot(right)
		local dvF
		if throttle > 0.05 then
			dvF = if vf < 0
				then math.min(tune.brake * dt, -vf)
				else math.clamp(tune.maxSpeed * throttle - vf, -tune.brake * dt, tune.accel * dt)
		elseif throttle < -0.05 then
			dvF = if vf > 1
				then -math.min(tune.brake * dt, vf)
				else math.max(-tune.accel * dt, -tune.reverseSpeed * -throttle - vf)
		else
			dvF = -math.sign(vf) * math.min(math.abs(vf), 8 * dt) -- coasting drag
		end
		local dvL = -vl * math.min(1, tune.grip * dt)
		body.AssemblyLinearVelocity = v + look * dvF * frac + right * dvL * frac

		-- Steering: blend the yaw rate toward the target; no steering when stopped.
		local yaw = av:Dot(up)
		local target = -steer * tune.turnRate * math.clamp(math.abs(vf) / 12, 0, 1) * math.sign(vf)
		av += up * ((target - yaw) * math.min(1, 10 * dt))
	end

	-- Self-righting toward the ground (or straight up in the air). Past the limit it gives up: you fall.
	local targetUp = if grounded > 0 then normal.Unit else Vector3.yAxis
	local axis = up:Cross(targetUp)
	local angle = math.asin(math.clamp(axis.Magnitude, 0, 1))
	if math.deg(angle) < tune.uprightLimit then
		local nonYaw = av - up * av:Dot(up)
		local correct = if axis.Magnitude > 1e-4 then axis.Unit * angle * tune.upright else Vector3.zero
		av = av - nonYaw + nonYaw:Lerp(correct, math.min(1, dt * (if grounded > 0 then 6 else 2)))
	end
	body.AssemblyAngularVelocity = av

	-- Speed FOV: feels faster without being faster.
	camera.FieldOfView += ((70 + math.min(v.Magnitude, 80) * 0.18) - camera.FieldOfView) * math.min(1, dt * 4)
end)

---------------------------------------------------------------------------- guide + parcel label

local guideBeam: Beam? = nil
local guideA0: Attachment? = nil
local parcelGui: BillboardGui? = nil

local function updateGuide()
	local _, body = myVehicle()
	if not job or not body then
		return
	end
	if not guideA0 or guideA0.Parent ~= body then
		if guideA0 then
			guideA0:Destroy()
		end
		guideA0 = make("Attachment", { Position = Vector3.new(0, 3, 0), Parent = body })
	end
	local zone = job.zone
	local a1 = zone:FindFirstChild("GuideTarget") :: Attachment?
		or make("Attachment", { Name = "GuideTarget", Parent = zone })
	if not guideBeam then
		guideBeam = make("Beam", {
			Color = ColorSequence.new(Color3.fromRGB(90, 255, 140)),
			LightEmission = 1,
			Width0 = 0.6,
			Width1 = 0.6,
			FaceCamera = true,
			Transparency = NumberSequence.new(0.3),
			Parent = workspace,
		})
	end
	local beam = guideBeam :: Beam
	beam.Attachment0, beam.Attachment1 = guideA0, a1
	distLabel.Text = math.floor((body.Position - zone.Position).Magnitude / 3.6) .. " m to go"
end

local function attachParcelGui()
	local parcels = workspace:FindFirstChild("Parcels")
	local parcel = parcels and parcels:FindFirstChild(player.Name) :: BasePart?
	if not parcel then
		return
	end
	if parcelGui and parcelGui.Parent == parcel then
		return
	end
	if parcelGui then
		parcelGui:Destroy()
	end
	local bb = make(
		"BillboardGui",
		{ Size = UDim2.fromOffset(90, 40), StudsOffset = Vector3.new(0, 2.5, 0), AlwaysOnTop = true, Parent = parcel }
	)
	local label = text({ Size = UDim2.fromScale(1, 1), Text = "100%", Parent = bb })
	local function show()
		local cond = parcel:GetAttribute("Condition") or 100
		label.Text = cond .. "%"
		label.TextColor3 = if cond > 60
			then Color3.fromRGB(120, 255, 140)
			elseif cond > 25 then Color3.fromRGB(255, 210, 80)
			else Color3.fromRGB(255, 80, 80)
		barFill.Size = UDim2.fromScale(math.clamp(cond / 100, 0, 1), 1)
		barFill.BackgroundColor3 = label.TextColor3
		condLabel.Text = cond .. "%"
	end
	show()
	parcel:GetAttributeChangedSignal("Condition"):Connect(show)
	parcelGui = bb
end

RunService.Heartbeat:Connect(function()
	updateGuide()
	attachParcelGui()
end)

---------------------------------------------------------------------------- server messages

local savedCollide: { [BasePart]: boolean } = {}
player.CharacterAdded:Connect(function()
	ragdolled = false
	table.clear(savedCollide)
end)

remote.OnClientEvent:Connect(function(kind: string, data: any)
	if kind == "Job" then
		job = data
		local def = Config.Parcels[data.parcelId]
		jobLabel.Text = "Deliver: " .. def.name .. " → " .. (data.label or data.to)
		if data.kind == "customer" then
			showPopup(
				"CUSTOMER ON FOOT!",
				"Follow the beam: they're walking. Hand it over up close.",
				Color3.fromRGB(120, 255, 160),
				3
			)
		elseif def.fragility >= 1 then
			showPopup("FRAGILE!", "Slow down on bumps.", Color3.fromRGB(255, 200, 80), 2.5)
		end
	elseif kind == "Hit" then
		shake = math.min(1, shake + data / 15)
		sound(Config.Sounds.hit, 1 + math.random() * 0.3)
		if parcelGui then
			local label = parcelGui:FindFirstChildOfClass("TextLabel") :: TextLabel
			label.TextColor3 = Color3.fromRGB(255, 40, 40)
			label.Size = UDim2.fromScale(1.4, 1.4)
			TweenService:Create(label, TweenInfo.new(0.2), { Size = UDim2.fromScale(1, 1) }):Play()
		end
	elseif kind == "Ragdoll" then
		local character = player.Character
		local humanoid = myHumanoid()
		local root = character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
		if not character or not humanoid or not root then
			return
		end
		ragdolled = true
		cleanCombo = 0
		humanoid:ChangeState(Enum.HumanoidStateType.Physics)
		for _, p in character:GetDescendants() do
			if p:IsA("BasePart") and p ~= root then
				savedCollide[p] = p.CanCollide
				p.CanCollide = true
			end
		end
		root.AssemblyLinearVelocity = data
		root:ApplyAngularImpulse(
			Vector3.new(math.random(-1, 1), math.random(-1, 1), math.random(-1, 1)) * root.AssemblyMass * 20
		)
		shake = 1
		camera.FieldOfView = 90
		sound(Config.Sounds.crash, 0.9 + math.random() * 0.3)
		showPopup(CRASH_WORDS[math.random(#CRASH_WORDS)], nil, Color3.fromRGB(255, 120, 80), 1.2)
	elseif kind == "Recover" then
		for p, was in savedCollide do
			if p.Parent then
				p.CanCollide = was
			end
		end
		table.clear(savedCollide)
		local humanoid = myHumanoid()
		if humanoid then
			humanoid:ChangeState(Enum.HumanoidStateType.GettingUp)
		end
		ragdolled = false
	elseif kind == "Delivered" then
		cleanCombo = if data.cleanBonus > 0 then cleanCombo + 1 else 0
		sound(Config.Sounds.deliver, 1 + math.min(cleanCombo, 8) * 0.08) -- rising pitch on a clean streak
		local lines = { data.name .. " at " .. data.condition .. "%: " .. data.base }
		if data.speedBonus > 0 then
			table.insert(lines, "Speedy +" .. data.speedBonus)
		end
		if data.cleanBonus > 0 then
			table.insert(lines, "No crash +" .. data.cleanBonus)
		end
		if (data.handoffBonus or 0) > 0 then
			table.insert(lines, "In person +" .. data.handoffBonus)
		end
		showPopup("+" .. data.total .. " COINS", table.concat(lines, "\n"), Color3.fromRGB(255, 220, 80), 3)
		coinsLabel.Size = UDim2.fromOffset(320, 60)
		TweenService:Create(coinsLabel, TweenInfo.new(0.4, Enum.EasingStyle.Back), { Size = UDim2.fromOffset(260, 46) })
			:Play()
	elseif kind == "Lost" then
		showPopup(data, nil, Color3.fromRGB(255, 90, 90), 2)
	elseif kind == "Bonus" then
		sound(Config.Sounds.deliver, 1.4)
		showPopup(data, nil, Color3.fromRGB(255, 220, 80), 1.2)
	end
end)
