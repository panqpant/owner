-- Saving and loading players' progress (DataStore), with session locking so two servers never
-- overwrite each other when a player hops, retries on errors, autosave, and a save on shutdown.
-- In Studio without "Enable Studio Access to API Services", progress lasts for the session only.

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local Profile = require(script.Parent.Profile)

local STORE_NAME = "Couriers_v1"
local LOCK_SECONDS = 600 -- a lock older than this is from a server that died: take it over
local AUTOSAVE_SECONDS = 120
local RETRIES = 4

local Data = {}

local profiles: { [Player]: { [string]: any } } = {}
local loading: { [Player]: boolean } = {}
local store: DataStore? = nil
local offline = false

do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(STORE_NAME)
	end)
	if ok then
		store = result
	else
		offline = true
		warn("DataStore unavailable, progress won't save this session:", result)
	end
end

local function key(player: Player): string
	return "player_" .. player.UserId
end

-- Calls fn up to RETRIES times with a growing wait. Returns ok, result.
local function retry<T>(fn: () -> T): (boolean, T | string)
	local lastErr = ""
	for attempt = 1, RETRIES do
		local ok, result = pcall(fn)
		if ok then
			return true, result
		end
		lastErr = tostring(result)
		if string.find(lastErr, "API Services") or string.find(lastErr, "StudioAccessToApisNotAllowed") then
			return false, lastErr -- Studio without API access: retrying won't help
		end
		task.wait(attempt * 1.5)
	end
	return false, lastErr
end

-- Loads (or creates) a player's save and locks it to this server. Yields. Returns the live profile.
function Data.load(player: Player): { [string]: any }
	if profiles[player] then
		return profiles[player]
	end
	loading[player] = true
	local profile: { [string]: any }? = nil
	if store and not offline then
		for _ = 1, 6 do -- if another server still holds the lock (the player just hopped), give it time to save
			local lockedElsewhere = false
			local ok, result = retry(function()
				return (store :: DataStore):UpdateAsync(key(player), function(saved)
					lockedElsewhere = false -- UpdateAsync may run this more than once
					local data = saved or {}
					local lock = data.lock
					if lock and lock.server ~= game.JobId and os.time() - (lock.time or 0) < LOCK_SECONDS then
						lockedElsewhere = true
						return nil -- leave it alone
					end
					data.lock = { server = game.JobId, time = os.time() }
					return data
				end)
			end)
			if not ok then
				warn("Couldn't load", player.Name, "- playing without saving:", result)
				offline = string.find(tostring(result), "API") ~= nil
				break
			end
			if not lockedElsewhere then
				profile = result :: any
				break
			end
			task.wait(5)
		end
		if not profile and player.Parent then
			-- still locked after ~30 s: the other server is stuck. Take over rather than lock them out.
			local ok, result = retry(function()
				return (store :: DataStore):UpdateAsync(key(player), function(saved)
					local data = saved or {}
					data.lock = { server = game.JobId, time = os.time() }
					return data
				end)
			end)
			if ok then
				profile = result :: any
			end
		end
	end
	local live = Profile.reconcile(profile or {}, Profile.default())
	live.lock = nil -- the lock lives in the store, not in the game's copy
	loading[player] = nil
	if player.Parent then
		profiles[player] = live
	end
	return live
end

-- Writes the save. `release` drops this server's lock (the player is leaving).
function Data.save(player: Player, release: boolean?)
	local profile = profiles[player]
	if not profile or not store or offline then
		return
	end
	local ok, err = retry(function()
		return (store :: DataStore):UpdateAsync(key(player), function(saved)
			local lock = saved and saved.lock
			if lock and lock.server ~= game.JobId and os.time() - (lock.time or 0) < LOCK_SECONDS then
				return nil -- another server took over (we were stuck): don't overwrite its newer data
			end
			local out = table.clone(profile)
			out.lock = if release then nil else { server = game.JobId, time = os.time() }
			return out
		end)
	end)
	if not ok then
		warn("Couldn't save", player.Name, err)
	end
end

function Data.get(player: Player): { [string]: any }?
	return profiles[player]
end

-- Yields until the player's save is loaded (or they leave).
function Data.wait(player: Player): { [string]: any }?
	while not profiles[player] and player.Parent do
		task.wait(0.1)
	end
	return profiles[player]
end

-- Coins go through here so the leaderboard number, the save and the lifetime stat all agree.
function Data.addCoins(player: Player, amount: number)
	local profile = profiles[player]
	if not profile then
		return
	end
	profile.coins = math.max(0, profile.coins + amount)
	if amount > 0 then
		profile.stats.coinsEarned += amount
	end
	local stats = player:FindFirstChild("leaderstats")
	local coins = stats and stats:FindFirstChild("Coins") :: IntValue?
	if coins then
		coins.Value = profile.coins
	end
end

function Data.bump(player: Player, stat: string, by: number?)
	local profile = profiles[player]
	if profile then
		profile.stats[stat] = (profile.stats[stat] or 0) + (by or 1)
	end
end

Players.PlayerRemoving:Connect(function(player)
	while loading[player] do
		task.wait(0.1) -- don't save over a load that's still in flight
	end
	if profiles[player] then
		Data.save(player, true)
		profiles[player] = nil
	elseif store and not offline then
		-- left while loading: the save was never used here, just let go of the lock
		retry(function()
			return (store :: DataStore):UpdateAsync(key(player), function(saved)
				if saved and saved.lock and saved.lock.server == game.JobId then
					saved.lock = nil
					return saved
				end
				return nil
			end)
		end)
	end
end)

game:BindToClose(function()
	if RunService:IsStudio() and offline then
		return
	end
	local pending = 0
	for player in profiles do
		pending += 1
		task.spawn(function()
			Data.save(player, true)
			pending -= 1
		end)
	end
	local started = os.clock()
	while pending > 0 and os.clock() - started < 25 do
		task.wait(0.1)
	end
end)

task.spawn(function()
	while true do
		task.wait(AUTOSAVE_SECONDS)
		for player in profiles do
			task.spawn(Data.save, player)
		end
	end
end)

return Data
