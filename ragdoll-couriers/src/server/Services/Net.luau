-- The one RemoteEvent the game talks over. Messages are (kind, data); see Main and the client scripts.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local remote = Instance.new("RemoteEvent")
remote.Name = "Couriers"
remote.Parent = ReplicatedStorage

return remote
