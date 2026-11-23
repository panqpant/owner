--!strict
-- What each building is for. Commercial buildings get a use from the real Florida mix
-- (BuildingUses.luau: Census business counts + national civic totals), limited to the uses that fit
-- their building style; homes and farms get theirs directly. Then the playable map-marker buildings
-- are chosen from those uses, spread across the map.
local Data = require("./BuildingUses")
local Hash = require("./Hash")

local Uses = {}

-- Which use groups each building style can hold (a warehouse isn't a dentist; a tower isn't a car wash).
local GROUPS: { [string]: { [string]: boolean } } = {
	warehouse = { ["Industry & logistics"] = true, Vehicles = true, Utilities = true },
	campus = { Community = true, Health = true, ["Food & nightlife"] = true },
	tower = { ["Money & offices"] = true, Health = true, ["Lodging & leisure"] = true, ["Food & nightlife"] = true },
}
local GENERAL = { Vehicles = true, Shopping = true, ["Food & nightlife"] = true, ["Personal services"] = true,
	["Money & offices"] = true, Health = true, ["Lodging & leisure"] = true, Community = true, Civic = true }
local COMMERCIAL = { tower = true, midrise = true, deco = true, stucco = true, warehouse = true, campus = true, shack = true }
local DIRECT = { house = "Home", trailer = "Home", farmhouse = "Farm house", barn = "Farm", silo = "Farm",
	gas = "Gas station", church = "Religious congregation (private)", diner = "Full-service restaurant" }

-- Uses that need a big building: smallest typical real footprint, m² (the building redraws if smaller).
local MIN_M2: { [string]: number } = {
	["Supercenter / warehouse club"] = 3000, ["Department store"] = 3000, ["Hospital (private)"] = 3000, ["Home centre / hardware"] = 2500,
	["Sugar mill / refinery"] = 3000, ["Amusement / theme park"] = 3000, ["Port / marine cargo"] = 3000, ["Public high school"] = 2000,
	["Public middle school"] = 2000, ["Casino"] = 2000, ["Warehouse / distribution"] = 2000, ["Public elementary school"] = 1500,
	["Supermarket / grocery"] = 1500, ["Cinema"] = 1500, ["Self-storage"] = 1500, ["Bowling centre"] = 1200, ["College / university"] = 1000,
	["Nursing home"] = 1000, ["Furniture store"] = 800, ["Electronics store"] = 800, ["Hotel / motel"] = 600,
}
local STUD2_PER_M2 = 2.4 ^ 2 -- Config.STUD_PER_M squared

-- Weighted pick from the district's real mix, restricted to the style's groups.
local function pick(mix: { { use: string, group: string, w: number } }, allowed: { [string]: boolean }, roll: number): string
	local total = 0
	for _, m in mix do
		if allowed[m.group] then
			total += m.w
		end
	end
	local acc = roll * total
	for _, m in mix do
		if allowed[m.group] then
			acc -= m.w
			if acc <= 0 then
				return m.use
			end
		end
	end
	return mix[#mix].use
end

-- Sets b.use on every building (deterministic per seed).
function Uses.assign(buildings: { any }, seed: number)
	local rng = Hash.rng(seed)
	for _, b in buildings do
		local direct = DIRECT[b.style]
		if direct then
			b.use = direct
		elseif b.style == "store" then -- hamlet general store: a rural shop of some kind
			b.use = pick(Data.rural, { Shopping = true }, rng:next())
		elseif COMMERCIAL[b.style] then
			local mix = if b.district == "keytown" then Data.keys
				elseif b.style == "shack" or b.district == "hamlet" then Data.rural
				else Data.metro
			local area = b.w * b.d / STUD2_PER_M2
			for _ = 1, 8 do -- redraw from the same real mix until the use fits the building
				b.use = pick(mix, GROUPS[b.style] or GENERAL, rng:next())
				if area >= (MIN_M2[b.use] or 0) then
					break
				end
			end
		else
			b.use = "Home"
		end
	end
end

-- Marks the playable buildings: for each feature, `count` buildings of its use, spread out where people
-- are. Candidates in random order are accepted unless too close to one already chosen; the spacing starts
-- at the even-spread distance for the count and shrinks if too few fit. Sets b.marker = feature.
function Uses.markers(buildings: { any }, seed: number)
	local rng = Hash.rng(seed)
	-- no district gets more than 1.5x its fair share of markers by building count (small towns stay uncluttered)
	local total, inDistrict, cap, used = 0, {}, {}, {}
	for _, m in Data.markers do
		total += m.count
	end
	for _, b in buildings do
		inDistrict[b.district] = (inDistrict[b.district] or 0) + 1
	end
	for dId, n in inDistrict do
		cap[dId], used[dId] = math.max(2, math.ceil(1.5 * n * total / #buildings)), 0
	end
	for _, m in Data.markers do
		local pool = {}
		local x0, z0, x1, z1 = math.huge, math.huge, -math.huge, -math.huge
		for _, b in buildings do
			if b.use == m.use and not b.marker then
				table.insert(pool, b)
				x0, z0, x1, z1 = math.min(x0, b.x), math.min(z0, b.z), math.max(x1, b.x), math.max(z1, b.z)
			end
		end
		for i = #pool, 2, -1 do -- shuffle
			local j = rng:int(1, i)
			pool[i], pool[j] = pool[j], pool[i]
		end
		local spacing = 0.5 * math.sqrt((x1 - x0) * (z1 - z0) / math.max(m.count, 1))
		local chosen = {}
		while #chosen < math.min(m.count, #pool) and spacing > 1 do
			for _, b in pool do
				if #chosen >= m.count then
					break
				end
				local ok = not b.marker and used[b.district] < cap[b.district]
				for _, c in chosen do
					ok = ok and (b.x - c.x) ^ 2 + (b.z - c.z) ^ 2 >= spacing * spacing
				end
				if ok then
					b.marker = m.feature
					used[b.district] += 1
					table.insert(chosen, b)
				end
			end
			spacing *= 0.7
		end
	end
end

return Uses
