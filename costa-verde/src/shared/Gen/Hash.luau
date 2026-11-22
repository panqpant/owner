--!strict
-- Deterministic integer hashing + RNG. Pure Luau (no Roblox APIs) so the same seed gives
-- the same world in Roblox and in Lune previews.

local Hash = {}

local TWO32 = 4294967296

-- 32-bit multiply without losing precision in doubles (split a into 16-bit halves).
local function mul32(a: number, b: number): number
	local hi = bit32.rshift(a, 16)
	local lo = bit32.band(a, 0xFFFF)
	return ((hi * b % 65536) * 65536 + lo * b) % TWO32
end

function Hash.int(a: number, b: number?, c: number?): number
	local h = bit32.bxor(mul32(bit32.band(a, 0xFFFFFFFF), 0x9E3779B1), mul32(bit32.band(b or 0, 0xFFFFFFFF), 0x85EBCA77))
	h = bit32.bxor(h, mul32(bit32.band(c or 0, 0xFFFFFFFF), 0xC2B2AE3D))
	h = mul32(bit32.bxor(h, bit32.rshift(h, 15)), 0x2C1B3C6D)
	h = mul32(bit32.bxor(h, bit32.rshift(h, 12)), 0x297A2D39)
	return bit32.bxor(h, bit32.rshift(h, 15))
end

-- Hash to [0, 1).
function Hash.float(a: number, b: number?, c: number?): number
	return Hash.int(a, b, c) / TWO32
end

export type Rng = {
	next: (self: Rng) -> number,
	range: (self: Rng, lo: number, hi: number) -> number,
	int: (self: Rng, lo: number, hi: number) -> number,
	pick: <T>(self: Rng, list: { T }) -> T,
	seed: number,
	n: number,
}

local RngMeta = {}
RngMeta.__index = RngMeta

function RngMeta.next(self: Rng): number
	self.n += 1
	return Hash.float(self.seed, self.n, 0x5EED)
end

function RngMeta.range(self: Rng, lo: number, hi: number): number
	return lo + (hi - lo) * self:next()
end

function RngMeta.int(self: Rng, lo: number, hi: number): number
	return lo + math.floor(self:next() * (hi - lo + 1))
end

function RngMeta.pick<T>(self: Rng, list: { T }): T
	return list[1 + math.floor(self:next() * #list)]
end

function Hash.rng(seed: number): Rng
	return (setmetatable({ seed = seed, n = 0 }, RngMeta) :: any) :: Rng
end

return Hash
