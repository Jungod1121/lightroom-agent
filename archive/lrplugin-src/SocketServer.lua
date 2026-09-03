-- SocketServer.lua — LrSocket 服务（生命周期结构对齐社区实证实现）
-- 双通道：req(mode=receive, 收请求) + resp(mode=send, 发响应)
-- LrSocket 关键行为（实测）：bind 后空闲约 10s 会报 timeout；onError/onClosed 后
-- 必须显式 reconnect()（或 close+rebind）才回到监听态；消息走 onMessage 回调。
-- 因此采用"主循环 + 状态旗标"模式管理两个 socket 的恢复，而非一次性 bind。

local LrSocket = import "LrSocket"
local LrTasks = import "LrTasks"
local LrFunctionContext = import "LrFunctionContext"
local LrFileUtils = import "LrFileUtils"

local Logger = require "Logger"
local Config = require "Config"
local Router = require "Router"
local Json = require "Json"

local log = Logger:get()

local SocketServer = {}

local state = {
	running = false,
	context = nil,
	token = nil,
	reqSock = nil,
	respSock = nil,
	respSend = nil, -- resp 通道当前 client 连接（send 用）
	reqPort = Config.BASE_PORT,
	respPort = Config.BASE_PORT + 1,
	reqBuffer = "",
	-- 恢复旗标
	reqNeedsReconnect = false,
	respNeedsReconnect = false,
	respNeedsRebind = false,
	-- gen：rebind 代际守卫，防止陈旧回调触发再次 rebind
	gen = 0,
}

-- ---- 发送 ----
local function sendFrame(text)
	if not state.respSend then
		log:warn("sendFrame skipped: response client not connected")
		return false
	end
	local ok, err = pcall(function()
		state.respSend:send(text .. "\n")
	end)
	if not ok then
		log:error("send failed: " .. tostring(err))
	end
	return ok
end

-- ---- 端口文件 ----
local function writePortsFile()
	local payload = Json.encode({
		request = state.reqPort,
		response = state.respPort,
		token = state.token,
	})
	local ok, err = pcall(function()
		local file = io.open(Config:portsFile(), "w")
		if file then
			file:write(payload)
			file:close()
		end
	end)
	if ok then
		log:info("ports file written: " .. Config:portsFile())
	else
		log:error("ports file failed: " .. tostring(err))
	end
end

-- ---- 帧分发 ----
local function dispatchFrame(line)
	local ok, msg = pcall(Json.decode, line)
	if not ok or type(msg) ~= "table" then
		log:error("bad frame: " .. tostring(line):sub(1, 100))
		return
	end
	if state.token and msg.token and msg.token ~= state.token then
		log:warn("token mismatch")
		sendFrame(Json.encode({ v = 1, id = msg.id, success = false,
			error = { code = "AUTH_FAILED", message = "token mismatch" } }))
		return
	end
	local id = msg.id
	local err, result = Router:dispatch(msg.command, msg.params or {}, function()
		local LrApplication = import "LrApplication"
		return LrApplication.activeCatalog():getTargetPhoto()
	end)
	local resp
	if err then
		resp = Json.encode({ v = 1, id = id, success = false, error = err })
	else
		resp = Json.encode({ v = 1, id = id, success = true, result = result or {} })
	end
	local sent = sendFrame(resp)
	log:info("RESP built len=" .. #resp .. " sent=" .. tostring(sent) ..
		" respSendNil=" .. tostring(state.respSend == nil))
end

local function onReqMessage(_, message)
	log:info("REQ-MESSAGE received: " .. tostring(message):sub(1, 80))
	state.reqBuffer = state.reqBuffer .. tostring(message or "")
	while true do
		local nl = string.find(state.reqBuffer, "\n", 1, true)
		if not nl then break end
		local line = string.sub(state.reqBuffer, 1, nl - 1)
		state.reqBuffer = string.sub(state.reqBuffer, nl + 1)
		if line ~= "" then
			-- 诊断发现：LrSocket onMessage 回调环境里 startAsyncTask 的任务不会被调度，
			-- 因此这里同步分发（M1 的 system/catalog/develop 均为同步 SDK API；
			-- 需要异步上下文的命令如 render 后续在其 handler 内自行创建 task 上下文）。
			local ok, err = pcall(dispatchFrame, line)
			log:info("DISPATCH-RESULT ok=" .. tostring(ok) .. (ok and "" or (" err=" .. tostring(err))))
		end
	end
end

-- ---- bind ----
local function bindReq(context)
	return LrSocket.bind {
		functionContext = context,
		plugin = _PLUGIN,
		port = state.reqPort,
		mode = "receive",
		onConnected = function()
			log:info("req channel connected")
			-- 新 request client = 新会话。LrSocket send-mode listener 无法可靠感知
			-- 旧 client 断开（会"假死"占住连接拒绝新 client），因此强制 rebind
			-- response listener，让当前 client 的 resp 连接能真正被接受。
			state.respNeedsRebind = true
		end,
		onMessage = onReqMessage,
		onClosed = function()
			log:info("req channel closed, mark reconnect")
			state.reqNeedsReconnect = true
		end,
		onError = function(_, err)
			local s = tostring(err)
			if not state.respSend and not state.running then return end
			log:info("req channel error: " .. s .. " -> reconnect")
			state.reqNeedsReconnect = true
		end,
	}
end

local function bindResp(context, myGen)
	local function live()
		return state.gen == myGen
	end
	return LrSocket.bind {
		functionContext = context,
		plugin = _PLUGIN,
		port = state.respPort,
		mode = "send",
		onConnected = function(sock)
			if not live() then return end
			state.respSend = sock -- onConnected 传入的连接对象用于 send
			log:info("resp channel connected")
		end,
		onMessage = function() end, -- send-mode 不应有上行消息
		onClosed = function()
			if not live() then return end
			log:info("resp channel closed -> rebind")
			state.respSend = nil
			state.respNeedsRebind = true
		end,
		onError = function(_, err)
			if not live() then return end
			local s = tostring(err)
			if s:find("timeout") or s:find("client") then
				log:info("resp channel no-client (" .. s .. ") -> reconnect")
				state.respNeedsReconnect = true
			else
				log:info("resp channel error: " .. s .. " -> rebind")
				state.respSend = nil
				state.respNeedsRebind = true
			end
		end,
	}
end

-- ---- 公共接口 ----
function SocketServer:isRunning()
	return state.running
end

function SocketServer:start()
	if state.running then
		return { code = "BUSY", message = "server already running" }
	end

	state.token = Config:generateToken()

	LrFunctionContext.postAsyncTaskWithContext("lightroom_agent_sockets", function(context)
		state.context = context

		context:addCleanupHandler(function()
			log:info("context cleanup: closing sockets")
			for _, sock in ipairs({ state.reqSock, state.respSock }) do
				if sock then
					pcall(function() sock:close() end)
				end
			end
			state.reqSock = nil
			state.respSock = nil
			state.respSend = nil
			state.reqNeedsReconnect = false
			state.respNeedsReconnect = false
			state.respNeedsRebind = false
		end)

		local okReq, errReq = pcall(function()
			state.reqSock = bindReq(context)
		end)
		local okResp, errResp = pcall(function()
			state.gen = state.gen + 1
			state.respSock = bindResp(context, state.gen)
		end)

		if not (okReq and okResp) then
			log:error("bind failed; req=" .. tostring(errReq) .. " resp=" .. tostring(errResp))
			return
		end

		state.running = true
		writePortsFile()
		log:info("LightroomAgent server started on req=" .. state.reqPort .. " resp=" .. state.respPort)

		-- 主循环：管理 socket 恢复 + 保持 context 存活
		while state.running do
			if state.reqNeedsReconnect and state.reqSock then
				state.reqNeedsReconnect = false
				log:info("reconnecting req socket")
				pcall(function() state.reqSock:reconnect() end)
			end
			if state.respNeedsRebind then
				state.respNeedsRebind = false
				state.gen = state.gen + 1
				local newGen = state.gen
				if state.respSock then
					pcall(function() state.respSock:close() end)
				end
				state.respSend = nil
				LrTasks.sleep(0.1)
				local okB, errB = pcall(function()
					state.respSock = bindResp(context, newGen)
				end)
				if not okB then
					log:error("resp rebind failed: " .. tostring(errB))
					state.respNeedsRebind = true
				else
					log:info("resp rebound gen=" .. newGen)
				end
			elseif state.respNeedsReconnect and state.respSock then
				state.respNeedsReconnect = false
				log:info("reconnecting resp socket")
				pcall(function() state.respSock:reconnect() end)
			end
			LrTasks.sleep(0.2)
		end

		log:info("server main loop exited")
	end)

	return { ok = true }
end

function SocketServer:stop()
	if not state.running then
		return { ok = false, reason = "not running" }
	end
	state.running = false
	local f = Config:portsFile()
	if LrFileUtils.exists(f) then
		LrFileUtils.delete(f)
	end
	log:info("server stop requested")
	return { ok = true }
end

function SocketServer:status()
	return {
		running = state.running,
		reqPort = state.reqPort,
		respPort = state.respPort,
	}
end

return SocketServer
