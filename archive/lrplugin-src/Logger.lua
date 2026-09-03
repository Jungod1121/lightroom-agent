-- Logger.lua — 极简日志封装（LrLogger）
local LrLogger = import "LrLogger"

local Logger = {}

local LOG_NAME = "LightroomAgent"

function Logger:get()
	local logger = LrLogger(LOG_NAME)
	logger:enable("logfile")
	return logger
end

return Logger
