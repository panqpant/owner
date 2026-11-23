-- Preview of what TerrainBuilder writes into Roblox: runs its column logic for a few areas and writes
-- build/terrain_<name>.json (4-stud heights, water levels, materials) for tools/blender/render_terrain.py.
-- Usage (from costa-verde/): lune run tools/export-terrain.luau
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local TB = require("../src/shared/TerrainBuilder")
local Gen = require("../src/shared/Gen")

TB.selfCheck()
local world = serde.decode("json", fs.readFile("build/world.json"))
local ridx = TB.roadIndex(world.roads)
local Vegetation = require("../src/shared/Vegetation")
local bidx = Vegetation.buildingIndex(world.buildings)
local WorldBuilder = require("../src/shared/WorldBuilder")
local D = {}
for _, d in world.districts do
	D[d.id] = d
end
local AREAS = { -- name, centre, size (studs)
	{ "keys", D.keytown.x, D.keytown.z, 2560 },
	{ "downtown", D.downtown.x, D.downtown.z, 2560 },
	{ "suburb", D.palmgrove.x, D.palmgrove.z, 2560 },
	{ "wetland", D.swamptown.x, D.swamptown.z, 2560 },
	{ "beach", D.beach.x, D.beach.z, 2560 },
	{ "country", Gen.Config.SIZE * 0.40625, Gen.Config.SIZE * 0.40625, 2560 },
}
for _, a in AREAS do
	local t0 = os.clock()
	local x0, z0 = math.floor((a[2] - a[4] / 2) / 16) * 16, math.floor((a[3] - a[4] / 2) / 16) * 16
	local c = TB.columns(x0, z0, a[4], a[4], ridx, bidx)
	c.x0, c.z0, c.res = x0, z0, 4
	c.items = Vegetation.place(c, x0, z0, ridx, bidx)
	c.pieces = WorldBuilder.pieces(world, { x0 = x0, z0 = z0, w = a[4], d = a[4] })
	print(a[1], #c.pieces, "greybox pieces")
	local per = {}
	for _, it in c.items do
		per[it[1]] = (per[it[1]] or 0) + 1
	end
	print(a[1], #c.items, "models", serde.encode("json", per))
	c.roads = {} -- grey road strips for the preview (parts in Roblox); drives are dirt terrain
	for _, r in world.roads do
		if r.kind ~= "drive" and math.max(r.ax, r.bx) > x0 and math.min(r.ax, r.bx) < x0 + a[4] and math.max(r.az, r.bz) > z0 and math.min(r.az, r.bz) < z0 + a[4] then
			table.insert(c.roads, { r.ax, r.az, r.bx, r.bz, r.width, r.bridge, r.kind })
		end
	end
	fs.writeFile("build/terrain_" .. a[1] .. ".json", serde.encode("json", c))
	print(string.format("%s: %dx%d columns in %.1fs", a[1], c.nx, c.nz, os.clock() - t0))
end
