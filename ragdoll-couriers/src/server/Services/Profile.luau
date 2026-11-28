-- What a player's save looks like, and how an old or partial save is brought up to date.
-- Pure Luau (no Roblox services) so it can be tested with Lune: lune run tests/profile.spec.luau

local Profile = {}

Profile.VERSION = 1

-- Every field a save has. New fields added here appear in old saves automatically (see reconcile).
function Profile.default(): { [string]: any }
	return {
		version = Profile.VERSION,
		coins = 0,
		xp = 0,
		level = 1,
		deliveries = 0,
		vehicles = { Scooter = true }, -- owned
		equipped = "Scooter",
		upgrades = { suspension = 0, padding = 0, engine = 0, cargo = 0, brakes = 0 },
		districts = { Hub = true, Suburbs = true }, -- unlocked
		settings = { feel = 2, music = true, sfx = true },
		stats = {
			crashes = 0,
			thievesCaught = 0,
			customersServed = 0,
			nearMisses = 0,
			bestCondition = 0,
			coinsEarned = 0,
		},
		daily = { day = 0, streak = 0 }, -- last claimed day number (os.time() // 86400) and the streak
		passes = {}, -- game pass name -> true (cached; MarketplaceService is checked on join too)
		receipts = {}, -- developer product receipt ids already granted, newest last (capped)
	}
end

-- Fills in anything missing from `data` using `template`, recursing into tables. Values the player
-- already has are never touched, and keys the template doesn't know about are kept as they are.
function Profile.reconcile(data: { [string]: any }, template: { [string]: any }): { [string]: any }
	for key, value in template do
		if data[key] == nil then
			data[key] = if type(value) == "table" then Profile.reconcile({}, value) else value
		elseif type(value) == "table" and type(data[key]) == "table" and not Profile.isList(value) then
			Profile.reconcile(data[key], value)
		end
	end
	return data
end

function Profile.isList(t: { [any]: any }): boolean
	return #t > 0 -- lists (like receipts) are copied whole, never merged item by item
end

-- Remembers a processed purchase receipt; keeps the newest `cap` so the save stays small.
function Profile.addReceipt(data: { [string]: any }, receiptId: string, cap: number?)
	local list = data.receipts
	table.insert(list, receiptId)
	local limit = cap or 50
	while #list > limit do
		table.remove(list, 1)
	end
end

function Profile.hasReceipt(data: { [string]: any }, receiptId: string): boolean
	return table.find(data.receipts, receiptId) ~= nil
end

return Profile
