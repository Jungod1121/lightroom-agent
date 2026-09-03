-- Json.lua — 自研精简 JSON 编解码（Lightroom 无内置 json 全局）
-- 覆盖协议所需：对象/数组/字符串/数字/布尔/null，嵌套递归。
-- 说明：Lightroom 的 Lua 环境不提供全局 json 对象（其它插件均自带实现），
-- 本项目按自己的实现编写，不复制任何第三方 json.lua。

local Json = {}

local ESCAPE_MAP = {
	['"'] = '\\"',
	["\\"] = "\\\\",
	["\b"] = "\\b",
	["\f"] = "\\f",
	["\n"] = "\\n",
	["\r"] = "\\r",
	["\t"] = "\\t",
}

local function escapeString(s)
	local out = {}
	local start = 1
	for i = 1, #s do
		local c = s:sub(i, i)
		local esc = ESCAPE_MAP[c]
		if esc then
			if i > start then
				table.insert(out, s:sub(start, i - 1))
			end
			table.insert(out, esc)
			start = i + 1
		elseif c:byte() < 32 then
			if i > start then
				table.insert(out, s:sub(start, i - 1))
			end
			table.insert(out, string.format("\\u%04x", c:byte()))
			start = i + 1
		end
	end
	if start <= #s then
		table.insert(out, s:sub(start))
	end
	return '"' .. table.concat(out) .. '"'
end

local function isArray(t)
	-- 键全为从 1 开始的连续整数 -> 数组
	local n = 0
	for k in pairs(t) do
		if type(k) ~= "number" then
			return false
		end
		if k < 1 or math.floor(k) ~= k then
			return false
		end
		n = n + 1
	end
	return n == #t and n > 0
end

function Json.encode(val)
	local function enc(v)
		local t = type(v)
		if t == "nil" then
			return "null"
		elseif t == "boolean" then
			return v and "true" or "false"
		elseif t == "number" then
			if v ~= v then -- NaN
				return "null"
			end
			return string.format("%.10g", v)
		elseif t == "string" then
			return escapeString(v)
		elseif t == "table" then
			if isArray(v) then
				local parts = {}
				for i = 1, #v do
					parts[i] = enc(v[i])
				end
				return "[" .. table.concat(parts, ",") .. "]"
			else
				local parts = {}
				local n = 0
				for k, val in pairs(v) do
					if type(k) == "string" and val ~= nil then
						n = n + 1
						parts[n] = escapeString(k) .. ":" .. enc(val)
					end
				end
				return "{" .. table.concat(parts, ",") .. "}"
			end
		end
		return "null"
	end
	return enc(val)
end

-- 码点 -> UTF-8 字符串（含补充平面，配合代理对合并）
local function utf8Char(cp)
	if cp < 0x80 then
		return string.char(cp)
	elseif cp < 0x800 then
		return string.char(0xC0 + math.floor(cp / 0x40), 0x80 + (cp % 0x40))
	elseif cp < 0x10000 then
		return string.char(
			0xE0 + math.floor(cp / 0x1000),
			0x80 + (math.floor(cp / 0x40) % 0x40),
			0x80 + (cp % 0x40))
	else
		return string.char(
			0xF0 + math.floor(cp / 0x40000),
			0x80 + (math.floor(cp / 0x1000) % 0x40),
			0x80 + (math.floor(cp / 0x40) % 0x40),
			0x80 + (cp % 0x40))
	end
end

-- ---- decode（递归下降）----

function Json.decode(s)
	local pos = 1
	local len = #s

	local function skipWs()
		while pos <= len do
			local c = s:sub(pos, pos)
			if c == " " or c == "\t" or c == "\n" or c == "\r" then
				pos = pos + 1
			else
				break
			end
		end
	end

	local function parseString()
		pos = pos + 1 -- 跳过开引号
		local out = {}
		while pos <= len do
			local c = s:sub(pos, pos)
			if c == '"' then
				pos = pos + 1
				return table.concat(out)
			elseif c == "\\" then
				pos = pos + 1
				local e = s:sub(pos, pos)
				if e == "n" then
					table.insert(out, "\n")
				elseif e == "t" then
					table.insert(out, "\t")
				elseif e == "r" then
					table.insert(out, "\r")
				elseif e == "b" then
					table.insert(out, "\b")
				elseif e == "f" then
					table.insert(out, "\f")
				elseif e == "u" then
					-- 处理 \uXXXX；遇到代理对（\uD800-\uDBFF 开头）时合并下一组
					local hex = s:sub(pos + 1, pos + 4)
					local cp = tonumber(hex, 16) or 63
					pos = pos + 4
					if cp >= 0xD800 and cp <= 0xDBFF and pos + 6 <= len then
						local hex2 = s:sub(pos + 3, pos + 6)
						local cp2 = tonumber(hex2, 16)
						if cp2 and cp2 >= 0xDC00 and cp2 <= 0xDFFF then
							cp = 0x10000 + (cp - 0xD800) * 0x400 + (cp2 - 0xDC00)
							pos = pos + 6
						end
					end
					table.insert(out, utf8Char(cp))
				else
					table.insert(out, e)
				end
				pos = pos + 1
			else
				table.insert(out, c)
				pos = pos + 1
			end
		end
		error("unterminated string")
	end

	local function parseNumber()
		local start = pos
		if s:sub(pos, pos) == "-" then
			pos = pos + 1
		end
		while pos <= len do
			local c = s:sub(pos, pos)
			if c:match("[0-9eE+.%-]") then
				pos = pos + 1
			else
				break
			end
		end
		local num = tonumber(s:sub(start, pos - 1))
		if not num then
			error("invalid number")
		end
		return num
	end

	local function parseValue()
		skipWs()
		if pos > len then
			error("unexpected end")
		end
		local c = s:sub(pos, pos)
		if c == "{" then
			pos = pos + 1
			local obj = {}
			skipWs()
			if s:sub(pos, pos) == "}" then
				pos = pos + 1
				return obj
			end
			while true do
				skipWs()
				local key = parseString()
				skipWs()
				if s:sub(pos, pos) ~= ":" then
					error("expected ':'")
				end
				pos = pos + 1
				obj[key] = parseValue()
				skipWs()
				local sep = s:sub(pos, pos)
				if sep == "," then
					pos = pos + 1
				elseif sep == "}" then
					pos = pos + 1
					return obj
				else
					error("expected ',' or '}'")
				end
			end
		elseif c == "[" then
			pos = pos + 1
			local arr = {}
			local n = 0
			skipWs()
			if s:sub(pos, pos) == "]" then
				pos = pos + 1
				return arr
			end
			while true do
				n = n + 1
				arr[n] = parseValue()
				skipWs()
				local sep = s:sub(pos, pos)
				if sep == "," then
					pos = pos + 1
				elseif sep == "]" then
					pos = pos + 1
					return arr
				else
					error("expected ',' or ']'")
				end
			end
		elseif c == '"' then
			return parseString()
		elseif c == "t" then
			pos = pos + 4
			return true
		elseif c == "f" then
			pos = pos + 5
			return false
		elseif c == "n" then
			pos = pos + 4
			return nil
		elseif c == "-" or c:match("%d") then
			return parseNumber()
		end
		error("unexpected char at " .. pos)
	end

	return parseValue()
end

return Json
