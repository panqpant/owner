-- Room lights in the detailed block: on at night (a different share of rooms each night), off by day.
local Lighting = game:GetService("Lighting")
local BlockImporter = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("BlockImporter"))
local wasNight, night = nil, 0
while true do
	local t = Lighting.ClockTime
	local isNight = t >= 18.6 or t < 6.2
	if isNight ~= wasNight then
		if isNight then
			night += 1
		end
		BlockImporter.setNight(isNight, night)
		wasNight = isNight
	end
	task.wait(5)
end
