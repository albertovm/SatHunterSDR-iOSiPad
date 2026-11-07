-- Generic 9600 bd telemetry: every frame the G3RUH chain decodes arrives in on_frame(frame).
-- AX.25 frames have src / dst / path / info; other HDLC frames only frame.bytes (the whole frame).

local function hex(s, n)
  local out = {}
  local m = math.min(#s, n)
  for i = 1, m do
    out[#out + 1] = string.format("%02x", string.byte(s, i))
  end
  local t = table.concat(out, " ")
  if #s > n then
    t = t .. " ..."
  end
  return t
end

-- text when at least 90 % of the bytes are printable ASCII (or tab / CR / LF)
local function readable(s)
  if #s == 0 then
    return false
  end
  local ok = 0
  for i = 1, #s do
    local b = string.byte(s, i)
    if (b >= 32 and b < 127) or b == 9 or b == 10 or b == 13 then
      ok = ok + 1
    end
  end
  return ok >= 0.9 * #s
end

function on_frame(frame)
  if frame.src ~= "" then
    local body
    if readable(frame.bytes) then
      body = string.gsub(frame.info, "[%c]", " ")
    else
      body = "[" .. #frame.bytes .. " bytes] " .. hex(frame.bytes, 24)
    end
    show.text(frame.src .. " > " .. frame.dst .. ": " .. body)
    local lat, lon = aprs.position(frame.info, frame.dst)
    if lat then
      show.map(lat, lon, frame.src)
    end
  else
    show.text("HDLC " .. #frame.bytes .. " bytes: " .. hex(frame.bytes, 24))
  end
end
