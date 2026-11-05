"""Frequency error per sample rate, interleaved (rates switched back to back, 6 rounds), so the RTL's
thermal drift cancels in the differences between rates."""
import sys, time, json
sys.path.insert(0, r"C:\Users\RF\SatHunter-SDR\tools\lab")
from lab import Phone, Vsg60Gen

out = open(r"D:\Measurements\freqcheck.log", "w", buffering=1)
ph = Phone("192.168.1.11", "1027")
g = Vsg60Gen(34.7, "127.0.0.1", 5124, r"C:\sathunter_lab", None)
rows = []
try:
    ph.cmd(cmd="decimation", factor=8)
    ph.cmd(cmd="gain", db=12.5)
    f0 = 436.6e6
    g.play(f0, -95, "sathunter_cw.cf32", [1.0] * 10000, 100e3)
    for rnd in range(6):
        for rate in (2400000.0, 1024000.0, 250000.0):
            ph.cmd(cmd="rate", hz=rate)
            ph.cmd(cmd="tune", hz=f0)
            time.sleep(1.2)
            m = ph.measure(f0, 3000, 1.0)
            t = time.time()
            rows.append({"round": rnd, "rate": rate, "t": t, "offset_hz": m["offset_hz"], "center_hz": m["center_hz"], "bin_hz": m["bin_hz"]})
            out.write(f"{rnd} {rate/1e6:.3f} {m['offset_hz']:+.1f} Hz (bin {m['bin_hz']:.0f})\n")
finally:
    g.close()
    ph.cmd(cmd="rate", hz=1024000.0)
json.dump(rows, open(r"D:\Measurements\freqcheck.json", "w"), indent=1)
