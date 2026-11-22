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
Gen.Hash = require("@self/Hash")
Gen.Noise = require("@self/Noise")

-- Heightmap grid for previews / minimap: rows of {h, materialIndex, districtIndex}.
function Gen.heightmap(cell: number)
	local n = math.floor(Gen.Config.SIZE / cell)
	local h, mat, dist, biome = table.create(n * n), table.create(n * n), table.create(n * n), table.create(n * n)
	for j = 0, n - 1 do
		for i = 0, n - 1 do
			local x, z = (i + 0.5) * cell, (j + 0.5) * cell
			local s = Gen.Terrain.sample(x, z)
			table.insert(h, math.floor(s.h * 10 + 0.5) / 10)
			table.insert(mat, s.material)
			table.insert(dist, Gen.Districts.at(x, z, s))
			table.insert(biome, s.biome)
		end
	end
	return { n = n, cell = cell, h = h, material = mat, district = dist, biome = biome }
end

return Gen
