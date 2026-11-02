#!/usr/bin/env python3
"""SatHunterSDR DSP check: every sample rate x decimation, and every demodulator x filter bandwidth,
measured with the VSG60 through the phone's lab link (needs the app's /audio endpoint, beta10-lab3+).

    python tools/lab/dsp_check.py --phone 192.168.1.11 --pin 1027 --vsg 127.0.0.1:5124 --atten 33.6

Part 1, decimation (per rate and decimation):
  - CW tone stepped across the span: level flatness, frequency error, absolute level vs decimation 1
  - tones outside the span: alias rejection of the decimation filter
  - noise floor in dBFS/Hz: must not change with the decimation
  - USB demodulation of a tone 1000 Hz above the VFO: the audio pitch must be 1000 Hz
Part 2, filter bandwidth (per mode and bandwidth):
  - AM / USB / LSB / CW: flat noise in, the audio spectrum is the filter shape -> measured edges
  - NFM / WFM: a 1 kHz FM tone in, audio pitch, level and SINAD

Results: measurements/<date_time>_<name>/ (results.json, report.md). Needs numpy.
"""

import argparse, io, json, math, os, sys, time, wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Phone, Vsg60Gen  # noqa: E402

BINS_GUESS = 4096


def audio_np(raw):
    w = wave.open(io.BytesIO(raw))
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32767
    return x, w.getframerate()


def psd(x, fs, nper=4096):
    """Welch PSD (Hann, 50 %), linear power per bin."""
    if len(x) < nper:
        nper = 1 << int(math.log2(max(256, len(x))))
    win = np.hanning(nper)
    segs = [x[k:k + nper] * win for k in range(0, len(x) - nper + 1, nper // 2)]
    p = np.mean([np.abs(np.fft.rfft(s)) ** 2 for s in segs], axis=0)
    return np.fft.rfftfreq(nper, 1 / fs), p


def tone_stats(x, fs, lo=50, hi=20000):
    """Dominant tone: frequency (interpolated), level dBFS, SINAD over lo..hi."""
    f, p = psd(x, fs, 16384)
    band = (f >= lo) & (f <= hi)
    k = int(np.argmax(np.where(band, p, 0)))
    if 0 < k < len(p) - 1:
        a, b, c = np.log(p[k - 1:k + 2] + 1e-30)
        frac = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0
    else:
        frac = 0
    df = f[1] - f[0]
    sig = p[max(0, k - 4):k + 5].sum()
    rest = p[band].sum() - sig
    return {"tone_hz": float(f[k] + frac * df), "tone_dbfs": float(10 * math.log10(sig / (np.sum(np.hanning(16384) ** 2) * 16384 / 2) + 1e-30)),
            "sinad_db": float(10 * math.log10(sig / max(rest, 1e-30)))}


def edges(x, fs, ref_band, drop=6.0):
    """Audio passband edges at -drop dB relative to the median level in ref_band (Hz)."""
    f, p = psd(x, fs, 8192)
    # smooth over ~100 Hz
    k = max(1, int(100 / (f[1] - f[0])))
    ps = np.convolve(p, np.ones(k) / k, mode="same")
    ref = np.median(ps[(f >= ref_band[0]) & (f <= ref_band[1])])
    above = ps >= ref * 10 ** (-drop / 10)
    centre = int(np.argmin(np.abs(f - (ref_band[0] + ref_band[1]) / 2)))
    lo = centre
    while lo > 0 and above[lo - 1]:
        lo -= 1
    hi = centre
    while hi < len(f) - 1 and above[hi + 1]:
        hi += 1
    return float(f[lo]), float(f[hi]), f, 10 * np.log10(ps / ref + 1e-30)


def fm_tone(rate, dev, fm=1000.0, periods=100):
    n = int(round(rate / fm)) * periods
    t = np.arange(n) / rate
    ph = 2 * np.pi * dev / fm * np.sin(2 * np.pi * fm * t)  # periodic: whole number of tone periods
    return [complex(v) for v in np.exp(1j * ph)]


def noise_iq(rate, bw, n=1 << 16, seed=2):
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(n, 1 / rate)
    spec = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) * (np.abs(f) <= bw / 2)
    x = np.fft.ifft(spec)
    x /= np.abs(x).max()
    papr = 10 * math.log10(1.0 / np.mean(np.abs(x) ** 2))
    return [complex(v) for v in x], papr


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--freq", type=float, default=436.6e6)
    ap.add_argument("--atten", type=float, default=0.0, help="dB between the generator and the receiver input")
    ap.add_argument("--gain", type=float, default=12.5)
    ap.add_argument("--rates", default="2400000,1024000,250000")
    ap.add_argument("--decims", default="1,2,4,8")
    ap.add_argument("--level", type=float, default=-95, help="CW level for the decimation part, dBm at the receiver input")
    ap.add_argument("--noise-psd", type=float, default=-145, help="noise density for the filter part, dBm/Hz")
    ap.add_argument("--fm-level", type=float, default=-100, help="FM tone level, dBm")
    ap.add_argument("--secs", type=float, default=1.0)
    ap.add_argument("--part", choices=["all", "decim", "bw"], default="all")
    ap.add_argument("--name", default="dsp-check")
    a = ap.parse_args()

    phone = Phone(a.phone, a.pin, a.port)
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.atten, host, int(port), a.vsg_dir, None)
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    st0 = phone.status()
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "freq_hz": a.freq, "atten_db": a.atten, "gain_db": a.gain,
           "phone": {k: st0.get(k) for k in ("source_status", "rate", "decimation", "bins", "mode", "bw")}}
    restore = {"rate": st0.get("rate"), "decimation": st0.get("decimation"), "mode": st0.get("mode"), "bw": st0.get("bw")}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)

    try:
        phone.cmd(cmd="gain", db=a.gain)
        # ---------------- Part 1: rates x decimations
        if a.part in ("all", "decim"):
            rates = [float(x) for x in a.rates.split(",") if x.strip()]
            decims = [int(x) for x in a.decims.split(",") if x.strip()]
            tone = [1.0] * 10_000
            res["decim"] = []
            total = len(rates) * len(decims)
            n = 0
            for rate in rates:
                ref_db = None
                for d in decims:
                    n += 1
                    phone.phase("decimation", n, total, f"rate {rate / 1e6:.3f} MS/s, /{d}")
                    phone.cmd(cmd="rate", hz=rate)
                    phone.cmd(cmd="decimation", factor=d)
                    phone.cmd(cmd="mode", mode="USB", bw=2800.0)
                    phone.cmd(cmd="tune", hz=a.freq)
                    time.sleep(2.0)
                    st = phone.status()
                    c, span, bins = st["spectrum_center_hz"], st["spectrum_rate"], st.get("bins", BINS_GUESS)
                    bin_hz = span / bins
                    mbw = max(2000.0, 24 * bin_hz)
                    row = {"rate": rate, "decimation": d, "span_hz": span, "center_hz": c, "vfo_hz": st["vfo_hz"], "bin_hz": bin_hz,
                           "inband": [], "alias": []}
                    # noise floor, generator off
                    gen.off()
                    m = phone.measure(c + 0.2 * span, mbw, a.secs)
                    row["noise_dbfs_hz"] = m["noise_dbfs_per_bin"] - 10 * math.log10(bin_hz)
                    # in-band tone positions
                    gen.play(a.freq, a.level, "sathunter_cw.cf32", tone, 100e3)
                    for frac in (-0.45, -0.35, -0.25, -0.15, -0.05, 0.05, 0.15, 0.25, 0.35, 0.45):
                        hz = c + frac * span
                        gen.tune(hz)
                        time.sleep(0.3)
                        m = phone.measure(hz, mbw, a.secs)
                        row["inband"].append({"frac": frac, "hz": hz, "peak_dbfs": m["peak_dbfs"], "offset_hz": m["offset_hz"],
                                              "snr_db": m["peak_snr_db"]})
                    pk = [r["peak_dbfs"] for r in row["inband"]]
                    row["flatness_db"] = max(pk) - min(pk)
                    mid = [r["peak_dbfs"] for r in row["inband"] if abs(r["frac"]) <= 0.25]
                    row["level_dbfs"] = sum(mid) / len(mid)
                    if d == 1 or ref_db is None:
                        ref_db = row["level_dbfs"]
                    row["level_vs_ref_db"] = row["level_dbfs"] - ref_db
                    row["max_freq_err_hz"] = max(abs(r["offset_hz"]) for r in row["inband"])
                    # outside the span: where the alias would land, and how strong it is
                    if d > 1:
                        for frac in (0.55, 0.7, 0.9, -0.55, -0.7, -0.9):
                            hz = c + frac * span
                            alias = c + (frac - math.copysign(1.0, frac)) * span
                            gen.tune(hz)
                            time.sleep(0.3)
                            m = phone.measure(alias, mbw, a.secs)
                            row["alias"].append({"frac": frac, "tone_hz": hz, "alias_hz": alias, "alias_dbfs": m["peak_dbfs"],
                                                 "alias_snr_db": m["peak_snr_db"], "rejection_db": row["level_dbfs"] - m["peak_dbfs"]})
                        row["min_rejection_db"] = min(r["rejection_db"] for r in row["alias"])
                    # USB pitch: tone 1000 Hz above the VFO
                    gen.tune(st["vfo_hz"] + 1000)
                    time.sleep(0.8)
                    x, fs = audio_np(phone._req("GET", "/audio?secs=2", timeout=40))
                    t = tone_stats(x, fs)
                    row["usb_pitch_hz"] = t["tone_hz"]
                    row["usb_sinad_db"] = t["sinad_db"]
                    row["audio_rate"] = fs
                    phone.log(f"{rate / 1e6:.3f} MS/s /{d}: span {span / 1e3:.0f} kHz, flat {row['flatness_db']:.1f} dB, level {row['level_vs_ref_db']:+.1f} dB, "
                              f"noise {row['noise_dbfs_hz']:.1f} dBFS/Hz, f err {row['max_freq_err_hz']:.0f} Hz, "
                              f"alias {row.get('min_rejection_db', float('nan')):.0f} dB, pitch {t['tone_hz']:.0f} Hz")
                    res["decim"].append(row)
                    save()
                    gen.off()

        # ---------------- Part 2: modes x bandwidths
        if a.part in ("all", "bw"):
            phone.cmd(cmd="rate", hz=1024000.0)
            phone.cmd(cmd="decimation", factor=1)
            phone.cmd(cmd="tune", hz=a.freq)
            time.sleep(1.5)
            vfo = phone.status()["vfo_hz"]
            res["bw"] = []
            tests = [("AM", [3000, 5000, 10000, 20000]), ("USB", [1800, 2400, 2800, 3500]), ("LSB", [1800, 2400, 2800, 3500]),
                     ("CW", [250, 500, 1000, 2000])]
            nrate, nbw = 200e3, 120e3
            iq, papr = noise_iq(nrate, nbw)
            mean = a.noise_psd + 10 * math.log10(nbw)
            gen.play(vfo, mean + papr, "sathunter_noise_120k.cf32", iq, nrate)
            k = 0
            total = sum(len(b) for _, b in tests) + 7
            for mode, bws in tests:
                for bw in bws:
                    k += 1
                    phone.phase("filter bandwidth", k, total, f"{mode} {bw} Hz")
                    phone.cmd(cmd="mode", mode=mode, bw=float(bw))
                    time.sleep(1.5)
                    x, fs = audio_np(phone._req("GET", "/audio?secs=3", timeout=40))
                    if mode == "AM":
                        ref, exp = (200, bw / 4), (0, bw / 2)
                    elif mode in ("USB", "LSB"):
                        ref, exp = (bw * 0.3, bw * 0.6), (0, bw)
                    else:
                        f, p = psd(x, fs, 8192)
                        idx = np.flatnonzero((f > 100) & (f < 4000))
                        fc = float(f[idx[int(np.argmax(p[idx]))]])  # the beat note: the middle of the passband
                        ref, exp = (fc - bw * 0.15, fc + bw * 0.15), (fc - bw / 2, fc + bw / 2)
                    lo, hi, f, rel = edges(x, fs, ref)
                    row = {"mode": mode, "bw_hz": bw, "edge_lo_hz": lo, "edge_hi_hz": hi, "width_hz": hi - lo,
                           "expected_lo_hz": exp[0], "expected_hi_hz": exp[1], "expected_width_hz": exp[1] - exp[0],
                           "width_ratio": (hi - lo) / (exp[1] - exp[0]),
                           "shape_f": [float(v) for v in f[::4]], "shape_db": [float(v) for v in rel[::4]]}
                    res["bw"].append(row)
                    phone.log(f"{mode} {bw} Hz: audio -6 dB {lo:.0f}..{hi:.0f} Hz (width {hi - lo:.0f}, expected {exp[1] - exp[0]:.0f}, x{row['width_ratio']:.2f})")
                    save()
            gen.off()
            # FM: a 1 kHz tone
            res["fm"] = []
            for mode, dev, rate, bws in (("NFM", 2500.0, 100e3, [6250, 12500, 25000]), ("WFM", 50000.0, 1e6, [50000, 100000, 180000, 250000])):
                gen.play(vfo, a.fm_level, f"sathunter_fm_{mode.lower()}_{int(dev)}.cf32", fm_tone(rate, dev), rate)
                for bw in bws:
                    k += 1
                    phone.phase("filter bandwidth", k, total, f"{mode} {bw} Hz, deviation {dev / 1e3:.1f} kHz")
                    phone.cmd(cmd="mode", mode=mode, bw=float(bw))
                    time.sleep(1.5)
                    x, fs = audio_np(phone._req("GET", "/audio?secs=3", timeout=40))
                    t = tone_stats(x, fs)
                    row = {"mode": mode, "bw_hz": bw, "deviation_hz": dev, "carson_hz": 2 * (dev + 1000), **t}
                    res["fm"].append(row)
                    phone.log(f"{mode} {bw} Hz: tone {t['tone_hz']:.1f} Hz, {t['tone_dbfs']:.1f} dBFS, SINAD {t['sinad_db']:.1f} dB")
                    save()
                gen.off()
        phone.phase("done", 1, 1, os.path.relpath(out, root))
    finally:
        gen.close()
        try:
            if restore["rate"]:
                phone.cmd(cmd="rate", hz=restore["rate"])
            if restore["decimation"]:
                phone.cmd(cmd="decimation", factor=restore["decimation"])
        except SystemExit:
            pass
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
    print(f"\nResults: {out}")


if __name__ == "__main__":
    main()
