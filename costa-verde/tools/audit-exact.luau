-- Exact-resolution checks for tools/audit_world.py (uses the game's own terrain code):
-- roads whose midpoint is in water without a bridge flag, and loose major-road ends that are inland
-- (not at the coast or map edge). Usage: lune run tools/audit-exact.luau -> build/audit_exact.json
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local Gen = require("../src/shared/Gen")
local T = Gen.Terrain
local W = serde.decode("json", fs.readFile("build/world.json"))

local wet = {}
for _, r in W.roads do
	if r.kind ~= "runway" and r.kind ~= "drive" and not r.bridge then
		local s = T.sample((r.ax + r.bx) / 2, (r.az + r.bz) / 2)
		if s.water then
			wet[r.kind] = (wet[r.kind] or 0) + math.sqrt((r.bx - r.ax) ^ 2 + (r.bz - r.az) ^ 2)
		end
	end
end

local deg, kindAt = {}, {}
local function key(x, z)
	return math.round(x * 2) .. "," .. math.round(z * 2)
end
for _, r in W.roads do
	if r.kind ~= "runway" then
		for _, p in { { r.ax, r.az }, { r.bx, r.bz } } do
			local k = key(p[1], p[2])
			deg[k] = (deg[k] or 0) + 1
			kindAt[k] = { r.kind, p[1], p[2] }
		end
	end
end
local inland = {}
local coastal = 0
local MAJOR = { freeway = true, boulevard = true, arterial = true, state = true }
for k, d in deg do
	local info = kindAt[k]
	if d == 1 and MAJOR[info[1]] then
		local x, z = info[2], info[3]
		local nearWater = false
		for a = 0, 7 do
			local s = T.sample(x + math.cos(a * math.pi / 4) * 250, z + math.sin(a * math.pi / 4) * 250)
			nearWater = nearWater or s.water ~= nil
		end
		if nearWater or x < 400 or z < 400 or x > W.size - 400 or z > W.size - 400 then
			coastal += 1
		else
			table.insert(inland, { kind = info[1], x = x, z = z })
		end
	end
end
fs.writeFile("build/audit_exact.json", serde.encode("json", { unbridged_studs = wet, coastal_ends = coastal, inland_ends = inland }))
print(serde.encode("json", { unbridged_studs = wet, coastal_ends = coastal, inland_ends = #inland }))
