-- Config.lua — 插件常量
local LrFileUtils = import "LrFileUtils"

local Config = {}

-- 端口基址：req = base, resp = base + 1
-- 若与其它进程冲突（如旧版本残留），改这里整体 +2 后重启 Lightroom 即可
Config.BASE_PORT = 54130
-- LrSocket 的 bind 地址须为 "localhost"（社区实现均用该值；"127.0.0.1" 会导致 bind 不进入监听态）
Config.HOST = "localhost"

-- 端口文件固定在 /tmp：Lightroom 沙箱裁掉了 os 库（os.getenv 等为 nil），
-- 而 io.open 可用（社区插件实证）；/tmp 两端均可读写。
-- Lightroom 的 os 库被裁剪，不要在本插件的任何模块里调用 os.*（os.time/os.getenv 均为 nil）。
function Config:portsFile()
	return "/tmp/lightroom_agent_ports.json"
end

-- 生成 128-bit 随机 hex（仅 math.random，避免使用被裁剪的 os 库）
function Config:generateToken()
	local out = {}
	for i = 1, 32 do
		out[i] = string.format("%x", math.random(0, 15))
	end
	return table.concat(out)
end

return Config
