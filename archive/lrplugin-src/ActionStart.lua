-- ActionStart.lua — 菜单: Start Server
local LrDialogs = import "LrDialogs"
local PluginInit = require "PluginInit"

local ok, result = pcall(PluginInit.startServer)
if not ok then
	LrDialogs.message("Lightroom Agent", "Start failed: " .. tostring(result))
else
	LrDialogs.message("Lightroom Agent", "Server " .. tostring(result))
end
