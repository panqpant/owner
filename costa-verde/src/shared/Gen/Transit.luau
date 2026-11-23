--!strict
-- Rail lines routed by A* over the terrain (Roads.route), stations where a line meets a town; metro
-- lines run along arterial grid lines (elevated over the median) with a station at every major
-- intersection.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")
local Roads = require("./Roads")

local Transit = {}

export type Track = { ax: number, az: number, bx: number, bz: number, line: string, kind: string, bridge: boolean, elevated: boolean }
export type Station = { x: number, z: number, y: number, line: string, name: string }

local W = Config.SIZE
local SP = Config.ROADS.ARTERIAL_SPACING

-- Metro path: snap anchors to arterial intersections, then follow grid lines (vertical leg, then horizontal).
local function gridPath(anchors: { { number } }): ({ number }, { { number } })
	local pts, stops = {}, {}
	local function add(x: number, z: number)
		if #pts == 0 or pts[#pts - 1] ~= x or pts[#pts] ~= z then
			table.insert(pts, x)
			table.insert(pts, z)
		end
	end
	local function leg(x0: number, z0: number, x1: number, z1: number)
		local n = math.max(math.abs(x1 - x0), math.abs(z1 - z0)) // 40
		for k = 0, n do
			add(x0 + (x1 - x0) * k / math.max(n, 1), z0 + (z1 - z0) * k / math.max(n, 1))
		end
	end
	local prev: { number }? = nil
	for _, a in anchors do
		local x, z = math.round(a[1] * W / SP) * SP, math.round(a[2] * W / SP) * SP
		if prev then
			leg(prev[1], prev[2], prev[1], z)
			leg(prev[1], z, x, z)
		end
		prev = { x, z }
	end
	for i = 1, #pts - 1, 2 do
		if pts[i] % SP == 0 and pts[i + 1] % SP == 0 then -- every arterial crossing on the line
			table.insert(stops, { pts[i], pts[i + 1] })
		end
	end
	return pts, stops
end

function Transit.generate(settlements: { { x: number, z: number, name: string } }): ({ Track }, { Station })
	local tracks: { Track } = {}
	local stations: { Station } = {}
	local function nameAt(x: number, z: number, line: string, count: number): string
		for _, st in settlements do
			if (st.x - x) ^ 2 + (st.z - z) ^ 2 < 600 ^ 2 then
				return st.name
			end
		end
		local d = Districts.byId[Districts.at(x, z)]
		return (if d then d.name else line) .. ` {count}`
	end
	for _, line in Config.RAIL do
		local metro = line.kind == "metro"
		local pts, stops
		if metro then
			pts, stops = gridPath(line.points)
		else
			pts = Roads.route(line.points, "rail")
		end
		for i = 1, #pts - 3, 2 do
			local s = Terrain.sample((pts[i] + pts[i + 2]) / 2, (pts[i + 1] + pts[i + 3]) / 2)
			table.insert(tracks, { ax = pts[i], az = pts[i + 1], bx = pts[i + 2], bz = pts[i + 3], line = line.name, kind = line.kind, bridge = s.water ~= nil, elevated = metro })
		end
		local count = 0
		if metro then
			for _, p in stops do
				count += 1
				table.insert(stations, { x = p[1], z = p[2], y = Terrain.sample(p[1], p[2]).h, line = line.name, name = nameAt(p[1], p[2], line.name, count) })
			end
		else
			-- rail: a station every `spacing` along the line where it passes a town or the built-up area
			local since = math.huge
			for i = 1, #pts - 3, 2 do
				since += 40
				local x, z = pts[i], pts[i + 1]
				local s = Terrain.sample(x, z)
				local town = Districts.urban(x, z) > 0
				for _, st in settlements do
					town = town or (st.x - x) ^ 2 + (st.z - z) ^ 2 < 600 ^ 2
				end
				if town and not s.water and since >= line.spacing then
					since = 0
					count += 1
					table.insert(stations, { x = x, z = z, y = s.h, line = line.name, name = nameAt(x, z, line.name, count) })
				end
			end
		end
	end
	return tracks, stations
end

return Transit
