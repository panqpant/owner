-- Pure game maths: no Roblox APIs, so tests/formula.spec.luau runs it in Lune.

local Formula = {}

-- Condition points (0-100) lost from one impact.
function Formula.impactDamage(impact: number, fragility: number, tolerance: number, scale: number): number
	return math.max(0, impact - tolerance) * fragility * scale
end

export type Payout = { total: number, base: number, speedBonus: number, cleanBonus: number }

-- condition is 0-100.
function Formula.payout(
	pay: number,
	condition: number,
	seconds: number,
	parSeconds: number,
	crashed: boolean,
	speedBonus: number,
	cleanBonus: number
): Payout
	local base = math.floor(pay * math.clamp(condition, 0, 100) / 100 + 0.5)
	local speed = if seconds <= parSeconds and base > 0 then math.floor(base * speedBonus + 0.5) else 0
	local clean = if not crashed and base > 0 then math.floor(base * cleanBonus + 0.5) else 0
	return { total = base + speed + clean, base = base, speedBonus = speed, cleanBonus = clean }
end

return Formula
