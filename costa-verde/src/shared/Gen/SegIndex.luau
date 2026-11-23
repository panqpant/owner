--!strict
-- Spatial hash of road segments, to keep buildings off roads.
local SegIndex = {}

function SegIndex.new()
	local cells: { [number]: { { number } } } = {}
	local CELL = 128
	local idx = {}
	function idx.add(ax: number, az: number, bx: number, bz: number, hw: number)
		for gx = math.floor((math.min(ax, bx) - hw) / CELL), math.floor((math.max(ax, bx) + hw) / CELL) do
			for gz = math.floor((math.min(az, bz) - hw) / CELL), math.floor((math.max(az, bz) + hw) / CELL) do
				local k = (gx + 4096) * 8192 + gz + 4096
				cells[k] = cells[k] or {}
				table.insert(cells[k], { ax, az, bx, bz, hw })
			end
		end
	end
	function idx.clear(x: number, z: number, r: number): boolean
		local gx, gz = math.floor(x / CELL), math.floor(z / CELL)
		for i = -1, 1 do
			for j = -1, 1 do
				for _, sg in cells[(gx + i + 4096) * 8192 + gz + j + 4096] or {} do
					local dx, dz = sg[3] - sg[1], sg[4] - sg[2]
					local t = math.clamp(((x - sg[1]) * dx + (z - sg[2]) * dz) / math.max(dx * dx + dz * dz, 1e-6), 0, 1)
					if (x - sg[1] - dx * t) ^ 2 + (z - sg[2] - dz * t) ^ 2 < (r + sg[5]) ^ 2 then
						return false
					end
				end
			end
		end
		return true
	end
	-- A rotated building box (centre, width along rot, depth): corners and edge midpoints all off the road.
	function idx.boxClear(x: number, z: number, w: number, d: number, rotDeg: number): boolean
		local c, s = math.cos(math.rad(rotDeg)), math.sin(math.rad(rotDeg))
		for _, p in { { -1, -1 }, { 1, -1 }, { 1, 1 }, { -1, 1 }, { 0, -1 }, { 1, 0 }, { 0, 1 }, { -1, 0 } } do
			local px, pz = p[1] * w / 2, p[2] * d / 2
			if not idx.clear(x + c * px - s * pz, z + s * px + c * pz, 2) then
				return false
			end
		end
		return true
	end
	return idx
end


return SegIndex
