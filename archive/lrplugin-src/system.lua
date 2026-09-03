-- system.lua
local LrApplication = import "LrApplication"
local SocketServer = require "SocketServer"

local System = {}

local handlers = {
	{
		name = "ping",
		fn = function()
			-- os.time 在 Lightroom 沙箱可能被裁剪，安全取值
			local ok, t = pcall(os.time)
			return { pong = true, time = ok and t or 0 }
		end,
	},
	{
		name = "status",
		fn = function()
			local catalog = LrApplication.activeCatalog()
			local s = SocketServer:status()
			return {
				running = s.running,
				reqPort = s.reqPort,
				respPort = s.respPort,
				catalogPath = catalog:getCatalogPath(),
				appVersion = LrApplication.versionString() or "unknown",
			}
		end,
	},
	{
		name = "stop",
		fn = function()
			return SocketServer:stop()
		end,
	},
}

System.handlers = handlers
return System
