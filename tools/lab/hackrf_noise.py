"""Does the HackRF add noise at the receiver? Silence (zeros) at TX VGA 0 / 20 / 47, LO in and out of
band, and a far-away LO, with the receiver's noise floor read each time.

    python tools/lab/hackrf_noise.py --ip 192.168.1.237
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
ph.cmd(cmd="gain", db=12.5)
ph.cmd(cmd="decimation", factor=8)
ph.cmd(cmd="tune", hz=a.hz)
gen = HackRfGen(70.5)
try:
    gen.off()
    for lo, vga in ((a.hz + 300e6, 0), (a.hz - 250e3, 0), (a.hz - 250e3, 20), (a.hz - 250e3, 47), (a.hz + 300e6, 47), (a.hz - 250e3, 0)):
        gen._cmd(cmd="lo", hz=lo)
        gen._cmd(cmd="gain", vga=vga, amp=False)
        time.sleep(1.5)
        m = ph._req("GET", "/measure?hz=%d&bw=12000&secs=3" % a.hz)
        print("LO %+8.3f MHz from the channel, VGA %2d: floor %.2f dBFS/bin" % ((lo - a.hz) / 1e6, vga, m["noise_dbfs_per_bin"]), flush=True)
finally:
    gen.close()
