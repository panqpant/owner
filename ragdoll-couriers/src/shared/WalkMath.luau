-- Paths along the pedestrian walks, shared by the server and every client. Customers and thieves move
-- by formula (path, speed, start time on the server clock), so everyone computes the same position
-- without the server streaming it.

local WalkMath = {}

export type Path = { points: { Vector3 }, cum: { number }, length: number }
export type Walk = Path & { district: string, weight: number }

function WalkMath.path(points: { Vector3 }): Path
	local cum = { 0 }
	for k = 2, #points do
		cum[k] = cum[k - 1] + (points[k] - points[k - 1]).Magnitude
	end
	return { points = points, cum = cum, length = cum[#cum] }
end

-- Every walk in world space (walks are stored relative to the city's origin).
function WalkMath.load(origin: Vector3): { Walk }
	local Walks = require(script.Parent.Walks) -- required here so the maths can be tested outside Roblox
	local out = {}
	for _, w in Walks.walks do
		local pts = {}
		for k, p in w.p do
			pts[k] = origin + Vector3.new(p[1], p[2], p[3])
		end
		local walk = WalkMath.path(pts) :: Walk
		walk.district = w.d
		walk.weight = (Walks.density[w.d] or 1) * walk.length
		table.insert(out, walk)
	end
	return out
end

-- Position and heading at distance s along a path (clamped to its ends).
function WalkMath.at(path: Path, s: number): (Vector3, Vector3)
	local cum, pts = path.cum, path.points
	for k = 2, #pts do
		if s <= cum[k] or k == #pts then
			local seg = cum[k] - cum[k - 1]
			local a = if seg > 0 then math.clamp((s - cum[k - 1]) / seg, 0, 1) else 0
			local dir = pts[k] - pts[k - 1]
			return pts[k - 1]:Lerp(pts[k], a), if dir.Magnitude > 0 then dir.Unit else Vector3.zAxis
		end
	end
	return pts[1], Vector3.zAxis
end

-- Pacing end to end: where someone who set off from s0 heading dir (+1 or -1) is after `elapsed`.
-- Returns the distance along the path and the direction they're now heading.
function WalkMath.pingPong(length: number, s0: number, dir: number, speed: number, elapsed: number): (number, number)
	if length <= 0 then
		return 0, dir
	end
	local u = (s0 + dir * speed * elapsed) % (2 * length) -- Luau's % is never negative for a positive divisor
	if u <= length then
		return u, dir
	end
	return 2 * length - u, -dir
end

return WalkMath
