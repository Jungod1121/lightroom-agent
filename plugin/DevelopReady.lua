local LrApplication = import 'LrApplication'
local LrApplicationView = import 'LrApplicationView'
local LrTasks = import 'LrTasks'

local PhotoLookup = require 'PhotoLookup'

local DevelopReady = {}

function DevelopReady.ensure(photo_id)
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

return DevelopReady
