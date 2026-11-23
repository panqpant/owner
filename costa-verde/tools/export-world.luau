-- Runs the world generator outside Roblox and writes build/world.json for Blender previews.
-- Usage (from costa-verde/): lune run tools/export-world.luau
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local Gen = require("../src/shared/Gen")

local t0 = os.clock()
local hm = Gen.heightmap(Gen.Config.CELL)
local city = Gen.City.generate()
local settlements = Gen.Rural.generate(city.roads, city.buildings, city.shared)
Gen.Uses.assign(city.buildings, Gen.Config.SEED + 800) -- every building gets a real use
Gen.Uses.markers(city.buildings, Gen.Config.SEED + 801) -- then the playable ones
Gen.Shapes.assign(city.buildings, Gen.Config.SEED + 802) -- and a real shape each
local pois = Gen.Rural.pois()
local tracks, stations = Gen.Transit.generate(settlements, city.roads)

local districts = {}
for _, d in Gen.Config.DISTRICTS do
	table.insert(districts, { id = d.id, name = d.name, x = d.u * Gen.Config.SIZE, z = d.v * Gen.Config.SIZE })
end

if not fs.isDir("build") then
	fs.writeDir("build")
end
fs.writeFile(
	"build/world.json",
	serde.encode("json", {
		size = Gen.Config.SIZE,
		heightmap = hm,
		roads = city.roads,
		buildings = city.buildings,
		parks = city.parks,
		districts = districts,
		landmarks = city.landmarks,
		settlements = settlements,
		pois = pois,
		tracks = tracks,
		stations = stations,
	})
)
print(
	string.format(
		"world: %d buildings, %d roads, %d parks, %d hamlets, %d easter eggs, %d stations, %dx%d heightmap in %.1fs",
		#city.buildings,
		#city.roads,
		#city.parks,
		#settlements,
		#pois,
		#stations,
		hm.n,
		hm.n,
		os.clock() - t0
	)
)
