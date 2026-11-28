-- Run with: lune run tests/profile.spec.luau
local Profile = require("../src/server/Services/Profile")

local function eq(a, b, what)
	assert(a == b, `{what}: expected {b}, got {a}`)
end

-- a brand-new player gets the full default
local fresh = Profile.reconcile({}, Profile.default())
eq(fresh.coins, 0, "fresh coins")
eq(fresh.vehicles.Scooter, true, "starts with the scooter")
eq(fresh.upgrades.brakes, 0, "upgrade levels exist")

-- an old save keeps its values and gains new fields
local old = { coins = 1234, vehicles = { Scooter = true, Van = true }, upgrades = { engine = 3 } }
Profile.reconcile(old, Profile.default())
eq(old.coins, 1234, "coins kept")
eq(old.vehicles.Van, true, "owned van kept")
eq(old.upgrades.engine, 3, "engine level kept")
eq(old.upgrades.padding, 0, "missing upgrade filled in")
eq(old.settings.feel, 2, "settings added")
eq(old.daily.streak, 0, "daily added")

-- defaults are copies: changing one player's save never changes another's
local a = Profile.reconcile({}, Profile.default())
local b = Profile.reconcile({}, Profile.default())
a.vehicles.Van = true
eq(b.vehicles.Van, nil, "no shared tables")

-- receipts: remembered, capped, oldest dropped
local r = Profile.reconcile({}, Profile.default())
for k = 1, 60 do
	Profile.addReceipt(r, "r" .. k)
end
eq(#r.receipts, 50, "capped at 50")
eq(Profile.hasReceipt(r, "r60"), true, "newest kept")
eq(Profile.hasReceipt(r, "r5"), false, "oldest dropped")

print("profile ok")
