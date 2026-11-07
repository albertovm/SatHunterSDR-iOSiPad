"""HackRF waveform check: the same level as CW and as an FM waveform (SSTV), channel power compared.
FM has a constant envelope, so its channel power must equal the CW's at the same set level.

    python tools/lab/hackrf_diag.py --ip 192.168.1.237 --atten 70.5
"""
import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from hackrf_gen import HackRfGen  # noqa: E402
from lab import Phone  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ip", default="192.168.1.237")
ap.add_argument("--pin", default="1027")
ap.add_argument("--atten", type=float, default=70.5)
ap.add_argument("--hz", type=float, default=436.6e6)
a = ap.parse_args()
ph = Phone(a.ip, a.pin)
ph.cmd(cmd="gain", db=12.5)
ph.cmd(cmd="decimation", factor=8)
ph.cmd(cmd="tune", hz=a.hz)
time.sleep(1)
gen = HackRfGen(a.atten)
fs = 25e3
t = np.arange(int(fs * 4)) / fs
fm = np.exp(1j * 2 * np.pi * 3000 * np.cumsum(np.sin(2 * np.pi * 1500 * t)) / fs).astype(np.complex64)  # 3 kHz dev tone
try:
    gen.off()
    time.sleep(1)
    m = ph._req("GET", "/measure?hz=%d&bw=12000&secs=2" % a.hz)
    print("off:          floor %.1f dBFS/bin" % m["noise_dbfs_per_bin"])
    for lv in (-100, -110, -120):
        gen.cw(a.hz, lv)
        time.sleep(1)
        c = ph._req("GET", "/measure?hz=%d&bw=12000&secs=2" % a.hz)
        gen.play(a.hz, lv, "diag_fm3k", fm, fs)
        time.sleep(1)
        f = ph._req("GET", "/measure?hz=%d&bw=12000&secs=2" % a.hz)
        print("%5d dBm  CW: peak %6.1f dBFS, ch SNR %5.1f dB | FM 3k: peak %6.1f, ch SNR %5.1f dB | %s" % (
            lv, c["peak_dbfs"], c["channel_snr_db"], f["peak_dbfs"], f["channel_snr_db"], gen.last))
finally:
    gen.close()
