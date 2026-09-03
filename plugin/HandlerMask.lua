local LrDevelopController = import 'LrDevelopController'
local LrTasks = import 'LrTasks'

local DevelopReady = require 'DevelopReady'
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

local function serializeMasks(masks)
    local out = {}
    if type(masks) ~= "table" then
        return out
    end
    for i, m in ipairs(masks) do
        out[i] = {
            id = m.id or m.ID or m.maskId,
            name = m.name or m.Name,
            type = m.type or m.maskType,
        }
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
    DevelopReady.ensure(args.photo_id)
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
    -- Sensei mask generation is slow
    LrTasks.sleep(1.2)
    local selected = LrDevelopController.getSelectedMask()
    local all = LrDevelopController.getAllMasks()
    Log.info(string.format("createAiMask photo=%s type=%s", args.photo_id, subtype))
    return {
        success = true,
        photo_id = args.photo_id,
        mask_type = subtype,
        selected = selected,
        masks = serializeMasks(all),
    }
end

function MaskHandler.createGradientMask(args)
    requireString(args.photo_id, "photo_id")
    local kind = args.kind or "linear"
    DevelopReady.ensure(args.photo_id)
    if kind == "radial" then
        LrDevelopController.createNewMask("radialGradient")
    else
        LrDevelopController.createNewMask("gradient")
    end
    LrTasks.sleep(0.4)
    local selected = LrDevelopController.getSelectedMask()
    Log.info(string.format("createGradientMask photo=%s kind=%s", args.photo_id, kind))
    return {
        success = true,
        photo_id = args.photo_id,
        kind = kind,
        selected = selected,
        note = "Gradient uses Lightroom's default geometry (typically top-down for linear). Brush painting is not supported.",
    }
end

function MaskHandler.listMasks(args)
    requireString(args.photo_id, "photo_id")
    DevelopReady.ensure(args.photo_id)
    local all = LrDevelopController.getAllMasks()
    return { success = true, photo_id = args.photo_id, masks = serializeMasks(all) }
end

function MaskHandler.selectMask(args)
    requireString(args.photo_id, "photo_id")
    if args.mask_id == nil then
        error("mask_id is required")
    end
    DevelopReady.ensure(args.photo_id)
    LrDevelopController.selectMask(args.mask_id)
    return { success = true, photo_id = args.photo_id, mask_id = args.mask_id }
end

function MaskHandler.setMaskSettings(args)
    requireString(args.photo_id, "photo_id")
    if type(args.settings) ~= "table" then
        error("settings must be a table")
    end
    DevelopReady.ensure(args.photo_id)
    if args.mask_id ~= nil then
        LrDevelopController.selectMask(args.mask_id)
        LrTasks.sleep(0.15)
    end
    local applied = {}
    for key, value in pairs(args.settings) do
        LrDevelopController.setValue(key, value)
        applied[key] = value
    end
    Log.info(string.format("setMaskSettings photo=%s keys=%d", args.photo_id, (function()
        local n = 0
        for _ in pairs(applied) do n = n + 1 end
        return n
    end)()))
    return { success = true, photo_id = args.photo_id, applied = applied }
end

function MaskHandler.deleteMask(args)
    requireString(args.photo_id, "photo_id")
    if args.mask_id == nil then
        error("mask_id is required")
    end
    DevelopReady.ensure(args.photo_id)
    LrDevelopController.deleteMask(args.mask_id)
    return { success = true, photo_id = args.photo_id, mask_id = args.mask_id }
end

return MaskHandler
