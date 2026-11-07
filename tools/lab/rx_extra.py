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
from lab import Phone, Vsg60Gen, cw_keying, wait_idle, cpu_load  # noqa: E402


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


def aprs_waveform(rate, dev, n_packets=10, gap_s=0.3):
    """n_packets APRS UI frames (numbered), AFSK 1200 audio FM-modulated with `dev` peak deviation."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from aprs_gen import ui_frame, hdlc_nrzi, afsk
    audio = []
    for k in range(n_packets):
        raw = ui_frame("HG0LAB-1", "APRS", ["WIDE1-1"], f"!4729.87N/01902.41E>SatHunter lab packet {k:02d}".encode())
        audio += afsk(hdlc_nrzi(raw, 40, 3), rate) + [0.0] * int(gap_s * rate)
    a = np.array(audio)
    ph = 2 * np.pi * dev * np.cumsum(a / max(1e-9, np.abs(a).max())) / rate
    return [complex(v) for v in np.exp(1j * ph)], len(a) / rate


def g3ruh_waveform(rate, dev, n_packets=10, gap_s=0.05, size=80):
    """n_packets AX.25 UI frames (numbered), 9600 bd G3RUH: HDLC + NRZI, scrambled 1 + x^12 + x^17,
    raised-cosine NRZ (roll-off 0.5), FM with `dev` peak deviation."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
    from aprs_gen import ui_frame, hdlc_nrzi
    baud = 9600.0
    bits = []
    for k in range(n_packets):
        raw = ui_frame("HG0LAB-2", "CQ", [], (f"SatHunter 9k6 lab frame {k:02d} " + "x" * size)[:size].encode())
        bits += hdlc_nrzi(raw, 24, 4) + [1] * int(gap_s * baud)
    reg, line = 0, []
    for d in bits:
        s = d ^ ((reg >> 11) & 1) ^ ((reg >> 16) & 1)
        reg = ((reg << 1) | s) & 0x3FFFF
        line.append(s)
    sps = rate / baud
    n = int(np.ceil(len(line) * sps))
    t = np.arange(-4 * sps, 4 * sps + 1) / sps
    beta = 0.5
    den = 1 - (2 * beta * t) ** 2
    h = np.sinc(t) * np.where(np.abs(den) < 1e-6, np.pi / 4, np.cos(np.pi * beta * t) / np.where(np.abs(den) < 1e-6, 1, den))
    imp = np.zeros(n)
    idx = ((np.arange(len(line)) + 0.5) * sps).astype(int)
    imp[idx[idx < n]] = (2 * np.array(line) - 1)[idx < n]
    bb = np.convolve(imp, h, mode="same")
    bb /= np.abs(bb).max()
    ph = 2 * np.pi * dev * np.cumsum(bb) / rate
    return np.exp(1j * ph).astype(np.complex64), n / rate


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--gen", choices=["vsg60", "hackrf"], default="vsg60")
    ap.add_argument("--freq", type=float, default=436.6e6)
    ap.add_argument("--part", choices=["twotone", "doppler", "aprs", "g3ruh"], required=True)
    ap.add_argument("--g3ruh-levels", default="-100,-105,-108,-110,-112,-114,-116,-118,-120", help="g3ruh: dBm")
    ap.add_argument("--g3ruh-dev", type=float, default=3000.0, help="g3ruh: FM deviation, Hz")
    ap.add_argument("--g3ruh-bws", default="20000", help="g3ruh: NFM channel bandwidths, Hz")
    ap.add_argument("--g3ruh-secs", type=float, default=20.0, help="g3ruh: listening time per level")
    ap.add_argument("--gains", default="12.5,29.7", help="twotone: RTL gains")
    ap.add_argument("--levels", default="-125,-120,-115,-110,-105,-100,-97,-94,-91,-88,-85,-82,-79",
                    help="twotone: level of each tone at the receiver input, dBm")
    ap.add_argument("--rates", default="0,10,25,50,100", help="doppler: Hz/s")
    ap.add_argument("--cw-levels", default="-135,-141", help="doppler: dBm")
    ap.add_argument("--text", default="VVV DE HG0LAB TEST")
    ap.add_argument("--wpm", type=float, default=15)
    ap.add_argument("--arb-rate", type=float, default=25e3, help="doppler: waveform rate (long files at 100 kS/s crash the VSG software)")
    ap.add_argument("--cw-bw", type=float, default=2000.0, help="doppler: CW filter bandwidth, Hz")
    ap.add_argument("--aprs-levels", default="-105,-110,-115,-118,-120,-122,-124,-126,-128", help="aprs: dBm")
    ap.add_argument("--aprs-dev", type=float, default=3000.0, help="aprs: FM deviation, Hz")
    ap.add_argument("--aprs-bws", default="12500", help="aprs: NFM channel bandwidths, Hz")
    ap.add_argument("--aprs-secs", type=float, default=30.0, help="aprs: listening time per level")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()

    phone = Phone(a.phone, a.pin)
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    if a.gen == "hackrf":
        from hackrf_gen import HackRfGen
        gen = HackRfGen(a.atten)
    else:
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
        elif a.part == "aprs":
            phone.cmd(cmd="gain", db=12.5)
            phone.cmd(cmd="aprs", on=True)
            phone.cmd(cmd="tune", hz=a.freq)
            time.sleep(1.5)
            rate = 50e3
            iq, loop_s = aprs_waveform(rate, a.aprs_dev)
            per_s = 10 / loop_s
            res["aprs"] = {"deviation_hz": a.aprs_dev, "packets_per_loop": 10, "loop_s": loop_s, "rows": []}
            lv_list = [float(x) for x in a.aprs_levels.split(",")]
            runs = [(float(bw), lv) for bw in a.aprs_bws.split(",") for lv in lv_list]
            cur_bw = None
            for k, (bw, lv) in enumerate(runs):
                if bw != cur_bw:
                    phone.cmd(cmd="mode", mode="NFM", bw=bw)
                    cur_bw = bw
                    time.sleep(1.0)
                phone.phase("APRS", k + 1, len(runs), f"NFM {bw / 1e3:g} kHz, {lv:.0f} dBm, {a.aprs_dev / 1e3:.1f} kHz deviation")
                gen.play(a.freq, lv, f"sathunter_aprs_{int(a.aprs_dev)}.cf32", iq, rate)
                time.sleep(1.0)
                wait_idle(phone)
                c0 = phone._req("GET", "/aprs?since=0")["count"]
                t0 = time.time()
                time.sleep(a.aprs_secs)
                r = phone._req("GET", f"/aprs?since={c0}")
                dt = time.time() - t0
                good = [f for f in r["frames"] if "SatHunter lab packet" in f.get("info", "")]
                expected = dt * per_s
                row = {"cpu_pct_after": cpu_load(), "bw_hz": bw, "level_dbm": lv, "decoded": len(good), "expected": expected, "success": min(1.0, len(good) / expected), "bad_crc_total": r["bad_crc"]}
                res["aprs"]["rows"].append(row)
                phone.log(f"APRS {bw / 1e3:g} kHz {lv:.0f} dBm: {len(good)} of ~{expected:.0f} packets ({100 * row['success']:.0f} %)")
                save()
            gen.off()
        elif a.part == "g3ruh":
            phone.cmd(cmd="gain", db=12.5)
            phone.cmd(cmd="fsk9k6", on=True)
            phone.cmd(cmd="tune", hz=a.freq)
            time.sleep(1.5)
            rate = 100e3
            iq, loop_s = g3ruh_waveform(rate, a.g3ruh_dev)
            per_s = 10 / loop_s
            res["g3ruh"] = {"deviation_hz": a.g3ruh_dev, "frames_per_loop": 10, "loop_s": loop_s, "rows": []}
            lv_list = [float(x) for x in a.g3ruh_levels.split(",")]
            runs = [(float(bw), lv) for bw in a.g3ruh_bws.split(",") for lv in lv_list]
            cur_bw = None
            for k, (bw, lv) in enumerate(runs):
                if bw != cur_bw:
                    phone.cmd(cmd="mode", mode="NFM", bw=bw)
                    cur_bw = bw
                    time.sleep(1.0)
                phone.phase("9k6 G3RUH", k + 1, len(runs), f"NFM {bw / 1e3:g} kHz, {lv:.0f} dBm, {a.g3ruh_dev / 1e3:.1f} kHz deviation")
                gen.play(a.freq, lv, f"sathunter_g3ruh_{int(a.g3ruh_dev)}.cf32", iq, rate)
                time.sleep(1.0)
                wait_idle(phone)
                c0 = phone._req("GET", "/aprs?since=0")["count"]
                t0 = time.time()
                time.sleep(a.g3ruh_secs)
                r = phone._req("GET", f"/aprs?since={c0}")
                dt = time.time() - t0
                good = [f for f in r["frames"] if "SatHunter 9k6 lab frame" in f.get("info", "")]
                expected = dt * per_s
                row = {"cpu_pct_after": cpu_load(), "bw_hz": bw, "level_dbm": lv, "decoded": len(good), "expected": expected,
                       "success": min(1.0, len(good) / expected)}
                res["g3ruh"]["rows"].append(row)
                phone.log(f"9k6 {bw / 1e3:g} kHz {lv:.0f} dBm: {len(good)} of ~{expected:.0f} frames ({100 * row['success']:.0f} %)")
                save()
            gen.off()
        else:
            phone.cmd(cmd="mode", mode="CW", bw=a.cw_bw)
            phone.cmd(cmd="gain", db=12.5)
            phone.cmd(cmd="tune", hz=a.freq)
            time.sleep(1.5)
            res["doppler"] = []
            rates = [float(x) for x in a.rates.split(",")]
            lvls = [float(x) for x in a.cw_levels.split(",")]
            msg_s = len(cw_keying(a.text, a.wpm, 100)) / 100
            k = 0
            for r in rates:
                iq = keyed_chirp(a.text, a.wpm, a.arb_rate, r)
                for lv in lvls:
                    k += 1
                    phone.phase("Doppler CW", k, len(rates) * len(lvls), f"{r:.0f} Hz/s, {lv:.0f} dBm")
                    wait_idle(phone)
                    gen.play(a.freq, lv, f"sathunter_chirp_{int(r)}_{int(a.arb_rate)}.cf32", iq, a.arb_rate)
                    time.sleep(max(8.0, 2.2 * msg_s))
                    c = phone.cw(max(8, int(2.2 * msg_s)))
                    ok = a.text.replace(" ", "") in c["text"].replace(" ", "")
                    row = {"hz_per_s": r, "level_dbm": lv, "cw_bw_hz": a.cw_bw, "sweep_hz": r * msg_s, "text": c["text"], "ok": ok,
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
