#!/usr/bin/env python3
"""More LNA characterisation with the lna_char.py setup (VSG60 - pad - coax - LNA - bias tee - pad - BB60C):

  stab     gain at --f0 every --stab-every s for --stab-mins min (supply / warm-up drift, glitches)
  p1db     compression sweep at several frequencies (points off by > 3 dB are re-measured)
  ip3      two-tone IIP3 vs tone spacing at --f0, and at 100 kHz at a few frequencies
  block    close-in blocking: wanted tone at --f0, one blocker at +-offsets from the same ARB, 1 dB desense
  harm     2nd and 3rd harmonics vs input level
  spur     no input: output sweep 20 MHz - 3 GHz, peaks over the floor (oscillation / spurs)
  nf       noise-figure estimate from the output noise hump (in band vs out of band, the analyser's own
           noise subtracted); rough with an output pad in place

    python tools/lab/lna_extra.py --parts stab,p1db,ip3,block,harm,spur,nf --name lna-extra
"""

import argparse, glob, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Vsg60Gen, wait_idle  # noqa: E402
from bb60 import BB60  # noqa: E402

VSG_MAX = 8.0


def tones(rate, offs, amps, period_hz):
    """Sum of tones (offsets Hz, linear amplitudes), one period of `period_hz`, normalised to peak 1.
    Returns samples and each tone's level relative to the set (peak) level, dB."""
    n = int(round(rate / period_hz))
    while n < 2000:
        n *= 2
    t = np.arange(n) / rate
    x = sum(a * np.exp(1j * 2 * np.pi * o * t) for o, a in zip(offs, amps))
    pk = np.abs(x).max()
    return x / pk, [20 * math.log10(a / pk) for a in amps]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\\sathunter_lab")
    ap.add_argument("--cal", help="path_cal results.json (default: newest)")
    ap.add_argument("--out-loss", type=float, default=30.5)
    ap.add_argument("--f0", type=float, default=436e6)
    ap.add_argument("--parts", default="stab,p1db,ip3,block,harm,spur,nf")
    ap.add_argument("--stab-mins", type=float, default=10)
    ap.add_argument("--stab-every", type=float, default=10)
    ap.add_argument("--p1db-freqs", default="426,430,433,436,438,441,443")
    ap.add_argument("--ip3-spacings", default="0.02,0.1,1,4", help="MHz")
    ap.add_argument("--ip3-freqs", default="432,440", help="MHz, at 100 kHz spacing")
    ap.add_argument("--block-offsets", default="-18,-15,15,18", help="MHz")
    ap.add_argument("--name", default="lna-extra")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    cal_path = a.cal or sorted(glob.glob(os.path.join(root, "measurements", "*path-cal*", "results.json")))[-1]
    cal = json.load(open(cal_path))
    cf = np.array([p["freq_hz"] for p in cal["points"]]); cl = np.array([p["loss_db"] for p in cal["points"]])

    def in_loss(f):
        return float(np.interp(f, cf, cl)) - a.out_loss

    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cal": os.path.relpath(cal_path, root), "out_loss_db": a.out_loss,
           "f0_hz": a.f0, "note": a.note}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)

    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(0.0, host, int(port), a.vsg_dir, None)
    bb = BB60()
    parts = a.parts.split(",")

    def ref_for(pout_dut):
        return max(-50.0, min(10.0, pout_dut - a.out_loss + 8))

    def gain_at(f, pin, span=50e3, rbw=1e3, expect=None):
        """CW gain; re-measured (up to 3x) when it is > 3 dB off `expect`."""
        for k in range(3):
            gen.cw(f, pin + in_loss(f))
            time.sleep(0.15 + 0.35 * k)
            p, _ = bb.peak(f, span=span, rbw=rbw, ref_dbm=ref_for(pin + 51))
            g = p + a.out_loss - pin
            if expect is None or abs(g - expect) <= 3:
                return g, k
        return g, k

    try:
        wait_idle()
        gen.off()
        if "stab" in parts:
            res["stab"] = []
            t0 = time.time()
            pin = -60.0
            while time.time() - t0 < a.stab_mins * 60:
                gen.cw(a.f0, pin + in_loss(a.f0))
                time.sleep(0.2)
                vals = []
                for _ in range(5):
                    p, _ = bb.peak(a.f0, span=50e3, rbw=1e3, ref_dbm=ref_for(pin + 51))
                    vals.append(p + a.out_loss - pin)
                res["stab"].append({"t": time.time() - t0, "gains_db": vals})
                print(f"stab {time.time() - t0:5.0f} s: {min(vals):.2f}..{max(vals):.2f} dB", flush=True)
                save()
                time.sleep(max(0.0, a.stab_every - 1.5))
            g = np.array([v for r in res["stab"] for v in r["gains_db"]])
            res["stab_summary"] = {"min": float(g.min()), "max": float(g.max()), "std": float(g.std()),
                                   "glitches": int(np.sum(np.abs(g - np.median(g)) > 3))}
            gen.off()
        if "p1db" in parts:
            res["p1db_multi"] = {}
            for fm in (float(x) for x in a.p1db_freqs.split(",")):
                f = fm * 1e6
                rows, prev, retries = [], None, 0
                for pin in np.arange(-55.0, -10.0, 1.0):
                    if pin + in_loss(f) > VSG_MAX:
                        break
                    g, k = gain_at(f, float(pin), expect=prev)
                    retries += k
                    rows.append({"pin_dbm": float(pin), "gain_db": g, "pout_dbm": float(pin) + g, "retries": k})
                    prev = g
                g0 = float(np.median([r["gain_db"] for r in rows[:10]]))
                comp = [r for r in rows if r["gain_db"] <= g0 - 1]
                res["p1db_multi"][f"{fm:g}"] = {"rows": rows, "small_signal_gain_db": g0, "retries": retries,
                                                "ip1db_dbm": comp[0]["pin_dbm"] if comp else None,
                                                "op1db_dbm": comp[0]["pout_dbm"] if comp else None,
                                                "max_in_dbm": rows[-1]["pin_dbm"], "max_compression_db": g0 - min(r["gain_db"] for r in rows)}
                s = res["p1db_multi"][f"{fm:g}"]
                print(f"P1dB {fm:g} MHz: G {g0:.1f} dB, IP1dB {s['ip1db_dbm']}, OP1dB {s['op1db_dbm']}, retries {retries}", flush=True)
                save()
            gen.off()
        if "ip3" in parts:
            res["ip3_multi"] = []
            cases = [(a.f0, float(x) * 1e6) for x in a.ip3_spacings.split(",")] + [(float(x) * 1e6, 100e3) for x in a.ip3_freqs.split(",")]
            for fc, df in cases:
                rate = min(40e6, max(1e6, 10 * df))
                x, lv = tones(rate, [-df / 2, df / 2], [1, 1], df / 2)  # period of the pair: 2/df
                name = f"sathunter_2t_{int(df)}.cf32"
                f1, f2, i1, i2 = fc - df / 2, fc + df / 2, fc - 1.5 * df, fc + 1.5 * df
                rbw = min(1e3, df / 20)
                span = min(200e3, df / 2)
                rows = []
                for pin in np.arange(-50.0, -27.9, 2.0):
                    vsg = pin - lv[0] + in_loss(fc)
                    if vsg > VSG_MAX:
                        break
                    gen.play(fc, vsg, name, list(x), rate)
                    time.sleep(0.2)
                    ref = ref_for(pin + 51)
                    p1 = bb.peak(f1, span, rbw, ref)[0]; p2 = bb.peak(f2, span, rbw, ref)[0]
                    q1 = bb.peak(i1, span, rbw, ref)[0]; q2 = bb.peak(i2, span, rbw, ref)[0]
                    po = (p1 + p2) / 2 + a.out_loss
                    pim = max(q1, q2) + a.out_loss
                    oip3 = po + (po - pim) / 2
                    rows.append({"pin_per_tone_dbm": float(pin), "pout_per_tone_dbm": po, "im3_low_dbm": q1 + a.out_loss,
                                 "im3_high_dbm": q2 + a.out_loss, "oip3_dbm": oip3, "iip3_dbm": oip3 - (po - pin)})
                gen.loaded = None
                good = [r for r in rows if r["pout_per_tone_dbm"] - max(r["im3_low_dbm"], r["im3_high_dbm"]) < 80]
                iip3 = float(np.median([r["iip3_dbm"] for r in good])) if good else None
                res["ip3_multi"].append({"fc_hz": fc, "spacing_hz": df, "rows": rows, "iip3_dbm": iip3,
                                         "oip3_dbm": float(np.median([r["oip3_dbm"] for r in good])) if good else None})
                print(f"IIP3 at {fc / 1e6:.0f} MHz, {df / 1e3:g} kHz: {iip3}", flush=True)
                save()
            gen.off()
        if "block" in parts:
            res["block"] = []
            rel = -40.0  # wanted tone 40 dB under the blocker: one waveform per offset, swept with the VSG level
            for off_mhz in (float(x) for x in a.block_offsets.split(",")):
                off = off_mhz * 1e6
                fc = a.f0 + off / 2  # carrier half way: the LO leakage is away from both tones
                half = abs(off) / 2
                rate = half * math.floor(40e6 / half)  # whole samples per period of both tones
                x, lv = tones(rate, [-off / 2, off / 2], [10 ** (rel / 20), 1.0], half)
                gen.loaded = None
                rows = []
                for pb in np.arange(-50.0, -9.9, 2.0):
                    vsg = pb - lv[1] + in_loss(a.f0 + off)  # blocker at pb at the LNA input
                    if vsg > VSG_MAX:
                        break
                    gen.play(fc, vsg, "sathunter_block.cf32", list(x), rate)
                    time.sleep(0.2)
                    pw_in = vsg + lv[0] - in_loss(a.f0)
                    p, _ = bb.peak(a.f0, 20e3, 300, ref_for(max(pw_in + 51, pb + 20)))
                    rows.append({"blocker_dbm": float(pb), "wanted_in_dbm": pw_in, "wanted_gain_db": p + a.out_loss - pw_in})
                g0 = float(np.median([r["wanted_gain_db"] for r in rows[:4]])) if rows else None
                d1 = next((r["blocker_dbm"] for r in rows if r["wanted_gain_db"] <= g0 - 1), None) if rows else None
                res["block"].append({"offset_hz": off, "rows": rows, "gain_unblocked_db": g0, "blocker_1db_desense_dbm": d1,
                                     "max_blocker_dbm": rows[-1]["blocker_dbm"] if rows else None})
                print(f"blocker {off_mhz:+g} MHz: 1 dB desense at {d1} dBm (max tried {rows[-1]['blocker_dbm'] if rows else None})", flush=True)
                save()
            gen.loaded = None
            gen.off()
        if "harm" in parts:
            res["harm"] = []
            for pin in (-50.0, -40.0, -35.0, -30.0, -25.0, -20.0):
                if pin + in_loss(a.f0) > VSG_MAX:
                    break
                gen.cw(a.f0, pin + in_loss(a.f0))
                time.sleep(0.2)
                p1 = bb.peak(a.f0, 50e3, 1e3, ref_for(pin + 51))[0] + a.out_loss
                h = {}
                for n in (2, 3):
                    ref = ref_for(pin + 51)  # the fundamental is at the analyser input too: same ref level
                    v = bb.peak(n * a.f0, 50e3, 1e3, ref)[0] + a.out_loss
                    nz = bb.noise(n * a.f0 + 100e3, 50e3, 1e3, ref) + a.out_loss
                    h[n] = {"dbm": v, "dbc": v - p1, "floor_dbm": nz, "under_floor": v - nz < 6}
                res["harm"].append({"pin_dbm": pin, "pout_dbm": p1, "h2": h[2], "h3": h[3]})
                print(f"harm in {pin:.0f}: out {p1:.1f} dBm, H2 {h[2]['dbc']:.0f} dBc{' (floor)' if h[2]['under_floor'] else ''}, "
                      f"H3 {h[3]['dbc']:.0f} dBc{' (floor)' if h[3]['under_floor'] else ''}", flush=True)
                save()
            gen.off()
        if "spur" in parts:
            gen.off()
            time.sleep(0.5)
            res["spur"] = []
            for c in np.arange(70e6, 3000e6, 100e6):
                f, v = bb.trace(c, 100e6, 30e3, ref_dbm=-40, sweeps=2)
                fl = float(np.median(v))
                for k in np.where(v > fl + 10)[0]:
                    if v[k] == v[max(0, k - 20):k + 21].max():
                        res["spur"].append({"freq_hz": float(f[k]), "bb_dbm": float(v[k]), "floor_dbm": fl,
                                            "at_lna_out_dbm": float(v[k]) + a.out_loss, "mult_80mhz": abs(f[k] / 80e6 - round(f[k] / 80e6)) * 80e6 < 50e3})
            print(f"spur scan: {len(res['spur'])} peaks over floor + 10 dB", flush=True)
            save()
        if "nf" in parts:
            gen.off()
            time.sleep(0.5)
            g_cw = gain_at(a.f0, -60.0)[0]
            gen.off()
            time.sleep(0.5)
            rows = []
            for f in (430e6, 433e6, 436e6, 439e6, 441e6):
                n_in = bb.noise_density(f, span=1e6, rbw=10e3, ref_dbm=-60)
                rows.append({"freq_hz": f, "density_dbm_hz": n_in})
            n_out = [bb.noise_density(f, span=1e6, rbw=10e3, ref_dbm=-60) for f in (400e6, 410e6, 460e6, 470e6)]
            floor = float(10 * np.log10(np.mean([10 ** (v / 10) for v in n_out])))
            for r in rows:
                hump = r["density_dbm_hz"] - floor
                r["hump_db"] = hump
                if hump > 0.3:
                    lna_out = 10 * math.log10(10 ** (r["density_dbm_hz"] / 10) - 10 ** (floor / 10)) + a.out_loss  # at the LNA output
                    # LNA output noise = kT0 * F * G (input terminated at ~290 K) -> F = N / (kT0 G); the floor
                    # measured out of band already holds the pad's own -174 dBm/Hz
                    r["nf_db"] = lna_out - (-174.0) - g_cw
                else:
                    r["nf_db"] = None
            res["nf"] = {"gain_436_db": g_cw, "floor_dbm_hz": floor, "floor_points": n_out, "rows": rows}
            print("NF estimate:", [(r["freq_hz"] / 1e6, round(r["hump_db"], 2), r["nf_db"] and round(r["nf_db"], 2)) for r in rows], flush=True)
            save()
    finally:
        try:
            gen.off()
        except SystemExit:
            pass
        gen.close()
        bb.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
