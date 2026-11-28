-- Run with: lune run tests/formula.spec.luau
local Formula = require("../src/shared/Formula")

local function eq(a, b, what)
	assert(a == b, `{what}: expected {b}, got {a}`)
end

-- damage
eq(Formula.impactDamage(10, 1.2, 22, 0.6), 0, "below tolerance is free")
eq(Formula.impactDamage(32, 1, 22, 0.5), 5, "linear above tolerance")

-- payout
local p = Formula.payout(300, 50, 10, 20, false, 0.2, 0.25)
eq(p.base, 150, "half condition, half pay")
eq(p.speedBonus, 30, "speed bonus")
eq(p.cleanBonus, 38, "clean bonus rounds")
eq(p.total, 218, "total")

local slow = Formula.payout(300, 100, 30, 20, true, 0.2, 0.25)
eq(slow.total, 300, "no bonuses when slow and crashed")

local ruined = Formula.payout(300, -5, 1, 20, false, 0.2, 0.25)
eq(ruined.total, 0, "ruined parcel pays nothing, no bonuses")

print("formula: all tests passed")
