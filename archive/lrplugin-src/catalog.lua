-- Handlers/catalog.lua — 目录只读操作（M1）
local LrApplication = import "LrApplication"

local Catalog = {}

-- 选中的照片集合（Library 网格/胶片）
local function getSelectedSet()
	local catalog = LrApplication.activeCatalog()
	return catalog:getSelectedPhotos()
end

-- 照片对象 -> 轻量元数据表
local function summarize(photo)
	local ok, path = pcall(function()
		return photo:getRawMetadata("path")
	end)
	local okName, name = pcall(function()
		return photo:getRawMetadata("fileName")
	end)
	local okDate, date = pcall(function()
		return photo:getRawMetadata("dateTimeOriginal")
	end)
	local okStar, star = pcall(function()
		return photo:getRawMetadata("rating")
	end)
	local okId, id = pcall(function()
		return photo:getLocalizedFilePath()
	end)
	local photoId = nil
	if okId then
		-- LrPhoto 无公开稳定 id，SDK 用路径唯一标识
		photoId = path
	end
	local t = {}
	if ok and path then t.path = path end
	if okName and name then t.fileName = name end
	if okDate and date then t.dateTimeOriginal = date end
	if okStar and star then t.rating = star end
	t.key = photoId or (ok and path or nil)
	return t
end

local handlers = {
	{
		name = "getSelected",
		fn = function()
			local photos = getSelectedSet()
			local out = {}
			for _, p in ipairs(photos) do
				table.insert(out, summarize(p))
			end
			return { photos = out, count = #out }
		end,
	},
	{
		name = "getTarget",
		needsPhoto = true,
		fn = function(ctx)
			return summarize(ctx.photo)
		end,
	},
}

Catalog.handlers = handlers
return Catalog
