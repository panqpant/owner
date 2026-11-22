--!strict
-- Hand-authored layout of Costa Verde. Positions are normalized (u = west->east, v = north->south,
-- both 0..1) and scaled by SIZE. Everything between these anchors is generated.

export type District = {
	id: string,
	name: string,
	u: number,
	v: number,
	radius: number, -- normalized
	urban: boolean,
	block: number?, -- studs between grid roads
	minH: number?, -- building height range, studs
	maxH: number?,
	style: string?,
	parkChance: number?,
	special: boolean?, -- placed by terrain feature (barrier island, keys), not by distance
}

local Config = {}

Config.SEED = 1984
Config.SIZE = 40960 -- studs per side, ~11.7 km at 0.28 m/stud
Config.CELL = 64 -- heightmap sample spacing (studs)
Config.SEA = 0 -- water surface height
Config.ROAD_W = 28
Config.HIGHWAY_W = 56
Config.SECTION = 1600 -- rural section-line road spacing (US ~1 mile grid, compressed)
Config.COUNTY_W = 20

-- Hand-drawn outline, clockwise: { u, v, roughness }. 0 = smooth sandy Atlantic coast,
-- 1 = ragged mangrove Gulf coast that breaks into islets (from USGS reference study).
Config.COAST = {
	{ 0.1, 0.07, 0.6 }, { 0.25, 0.05, 0.5 }, { 0.42, 0.06, 0.4 }, { 0.6, 0.05, 0.35 }, { 0.76, 0.07, 0.2 },
	{ 0.8, 0.15, 0.05 }, { 0.81, 0.28, 0.05 }, { 0.795, 0.38, 0.05 }, { 0.765, 0.48, 0.1 }, { 0.755, 0.58, 0.15 },
	{ 0.73, 0.69, 0.25 }, { 0.68, 0.77, 0.45 }, { 0.6, 0.82, 0.7 }, { 0.52, 0.835, 0.9 }, { 0.46, 0.8, 1 },
	{ 0.4, 0.83, 1 }, { 0.32, 0.86, 0.95 }, { 0.25, 0.82, 1 }, { 0.19, 0.74, 1 }, { 0.15, 0.64, 0.95 },
	{ 0.13, 0.56, 0.85 }, { 0.17, 0.51, 0.85 }, { 0.12, 0.475, 0.8 }, { 0.09, 0.38, 0.6 }, { 0.075, 0.25, 0.5 },
	{ 0.085, 0.14, 0.5 },
}

-- Barrier island chain offshore of the metro; inlets at these v values.
Config.BARRIER = { v0 = 0.3, v1 = 0.7, offset = 0.03, width = 0.006, inlets = { 0.405, 0.555, 0.64 } }

-- Keys: quadratic arc from the south-east cape (a) bending through c to b.
Config.KEYS_ARC = { a = { 0.6, 0.845 }, c = { 0.5, 0.97 }, b = { 0.2, 0.94 }, count = 24 }

Config.BIG_LAKE = { 0.43, 0.24, 0.045 }
Config.WETLANDS = { 0.4, 0.64, 0.24, 0.17 } -- centre u, v, radius u, radius v

-- Metro sprawl: cores whose union is built up; hard western levee line like real wetland edges.
Config.URBAN = {
	cores = { { 0.72, 0.5, 0.11 }, { 0.75, 0.33, 0.09 }, { 0.71, 0.64, 0.08 }, { 0.15, 0.41, 0.05 }, { 0.3, 0.7, 0.014 }, { 0.47, 0.33, 0.014 } },
	levee = 0.6, -- metro stops at this u (south of v = 0.3)
}
Config.BLOCK = 200
Config.ARTERIAL_EVERY = 5
Config.ARTERIAL_W = 44

Config.DISTRICTS = {
	-- Port Solano metro (south-east coast)
	{ id = "downtown", name = "Port Solano Downtown", u = 0.735, v = 0.52, radius = 0.06, urban = true, block = 220, minH = 90, maxH = 620, style = "tower", parkChance = 0.06 },
	{ id = "midtown", name = "Midtown", u = 0.75, v = 0.44, radius = 0.045, urban = true, block = 220, minH = 40, maxH = 220, style = "midrise", parkChance = 0.06 },
	{ id = "beach", name = "Coral Strand", u = 0.775, v = 0.52, radius = 0.25, urban = true, block = 200, minH = 30, maxH = 150, style = "deco", parkChance = 0.05, special = true },
	{ id = "calle", name = "Calle Verde", u = 0.69, v = 0.53, radius = 0.04, urban = true, block = 180, minH = 18, maxH = 60, style = "stucco", parkChance = 0.08 },
	{ id = "docks", name = "Solano Docks", u = 0.735, v = 0.595, radius = 0.035, urban = true, block = 320, minH = 25, maxH = 55, style = "warehouse", parkChance = 0.02 },
	{ id = "northshore", name = "North Shore", u = 0.76, v = 0.34, radius = 0.07, urban = true, block = 260, minH = 14, maxH = 26, style = "house", parkChance = 0.1 },
	{ id = "westside", name = "Westside", u = 0.69, v = 0.41, radius = 0.05, urban = true, block = 260, minH = 14, maxH = 26, style = "house", parkChance = 0.1 },
	{ id = "palmgrove", name = "Palm Grove", u = 0.69, v = 0.64, radius = 0.065, urban = true, block = 260, minH = 14, maxH = 26, style = "house", parkChance = 0.1 },
	{ id = "university", name = "Costa Verde University", u = 0.65, v = 0.49, radius = 0.03, urban = true, block = 300, minH = 30, maxH = 70, style = "campus", parkChance = 0.3 },
	{ id = "airport", name = "Solano International", u = 0.64, v = 0.585, radius = 0.03, urban = false },
	-- Gulf coast town (west)
	{ id = "gulftown", name = "Pelican Bay", u = 0.15, v = 0.41, radius = 0.05, urban = true, block = 240, minH = 16, maxH = 45, style = "stucco", parkChance = 0.1 },
	-- Interior
	{ id = "wetlands", name = "Sawgrass Wetlands", u = 0.36, v = 0.66, radius = 0.19, urban = false },
	{ id = "swamptown", name = "Gator Hollow", u = 0.3, v = 0.7, radius = 0.02, urban = true, block = 220, minH = 10, maxH = 18, style = "shack", parkChance = 0.2 },
	{ id = "rural", name = "Citrus County", u = 0.38, v = 0.18, radius = 0.25, urban = false },
	{ id = "truckstop", name = "Mile 88", u = 0.47, v = 0.33, radius = 0.014, urban = true, block = 200, minH = 12, maxH = 20, style = "shack", parkChance = 0.1 },
	{ id = "base", name = "Fort Calusa (restricted)", u = 0.17, v = 0.15, radius = 0.045, urban = false },
	-- Keys
	{ id = "keys", name = "The Sunset Keys", u = 0.4, v = 0.93, radius = 0.2, urban = false, special = true },
}

-- Highways between anchor points (normalized). Bridges are detected where they cross water.
Config.HIGHWAYS = {
	{ { 0.7, 0.06 }, { 0.71, 0.3 }, { 0.72, 0.45 }, { 0.71, 0.6 }, { 0.66, 0.72 }, { 0.6, 0.8 } }, -- I-1 coast spine
	{ { 0.72, 0.45 }, { 0.62, 0.43 }, { 0.47, 0.33 }, { 0.3, 0.36 }, { 0.15, 0.41 } }, -- cross-state
	{ { 0.47, 0.33 }, { 0.45, 0.15 }, { 0.42, 0.06 } }, -- north to Citrus County
	{ { 0.15, 0.41 }, { 0.15, 0.25 }, { 0.17, 0.15 } }, -- base road
	{ { 0.6, 0.62 }, { 0.45, 0.66 }, { 0.3, 0.7 } }, -- wetlands trail (dead straight, like the real ones)
	{ { 0.74, 0.5 }, { 0.81, 0.5 } }, -- causeway to Coral Strand
	{ { 0.77, 0.36 }, { 0.84, 0.36 } }, -- north causeway
	{ { 0.73, 0.6 }, { 0.79, 0.62 } }, -- south causeway
	{ { 0.6, 0.8 }, { 0.6, 0.845 }, { 0.56, 0.9 }, { 0.5, 0.93 }, { 0.42, 0.945 }, { 0.32, 0.948 }, { 0.2, 0.94 } }, -- overseas highway
}

-- Rail: smoothed polylines; stations every `spacing` studs where the line meets a town.
Config.RAIL = {
	{ name = "Coastline Railway", kind = "rail", spacing = 2600, points = { { 0.69, 0.06 }, { 0.695, 0.3 }, { 0.705, 0.45 }, { 0.7, 0.6 }, { 0.65, 0.72 }, { 0.585, 0.8 } } },
	{ name = "Gulf Line", kind = "rail", spacing = 3500, points = { { 0.705, 0.47 }, { 0.6, 0.455 }, { 0.47, 0.35 }, { 0.3, 0.38 }, { 0.15, 0.43 } } },
	{ name = "Citrus Freight", kind = "rail", spacing = 3500, points = { { 0.47, 0.35 }, { 0.44, 0.15 }, { 0.4, 0.06 } } },
	{ name = "Metro Green", kind = "metro", spacing = 1100, points = { { 0.76, 0.3 }, { 0.752, 0.4 }, { 0.742, 0.47 }, { 0.735, 0.52 }, { 0.72, 0.59 }, { 0.69, 0.67 } } },
	{ name = "Metro Orange", kind = "metro", spacing = 1100, points = { { 0.735, 0.52 }, { 0.69, 0.53 }, { 0.655, 0.55 }, { 0.64, 0.58 } } },
}

-- Original hamlet names for crossroads settlements.
Config.HAMLET_NAMES = {
	"Sabal Junction", "Cypress Bend", "Blackwater Flats", "Mango Hill", "Indigo Crossing", "Heron Bend",
	"Lime Ridge", "Turpentine Camp", "Bluegill", "Hatchet Creek", "Orange Blossom", "Palmetto Corners",
	"Sinkhole Springs", "Bone Ridge", "Kissing Bridge", "Sunnyvale Acres", "Gopher Hollow", "Saltlick",
	"Rattler Crossing", "Three Oaks", "Dusty Gulch", "Moss Landing", "Pelton", "Harlow", "Copperhead",
}

-- Easter eggs: kind, display name, how many, which biomes they can appear in, rural-only.
Config.EASTER_EGGS = {
	{ kind = "crop_circle", name = "Crop Circle", count = 4, biomes = { "farm" }, rural = true },
	{ kind = "giant_orange", name = "World's Biggest Orange", count = 1, biomes = { "farm" }, rural = true },
	{ kind = "radio_tower", name = "Numbers Station", count = 3, biomes = { "farm", "scrub" }, rural = true },
	{ kind = "meteor_crater", name = "Fresh Crater", count = 1, biomes = { "farm" }, rural = true },
	{ kind = "abandoned_motel", name = "Sunset Vista Motor Lodge (closed)", count = 3, biomes = { "scrub" }, rural = true },
	{ kind = "ufo_crash", name = "Something Fell Here", count = 1, biomes = { "scrub" }, rural = true },
	{ kind = "ghost_town", name = "Old Calloway", count = 1, biomes = { "scrub" }, rural = true },
	{ kind = "secret_bunker", name = "Hatch", count = 2, biomes = { "scrub" }, rural = true },
	{ kind = "haunted_church", name = "Chapel of the Lost", count = 1, biomes = { "scrub" }, rural = true },
	{ kind = "abandoned_park", name = "Dinoland (abandoned)", count = 1, biomes = { "scrub" }, rural = true },
	{ kind = "buried_car", name = "Half-Buried Convertible", count = 2, biomes = { "scrub", "farm" }, rural = true },
	{ kind = "gator_shrine", name = "Gator Shrine", count = 3, biomes = { "wetland", "hammock" }, rural = true },
	{ kind = "swamp_ape", name = "Big Tracks", count = 4, biomes = { "hammock" }, rural = true },
	{ kind = "plane_wreck", name = "Lost Flight 19-B", count = 2, biomes = { "wetland" }, rural = true },
	{ kind = "tiki_bar", name = "Hidden Tiki Bar", count = 2, biomes = { "mangrove" }, rural = true },
	{ kind = "skull_rock", name = "Skull Rock", count = 2, biomes = { "mangrove" }, rural = true },
	{ kind = "sunken_yacht", name = "Sunken Yacht", count = 4, biomes = { "sea" }, rural = true },
	{ kind = "mermaid_statue", name = "Mermaid Statue (underwater)", count = 2, biomes = { "sea" }, rural = true },
	{ kind = "shipwreck", name = "Spanish Wreck", count = 3, biomes = { "bay", "sea" }, rural = true },
	{ kind = "lighthouse", name = "Old Lighthouse", count = 3, biomes = { "beach" }, rural = false },
	{ kind = "treasure_chest", name = "Pirate Cache", count = 6, biomes = { "beach", "mangrove" }, rural = true },
	{ kind = "message_bottle", name = "Message in a Bottle", count = 6, biomes = { "beach" }, rural = false },
}

return Config
