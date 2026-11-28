-- Run with: lune run tests/walkmath.spec.luau
local WalkMath = require("../src/shared/WalkMath")

local function near(a, b, what)
	assert(math.abs(a - b) < 1e-9, `{what}: expected {b}, got {a}`)
end

-- forwards along a 10-stud walk at 2 studs/s from s = 3
local s, d = WalkMath.pingPong(10, 3, 1, 2, 2)
near(s, 7, "still going out")
near(d, 1, "heading out")
s, d = WalkMath.pingPong(10, 3, 1, 2, 5) -- 13 travelled -> bounced off the end at 10, back to 7
near(s, 7, "bounced back")
near(d, -1, "heading back")
s, d = WalkMath.pingPong(10, 3, 1, 2, 10) -- 23 -> past 20, out again from 0 to 3
near(s, 3, "second lap")
near(d, 1, "out again")

-- backwards from s = 3: hits 0 after 1.5 s, then walks out
s, d = WalkMath.pingPong(10, 3, -1, 2, 1)
near(s, 1, "going back")
near(d, -1, "heading back")
s, d = WalkMath.pingPong(10, 3, -1, 2, 2.5)
near(s, 2, "bounced off the start")
near(d, 1, "heading out")

-- a zero-length walk stays put
s = WalkMath.pingPong(0, 0, 1, 5, 9)
near(s, 0, "zero length")

print("walkmath ok")
