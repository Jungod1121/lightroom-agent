local LrApplication = import 'LrApplication'
local LrApplicationView = import 'LrApplicationView'
local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

local PhotoLookup = require 'PhotoLookup'
local Log = require 'Log'

local MaskHandler = {}

local AI_SUBTYPES = {
    subject = true,
    sky = true,
    background = true,
    objects = true,
    people = true,
    landscape = true,
}

local function requireString(v, name)
    if type(v) ~= "string" or v == "" then
        error(name .. " must be a non-empty string")
    end
end

local function ensureDevelop(photo_id)
    local catalog = LrApplication.activeCatalog()
    local photo = nil
    catalog:withReadAccessDo(function()
        photo = PhotoLookup.resolveOne(catalog, photo_id)
    end)
    if not photo then
        error("Photo not found: " .. tostring(photo_id))
    end
    catalog:setSelectedPhotos(photo, {})
    if LrApplicationView.getCurrentModuleName() ~= "develop" then
        LrApplicationView.switchToModule("develop")
    end
    local waited = 0
    while waited < 12 do
        local ready = false
        if LrApplicationView.getCurrentModuleName() == "develop" then
            catalog:withReadAccessDo(function()
                ready = catalog:getTargetPhoto() == photo
            end)
        end
        if ready then
            return photo
        end
        LrTasks.sleep(0.25)
        waited = waited + 0.25
    end
    error("Develop module did not select photo " .. tostring(photo_id) .. " in time")
end

local function serializeMasks(masks)
    local out = {}
    if type(masks) ~= "table" then
        return out
    end
    for i, m in ipairs(masks) do
        local item = {}
        if type(m) == "table" then
            item.id = m.id or m.ID or m.maskId
            item.name = m.name or m.Name
            item.type = m.type or m.maskType
        else
            item.id = tostring(m)
        end
        out[i] = item
    end
    return out
end

function MaskHandler.createAiMask(args)
    requireString(args.photo_id, "photo_id")
    requireString(args.mask_type, "mask_type")
    local subtype = args.mask_type
    if not AI_SUBTYPES[subtype] then
        error("mask_type must be subject, sky, background, objects, people, or landscape")
    end
    ensureDevelop(args.photo_id)
    local op = args.operation or "new"
    if op == "add" then
        LrDevelopController.addToCurrentMask("aiSelection", subtype)
    elseif op == "subtract" then
        LrDevelopController.subtractFromCurrentMask("aiSelection", subtype)
    elseif op == "intersect" then
        LrDevelopController.intersectWithCurrentMask("aiSelection", subtype)
    else
        LrDevelopController.createNewMask("aiSelection", subtype)
    end
    LrTasks.sleep(1.2)
    Log.info(string.format("createAiMask photo=%s type=%s", args.photo_id, subtype))
    return {
        success = true,
        photo_id = args.photo_id,
        mask_type = subtype,
        selected = LrDevelopController.getSelectedMask(),
        masks = serializeMasks(LrDevelopController.getAllMasks()),
    }
end

function MaskHandler.createGradientMask(args)
    requireString(args.photo_id, "photo_id")
    local kind = args.kind or "linear"
    ensureDevelop(args.photo_id)
    if kind == "radial" then
        LrDevelopController.createNewMask("radialGradient")
    else
        LrDevelopController.createNewMask("gradient")
    end
    LrTasks.sleep(0.4)
    Log.info(string.format("createGradientMask photo=%s kind=%s", args.photo_id, kind))
    return {
        success = true,
        photo_id = args.photo_id,
        kind = kind,
        selected = LrDevelopController.getSelectedMask(),
    }
end

function MaskHandler.listMasks(args)
    requireString(args.photo_id, "photo_id")
    ensureDevelop(args.photo_id)
    return {
        success = true,
        photo_id = args.photo_id,
        masks = serializeMasks(LrDevelopController.getAllMasks()),
    }
end

function MaskHandler.selectMask(args)
    requireString(args.photo_id, "photo_id")
    if args.mask_id == nil then
        error("mask_id is required")
    end
    ensureDevelop(args.photo_id)
    LrDevelopController.selectMask(args.mask_id)
    return { success = true, photo_id = args.photo_id, mask_id = args.mask_id }
end

function MaskHandler.setMaskSettings(args)
    requireString(args.photo_id, "photo_id")
    if type(args.settings) ~= "table" then
        error("settings must be a table")
    end
    ensureDevelop(args.photo_id)
    if args.mask_id ~= nil then
        LrDevelopController.selectMask(args.mask_id)
        LrTasks.sleep(0.15)
    end
    local applied = {}
    local n = 0
    for key, value in pairs(args.settings) do
        LrDevelopController.setValue(key, value)
        applied[key] = value
        n = n + 1
    end
    Log.info(string.format("setMaskSettings photo=%s keys=%d", args.photo_id, n))
    return { success = true, photo_id = args.photo_id, applied = applied }
end

function MaskHandler.deleteMask(args)
    requireString(args.photo_id, "photo_id")
    if args.mask_id == nil then
        error("mask_id is required")
    end
    ensureDevelop(args.photo_id)
    LrDevelopController.deleteMask(args.mask_id)
    return { success = true, photo_id = args.photo_id, mask_id = args.mask_id }
end

return MaskHandler
