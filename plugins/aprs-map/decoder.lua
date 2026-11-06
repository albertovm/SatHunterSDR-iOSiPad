-- Generic APRS: every AX.25 frame the core decodes arrives in on_frame(frame).
-- (Satellite-specific plugins such as iss-aprs take over when their satellite is selected.)

function on_frame(frame)
  local via = ""
  if #frame.path > 0 then
    via = " via " .. table.concat(frame.path, ",")
  end
  show.text(frame.src .. " > " .. frame.dst .. via .. ": " .. frame.info)

  local lat, lon = aprs.position(frame.info, frame.dst)
  if lat then
    show.map(lat, lon, frame.src)
  end
end
