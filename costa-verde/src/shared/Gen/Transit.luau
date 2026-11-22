--!strict
-- Rail lines and metro: smoothed polylines from Config.RAIL, bridges over water, stations spaced
-- along the line wherever it runs through built-up land or a hamlet.
local Config = require("./Config")
local Terrain = require("./Terrain")
local Districts = require("./Districts")

local Transit = {}

export type Track = { ax: number, az: number, bx: number, bz: number, line: string, kind: string, bridge: boolean, elevated: boolean }
export type Station = { x: number, z: number, y: number, line: string, name: string }

local W = Config.SIZE

local function smooth(points: { { number } }): { { number } }
	if #points < 3 then
		return points
	end
	local out = {}
	for i = 1, #points - 1 do
		local p0, p1, p2, p3 = points[math.max(1, i - 1)], points[i], points[i + 1], points[math.min(#points, i + 2)]
		for k = 0, 7 do
			local t = k / 8
			local function c(a: number, b: number, cc: number, d: number)
				return 0.5 * (2 * b + (-a + cc) * t + (2 * a - 5 * b + 4 * cc - d) * t * t + (-a + 3 * b - 3 * cc + d) * t * t * t)
			end
			table.insert(out, { c(p0[1], p1[1], p2[1], p3[1]), c(p0[2], p1[2], p2[2], p3[2]) })
		end
	end
	table.insert(out, points[#points])
	return out
end

function Transit.generate(settlements: { { x: number, z: number, name: string } }): ({ Track }, { Station })
	local tracks: { Track } = {}
	local stations: { Station } = {}
	for _, line in Config.RAIL do
		local pts = smooth(line.points)
		local sinceStation = math.huge
		local count = 0
		for p = 1, #pts - 1 do
			local ax, az = pts[p][1] * W, pts[p][2] * W
			local bx, bz = pts[p + 1][1] * W, pts[p + 1][2] * W
			local len = math.sqrt((bx - ax) ^ 2 + (bz - az) ^ 2)
			local mx, mz = (ax + bx) / 2, (az + bz) / 2
			local s = Terrain.sample(mx, mz)
			table.insert(tracks, { ax = ax, az = az, bx = bx, bz = bz, line = line.name, kind = line.kind, bridge = s.water ~= nil, elevated = line.kind == "metro" })
			sinceStation += len
			local urban = Districts.urban(mx, mz) > 0 or s.shape == "barrier"
			local near: string? = nil
			for _, st in settlements do
				if (st.x - mx) ^ 2 + (st.z - mz) ^ 2 < 500 ^ 2 then
					near = st.name
				end
			end
			if not s.water and sinceStation >= line.spacing and (urban or near) then
				count += 1
				local district = Districts.byId[Districts.at(mx, mz, s)]
				table.insert(stations, {
					x = mx,
					z = mz,
					y = s.h,
					line = line.name,
					name = near or (if district then district.name else line.name) .. (if count > 1 then ` {count}` else ""),
				})
				sinceStation = 0
			end
		end
	end
	return tracks, stations
end

return Transit
