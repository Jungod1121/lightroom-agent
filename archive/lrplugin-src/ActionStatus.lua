-- ActionStatus.lua — 菜单: Show Status
local LrDialogs = import "LrDialogs"
local SocketServer = require "SocketServer"

local s = SocketServer:status()
local msg = string.format(
	"running: %s\nreq port: %s\nresp port: %s",
	tostring(s.running),
	tostring(s.reqPort or "n/a"),
	tostring(s.respPort or "n/a")
)
LrDialogs.message("Lightroom Agent", msg)
