#!/usr/bin/env python3
"""RTL-SDR frequency drift vs time (warm-up after plugging in, or long-term): the VSG60 plays a steady CW
carrier, the phone measures its offset every --every seconds. Run it right after plugging the dongle in.

    python tools/lab/drift.py --phone 192.168.1.11 --pin 1027 --atten 34.7 --mins 90 --name rtl-drift
"""

import argparse, json, os, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Phone, Vsg60Gen, wait_idle  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--freq", type=float, default=436.6e6)
    ap.add_argument("--level", type=float, default=-95.0, help="at the receiver input, dBm")
    ap.add_argument("--mins", type=float, default=90.0)
    ap.add_argument("--every", type=float, default=15.0)
    ap.add_argument("--plugged", default="", help="when the dongle was plugged in (HH:MM), for the report")
    ap.add_argument("--name", default="rtl-drift")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    ph = Phone(a.phone, a.pin)
    st = ph.status()
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "freq_hz": a.freq, "level_dbm": a.level, "plugged": a.plugged, "note": a.note,
           "phone": {k: st.get(k) for k in ("source", "source_status", "rate", "gain", "ppm", "bias_tee", "decimation")}, "rows": []}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)

    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.atten, host, int(port), a.vsg_dir if hasattr(a, "vsg_dir") else r"C:\sathunter_lab", None)
    try:
        ph.cmd(cmd="rate", hz=1024000.0)
        ph.cmd(cmd="decimation", factor=8)
        ph.cmd(cmd="tune", hz=a.freq)
        gen.cw(a.freq, a.level)
        time.sleep(1.0)
        t0 = time.time()
        while time.time() - t0 < a.mins * 60:
            t = time.time()
            m = ph.measure(a.freq, 3000, 2)
            res["rows"].append({"t": t - t0, "unix": t, "offset_hz": m["offset_hz"], "ppm": m["offset_hz"] / a.freq * 1e6,
                                "snr_db": m.get("peak_snr_db"), "bin_hz": m.get("bin_hz")})
            print(f"{(t - t0) / 60:6.1f} min: {m['offset_hz']:+8.1f} Hz ({m['offset_hz'] / a.freq * 1e6:+.3f} ppm), SNR {m.get('peak_snr_db', 0):.0f} dB", flush=True)
            save()
            time.sleep(max(0.0, a.every - (time.time() - t)))
    finally:
        gen.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
