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
	minH: number?, -- building height range, studs
	maxH: number?,
	style: string?,
	parkChance: number?,
	landscape: boolean?, -- open-country district: never claims land inside a built-up town area
	special: boolean?, -- placed by terrain feature (barrier island, keys), not by distance
}

local Config = {}

Config.SEED = 1984
Config.SIZE = 40960 -- studs per side, ~11.7 km at 0.28 m/stud
Config.CELL = 64 -- heightmap sample spacing (studs)
Config.ROAD_W = 28
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
-- The chain ends in its biggest island, home of Key Marisol (like real keys chains): u, v, half-length, half-width.
Config.TOWN_KEY = { 0.205, 0.942, 0.026, 0.01 }

Config.BIG_LAKE = { 0.43, 0.24, 0.045 }
Config.WETLANDS = { 0.4, 0.64, 0.24, 0.17 } -- centre u, v, radius u, radius v

-- Metro sprawl: cores whose union is built up; hard western levee line like real wetland edges.
Config.URBAN = {
	cores = { { 0.72, 0.5, 0.11 }, { 0.75, 0.33, 0.09 }, { 0.71, 0.64, 0.08 }, { 0.15, 0.41, 0.05 }, { 0.3, 0.7, 0.022 }, { 0.47, 0.33, 0.022 }, { 0.205, 0.942, 0.024 } },
	levee = 0.6, -- metro stops at this u (south of v = 0.3)
}

Config.DISTRICTS = {
	-- Port Solano metro (south-east coast)
	{ id = "downtown", name = "Port Solano Downtown", u = 0.735, v = 0.52, radius = 0.06, urban = true, minH = 90, maxH = 620, style = "tower", parkChance = 0.06 },
	{ id = "midtown", name = "Midtown", u = 0.75, v = 0.44, radius = 0.045, urban = true, minH = 40, maxH = 220, style = "midrise", parkChance = 0.06 },
	{ id = "beach", name = "Coral Strand", u = 0.775, v = 0.52, radius = 0.25, urban = true, minH = 30, maxH = 150, style = "deco", parkChance = 0.05, special = true },
	{ id = "calle", name = "Calle Verde", u = 0.69, v = 0.53, radius = 0.04, urban = true, minH = 18, maxH = 60, style = "stucco", parkChance = 0.08 },
	{ id = "docks", name = "Solano Docks", u = 0.735, v = 0.595, radius = 0.035, urban = true, minH = 25, maxH = 55, style = "warehouse", parkChance = 0.02 },
	{ id = "northshore", name = "North Shore", u = 0.76, v = 0.34, radius = 0.07, urban = true, minH = 14, maxH = 26, style = "house", parkChance = 0.1 },
	{ id = "westside", name = "Westside", u = 0.69, v = 0.41, radius = 0.05, urban = true, minH = 14, maxH = 26, style = "house", parkChance = 0.1 },
	{ id = "palmgrove", name = "Palm Grove", u = 0.69, v = 0.64, radius = 0.065, urban = true, minH = 14, maxH = 26, style = "house", parkChance = 0.1 },
	{ id = "university", name = "Costa Verde University", u = 0.65, v = 0.49, radius = 0.03, urban = true, minH = 30, maxH = 70, style = "campus", parkChance = 0.3 },
	{ id = "airport", name = "Solano International", u = 0.64, v = 0.585, radius = 0.03, urban = false },
	-- Gulf coast town (west)
	{ id = "gulftown", name = "Pelican Bay", u = 0.15, v = 0.41, radius = 0.05, urban = true, minH = 16, maxH = 45, style = "stucco", parkChance = 0.1 },
	-- Interior
	{ id = "wetlands", name = "Sawgrass Wetlands", u = 0.36, v = 0.66, radius = 0.19, urban = false, landscape = true },
	{ id = "swamptown", name = "Gator Hollow", u = 0.3, v = 0.7, radius = 0.02, urban = true, minH = 10, maxH = 18, style = "shack", parkChance = 0.2 },
	{ id = "rural", name = "Citrus County", u = 0.38, v = 0.18, radius = 0.25, urban = false, landscape = true },
	{ id = "truckstop", name = "Mile 88", u = 0.47, v = 0.33, radius = 0.014, urban = true, minH = 12, maxH = 20, style = "shack", parkChance = 0.1 },
	{ id = "base", name = "Fort Calusa (restricted)", u = 0.17, v = 0.15, radius = 0.045, urban = false },
	-- Keys
	{ id = "keys", name = "The Sunset Keys", u = 0.4, v = 0.93, radius = 0.2, urban = false, special = true },
	{ id = "keytown", name = "Key Marisol", u = 0.205, v = 0.942, radius = 0.024, urban = true, minH = 12, maxH = 40, style = "stucco", parkChance = 0.08, special = true },
}

-- Major roads (Roads.luau). Freeways and state roads are routed by A* through these waypoints
-- (normalized u, v); COST weights the terrain per profile (water and lakes mean bridges).
Config.ROADS = {
	FREEWAY_W = 64, BOULEVARD_W = 56, ARTERIAL_W = 44, STATE_W = 30, RAMP_W = 22,
	ARTERIAL_SPACING = 1200, -- one continuous major-road grid over every built-up area
	BRIDGE_GAP = 400, -- arterials bridge water gaps up to this long
	CAUSEWAY_EVERY = 3, CAUSEWAY_GAP = 1700, -- every 3rd east-west arterial crosses the bay to the beach
	SEED_STEP = 120, -- candidate side-street starts along majors (the trained seedEvery picks from these)
	MAJOR_STITCH = 1500, -- loose major-road ends join the nearest other major within this reach
	-- Interchange types measured on 347 real Florida interchanges (tools/interchange_stats.py), excluding
	-- freeway-to-freeway systems, which are placed wherever two freeways cross.
	INTERCHANGE_MIX = {
		urban = { clover = 0.011, diamond = 0.731, parclo = 0.255, spui = 0.004 },
		rural = { diamond = 0.820, parclo = 0.120, spui = 0.060 },
	},
	COST = {
		freeway = { water = 12, lake = 60, wetland = 2.5, mangrove = 4, urban = 1 },
		state = { water = 25, lake = 80, wetland = 3, mangrove = 6, urban = 1.2 },
		rail = { water = 15, lake = 80, wetland = 2.5, mangrove = 5, urban = 1.6 },
		connector = { water = 25, lake = 80, wetland = 3, mangrove = 6, urban = 1.2, landmark = 500 },
	},
	FREEWAYS = {
		{ { 0.72, 0.1 }, { 0.71, 0.3 }, { 0.715, 0.45 }, { 0.712, 0.52 }, { 0.7, 0.62 }, { 0.64, 0.74 }, { 0.6, 0.81 } }, -- I-1 coast spine through downtown
		{ { 0.712, 0.47 }, { 0.6, 0.44 }, { 0.47, 0.33 }, { 0.3, 0.37 }, { 0.15, 0.41 } }, -- cross-state to Pelican Bay
		{ { 0.47, 0.33 }, { 0.45, 0.16 }, { 0.44, 0.095 } }, -- north to Citrus County, ends on the north road
		{ { 0.712, 0.52 }, { 0.8, 0.5 } }, -- downtown causeway to Coral Strand
		{ { 0.7, 0.62 }, { 0.5, 0.64 }, { 0.3, 0.7 }, { 0.22, 0.52 }, { 0.22, 0.4 } }, -- wetlands expressway coast to coast via Gator Hollow, joins the cross-state freeway
		{ { 0.6, 0.81 }, { 0.58, 0.87 }, { 0.5, 0.925 }, { 0.4, 0.945 }, { 0.3, 0.948 }, { 0.2, 0.94 } }, -- overseas highway down the Keys
	},
	STATE = {
		-- Pelican Bay, past Fort Calusa and along the north coast to the coast freeway: one continuous road
		{ { 0.15, 0.41 }, { 0.16, 0.25 }, { 0.17, 0.15 }, { 0.25, 0.1 }, { 0.44, 0.095 }, { 0.6, 0.095 }, { 0.72, 0.1 } },
		{ { 0.3, 0.2 }, { 0.47, 0.33 }, { 0.62, 0.3 }, { 0.74, 0.3 } }, -- ridge road through the lake district
		{ { 0.3, 0.09 }, { 0.3, 0.37 } }, -- county line road
	},
}

-- Rail: waypoints routed by A* over the terrain, stations every `spacing` studs in towns. Metro: anchors
-- snapped to arterial intersections, track follows the arterial grid, a station at every crossing.
Config.RAIL = {
	{ name = "Coastline Railway", kind = "rail", spacing = 2600, points = { { 0.68, 0.07 }, { 0.685, 0.3 }, { 0.695, 0.45 }, { 0.69, 0.6 }, { 0.64, 0.72 }, { 0.585, 0.8 } } },
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

-- Terrain learned from 12 real USGS 3DEP elevation regions (tools/terrain_stats.py): mean elevation (m)
-- and RMS height per wavelength band (m) per land type. `cal` is fitted by tools/train_terrain.py.
Config.STUD_PER_M = 2.4 -- horizontal compression (matches tools/fetch_roads.py)
Config.VERT = 3.5 -- studs per metre vertically (true scale)
Config.TERRAIN = {
	bands_m = { 150, 300, 600, 1200, 2400, 4800 },
	mean = { coast = 7.0, farm = 33.4, scrub = 16.7, wetland = 3.0 },
	amps = {
		coast = { 1, 1, 1, 1, 1, 1 },
		farm = { 1, 1, 1, 1, 1, 1 },
		scrub = { 1, 1, 1, 1, 1, 1 },
		wetland = { 1, 1, 1, 1, 1, 1 },
	},
	cal = {
		coast = { 1.000, 1.000, 1.000, 1.000, 1.000, 1.000 },
		farm = { 0.411, 1.296, 4.129, 4.602, 3.497, 3.497 },
		scrub = { 0.166, 0.100, 0.100, 0.100, 0.100, 0.100 },
		wetland = { 0.260, 0.106, 0.100, 0.100, 0.100, 0.100 },
	},
}

return Config
