-- ActionStop.lua — 菜单: Stop Server
local LrDialogs = import "LrDialogs"
local PluginInit = require "PluginInit"

local ok, result = pcall(PluginInit.stopServer)
if not ok then
	LrDialogs.message("Lightroom Agent", "Stop failed: " .. tostring(result))
else
	LrDialogs.message("Lightroom Agent", "Server stopped")
end
