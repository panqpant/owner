-- Ragdolls the rider's own avatar: ball sockets sit ready on every joint and a crash swaps them in.

---------------------------------------------------------------------------- ragdoll

-- Ball sockets sit ready on every joint; a crash swaps the motors for them.
local function rigRagdoll(character: Model)
	local humanoid = character:FindFirstChildOfClass("Humanoid") :: Humanoid
	humanoid.BreakJointsOnDeath = false
	for _, motor in character:GetDescendants() do
		if
			motor:IsA("Motor6D")
			and motor.Name ~= "Root"
			and motor.Name ~= "RootJoint"
			and motor.Part0
			and motor.Part1
		then
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

return {
	rigRagdoll = rigRagdoll,
	setRagdoll = setRagdoll,
}
