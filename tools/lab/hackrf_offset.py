"""Frequency check of the HackRF generator (ppm correction applied): CW at --hz, offset seen by the phone.

    python tools/lab/hackrf_offset.py --ip 192.168.1.237
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from hackrf_gen import HackRfGen  # noqa: E402
from lab import Phone  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ip", default="192.168.1.237")
ap.add_argument("--pin", default="1027")
ap.add_argument("--hz", type=float, default=436.6e6)
a = ap.parse_args()
ph = Phone(a.ip, a.pin)
ph.cmd(cmd="decimation", factor=8)
ph.cmd(cmd="tune", hz=a.hz)
g = HackRfGen(70.5)
try:
    for lv in (-100, -110):
        g.cw(a.hz, lv)
        time.sleep(1.5)
        m = ph._req("GET", "/measure?hz=%d&bw=12000&secs=2" % a.hz)
        print("%d dBm: offset %+.0f Hz, peak %.1f dBFS (lo %.1f Hz, cal ppm %s)" % (lv, m["offset_hz"], m["peak_dbfs"], g.lo, g.cal.get("ppm")))
finally:
    g.close()
