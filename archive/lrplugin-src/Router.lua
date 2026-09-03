-- Router.lua — 命令路由：command -> handler 函数
-- handler 模块导出注册项列表：
--   { { name="ping", fn=function(ctx, params) -> result end, needsPhoto=false }, ... }
-- ctx.photo 在 needsPhoto=true 时为当前目标照片对象
local Logger = Logger or require "Logger"
local log = Logger:get()

local Router = {}

Router.table = {}

function Router:register(prefix, entries)
	for _, e in ipairs(entries or {}) do
		local key = prefix .. "." .. e.name
		self.table[key] = {
			fn = e.fn,
			needsPhoto = e.needsPhoto or false,
		}
		log:debug("registered: " .. key)
	end
end

-- 返回 err | nil, result
function Router:dispatch(command, params, photoGetter)
	local def = self.table[command]
	if not def then
		return { code = "UNKNOWN_COMMAND", message = "unknown command: " .. tostring(command) }
	end

	local ctx = {}
	if def.needsPhoto then
		local ok, photo = pcall(photoGetter)
		if not ok or not photo then
			return { code = "NO_PHOTO_SELECTED", message = "no photo selected in Lightroom" }
		end
		ctx.photo = photo
	end

	local ok, result = pcall(def.fn, ctx, params or {})
	if not ok then
		log:error("handler error for " .. command .. ": " .. tostring(result))
		return { code = "SDK_ERROR", message = tostring(result) }
	end
	if type(result) == "table" and result.__error then
		return result.__error
	end
	return nil, result
end

return Router
