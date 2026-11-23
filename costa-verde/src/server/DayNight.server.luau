-- Runs the day/night cycle (see ReplicatedStorage.Shared.LightingPreset).
local LightingPreset = require(game:GetService("ReplicatedStorage"):WaitForChild("Shared"):WaitForChild("LightingPreset"))
LightingPreset.runCycle()
