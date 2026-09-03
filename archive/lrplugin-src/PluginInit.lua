-- PluginInit.lua — 插件入口：注册路由表、暴露菜单动作
local Logger = Logger or require "Logger"
local Config = Config or require "Config"
local Router = Router or require "Router"
local SocketServer = SocketServer or require "SocketServer"

local log = Logger:get()

-- 注册所有 handler 模块（LrC 的 require 只支持插件根目录平铺模块）
local function registerAll()
	local system = require "system"
	local catalog = require "catalog"
	local develop = require "develop"
	local render = require "render"

	Router:register("system", system.handlers)
	Router:register("catalog", catalog.handlers)
	Router:register("develop", develop.handlers)
	Router:register("render", render.handlers)

	log:info("LightroomAgent: handlers registered")
end

-- 菜单动作（Actions.lua 通过 require 拿到本模块再调用）
local PluginInit = {}

function PluginInit.startServer()
	if SocketServer:isRunning() then
		log:info("start requested but already running")
		return "already running"
	end
	registerAll()
	SocketServer:start()
	return "started"
end

function PluginInit.stopServer()
	return SocketServer:stop()
end

-- LrInitPlugin 回调：初始化即注册（提前注册，避免首次 Start 时重复）
registerAll()

return PluginInit
