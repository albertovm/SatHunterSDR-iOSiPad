"""Pack Natural Earth 1:110m land polygons (public domain) for the app's world map.

    python tools/make_land.py ne_110m_land.geojson android/app/src/main/assets/land110.bin

Format (little endian): u16 ring count; per ring u16 point count, then (lon, lat) as int16 in 1/100 degree.
Source: https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_land.geojson
"""
import json
import struct
import sys

g = json.load(open(sys.argv[1]))
rings = []
for f in g["features"]:
    geo = f["geometry"]
    for poly in [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]:
        rings.append(poly[0])
out = bytearray(struct.pack("<H", len(rings)))
for r in rings:
    out += struct.pack("<H", len(r))
    for lon, lat in r:
        out += struct.pack("<hh", round(lon * 100), round(lat * 100))
open(sys.argv[2], "wb").write(out)
print(len(rings), "rings,", sum(len(r) for r in rings), "points,", len(out), "bytes")
