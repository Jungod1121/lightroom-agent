-- PluginShutdown.lua — 退出清理
local SocketServer = SocketServer or require "SocketServer"
local Logger = Logger or require "Logger"
local log = Logger:get()

if SocketServer:isRunning() then
	SocketServer:stop()
	log:info("LightroomAgent stopped on plugin shutdown")
end
