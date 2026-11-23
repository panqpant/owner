--!strict
-- Building shapes. Every building becomes one or more parts (footprint polygon, height, roof), built from
-- real US/Florida building types and fitted inside its lot. Local frame: x along the street, z away from
-- it; the street is at z = -d/2, so garages, porches and shopfronts face -z.
-- Homes: each neighbourhood (arterial block) draws a small palette of house types, size and roof, so
-- houses on a street are similar but each varies (mirrored, garage side, size).
local Hash = require("./Hash")
local Footprints = require("./FootprintData")

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
		local ud = d * 0.9 * (if r:next() < 0.5 then 1 else r:range(0.55, 0.9)) -- uneven rear additions; fronts on the street line
		table.insert(parts, part(rect(-w * 0.475 + uw * (i + 0.5), -d * 0.45 + ud / 2, uw * 0.99, ud), h * r:range(0.7, 1.15), "flat"))
	end
	return parts
end
local function warehouse(w: number, d: number, h: number, r: Hash.Rng): { Part } -- shed + loading docks + office
	return { part(rect(0, d * 0.08, w * 0.95, d * 0.75), h, "flat"), part(rect(-w * 0.32, -d * 0.38, w * 0.28, d * 0.14), h * 0.5, "flat"),
		part(rect(w * 0.2, -d * 0.33, w * 0.5, d * 0.06), h * 0.15, "flat") }
end
local function campus(w: number, d: number, h: number, r: Hash.Rng): { Part } -- H plan; long footprints get an L
	if math.max(w, d) > 1.6 * math.min(w, d) then
		return { part(rect(0, -d * 0.2, w, d * 0.6), h, "gable"), part(rect(-w * 0.3, d * 0.2, w * 0.4, d * 0.6), h * 0.85, "gable") }
	end
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

-- Stretch parts so their bounding box is exactly the w x d footprint (the real size drawn in City).
local function fit(parts: { Part }, w: number, d: number)
	local x0, z0, x1, z1 = math.huge, math.huge, -math.huge, -math.huge
	for _, p in parts do
		for i = 1, #p.pts - 1, 2 do
			x0, x1 = math.min(x0, p.pts[i]), math.max(x1, p.pts[i])
			z0, z1 = math.min(z0, p.pts[i + 1]), math.max(z1, p.pts[i + 1])
		end
	end
	local sx, sz = w / math.max(x1 - x0, 1e-6), d / math.max(z1 - z0, 1e-6)
	for _, p in parts do
		for i = 1, #p.pts - 1, 2 do
			p.pts[i] = (p.pts[i] - x0) * sx - w / 2
			p.pts[i + 1] = (p.pts[i + 1] - z0) * sz - d / 2
		end
	end
end

-- A part that is the whole footprint box makes the outline a plain rectangle; cut a corner out of it
-- (an L), and pull parts standing on it (base > 0) away from that corner.
local function notch(parts: { Part }, w: number, d: number, r: Hash.Rng)
	for _, p in parts do
		if #p.pts == 8 and p.base == 0 and math.abs(p.pts[1] + w / 2) < 0.01 and math.abs(p.pts[5] - w / 2) < 0.01
			and math.abs(p.pts[2] + d / 2) < 0.01 and math.abs(p.pts[6] - d / 2) < 0.01 then
			local nx, nz = r:range(0.2, 0.4), r:range(0.25, 0.5)
			local fx, fz = if r:next() < 0.5 then 1 else -1, 1 -- cut a back corner, keep the street face whole
			local cx, cz = fx * w / 2, fz * d / 2 -- corner removed
			local ix, iz = cx - fx * nx * w, cz - fz * nz * d
			p.pts = { -cx, -cz, cx, -cz, cx, iz, ix, iz, ix, cz, -cx, cz }
			for _, q in parts do
				if q.base > 0 then
					for i = 1, #q.pts - 1, 2 do
						q.pts[i] = -cx + (q.pts[i] + cx) * (1 - nx)
						q.pts[i + 1] = -cz + (q.pts[i + 1] + cz) * (1 - nz)
					end
				end
			end
			return
		end
	end
end

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
		-- real share of plain-rectangle outlines per style (FootprintData); use-specific forms keep theirs
		local f = Footprints[b.style]
		if f and not useShape then
			if r:next() < f.box then
				local roof = if b.style == "house" then parts[1].roof else "flat"
				parts = { part(rect(0, 0, w, d), parts[1].h, roof) }
			else
				fit(parts, w, d)
				notch(parts, w, d, r)
			end
		end
		fit(parts, w, d)
		b.parts = parts
	end
end

-- Landmarks: a real site plan per kind instead of one box, inside the landmark's w x d footprint.
-- Roofs name the surface for the renderer and builder: lot (car park), field, stands, runway, deck,
-- tank, water, panel, wall, pit.
local function ringParts(rx: number, rz: number, t: number, h: number, n: number, roof: string): { Part }
	local out = {}
	for k = 0, n - 1 do
		local a0, a1 = k / n * 2 * math.pi, (k + 1) / n * 2 * math.pi
		table.insert(out, part({ math.cos(a0) * rx, math.sin(a0) * rz, math.cos(a1) * rx, math.sin(a1) * rz,
			math.cos(a1) * (rx - t), math.sin(a1) * (rz - t), math.cos(a0) * (rx - t), math.sin(a0) * (rz - t) }, h, roof))
	end
	return out
end
local function add(list: { Part }, more: { Part })
	for _, p in more do
		table.insert(list, p)
	end
end
local function has(name: string, words: { string }): boolean
	for _, wd in words do
		if string.find(name, "%f[%w]" .. wd .. "%f[%W]") then
			return true
		end
	end
	return false
end

local SITE: { { words: { string }, plan: (w: number, d: number, h: number, r: Hash.Rng) -> { Part } } } = {
	{ words = { "raceway", "racecourse", "speedway", "course" }, plan = function(w, d, h, r) -- oval track + grandstand
		local p = { part(rect(0, 0, w, d), 0.2, "lot") }
		add(p, ringParts(w * 0.45, d * 0.4, math.min(w, d) * 0.07, 0.4, 28, "runway"))
		table.insert(p, part(rect(0, -d * 0.45, w * 0.5, d * 0.08), h * 0.4, "stands"))
		return p
	end },
	{ words = { "stadium", "ballpark", "arena", "fronton", "rodeo", "fairgrounds" }, plan = function(w, d, h, r) -- bowl around a field
		local p = { part(rect(0, 0, w, d), 0.2, "lot"), part(circle(0, 0, math.min(w, d) * 0.3, 20), 0.5, "field") }
		local rx, rz = w * 0.36, d * 0.36
		add(p, ringParts(rx, rz, math.min(rx, rz) * 0.32, h * 0.5, 24, "stands"))
		return p
	end },
	{ words = { "airfield", "airport", "air station", "boneyard", "jets", "skydive" }, plan = function(w, d, h, r)
		local hangars = {}
		for k = 0, 2 do
			table.insert(hangars, part(rect(-w * 0.35 + k * w * 0.1, d * 0.38, w * 0.07, d * 0.18), 20, "flat"))
		end
		local p = { part(rect(0, -d * 0.22, w * 0.98, d * 0.22), 0.3, "runway"), part(rect(0, d * 0.06, w * 0.85, d * 0.07), 0.3, "runway"),
			part(rect(-w * 0.25, d * 0.28, w * 0.35, d * 0.16), 0.3, "lot"), part(rect(w * 0.15, d * 0.36, w * 0.14, d * 0.2), 18, "flat"),
			part(circle(w * 0.3, d * 0.36, d * 0.05, 8), h, "flat") }
		add(p, hangars)
		return p
	end },
	{ words = { "mall", "galleria", "outlets", "power center", "swap" }, plan = function(w, d, h, r) -- concourse + anchors in a car park
		return { part(rect(0, 0, w, d), 0.2, "lot"), part(rect(0, d * 0.05, w * 0.6, d * 0.18), h * 0.7, "flat"),
			part(rect(-w * 0.33, d * 0.05, w * 0.16, d * 0.36), h, "flat"), part(rect(w * 0.33, d * 0.05, w * 0.16, d * 0.36), h, "flat"),
			part(rect(0, d * 0.2, w * 0.18, d * 0.22), h, "flat"), part(rect(w * 0.12, -d * 0.36, w * 0.2, d * 0.14), h * 1.4, "flat") }
	end },
	{ words = { "pier", "wharf", "dock", "docks", "basin", "marina", "fleet", "watersports", "boathouse" }, plan = function(w, d, h, r)
		local p = { part(rect(0, 0, w * 0.96, d * 0.12), 0.6, "deck"), part(rect(w * 0.42, 0, w * 0.08, d * 0.7), 0.6, "deck"),
			part(rect(-w * 0.38, 0, w * 0.1, d * 0.2), h * 0.4, "flat") }
		for k = 1, 4 do -- finger slips
			table.insert(p, part(rect(-w * 0.2 + k * w * 0.1, d * 0.2, w * 0.015, d * 0.26), 0.6, "deck"))
		end
		return p
	end },
	{ words = { "tank farm", "fuel farm", "water treatment", "pump station" }, plan = function(w, d, h, r) -- grid of tanks
		local p = { part(rect(0, 0, w, d), 0.2, "lot") }
		local n = math.max(2, math.floor(math.min(w, d) / 70))
		local rr = math.min(w, d) / n * 0.35
		for i = 0, n - 1 do
			for j = 0, n - 1 do
				table.insert(p, part(circle(-w / 2 + w * (i + 0.5) / n, -d / 2 + d * (j + 0.5) / n, rr, 14), h * r:range(0.4, 0.8), "tank"))
			end
		end
		return p
	end },
	{ words = { "nuclear", "power", "energy" }, plan = function(w, d, h, r) -- turbine hall, cooling towers, switchyard
		return { part(rect(0, 0, w, d), 0.2, "lot"), part(rect(-w * 0.1, -d * 0.1, w * 0.4, d * 0.22), h * 0.6, "flat"),
			part(circle(w * 0.25, -d * 0.12, math.min(w, d) * 0.15, 16), h, "dome"), part(circle(-w * 0.35, d * 0.25, math.min(w, d) * 0.12, 16), h * 0.8, "dome"),
			part(rect(w * 0.2, d * 0.3, w * 0.35, d * 0.25), 6, "panel") }
	end },
	{ words = { "solar" }, plan = function(w, d, h, r) -- panel rows
		local p = {}
		for k = 0, 11 do
			table.insert(p, part(rect(0, -d * 0.46 + k * d * 0.084, w * 0.95, d * 0.05), 3, "panel"))
		end
		return p
	end },
	{ words = { "container", "rail yard", "distribution", "cargo", "auto export", "transit garage", "storage" }, plan = function(w, d, h, r)
		local p = { part(rect(0, 0, w, d), 0.2, "lot") }
		for k = 0, 7 do -- stacks / sheds in rows
			table.insert(p, part(rect(-w * 0.1, -d * 0.4 + k * d * 0.1, w * 0.7, d * 0.06), h * 0.25, "flat"))
		end
		table.insert(p, part(rect(w * 0.38, 0, w * 0.04, d * 0.9), h, "flat")) -- crane rail / loading shed
		return p
	end },
	{ words = { "penitentiary", "prison", "jail", "detention" }, plan = function(w, d, h, r) -- wall + hub + radial wings
		local t = math.min(w, d) * 0.02
		local p = { part(rect(0, -d / 2 + t / 2, w, t), 20, "wall"), part(rect(0, d / 2 - t / 2, w, t), 20, "wall"),
			part(rect(-w / 2 + t / 2, 0, t, d), 20, "wall"), part(rect(w / 2 - t / 2, 0, t, d), 20, "wall"),
			part(circle(0, 0, math.min(w, d) * 0.1, 12), h, "flat") }
		for k = 0, 5 do
			local a = k / 6 * 2 * math.pi
			local cx, cz = math.cos(a) * math.min(w, d) * 0.25, math.sin(a) * math.min(w, d) * 0.25
			local ux, uz, L, T = math.cos(a), math.sin(a), math.min(w, d) * 0.15, math.min(w, d) * 0.05
			table.insert(p, part({ cx - ux * L - uz * T, cz - uz * L + ux * T, cx + ux * L - uz * T, cz + uz * L + ux * T,
				cx + ux * L + uz * T, cz + uz * L - ux * T, cx - ux * L + uz * T, cz - uz * L - ux * T }, h * 0.7, "flat"))
		end
		return p
	end },
	{ words = { "hospital", "medical" }, plan = function(w, d, h, r) -- cross-plan tower, garage
		return { part(rect(0, 0, w, d), 0.2, "lot"), part(rect(-w * 0.1, 0, w * 0.6, d * 0.2), h, "flat"), part(rect(-w * 0.1, 0, w * 0.2, d * 0.6), h, "flat"),
			part(rect(w * 0.34, -d * 0.3, w * 0.22, d * 0.3), h * 0.35, "flat"), part(circle(-w * 0.1, 0, math.min(w, d) * 0.05, 8), h * 1.05, "flat") }
	end },
	{ words = { "university", "college", "school", "institute", "greek", "library" }, plan = function(w, d, h, r) -- halls around a quad
		return { part(rect(0, d * 0.38, w, d * 0.24), 0.2, "lot"), part(rect(0, 0, w * 0.45, d * 0.35), 0.4, "field"),
			part(rect(0, -d * 0.32, w * 0.7, d * 0.16), h, "gable"), part(rect(-w * 0.36, 0, w * 0.16, d * 0.45), h * 0.8, "gable"),
			part(rect(w * 0.36, 0, w * 0.16, d * 0.45), h * 0.8, "gable"), part(rect(0, d * 0.2, w * 0.3, d * 0.08), h * 0.6, "gable") }
	end },
	{ words = { "mine", "landfill" }, plan = function(w, d, h, r) -- terraced pit / mound
		local p = {}
		for k = 0, 3 do
			local f = 1 - k * 0.2
			table.insert(p, part(chamfer(0, 0, w * f, d * f, math.min(w, d) * f * 0.2), h * (k + 1) / 4, "pit"))
		end
		return p
	end },
	{ words = { "water park", "adventure park", "resort", "springs", "casino", "lagoon" }, plan = function(w, d, h, r)
		local p = { part(rect(0, 0, w, d), 0.3, "field"), part(rect(0, -d * 0.3, w * 0.6, d * 0.14), h, "flat"),
			part(rect(-w * 0.28, d * 0.33, w * 0.4, d * 0.24), 0.2, "lot") }
		for k = 0, 3 do
			table.insert(p, part(circle(-w * 0.25 + k * w * 0.17, d * 0.02 + (k % 2) * d * 0.1, math.min(w, d) * 0.07, 12), 0.3, "water"))
		end
		return p
	end },
	{ words = { "estates", "active living", "preserve", "country club", "horse farm", "dairy", "nursery", "stilt shacks" }, plan = function(w, d, h, r)
		local p = { part(rect(0, 0, w, d), 0.2, "field") } -- grounds with a grid of small buildings
		local n = math.max(2, math.floor(math.min(w, d) / 90))
		for i = 0, n - 1 do
			for j = 0, n - 1 do
				if r:next() < 0.7 then
					table.insert(p, part(rect(-w / 2 + w * (i + 0.5) / n, -d / 2 + d * (j + 0.5) / n, w / n * 0.4, d / n * 0.35), math.min(h, 20), "hip"))
				end
			end
		end
		return p
	end },
	{ words = { "tower", "light", "lighthouse", "buoy", "transmitter", "radar", "domes" }, plan = function(w, d, h, r)
		return { part(rect(0, 0, w, d), 0.2, "lot"), part(circle(0, 0, math.min(w, d) * 0.4, 12), h, "flat") }
	end },
}

function Shapes.landmark(l: any, r: Hash.Rng): { Part }
	local name = string.lower(l.name)
	for _, s in SITE do
		if has(name, s.words) then
			return s.plan(l.w, l.d, l.h, r)
		end
	end
	-- default: main building with a wing, set in its car park / grounds
	return { part(rect(0, 0, l.w, l.d), 0.2, "lot"), part(chamfer(0, -l.d * 0.1, l.w * 0.6, l.d * 0.5, math.min(l.w, l.d) * 0.08), l.h, "flat"),
		part(rect(l.w * 0.3, l.d * 0.15, l.w * 0.25, l.d * 0.3), l.h * 0.5, "flat") }
end

function Shapes.landmarks(list: { any }, seed: number)
	for i, l in list do
		if l.site ~= "bridge" then
			l.parts = Shapes.landmark(l, Hash.rng(Hash.int(seed, i, 11)))
		end
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
