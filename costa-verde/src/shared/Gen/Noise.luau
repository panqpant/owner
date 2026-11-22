--!strict
-- Seeded 2D value noise + fractal sum. Not math.noise: that one doesn't exist outside Roblox.
local Hash = require("./Hash")

local Noise = {}

local function smooth(t: number): number
	return t * t * (3 - 2 * t)
end

-- Value noise in [-1, 1].
function Noise.value(x: number, y: number, seed: number): number
	local ix, iy = math.floor(x), math.floor(y)
	local fx, fy = smooth(x - ix), smooth(y - iy)
	local a = Hash.float(ix, iy, seed)
	local b = Hash.float(ix + 1, iy, seed)
	local c = Hash.float(ix, iy + 1, seed)
	local d = Hash.float(ix + 1, iy + 1, seed)
	local top = a + (b - a) * fx
	local bottom = c + (d - c) * fx
	return (top + (bottom - top) * fy) * 2 - 1
end

-- Fractal sum, roughly in [-1, 1].
function Noise.fbm(x: number, y: number, seed: number, octaves: number?): number
	local total, amp, freq, norm = 0, 1, 1, 0
	for i = 1, octaves or 4 do
		total += Noise.value(x * freq, y * freq, seed + i * 101) * amp
		norm += amp
		amp *= 0.5
		freq *= 2
	end
	return total / norm
end

return Noise
