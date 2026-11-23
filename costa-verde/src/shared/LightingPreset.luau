--!strict
-- Costa Verde look: South Florida latitude, humid haze, warm low sun, puffy cumulus, gentle bloom.
-- Studio (edit mode, once): require(game.ReplicatedStorage.Shared.LightingPreset).apply()
-- The day/night cycle runs in-game from ServerScriptService.DayNight.
local LightingPreset = {}

LightingPreset.MINUTES_PER_DAY = 32 -- real minutes for one in-game day

local function child(parent: Instance, class: string, name: string): any
	local c = parent:FindFirstChild(name) or Instance.new(class)
	c.Name = name
	c.Parent = parent
	return c
end

function LightingPreset.apply()
	local L = game:GetService("Lighting") :: any
	pcall(function()
		L.Technology = Enum.Technology.Future -- best Roblox lighting (only settable in Studio)
	end)
	L.GeographicLatitude = 26 -- South Florida
	L.ClockTime = 16.5 -- late afternoon gold
	L.Brightness = 3
	L.EnvironmentDiffuseScale, L.EnvironmentSpecularScale = 1, 1
	L.OutdoorAmbient = Color3.fromRGB(128, 122, 112)
	L.Ambient = Color3.fromRGB(70, 70, 76)
	L.ShadowSoftness = 0.25
	L.ExposureCompensation = 0.1
	local atm = child(L, "Atmosphere", "Humidity") -- thick, warm, bright haze off the water
	atm.Density, atm.Offset = 0.34, 0.2
	atm.Color, atm.Decay = Color3.fromRGB(206, 196, 176), Color3.fromRGB(118, 128, 148)
	atm.Glare, atm.Haze = 0.45, 1.8
	local cc = child(L, "ColorCorrectionEffect", "Grade")
	cc.Saturation, cc.Contrast, cc.Brightness = 0.12, 0.06, 0.01
	cc.TintColor = Color3.fromRGB(255, 247, 236)
	local bloom = child(L, "BloomEffect", "Bloom")
	bloom.Intensity, bloom.Size, bloom.Threshold = 0.55, 28, 1.6
	local rays = child(L, "SunRaysEffect", "SunRays")
	rays.Intensity, rays.Spread = 0.05, 0.6
	local clouds = child(workspace.Terrain, "Clouds", "Cumulus")
	clouds.Cover, clouds.Density = 0.52, 0.62
	clouds.Color = Color3.fromRGB(250, 248, 244)
end

-- In-game: advance the clock (called by ServerScriptService.DayNight).
function LightingPreset.runCycle()
	local L = game:GetService("Lighting") :: any
	local RunService = game:GetService("RunService")
	RunService.Heartbeat:Connect(function(dt: number)
		L.ClockTime = (L.ClockTime + dt * 24 / (LightingPreset.MINUTES_PER_DAY * 60)) % 24
	end)
end

return LightingPreset
