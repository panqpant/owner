-- Builds a player's scooter. The client drives it (raycast suspension); the server owns everything else.
local World = require(script.Parent.World)
local part, vehiclesFolder = World.part, World.vehiclesFolder

---------------------------------------------------------------------------- vehicle

local function weld(a: BasePart, b: BasePart)
	local w = Instance.new("WeldConstraint")
	w.Part0, w.Part1 = a, b
	w.Parent = a
end

local function buildScooter(owner: Player, at: CFrame): Model
	local model = Instance.new("Model")
	model.Name = owner.Name
	local body = part({
		Name = "Body",
		Size = Vector3.new(2.4, 0.8, 5.6),
		CFrame = at,
		Color = Color3.fromRGB(255, 90, 60),
		Parent = model,
	})
	body.Anchored = false
	body.CustomPhysicalProperties = PhysicalProperties.new(1.5, 0.3, 0.2)
	model.PrimaryPart = body

	local function piece(
		name: string,
		size: Vector3,
		offset: CFrame,
		color: Color3,
		props: { [string]: any }?
	): BasePart
		local p = part({
			Name = name,
			Size = size,
			CFrame = at * offset,
			Color = color,
			Parent = model,
			CanCollide = false,
			Massless = true,
		})
		p.Anchored = false
		for k, v in props or {} do
			(p :: any)[k] = v
		end
		weld(body, p)
		return p
	end

	local wheelColor = Color3.fromRGB(30, 30, 30)
	piece(
		"FrontWheel",
		Vector3.new(0.6, 1.8, 1.8),
		CFrame.new(0, -0.9, -2.4),
		wheelColor,
		{ Shape = Enum.PartType.Cylinder }
	)
	piece(
		"RearWheel",
		Vector3.new(0.6, 1.8, 1.8),
		CFrame.new(0, -0.9, 2.4),
		wheelColor,
		{ Shape = Enum.PartType.Cylinder }
	)
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
	for i, offset in
		{
			Vector3.new(-1, -0.4, -2.4),
			Vector3.new(1, -0.4, -2.4),
			Vector3.new(-1, -0.4, 2.4),
			Vector3.new(1, -0.4, 2.4),
		}
	do
		local a = Instance.new("Attachment")
		a.Name = "Ray" .. i
		a.Position = offset
		a.Parent = body
	end

	model.Parent = vehiclesFolder
	body:SetNetworkOwner(owner)
	return model
end

return {
	weld = weld,
	buildScooter = buildScooter,
}
