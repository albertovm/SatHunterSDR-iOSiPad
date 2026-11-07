"""Spurs and interference in a receive channel with the generator silent: the display spectrum
(max-hold and average over a few seconds) around --hz, against the median floor.

    python tools/lab/inband_check.py --ip 192.168.1.237 --hz 436.6e6 --bw 12500
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from lab import Phone  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ip", default="192.168.1.237")
ap.add_argument("--pin", default="1027")
ap.add_argument("--hz", type=float, default=436.6e6)
ap.add_argument("--bw", type=float, default=12500)
ap.add_argument("--n", type=int, default=10)
a = ap.parse_args()
ph = Phone(a.ip, a.pin)
mx = None
avg = None
for _ in range(a.n):
    sp = ph._req("GET", "/spectrum?secs=0.5")
    d = np.array(sp["db"])
    mx = d if mx is None else np.maximum(mx, d)
    avg = 10 ** (d / 10) if avg is None else avg + 10 ** (d / 10)
c, fs, n = sp["center_hz"], sp["rate"], sp["bins"]
f = c + (np.arange(n) - n / 2) * fs / n
avg = 10 * np.log10(avg / a.n)
med = np.median(avg)
ch = np.abs(f - a.hz) <= a.bw / 2
print("span %.0f kHz, %d bins of %.1f Hz; median floor %.1f dB" % (fs / 1e3, n, fs / n, med))
print("channel: average max %.1f dB above the floor at %+.0f Hz; max-hold max %.1f dB above at %+.0f Hz" % (
    avg[ch].max() - med, f[ch][np.argmax(avg[ch])] - a.hz, mx[ch].max() - med, f[ch][np.argmax(mx[ch])] - a.hz))
top = np.argsort(avg)[::-1][:8]
for k in sorted(top):
    print("  spur %+9.0f Hz from the channel: %+.1f dB" % (f[k] - a.hz, avg[k] - med))
