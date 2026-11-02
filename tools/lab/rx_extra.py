#!/usr/bin/env python3
"""SatHunterSDR extra receiver checks with the VSG60 through the lab link.

    python tools/lab/rx_extra.py --phone 192.168.1.11 --pin 1027 --vsg 127.0.0.1:5124 --atten 34.7 --part twotone
    python tools/lab/rx_extra.py ... --part doppler

twotone: two equal CW tones 10 kHz apart inside the span, swept in level: tone and third-order
         product levels -> in-band IIP3 and spur-free dynamic range of the whole chain (LNA, R820T,
         8-bit ADC), per RTL gain.
doppler: keyed CW whose frequency ramps linearly (the residual Doppler left after TLE tracking, or a
         pass without tracking), several rates and levels -> does the CW decoder keep up?

Results: measurements/<date_time>_<name>/results.json (+ report by hand). Needs numpy.
"""

import argparse, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Phone, Vsg60Gen, cw_keying  # noqa: E402


def two_tone(rate, df, n=10_000):
    t = np.arange(n) / rate
    x = 0.5 * np.exp(-1j * np.pi * df * t) + 0.5 * np.exp(1j * np.pi * df * t)  # -df/2 and +df/2
    return [complex(v) for v in x]


def keyed_chirp(text, wpm, rate, hz_per_s):
    env = np.array(cw_keying(text, wpm, rate))
    t = np.arange(len(env)) / rate
    tc = t - t[-1] / 2  # frequency 0 in the middle of the message
    ph = 2 * np.pi * 0.5 * hz_per_s * tc ** 2
    return [complex(v) for v in env * np.exp(1j * ph)]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--freq", type=float, default=436.6e6)
    ap.add_argument("--part", choices=["twotone", "doppler"], required=True)
    ap.add_argument("--gains", default="12.5,29.7", help="twotone: RTL gains")
    ap.add_argument("--levels", default="-125,-120,-115,-110,-105,-100,-97,-94,-91,-88,-85,-82,-79",
                    help="twotone: level of each tone at the receiver input, dBm")
    ap.add_argument("--rates", default="0,10,25,50,100", help="doppler: Hz/s")
    ap.add_argument("--cw-levels", default="-135,-141", help="doppler: dBm")
    ap.add_argument("--text", default="VVV DE HG0LAB TEST")
    ap.add_argument("--wpm", type=float, default=15)
    ap.add_argument("--name", default=None)
    a = ap.parse_args()

    phone = Phone(a.phone, a.pin)
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.atten, host, int(port), a.vsg_dir, None)
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + (a.name or a.part))
    os.makedirs(out, exist_ok=True)
    st0 = phone.status()
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "part": a.part, "freq_hz": a.freq, "atten_db": a.atten,
           "phone": {k: st0.get(k) for k in ("source_status", "rate", "decimation", "ppm", "gain")}}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)

    try:
        phone.cmd(cmd="rate", hz=1024000.0)
        phone.cmd(cmd="decimation", factor=8)
        if a.part == "twotone":
            phone.cmd(cmd="mode", mode="USB", bw=2800.0)
            phone.cmd(cmd="tune", hz=a.freq)
            time.sleep(1.5)
            st = phone.status()
            c = st["spectrum_center_hz"]
            fv, df = c + 30e3, 10e3  # tones at c+25k, c+35k; IM3 at c+15k, c+45k
            f1, f2, i1, i2 = fv - df / 2, fv + df / 2, fv - 1.5 * df, fv + 1.5 * df
            iq = two_tone(100e3, df)
            res["tones_hz"], res["im3_hz"], res["sweeps"] = [f1, f2], [i1, i2], []
            for g in [float(x) for x in a.gains.split(",")]:
                phone.cmd(cmd="gain", db=g)
                rows = []
                for k, lv in enumerate(float(x) for x in a.levels.split(",")):
                    phone.phase("two-tone", k + 1, len(a.levels.split(",")), f"gain {g} dB, {lv:.0f} dBm per tone")
                    gen.play(fv, lv + 6.02, "sathunter_twotone_10k.cf32", iq, 100e3)  # set level = peak = tone + 6 dB
                    time.sleep(0.6)
                    m = {nm: phone.measure(hz, 400, 1.0) for nm, hz in (("t1", f1), ("t2", f2), ("i1", i1), ("i2", i2))}
                    row = {"gain_db": g, "tone_dbm": lv, **{f"{nm}_dbfs": m[nm]["peak_dbfs"] for nm in m},
                           **{f"{nm}_snr_db": m[nm]["peak_snr_db"] for nm in m}, "noise_dbfs_bin": m["i1"]["noise_dbfs_per_bin"]}
                    rows.append(row)
                    phone.log(f"gain {g}: {lv:.0f} dBm/tone: tones {row['t1_dbfs']:.1f}/{row['t2_dbfs']:.1f}, IM3 {row['i1_dbfs']:.1f}/{row['i2_dbfs']:.1f} dBFS")
                    save()
                gen.off()
                res["sweeps"].append({"gain_db": g, "rows": rows})
        else:
            phone.cmd(cmd="mode", mode="CW", bw=2000.0)
            phone.cmd(cmd="gain", db=12.5)
            phone.cmd(cmd="tune", hz=a.freq)
            time.sleep(1.5)
            res["doppler"] = []
            rates = [float(x) for x in a.rates.split(",")]
            lvls = [float(x) for x in a.cw_levels.split(",")]
            msg_s = len(cw_keying(a.text, a.wpm, 100)) / 100
            k = 0
            for r in rates:
                iq = keyed_chirp(a.text, a.wpm, 100e3, r)
                for lv in lvls:
                    k += 1
                    phone.phase("Doppler CW", k, len(rates) * len(lvls), f"{r:.0f} Hz/s, {lv:.0f} dBm")
                    gen.play(a.freq, lv, f"sathunter_chirp_{int(r)}.cf32", iq, 100e3)
                    time.sleep(max(8.0, 2.2 * msg_s))
                    c = phone.cw(max(8, int(2.2 * msg_s)))
                    ok = a.text.replace(" ", "") in c["text"].replace(" ", "")
                    row = {"hz_per_s": r, "level_dbm": lv, "sweep_hz": r * msg_s, "text": c["text"], "ok": ok,
                           "wpm": c["wpm"], "cn0_dbhz": c["cn0_dbhz"], "drift_hz_s": c.get("drift_hz_s")}
                    res["doppler"].append(row)
                    phone.log(f"{r:.0f} Hz/s ({r * msg_s:.0f} Hz per message), {lv:.0f} dBm: {'OK ' if ok else 'BAD'} \"{c['text']}\" drift {c.get('drift_hz_s')}")
                    save()
            gen.off()
        phone.phase("done", 1, 1, os.path.relpath(out, root))
    finally:
        gen.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
