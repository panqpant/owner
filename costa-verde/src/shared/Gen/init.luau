--!strict
-- Costa Verde world generator. Pure data: Roblox builds it (server/WorldBuilder), Lune exports it
-- for Blender previews (tools/export-world.luau). Same seed, same world.
local Gen = {}

Gen.Config = require("@self/Config")
Gen.Terrain = require("@self/Terrain")
Gen.Districts = require("@self/Districts")
Gen.City = require("@self/City")
Gen.Rural = require("@self/Rural")
Gen.Transit = require("@self/Transit")
Gen.Uses = require("@self/Uses")
Gen.Shapes = require("@self/Shapes")
Gen.Hash = require("@self/Hash")
Gen.Noise = require("@self/Noise")

-- Heightmap grid for previews / minimap: rows of {h, materialIndex, districtIndex}.
function Gen.heightmap(cell: number)
	local n = math.floor(Gen.Config.SIZE / cell)
	local ltype, built = table.create(n * n), table.create(n * n)
	local h, wat, mat, dist, biome = table.create(n * n), table.create(n * n), table.create(n * n), table.create(n * n), table.create(n * n)
	for j = 0, n - 1 do
		for i = 0, n - 1 do
			local x, z = (i + 0.5) * cell, (j + 0.5) * cell
			local s = Gen.Terrain.sample(x, z)
			table.insert(h, math.floor(s.h * 10 + 0.5) / 10)
			table.insert(wat, if s.water then math.floor(s.water * 10 + 0.5) / 10 else -9999)
			table.insert(mat, s.material)
			table.insert(dist, Gen.Districts.at(x, z, s))
			table.insert(biome, s.biome)
			table.insert(ltype, s.ltype)
			table.insert(built, not s.water and s.land > 20 and (s.shape == "barrier" or ((s.shape == "main" or s.shape == "key") and Gen.Districts.urban(x, z) > 0)))
		end
	end
	return { n = n, cell = cell, h = h, water = wat, material = mat, district = dist, biome = biome, ltype = ltype, built = built }
end

return Gen
