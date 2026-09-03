-- Handlers/render.lua — 渲染当前编辑态预览（M1：直方图闭环的"眼睛"）
-- 策略：把 photo 当前完整 develop settings（含未保存修改）交给 getRenderedPreview 渲染，
-- 保证直方图是"所见即所得"；返回本地文件路径，由 Python 侧读取分析，不走 socket 传大字节。
local LrTasks = import "LrTasks"

local Render = {}

local VALID_FORMATS = { JPEG = true, TIFF = true }

local function render(photo, params)
	local format = string.upper(params.format or "JPEG")
	if not VALID_FORMATS[format] then
		return { __error = { code = "BAD_PARAMETER", message = "format must be JPEG or TIFF" } }
	end
	local maxW = tonumber(params.maxWidth) or 1080
	local maxH = tonumber(params.maxHeight) or 1080
	local quality = tonumber(params.quality) or 90

	-- 捕获当前 develop 设置（getDevelopSettings 会包含 Develop 模块未保存的修改）
	local devOk, devSettings = pcall(function()
		return photo:getDevelopSettings()
	end)
	if not devOk then
		devSettings = nil
	end

	local spec = {
		maxWidth = maxW,
		maxHeight = maxH,
		format = format,
		quality = quality,
		async = false,
	}

	local ok, filePath, numReasons = pcall(function()
		return photo:getRenderedPreview(spec, "LIGHTROOM_AGENT_PREVIEW", devSettings)
	end)

	if not ok or not filePath then
		return {
			__error = {
				code = "SDK_ERROR",
				message = "getRenderedPreview failed: " .. tostring(filePath or "unknown"),
				reasons = numReasons,
			},
		}
	end

	return {
		path = filePath,
		format = format,
		width = maxW,
		height = maxH,
		usedDevelopSettings = devOk,
	}
end

local handlers = {
	{
		name = "preview",
		needsPhoto = true,
		fn = function(ctx, params)
			local r = render(ctx.photo, params)
			return r
		end,
	},
	-- 渲染后立即删除临时文件（Python 侧确认读完调用）
	{
		name = "cleanup",
		needsPhoto = false,
		fn = function(_, params)
			local LrFileUtils = import "LrFileUtils"
			local p = params.path
			if p and LrFileUtils.exists(p) then
				LrFileUtils.delete(p)
				return { deleted = true }
			end
			return { deleted = false }
		end,
	},
}

Render.handlers = handlers
return Render
