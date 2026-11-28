-- Customers on foot and parcel thieves: pedestrians every player sees in the same place. The server
-- announces each one (path, speed, server-clock start) and everyone computes positions from that.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared.Config)
local WalkMath = require(Shared.WalkMath)
local remote = require(script.Parent.Net)
local World = require(script.Parent.World)
local walks = World.walks

---------------------------------------------------------------------------- shared pedestrians (customers, thieves)

-- Every client draws these from the same path, speed and server-clock start time, so they match.
export type Actor = {
	id: number,
	kind: string,
	model: string,
	path: WalkMath.Path,
	speed: number,
	t0: number,
	s0: number,
	dir: number,
	once: boolean,
}
local PED_MODELS =
	{ "Ped_Shopper", "Ped_Business", "Ped_Elder", "Ped_Kid", "Ped_Jogger", "Ped_Tourist", "Ped_Worker", "Ped_Student" }
local actors: { [number]: Actor } = {}
local nextActorId = 0

local function actorData(a: Actor)
	return {
		id = a.id,
		kind = a.kind,
		model = a.model,
		points = a.path.points,
		speed = a.speed,
		t0 = a.t0,
		s0 = a.s0,
		dir = a.dir,
		once = a.once,
	}
end

local function addActor(kind: string, path: WalkMath.Path, speed: number, s0: number, dir: number, once: boolean): Actor
	nextActorId += 1
	local a: Actor = {
		id = nextActorId,
		kind = kind,
		model = PED_MODELS[math.random(#PED_MODELS)],
		path = path,
		speed = speed,
		t0 = workspace:GetServerTimeNow(),
		s0 = s0,
		dir = dir,
		once = once,
	}
	actors[a.id] = a
	remote:FireAllClients("Actor", actorData(a))
	return a
end

local function removeActor(a: Actor)
	if actors[a.id] then
		actors[a.id] = nil
		remote:FireAllClients("ActorGone", a.id)
	end
end

local function actorPos(a: Actor): Vector3
	local elapsed = workspace:GetServerTimeNow() - a.t0
	local s = if a.once
		then math.min(a.s0 + a.speed * elapsed, a.path.length)
		else (WalkMath.pingPong(a.path.length, a.s0, a.dir, a.speed, elapsed))
	return (WalkMath.at(a.path, s))
end

-- A thief's getaway: along the walk away from the rider, then across the junction to the nearest
-- walk end and on along that one, until the route is long enough for Config.ThiefSeconds.
local function getawayRoute(from: Vector3, rider: Vector3): WalkMath.Path?
	local best, bestWalk, bestS = math.huge, nil :: WalkMath.Walk?, 0
	for _, w in walks do
		for k = 2, #w.points do
			local a, b = w.points[k - 1], w.points[k]
			local ab = b - a
			local t = if ab.Magnitude > 0 then math.clamp((from - a):Dot(ab) / ab:Dot(ab), 0, 1) else 0
			local d = (a + ab * t - from).Magnitude
			if d < best then
				best, bestWalk, bestS = d, w, w.cum[k - 1] + ab.Magnitude * t
			end
		end
	end
	if not bestWalk or best > 40 then
		return nil
	end
	local walk = bestWalk :: WalkMath.Walk
	local ahead = WalkMath.at(walk, math.min(bestS + 4, walk.length))
	local behind = WalkMath.at(walk, math.max(bestS - 4, 0))
	local forward = (ahead - rider).Magnitude >= (behind - rider).Magnitude -- run away from the rider
	local points = { (WalkMath.at(walk, bestS)) }
	local function follow(w: WalkMath.Walk, fwd: boolean, fromS: number)
		if fwd then
			for k = 1, #w.points do
				if w.cum[k] > fromS then
					table.insert(points, w.points[k])
				end
			end
		else
			for k = #w.points, 1, -1 do
				if w.cum[k] < fromS then
					table.insert(points, w.points[k])
				end
			end
		end
	end
	follow(walk, forward, bestS)
	local used = { [walk] = true }
	local need = Config.ThiefSpeed * Config.ThiefSeconds
	while WalkMath.path(points).length < need do
		local here = points[#points]
		local nextWalk, nextFwd, nextD = nil :: WalkMath.Walk?, true, 60
		for _, w in walks do
			if not used[w] then
				local ds, de = (w.points[1] - here).Magnitude, (w.points[#w.points] - here).Magnitude
				if ds < nextD then
					nextWalk, nextFwd, nextD = w, true, ds
				end
				if de < nextD then
					nextWalk, nextFwd, nextD = w, false, de
				end
			end
		end
		if not nextWalk then
			break -- a dead end: the thief gets away early
		end
		local w = nextWalk :: WalkMath.Walk
		used[w] = true
		follow(w, nextFwd, if nextFwd then -1 else w.length + 1)
	end
	return if #points >= 2 then WalkMath.path(points) else nil
end

return {
	PED_MODELS = PED_MODELS,
	actors = actors,
	nextActorId = nextActorId,
	actorData = actorData,
	addActor = addActor,
	removeActor = removeActor,
	actorPos = actorPos,
	getawayRoute = getawayRoute,
}
