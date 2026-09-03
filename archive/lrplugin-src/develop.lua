-- Handlers/develop.lua — develop 参数读取（M1 只读；M2 扩展写/快照）
local Develop = {}

local function countKeys(t)
	local n = 0
	for _ in pairs(t) do
		n = n + 1
	end
	return n
end

local handlers = {
	{
		name = "getSettings",
		needsPhoto = true,
		fn = function(ctx)
			local ok, settings = pcall(function()
				return ctx.photo:getDevelopSettings()
			end)
			if not ok then
				return { __error = { code = "SDK_ERROR", message = tostring(settings) } }
			end
			return { settings = settings, keyCount = countKeys(settings) }
		end,
	},
}

Develop.handlers = handlers
return Develop
