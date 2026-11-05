#!/usr/bin/env python3
"""Explainer figure for a fast_pass.py run: the whole pass (sky track, Doppler, Doppler rate) from SGP4 and
the run's TLE, and the measured window (model, phone VFO, measured carrier, residual, CW decodes).

    python tools/lab/plot_pass_explainer.py measurements/2026-11-04_1447_fast-pass docs/img/pass-simulation.png
"""

import json, math, os, sys
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sgp4.api import Satrec

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fast_pass import gmst, station_ecef, WE  # noqa: E402

C = 299792.458
BLUE, ORANGE, GREEN, GREY, RED = "#2a6fdb", "#e8590c", "#2f9e44", "#868e96", "#c92a2a"


def look(sat, st, lat, lon, unix):
    jd = unix / 86400.0 + 2440587.5
    e, r, v = sat.sgp4(math.floor(jd), jd - math.floor(jd))
    th = gmst(jd)
    c, s = math.cos(th), math.sin(th)
    rot = np.array([[c, s, 0], [-s, c, 0], [0, 0, 1]])
    r_e = rot @ np.array(r)
    v_e = rot @ np.array(v) - np.cross([0, 0, WE], r_e)
    d = r_e - st
    rng = np.linalg.norm(d)
    la, lo = math.radians(lat), math.radians(lon)
    east = np.array([-math.sin(lo), math.cos(lo), 0])
    north = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    el = math.degrees(math.asin(np.dot(d, up) / rng))
    az = math.degrees(math.atan2(np.dot(d, east), np.dot(d, north))) % 360
    return az, el, rng, float(np.dot(d, v_e) / rng)


def main():
    run, out = sys.argv[1], sys.argv[2]
    d = json.load(open(os.path.join(run, "results.json"), encoding="utf-8"))
    sat = Satrec.twoline2rv(*d["tle"])
    stn = d["station"]
    st = station_ecef(stn["lat"], stn["lon"], stn["alt_m"])
    f_tx = d["tx_hz"]
    p = d["pass"]
    tca = p["tmax"]
    tt = np.arange(p["aos"], p["los"], 2.0)
    L = np.array([look(sat, st, stn["lat"], stn["lon"], t) for t in tt])
    az, el, rng, rr = L.T
    dop = -f_tx * rr / C
    rate = np.gradient(dop, tt)
    tr = d["track"]
    ts = np.array([r["sim_now"] for r in tr])
    model = np.array([r["model_hz"] for r in tr]) - f_tx
    vfo = np.array([r["vfo_hz"] for r in tr]) - f_tx
    meas = np.array([r["measured_hz"] for r in tr]) - f_tx
    key = np.array([r["measured_snr_db"] for r in tr]) >= 10  # keyed CW: key-up readings are noise
    ts_all, model_all, vfo_all = ts, model, vfo
    ts, model, vfo, meas = ts[key], model[key], vfo[key], meas[key]
    off = float(np.median(meas - vfo))
    resid = meas - vfo - off
    w0, w1 = ts_all.min(), ts_all.max()
    m = lambda t: (t - tca) / 60.0  # noqa: E731  minutes from the closest point

    fig = plt.figure(figsize=(16, 10.5))
    gs = fig.add_gridspec(3, 3, width_ratios=[1.05, 1.5, 1.5], height_ratios=[1, 1, 1.05], hspace=0.45, wspace=0.28)
    when = datetime.fromtimestamp(tca, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fig.suptitle(f"Simulated satellite pass in the lab: {d['satellite']} (NORAD {d['norad']}), {f_tx / 1e6:.3f} MHz CW beacon, "
                 f"max elevation {p['max_el']:.0f}°", fontsize=15, fontweight="bold", y=0.985)
    fig.text(0.5, 0.945, "VSG60A plays the beacon exactly as it would arrive from orbit (Doppler from SGP4 written into the waveform)  ->  "
             "Spacewalker LNA  ->  RTL-SDR V3  ->  SatHunterSDR on a phone, tracking the satellite with its own orbit model",
             ha="center", fontsize=10.5, color="#495057")

    # 1. sky track
    ax = fig.add_subplot(gs[0:2, 0], projection="polar")
    ax.set_theta_zero_location("N"); ax.set_theta_direction(-1)
    ax.plot(np.radians(az), 90 - el, color=GREY, lw=2)
    ww = (tt >= w0) & (tt <= w1)
    ax.plot(np.radians(az[ww]), 90 - el[ww], color=ORANGE, lw=5, solid_capstyle="round", label="2 min measured in the lab")
    ax.plot(np.radians(az[0]), 90 - el[0], "o", color=GREEN, ms=8); ax.text(np.radians(az[0]), 90 - el[0] + 9, "rises (AOS)", ha="center", fontsize=9)
    ax.plot(np.radians(az[-1]), 90 - el[-1], "s", color=RED, ms=7); ax.text(np.radians(az[-1]), 90 - el[-1] + 9, "sets (LOS)", ha="center", fontsize=9)
    k = int(np.argmax(el))
    ax.plot(np.radians(az[k]), 90 - el[k], "*", color=ORANGE, ms=14, mec="k")
    ax.annotate(f"closest point\n{el[k]:.0f}° elevation\n{rng[k]:.0f} km away", xy=(np.radians(az[k]), 90 - el[k]),
                xytext=(np.radians(60), 55), fontsize=9, arrowprops=dict(arrowstyle="->", color="k", lw=0.8),
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#adb5bd"))
    ax.set_rlim(0, 90); ax.set_rticks([0, 30, 60, 90]); ax.set_yticklabels(["90°", "60°", "30°", "0°"], fontsize=8)
    ax.set_xticks(np.radians([0, 90, 180, 270])); ax.set_xticklabels(["N", "E", "S", "W"])
    ax.set_title(f"Sky track over Budapest\n{(p['los'] - p['aos']) / 60:.1f} min above the horizon, {when}", fontsize=11, pad=14)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.2), fontsize=9, frameon=False)

    # 2. Doppler over the whole pass
    ax = fig.add_subplot(gs[0, 1:])
    ax.plot(m(tt), dop / 1e3, color=BLUE, lw=2)
    ax.axvspan(m(w0), m(w1), color=ORANGE, alpha=0.18, label="lab window")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_ylabel("Doppler shift, kHz"); ax.set_xlabel("minutes from the closest point")
    ax.set_title(f"Doppler: the signal arrives {dop.max() / 1e3:+.1f} kHz high when the satellite approaches, "
                 f"{dop.min() / 1e3:+.1f} kHz low when it leaves", fontsize=11)
    ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper right")
    ax.set_xlim(m(tt[0]), m(tt[-1]))

    # 3. Doppler rate
    ax = fig.add_subplot(gs[1, 1:])
    ax.plot(m(tt), rate, color=BLUE, lw=2)
    ax.axvspan(m(w0), m(w1), color=ORANGE, alpha=0.18)
    ax.set_ylabel("Doppler rate, Hz/s"); ax.set_xlabel("minutes from the closest point")
    ax.set_title(f"How fast the frequency moves: up to {abs(rate).max():.0f} Hz every second at the closest point "
                 f"(a 2 kHz CW filter is crossed in {2000 / abs(rate).max():.0f} s)", fontsize=11)
    ax.grid(alpha=0.3); ax.set_xlim(m(tt[0]), m(tt[-1]))

    # 4. the measured window
    ax = fig.add_subplot(gs[2, 0:2])
    ax.plot(ts_all - tca, model_all / 1e3, color=BLUE, lw=6, alpha=0.35, label="where the satellite is (independent SGP4)")
    ax.plot(ts_all - tca, vfo_all / 1e3, color=ORANGE, lw=1.8, label="where SatHunterSDR tunes (its own orbit model)")
    ax.plot(ts - tca, (meas - off) / 1e3, ".", color="k", ms=3, label=f"carrier the phone measured, key down ({off:+.0f} Hz reference offset removed)")
    for dc in d["decodes"]:
        ax.axvline(dc["t_from_tca"], color=GREEN, lw=1, ls="--")
    ax.set_xlabel("seconds from the closest point"); ax.set_ylabel("offset from 435.245 MHz, kHz")
    ax.set_title("The 2 minutes around the closest point: the receiver follows the satellite", fontsize=11)
    ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper right")

    # 5. residual
    ax = fig.add_subplot(gs[2, 2])
    sd = float(resid.std())
    ax.axhspan(-sd, sd, color=GREEN, alpha=0.15, label=f"±1σ = ±{sd:.0f} Hz")
    ax.plot(ts - tca, resid, ".", color="k", ms=3)
    ax.axhspan(-1000, -1000, color="none")
    ax.set_ylim(-60, 60)
    ax.set_xlabel("seconds from the closest point"); ax.set_ylabel("tracking error, Hz")
    ax.set_title("Tracking error (measured − tuned)", fontsize=11)
    ax.grid(alpha=0.3); ax.legend(fontsize=9, loc="upper right")
    ok = sum(1 for dc in d["decodes"] if "HG0LAB TEST" in dc["text"])
    cn0 = np.mean([dc["cn0_dbhz"] for dc in d["decodes"]])
    box = (f"Signal at the receiver: {d['level_dbm']:.0f} dBm  (C/N0 {cn0:.0f} dB-Hz)\n"
           f"CW 15 WPM \"VVV DE HG0LAB TEST\": decoded in {ok} of {len(d['decodes'])} windows (green lines)\n"
           f"Orbit model vs independent SGP4: {d['model_check']['doppler_diff_hz']:.2f} Hz apart\n"
           f"Tracking error {sd:.0f} Hz (1σ) at {d['max_rate_hz_s']:.0f} Hz/s Doppler rate")
    fig.text(0.05, 0.012, box.replace("\n", "     |     ", 1).replace("\n", "\n", 1), fontsize=10, va="bottom", ha="left",
             bbox=dict(boxstyle="round,pad=0.5", fc="#f1f3f5", ec="#adb5bd"))
    fig.subplots_adjust(bottom=0.14, top=0.91, left=0.05, right=0.98)
    fig.savefig(out, dpi=120)
    print(out, "sd", sd, "off", off)


if __name__ == "__main__":
    main()
