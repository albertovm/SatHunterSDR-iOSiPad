#!/usr/bin/env python3
"""Fast satellite pass with the Doppler inside the waveform: an independent SGP4 (python `sgp4`, the
satellite's TLE from SatNOGS, the phone's station) gives the frequency the satellite would be heard on
during the +-W seconds around the closest point of the phone's simulated pass. Keyed CW with that
Doppler is written as one ARB file, loaded and held; when the phone's simulated clock reaches the
start of the window, the waveform is started. The VSG is never retuned (retuning interrupts its
output, see measurements/2026-11-04_1331_pass-sim-leo-lab10).

    pip install sgp4 numpy
    python tools/lab/fast_pass.py --phone 192.168.1.11 --pin 1027 --atten 34.7 --norad 33498 --level -130

Also compares the phone's range rate with the independent SGP4 (a TLE / orbit model check).
"""

import argparse, json, math, os, sys, time, urllib.request

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Phone, Vsg60Gen, cw_keying, wait_idle  # noqa: E402

C = 299_792.458  # km/s
WE = 7.2921150e-5  # rad/s


def tle_from_satnogs(norad):
    url = f"https://db.satnogs.org/api/tle/?norad_cat_id={norad}&format=json"
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SatHunterSDR-lab"}), timeout=20) as r:
        t = json.loads(r.read())[0]
    return t["tle1"], t["tle2"]


def station_ecef(lat, lon, alt_m):
    a, f = 6378.137, 1 / 298.257223563
    e2 = f * (2 - f)
    la, lo = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(la) ** 2)
    h = alt_m / 1000
    return np.array([(n + h) * math.cos(la) * math.cos(lo), (n + h) * math.cos(la) * math.sin(lo), (n * (1 - e2) + h) * math.sin(la)])


def gmst(jd_ut1):
    t = (jd_ut1 - 2451545.0) / 36525.0
    g = 67310.54841 + (876600 * 3600 + 8640184.812866) * t + 0.093104 * t * t - 6.2e-6 * t ** 3
    return math.radians((g % 86400) / 240.0)


def range_rate(sat, st_ecef, unix):
    """Range rate (km/s, + = receding) and elevation (deg) from SGP4 (TEME -> ECEF by GMST)."""
    jd = unix / 86400.0 + 2440587.5
    jd_i, jd_f = math.floor(jd), jd - math.floor(jd)
    e, r, v = sat.sgp4(jd_i, jd_f)
    if e:
        raise RuntimeError(f"sgp4 error {e}")
    th = gmst(jd)
    c, s = math.cos(th), math.sin(th)
    rot = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    r_e = rot @ np.array(r)
    v_e = rot @ np.array(v) - np.cross([0, 0, WE], r_e)
    d = r_e - st_ecef
    rng = np.linalg.norm(d)
    up = st_ecef / np.linalg.norm(st_ecef)
    el = math.degrees(math.asin(np.dot(d, up) / rng))
    return float(np.dot(d, v_e) / rng), el


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--norad", type=int, required=True)
    ap.add_argument("--level", type=float, default=-130.0)
    ap.add_argument("--window", type=float, default=60.0, help="seconds before and after the closest point")
    ap.add_argument("--rate", type=float, default=25e3, help="ARB sample rate (20 kS/s plays 16 %% slow on the VSG60; 25 and 50 kS/s are right)")
    ap.add_argument("--decode-every", type=float, default=25.0)
    ap.add_argument("--text", default="VVV DE HG0LAB TEST")
    ap.add_argument("--wpm", type=float, default=15)
    ap.add_argument("--name", default="fast-pass")
    a = ap.parse_args()
    from sgp4.api import Satrec

    phone = Phone(a.phone, a.pin)
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    res = {"norad": a.norad, "level_dbm": a.level, "window_s": a.window, "started": time.strftime("%Y-%m-%d %H:%M:%S")}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)

    # Phone setup
    for c in ({"cmd": "real_time"}, {"cmd": "rate", "hz": 1024000.0}, {"cmd": "decimation", "factor": 8}, {"cmd": "gain", "db": 12.5},
              {"cmd": "sat_select", "norad": a.norad}):
        phone.cmd(**c)
    time.sleep(1.0)
    d = phone.cmd(cmd="sat_detail")
    tx = next((t for t in d["tx"] if t["uuid"] == d["selected_tx"]), d["tx"][0])
    f_tx = tx["freq"]
    p = d["pass"]
    st = phone.status()["station"]
    res.update({"satellite": d["name"], "tx_hz": f_tx, "pass": p, "station": st})
    print(f"{d['name']}: {f_tx / 1e6:.4f} MHz, pass max {p['max_el']:.0f} deg, TCA in {(p['tmax'] - d['now']) / 60:.1f} min")

    # Independent SGP4
    l1, l2 = tle_from_satnogs(a.norad)
    sat = Satrec.twoline2rv(l1, l2)
    st_e = station_ecef(st["lat"], st["lon"], st.get("alt_m", 0.0))
    res["tle"] = [l1, l2]
    # model check now (real time, the satellite may be below the horizon: range rate is still defined)
    look = d.get("look") or {}
    rr_ind, _ = range_rate(sat, st_e, d["now"])
    res["model_check"] = {"time": d["now"], "phone_rr_kms": look.get("range_rate_kms"), "sgp4_rr_kms": rr_ind,
                          "doppler_diff_hz": (rr_ind - look.get("range_rate_kms", rr_ind)) * f_tx / C}
    print(f"range rate now: phone {look.get('range_rate_kms')}, SGP4 {rr_ind:.5f} km/s -> {res['model_check']['doppler_diff_hz']:+.1f} Hz")

    # Waveform: window around TCA (simulated time)
    t0, t1 = p["tmax"] - a.window, p["tmax"] + a.window
    n = int((t1 - t0) * a.rate)
    tt = t0 + np.arange(0, n, int(a.rate // 10)) / a.rate  # 10 Hz model grid
    f_mod = np.array([f_tx * (1 - range_rate(sat, st_e, t)[0] / C) for t in tt])
    els = [range_rate(sat, st_e, t)[1] for t in tt]
    fc = round(float(np.mean([f_mod.min(), f_mod.max()])))  # VSG centre: the middle of the sweep
    f_off = np.interp(t0 + np.arange(n) / a.rate, tt, f_mod) - fc
    ph = 2 * np.pi * np.cumsum(f_off) / a.rate
    env = np.array(cw_keying(a.text, a.wpm, a.rate), dtype=np.float32)
    env = np.tile(env, n // len(env) + 1)[:n]
    iq = (env * np.exp(1j * ph)).astype(np.complex64)
    res.update({"vsg_centre_hz": fc, "doppler_span_hz": [float(f_mod.min() - f_tx), float(f_mod.max() - f_tx)],
                "max_rate_hz_s": float(np.max(np.abs(np.diff(f_mod)) * 10)), "max_el_sgp4": float(max(els))})
    print(f"window {2 * a.window:.0f} s: Doppler {res['doppler_span_hz'][0]:+.0f}..{res['doppler_span_hz'][1]:+.0f} Hz, up to {res['max_rate_hz_s']:.0f} Hz/s")
    name = f"sathunter_fastpass_{a.norad}.cf32"
    path = os.path.join(a.vsg_dir, name)
    iq.tofile(path)
    save()

    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.atten, host, int(port), a.vsg_dir, None)
    try:
        # load and hold (ARB off, RF off)
        gen.write(":OUTPut:STATe OFF")
        gen.write(":SOURce:RADio:ARB:WAVeform:UNLOAD")
        gen.write(f':SOURce:RADio:ARB:WAVeform:LOAD:BINFC "{path}"')
        gen.opc(120)
        if gen.query(":SOURce:RADio:ARB:WAVeform:LOAD?").strip() != "1":
            raise SystemExit("VSG60: could not load the waveform")
        for c in (f":SOURce:RADio:ARB:SRATe {a.rate:.0f}", ":SOURce:RADio:ARB:IQ:SCALe:AUTO:STATe ON",
                  ":SOURce:RADio:ARB:IQ:SCALe:AVERage:STATe OFF", ":SOURce:RADio:ARB:SAMPle:OFFSet 0",
                  f":SOURce:RADio:ARB:SAMPle:COUNt {n}", f":SOURce:RADio:ARB:SAMPle:PERiod {n}",
                  ":SOURce:RADio:ARB:TRIGger:TYPE CONTinuous", f":SOURce:FREQuency {fc}", f":SOURce:POWer {a.level + a.atten:.2f}",
                  ":OUTPut:MODulation:STATe ON"):
            gen.write(c)
        gen.check()
        wait_idle(phone)
        # simulated pass, tracking on
        phone.cmd(cmd="sat_track", on=True)
        phone.cmd(cmd="mode", mode="CW", bw=2000.0)
        phone.cmd(cmd="simulate")
        time.sleep(1.0)
        d = phone.cmd(cmd="sat_detail")
        shift = d["now"] - time.time()  # phone sim clock = wall + shift
        start_wall = t0 - shift
        print(f"simulated clock running; the waveform starts in {start_wall - time.time():.0f} s")
        while time.time() < start_wall - 0.05:
            time.sleep(min(1.0, max(0.01, start_wall - time.time() - 0.05)))
        gen.write(":SOURce:RADio:ARB:STATe ON")
        gen.write(":OUTPut:STATe ON")
        t_on = time.time()
        res["start_error_s"] = t_on - start_wall
        res["track"], res["decodes"] = [], []
        last_dec = t_on
        while time.time() - t_on < 2 * a.window:
            d = phone.cmd(cmd="sat_detail")
            vfo = phone.status()["vfo_hz"]
            sim = d["now"]
            f_model = float(np.interp(sim, tt, f_mod))
            m = phone.measure(f_model, 3000, 0.4)  # where the carrier really is (keyed: the key-down peaks)
            res["track"].append({"sim_now": sim, "el": (d.get("look") or {}).get("el"), "model_hz": f_model, "vfo_hz": vfo,
                                 "phone_rx_hz": d.get("rx_hz"), "error_hz": f_model - vfo,
                                 "measured_hz": m["peak_hz"], "measured_snr_db": m["peak_snr_db"]})
            if time.time() - last_dec >= a.decode_every:
                c = phone.cw(int(a.decode_every) - 1)
                ok = a.text.replace(" ", "") in c["text"].replace(" ", "")
                el = (d.get("look") or {}).get("el")
                res["decodes"].append({"sim_now": sim, "t_from_tca": sim - p["tmax"], "el": el, "text": c["text"], "ok": ok, "cn0_dbhz": c["cn0_dbhz"]})
                phone.log(f"TCA{sim - p['tmax']:+.0f}s el {el:.0f}: {'OK ' if ok else 'BAD'} \"{c['text']}\"")
                last_dec = time.time()
                save()
            time.sleep(0.2)
    finally:
        try:
            gen.write(":OUTPut:STATe OFF")
        except Exception:
            pass
        gen.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
        try:
            phone.cmd(cmd="real_time")
        except SystemExit:
            pass
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
