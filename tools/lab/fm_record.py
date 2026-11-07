"""Record the phone's FM discriminator (lab link /fm) while the generator plays 9k6 G3RUH frames,
at a few levels, for tuning the decoder offline (cargo run --example g3ruh_wav -- file.wav).

    python tools/lab/fm_record.py --gen hackrf --atten 70.5 --levels=-110,-112,-114,-116 --secs 30
"""
import argparse
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from lab import Phone  # noqa: E402
from rx_extra import g3ruh_waveform  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--ip", default="192.168.1.237")
ap.add_argument("--pin", default="1027")
ap.add_argument("--gen", choices=["hackrf", "vsg60"], default="hackrf")
ap.add_argument("--atten", type=float, required=True)
ap.add_argument("--freq", type=float, default=436.6e6)
ap.add_argument("--bw", type=float, default=20000)
ap.add_argument("--levels", default="-110,-112,-114,-116")
ap.add_argument("--secs", type=float, default=30)
ap.add_argument("--name", default="fm-g3ruh")
a = ap.parse_args()
ph = Phone(a.ip, a.pin)
if a.gen == "hackrf":
    from hackrf_gen import HackRfGen
    gen = HackRfGen(a.atten)
else:
    from lab import Vsg60Gen
    gen = Vsg60Gen(a.atten, "127.0.0.1", 5124, r"C:\sathunter_lab", None)
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
os.makedirs(out, exist_ok=True)
ph.cmd(cmd="gain", db=12.5)
ph.cmd(cmd="fsk9k6", on=True)
ph.cmd(cmd="mode", mode="NFM", bw=a.bw)
ph.cmd(cmd="tune", hz=a.freq)
time.sleep(1.5)
iq, loop_s = g3ruh_waveform(100e3, 3000.0)
try:
    for lv in [float(x) for x in a.levels.split(",")]:
        gen.play(a.freq, lv, "sathunter_g3ruh_3000.cf32", iq, 100e3)
        time.sleep(1.5)
        c0 = ph._req("GET", "/aprs?since=0")["count"]
        url = "http://%s:8765/fm?pin=%s&secs=%g" % (a.ip, a.pin, a.secs)
        data = urllib.request.urlopen(url, timeout=a.secs + 30).read()
        r = ph._req("GET", "/aprs?since=%d" % c0)
        n = sum(1 for f in r["frames"] if "SatHunter 9k6 lab frame" in f.get("info", ""))
        fn = os.path.join(out, "fm_%ddBm.wav" % round(-lv))
        open(fn, "wb").write(data)
        print("%.0f dBm: %s (%d bytes), phone decoded %d of ~%.0f frames" % (lv, fn, len(data), n, a.secs * 10 / loop_s), flush=True)
finally:
    gen.close()
