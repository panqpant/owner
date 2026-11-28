-- Ragdoll Couriers: every tuning number in one place. Change these, press Play, feel the difference.

local Config = {}

-- Driving feel. The client simulates the scooter, so these are read on the client.
-- Three presets so a phone tester can compare feels without opening Studio.
Config.Presets = {
	{
		name = "Twitchy",
		maxSpeed = 60, -- studs/s
		accel = 45, -- studs/s^2
		brake = 80,
		reverseSpeed = 15,
		turnRate = 3.0, -- rad/s at speed
		grip = 7, -- how fast sideways sliding is killed (per second)
		upright = 5, -- how hard it self-rights; low = tips over easily
		uprightLimit = 55, -- degrees; past this tilt it stops helping and you fall
		stiffness = 1.0,
		damping = 0.45,
	},
	{
		name = "Balanced",
		maxSpeed = 55,
		accel = 38,
		brake = 70,
		reverseSpeed = 15,
		turnRate = 2.5,
		grip = 9,
		upright = 9,
		uprightLimit = 65,
		stiffness = 1.0,
		damping = 0.6,
	},
	{
		name = "Heavy",
		maxSpeed = 48,
		accel = 28,
		brake = 60,
		reverseSpeed = 12,
		turnRate = 1.9,
		grip = 12,
		upright = 16,
		uprightLimit = 75,
		stiffness = 1.3,
		damping = 0.8,
	},
}
Config.DefaultPreset = 2

Config.RideHeight = 2.2 -- studs from the ray points to the ground at rest

-- Crashing. Read on the server, which watches the scooter's velocity.
Config.CrashDeltaV = 34 -- sudden speed change (studs/s) in one step that throws you off
Config.TiltCrashDegrees = 70 -- lying past this...
Config.TiltCrashSeconds = 0.5 -- ...for this long also counts as a crash
Config.RagdollSeconds = 1.8 -- plan: recover in under 2 seconds
Config.LaunchUp = 25 -- extra upward fling on a crash

-- Parcel damage: damage% = max(0, impact - tolerance) * fragility * DamageScale
Config.DamageScale = 0.6
Config.ParcelLostY = -30
Config.ParcelRetrieveSeconds = 20 -- dropped parcel comes back by itself after this...
Config.ParcelRetrievePenalty = 15 -- ...losing this many condition points
Config.ReloadDistance = 10 -- ride near a dropped parcel to scoop it back up

-- The kill test cycles through these, easiest first.
Config.Parcels = {
	pillow = {
		name = "Pillow",
		pay = 60,
		fragility = 0.3,
		tolerance = 30,
		size = Vector3.new(2.2, 1.2, 1.6),
		color = Color3.fromRGB(240, 240, 255),
		material = Enum.Material.Fabric,
	},
	tv = {
		name = "TV",
		pay = 300,
		fragility = 1.2,
		tolerance = 22,
		size = Vector3.new(2.4, 1.8, 0.8),
		color = Color3.fromRGB(30, 30, 35),
		material = Enum.Material.SmoothPlastic,
	},
	vase = {
		name = "Vase",
		pay = 240,
		fragility = 1.6,
		tolerance = 20,
		size = Vector3.new(1.2, 2.2, 1.2),
		color = Color3.fromRGB(80, 140, 220),
		material = Enum.Material.Glass,
	},
	fishtank = {
		name = "Fish Tank",
		pay = 700,
		fragility = 1.7,
		tolerance = 18,
		size = Vector3.new(2.4, 1.6, 1.4),
		color = Color3.fromRGB(120, 200, 255),
		material = Enum.Material.Glass,
	},
}
Config.JobOrder = { "pillow", "tv", "vase", "fishtank" } -- first job is always the pillow

-- Payout bonuses
Config.SpeedBonus = 0.2 -- +20% if delivered within par time
Config.CleanBonus = 0.25 -- +25% if you never crashed on the run
Config.ParSpeed = 35 -- par time = distance / this (studs/s)

-- Pedestrians (city only)
Config.PedHitSpeed = 10 -- studs/s: slower than this and you just nudge past
Config.PedHitDamage = 10 -- condition lost when you clip someone (and the no-crash bonus goes)
Config.NearMissSpeed = 25 -- studs/s: brush past someone at least this fast...
Config.NearMissRange = 8 -- ...within this many studs, without touching...
Config.NearMissCoins = 4 -- ...for this many coins
Config.NearMissMaxPerJob = 6
Config.HandoffEvery = 4 -- every 4th city job is a customer on foot
Config.HandoffBonus = 0.3 -- +30% for handing it over in person
Config.HandoffRange = 9 -- studs from the customer to hand it over
Config.HandoffMaxSpeed = 40 -- studs/s: you can hand it over on the move, not at full tilt
Config.CustomerSpeed = 4.5
Config.ThiefChance = 0.35 -- chance a thief grabs a parcel you drop in a crash
Config.ThiefSpeed = 13 -- studs/s: faster than walking, slower than a scooter
Config.ThiefSeconds = 30 -- catch them before they get this far
Config.ThiefCatchRange = 7
Config.ThiefCatchCoins = 15
Config.JobMinDistance = 250 -- city jobs go somewhere between these (studs, straight line)
Config.JobMaxDistance = 900

-- Sounds. Built-in Studio sounds so nothing needs uploading; swap for better ones later.
Config.Sounds = {
	crash = "rbxasset://sounds/uuhhh.mp3",
	deliver = "rbxasset://sounds/electronicpingshort.wav",
	hit = "rbxasset://sounds/action_jump_land.mp3",
}

return Config
