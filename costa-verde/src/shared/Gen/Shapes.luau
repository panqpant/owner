--!strict
-- Building shapes. Every building becomes one or more parts (footprint polygon, height, roof), built from
-- real US/Florida building types and fitted inside its lot. Local frame: x along the street, z away from
-- it; the street is at z = -d/2, so garages, porches and shopfronts face -z.
-- Homes: each neighbourhood (arterial block) draws a small palette of house types, size and roof, so
-- houses on a street are similar but each varies (mirrored, garage side, size).
local Hash = require("./Hash")

local Shapes = {}

export type Part = { pts: { number }, h: number, base: number, roof: string }

-- Polygon helpers (flat x, z lists) ----------------------------------------------------------------
local function rect(cx: number, cz: number, w: number, d: number): { number }
	return { cx - w / 2, cz - d / 2, cx + w / 2, cz - d / 2, cx + w / 2, cz + d / 2, cx - w / 2, cz + d / 2 }
end
local function chamfer(cx: number, cz: number, w: number, d: number, c: number): { number }
	return { cx - w / 2 + c, cz - d / 2, cx + w / 2 - c, cz - d / 2, cx + w / 2, cz - d / 2 + c, cx + w / 2, cz + d / 2 - c,
		cx + w / 2 - c, cz + d / 2, cx - w / 2 + c, cz + d / 2, cx - w / 2, cz + d / 2 - c, cx - w / 2, cz - d / 2 + c }
end
local function circle(cx: number, cz: number, r: number, n: number): { number }
	local p = {}
	for i = 0, n - 1 do
		local a = i / n * 2 * math.pi
		table.insert(p, cx + math.cos(a) * r)
		table.insert(p, cz + math.sin(a) * r)
	end
	return p
end
local function part(pts: { number }, h: number, roof: string, base: number?): Part
	return { pts = pts, h = h, base = base or 0, roof = roof }
end

-- Homes ------------------------------------------------------------------------------------------
-- Each returns parts inside w x d. m = 1 or -1 mirrors left/right.
local HOUSES: { [string]: (w: number, d: number, h: number, roof: string, m: number, r: Hash.Rng) -> { Part } } = {
	ranch = function(w, d, h, roof, m, r) -- long single storey + garage wing to the street
		local gw = w * 0.32
		return { part(rect(-m * gw / 2, 0, w - gw, d * 0.55), h, roof), part(rect(m * (w / 2 - gw / 2), -d * 0.12, gw, d * 0.5), h * 0.85, roof) }
	end,
	l_ranch = function(w, d, h, roof, m, r)
		return { part(rect(0, d * 0.08, w * 0.95, d * 0.42), h, roof), part(rect(m * w * 0.3, -d * 0.15, w * 0.34, d * 0.5), h, roof) }
	end,
	colonial = function(w, d, h, roof, m, r) -- two storey box, small porch
		return { part(rect(0, 0.05 * d, w * 0.72, d * 0.5), h * 1.8, roof), part(rect(0, -d * 0.25, w * 0.32, d * 0.1), h * 0.6, "flat") }
	end,
	courtyard = function(w, d, h, roof, m, r) -- Mediterranean U around a back courtyard
		return { part(rect(0, -d * 0.18, w * 0.9, d * 0.22), h, roof), part(rect(-w * 0.34, d * 0.1, w * 0.22, d * 0.4), h, roof),
			part(rect(w * 0.34, d * 0.1, w * 0.22, d * 0.4), h, roof) }
	end,
	bungalow = function(w, d, h, roof, m, r) -- small + deep front porch
		return { part(rect(0, d * 0.08, w * 0.62, d * 0.46), h * 0.9, roof), part(rect(0, -d * 0.22, w * 0.62, d * 0.14), h * 0.55, "flat") }
	end,
	split_level = function(w, d, h, roof, m, r)
		return { part(rect(-m * w * 0.18, 0, w * 0.5, d * 0.5), h * 1.6, roof), part(rect(m * w * 0.22, 0.03 * d, w * 0.42, d * 0.44), h, roof) }
	end,
	duplex = function(w, d, h, roof, m, r) -- two mirrored units
		return { part(rect(-w * 0.23, 0, w * 0.44, d * 0.55), h, roof), part(rect(w * 0.23, 0, w * 0.44, d * 0.55), h, roof) }
	end,
	townhouses = function(w, d, h, roof, m, r) -- a short row, each unit stepped a little
		local n = r:int(3, 5)
		local parts = {}
		for i = 0, n - 1 do
			local uw = w * 0.92 / n
			table.insert(parts, part(rect(-w * 0.46 + uw * (i + 0.5), (i % 2) * d * 0.04, uw * 0.98, d * 0.5), h * 1.7, roof))
		end
		return parts
	end,
	shotgun = function(w, d, h, roof, m, r) -- narrow and deep
		return { part(rect(0, d * 0.05, w * 0.4, d * 0.78), h * 0.9, roof), part(rect(0, -d * 0.4, w * 0.4, d * 0.08), h * 0.5, "flat") }
	end,
}
local HOUSE_SETS = { -- neighbourhood palettes (real Florida subdivision mixes)
	{ "ranch", "l_ranch", "ranch" }, { "courtyard", "l_ranch", "ranch" }, { "colonial", "split_level", "colonial" },
	{ "bungalow", "shotgun", "bungalow" }, { "ranch", "duplex", "l_ranch" }, { "townhouses", "townhouses", "duplex" },
	{ "courtyard", "colonial", "courtyard" },
}
local ROOFS = { "hip", "gable", "hip", "flat" } -- hip roofs dominate in hurricane country

-- Commercial and civic ---------------------------------------------------------------------------
local function tower(w: number, d: number, h: number, r: Hash.Rng): { Part }
	local kind = r:int(1, 4)
	local podium = part(rect(0, 0, w, d), math.min(h * 0.18, 60), "flat")
	if kind == 1 then -- setbacks
		return { podium, part(rect(0, d * 0.05, w * 0.7, d * 0.7), h * 0.75, "flat", podium.h), part(rect(0, d * 0.05, w * 0.45, d * 0.45), h * 0.12, "flat", podium.h + h * 0.75) }
	elseif kind == 2 then -- slab
		return { podium, part(rect(0, d * 0.1, w * 0.85, d * 0.38), h, "flat", podium.h) }
	elseif kind == 3 then -- rounded
		return { podium, part(circle(0, d * 0.05, math.min(w, d) * 0.36, 12), h, "dome", podium.h) }
	end
	return { podium, part(chamfer(0, d * 0.05, w * 0.72, d * 0.72, math.min(w, d) * 0.15), h, "flat", podium.h) } -- chamfered
end
local function midrise(w: number, d: number, h: number, r: Hash.Rng): { Part }
	local kind = r:int(1, 3)
	if kind == 1 then -- L block
		return { part(rect(0, -d * 0.2, w * 0.95, d * 0.5), h, "flat"), part(rect(-w * 0.3, d * 0.22, w * 0.35, d * 0.45), h * 0.8, "flat") }
	elseif kind == 2 then -- courtyard block
		return { part(rect(0, -d * 0.35, w * 0.95, d * 0.25), h, "flat"), part(rect(0, d * 0.35, w * 0.95, d * 0.25), h, "flat"),
			part(rect(-w * 0.36, 0, w * 0.23, d * 0.45), h, "flat"), part(rect(w * 0.36, 0, w * 0.23, d * 0.45), h, "flat") }
	end
	return { part(rect(0, 0, w * 0.95, d * 0.9), h * 0.6, "flat"), part(rect(0, d * 0.15, w * 0.6, d * 0.55), h * 0.4, "flat", h * 0.6) } -- stepped
end
local function deco(w: number, d: number, h: number, r: Hash.Rng): { Part } -- rounded corners + centre tower element
	local c = math.min(w, d) * 0.18
	return { part(chamfer(0, 0, w * 0.95, d * 0.85, c), h, "flat"), part(rect(0, -d * 0.4, w * 0.18, d * 0.08), h * 1.3, "spire") }
end
local function shopfronts(w: number, d: number, h: number, r: Hash.Rng): { Part } -- 2-4 attached shops, mixed heights
	local n = r:int(2, 4)
	local parts = {}
	for i = 0, n - 1 do
		local uw = w * 0.95 / n
		table.insert(parts, part(rect(-w * 0.475 + uw * (i + 0.5), d * 0.05, uw * 0.99, d * 0.8), h * r:range(0.7, 1.15), "flat"))
	end
	return parts
end
local function warehouse(w: number, d: number, h: number, r: Hash.Rng): { Part } -- shed + loading docks + office
	return { part(rect(0, d * 0.08, w * 0.95, d * 0.75), h, "flat"), part(rect(-w * 0.32, -d * 0.38, w * 0.28, d * 0.14), h * 0.5, "flat"),
		part(rect(w * 0.2, -d * 0.33, w * 0.5, d * 0.06), h * 0.15, "flat") }
end
local function campus(w: number, d: number, h: number, r: Hash.Rng): { Part } -- H plan
	return { part(rect(-w * 0.36, 0, w * 0.22, d * 0.9), h, "gable"), part(rect(w * 0.36, 0, w * 0.22, d * 0.9), h, "gable"),
		part(rect(0, 0, w * 0.5, d * 0.25), h * 0.85, "gable") }
end

-- Shapes driven by what the building is used for (overrides the style shape).
local USE_SHAPES: { [string]: (w: number, d: number, h: number, r: Hash.Rng) -> { Part } } = {
	["Gas station"] = function(w, d, h, r) -- pump canopy at the street, shop behind
		return { part(rect(0, -d * 0.18, w * 0.8, d * 0.35), h * 0.45, "canopy", h * 0.4), part(rect(0, d * 0.3, w * 0.6, d * 0.3), h * 0.7, "flat") }
	end,
	["Religious congregation (private)"] = function(w, d, h, r) -- nave + transept + steeple
		return { part(rect(0, d * 0.1, w * 0.35, d * 0.75), h, "gable"), part(rect(0, d * 0.18, w * 0.75, d * 0.2), h * 0.85, "gable"),
			part(rect(0, -d * 0.32, w * 0.14, w * 0.14), h * 2.2, "spire") }
	end,
	["Hotel / motel"] = function(w, d, h, r) -- two-storey L motel around the car park
		return { part(rect(0, d * 0.32, w * 0.95, d * 0.25), math.max(h * 0.6, 24), "flat"), part(rect(-w * 0.38, 0, w * 0.18, d * 0.6), math.max(h * 0.6, 24), "flat") }
	end,
	["Self-storage"] = function(w, d, h, r) -- long single-storey unit rows
		local parts = {}
		for i = 0, 3 do
			table.insert(parts, part(rect(0, -d * 0.36 + i * d * 0.24, w * 0.9, d * 0.14), 10, "flat"))
		end
		return parts
	end,
	["Car wash"] = function(w, d, h, r) -- tunnel perpendicular to the street + vacuum canopy
		return { part(rect(-w * 0.2, d * 0.05, w * 0.22, d * 0.8), 16, "flat"), part(rect(w * 0.25, -d * 0.1, w * 0.35, d * 0.25), 12, "canopy", 10) }
	end,
	["Fast food"] = function(w, d, h, r) -- small box set back behind its car park
		return { part(rect(0, d * 0.2, w * 0.55, d * 0.4), math.min(h, 20), "flat") }
	end,
	["Supercenter / warehouse club"] = function(w, d, h, r)
		return { part(rect(0, d * 0.25, w * 0.95, d * 0.5), 34, "flat") } -- big box behind a big car park
	end,
}

-- Assign shapes to every building (after Uses.assign). Sets b.parts and b.type.
function Shapes.assign(buildings: { any }, seed: number)
	local SP = 1200 -- neighbourhood = arterial block
	for i, b in buildings do
		local r = Hash.rng(Hash.int(seed, i, 7))
		local w, d, h = b.w, b.d, b.h
		local parts: { Part }
		local useShape = USE_SHAPES[b.use]
		if b.style == "house" then
			-- neighbourhood palette from the block, then per-house variation
			local cell = Hash.int(b.x // SP, b.z // SP, seed)
			local set = HOUSE_SETS[1 + cell % #HOUSE_SETS]
			local roof = ROOFS[1 + (cell // 7) % #ROOFS]
			local sizeK = 0.9 + ((cell // 31) % 5) * 0.05 -- the neighbourhood's era/size
			local kind = set[r:int(1, #set)]
			b.type = kind
			parts = HOUSES[kind](w * math.min(1, sizeK * r:range(0.92, 1.08)), d * math.min(1, sizeK * r:range(0.92, 1.08)), h, roof, if r:next() < 0.5 then 1 else -1, r)
		elseif useShape then
			b.type = b.use
			parts = useShape(w, d, h, r)
		elseif b.style == "tower" then
			b.type, parts = "tower", tower(w, d, h, r)
		elseif b.style == "midrise" then
			b.type, parts = "midrise", midrise(w, d, h, r)
		elseif b.style == "deco" then
			b.type, parts = "art deco", deco(w, d, h, r)
		elseif b.style == "stucco" or b.style == "shack" or b.style == "store" or b.style == "diner" then
			b.type, parts = "shopfronts", shopfronts(w, d, h, r)
		elseif b.style == "warehouse" then
			b.type, parts = "warehouse", warehouse(w, d, h, r)
		elseif b.style == "campus" then
			b.type, parts = "campus hall", campus(w, d, h, r)
		elseif b.style == "trailer" then
			b.type, parts = "mobile home", { part(rect(0, 0, w * 0.35, d * 0.9), 10, "flat") }
		elseif b.style == "farmhouse" then -- with wraparound porch
			b.type, parts = "farmhouse", { part(rect(0, d * 0.05, w * 0.7, d * 0.6), h * 1.5, "gable"), part(rect(0, -d * 0.3, w * 0.85, d * 0.12), h * 0.5, "flat"),
				part(rect(w * 0.38, 0, w * 0.1, d * 0.6), h * 0.5, "flat") }
		elseif b.style == "barn" then
			b.type, parts = "barn", { part(rect(0, 0, w * 0.9, d * 0.9), h, "gambrel") }
		elseif b.style == "silo" then
			b.type, parts = "silo", { part(circle(0, 0, math.min(w, d) * 0.45, 12), h, "dome") }
		else
			b.type, parts = b.style, { part(rect(0, 0, w * 0.9, d * 0.9), h, "flat") }
		end
		b.parts = parts
	end
end

-- Self-check: every part stays inside its lot box (used by the audit and tests).
function Shapes.inside(b: any): boolean
	for _, p in b.parts do
		for i = 1, #p.pts - 1, 2 do
			if math.abs(p.pts[i]) > b.w / 2 + 0.01 or math.abs(p.pts[i + 1]) > b.d / 2 + 0.01 then
				return false
			end
		end
	end
	return true
end

return Shapes
