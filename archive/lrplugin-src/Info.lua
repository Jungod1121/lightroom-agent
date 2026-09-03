-- Info.lua
return {
	LrSdkVersion = 5.0,
	LrSdkMinimumVersion = 5.0,

	LrToolkitIdentifier = "dev.lightroomagent.bridge",
	LrPluginName = "Lightroom Agent",

	LrInitPlugin = "PluginInit.lua",
	LrShutdownPlugin = "PluginShutdown.lua",

	LrExportMenuItems = {
		{
			title = "Lightroom Agent: Start Server",
			file = "ActionStart.lua",
		},
		{
			title = "Lightroom Agent: Stop Server",
			file = "ActionStop.lua",
		},
		{
			title = "Lightroom Agent: Show Status",
			file = "ActionStatus.lua",
		},
	},
}
