#!/usr/bin/env python3
"""Simulated satellite pass: the phone jumps its clock to the next pass of a real satellite (Simulate),
tracks it with its TLE Doppler correction, and the VSG60 plays keyed CW on the frequency the satellite
would be heard on at that moment (transmitter frequency x (1 - range rate / c), range rate from the
phone's own orbit model, updated 4x a second). Logged: the tracking error (VSG frequency - phone VFO)
and CW decodes over the whole pass.

    python tools/lab/pass_sim.py --phone 192.168.1.11 --pin 1027 --atten 34.7 --level -130

Pick: a CW satellite in 430-440 MHz whose next pass is the highest (largest Doppler rate), or --norad.
"""

import argparse, json, os, sys, threading, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Phone, Vsg60Gen, wait_idle  # noqa: E402

C_KMS = 299_792.458


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab")
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--level", type=float, default=-130.0, help="CW level at the receiver input, dBm")
    ap.add_argument("--norad", type=int, help="satellite (default: the best CW pass in 430-440 MHz)")
    ap.add_argument("--min-el", type=float, default=5.0, help="lowest elevation to play the signal at (deg); below it the generator is off")
    ap.add_argument("--decode-every", type=float, default=30.0)
    ap.add_argument("--text", default="VVV DE HG0LAB TEST")
    ap.add_argument("--wpm", type=float, default=15)
    ap.add_argument("--name", default="pass-sim")
    a = ap.parse_args()

    phone = Phone(a.phone, a.pin)
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)

    # 1. satellite
    sl = phone.cmd(cmd="sat_list")
    rows = sl["rows"]
    if a.norad:
        sat = next(r for r in rows if r["norad"] == a.norad)
    else:
        cand = [r for r in rows if "CW" in r.get("modes", "") and 430e6 <= r.get("freq", 0) <= 440e6
                and r.get("pass") and not r["pass"].get("always") and r["pass"]["aos"] > sl["now"] + 60]
        if not cand:
            raise SystemExit("no CW satellite in 430-440 MHz with a coming pass in the phone's list")
        sat = max(cand, key=lambda r: r["pass"]["max_el"])
    print(f"satellite {sat['name']} ({sat['norad']}), {sat['freq'] / 1e6:.4f} MHz, next pass max {sat['pass']['max_el']:.0f} deg")

    phone.cmd(cmd="rate", hz=1024000.0)
    phone.cmd(cmd="decimation", factor=8)
    phone.cmd(cmd="gain", db=12.5)
    phone.cmd(cmd="sat_select", norad=sat["norad"])
    time.sleep(1.0)
    d = phone.cmd(cmd="sat_detail")
    tx = next((t for t in d["tx"] if t["uuid"] == d["selected_tx"]), d["tx"][0])
    f_tx = tx["freq"]
    phone.cmd(cmd="sat_track", on=True)
    phone.cmd(cmd="mode", mode="CW", bw=2000.0)
    phone.cmd(cmd="simulate")
    time.sleep(2.0)

    gen = Vsg60Gen(a.atten, host, int(port), a.vsg_dir, None)
    res = {"satellite": sat["name"], "norad": sat["norad"], "tx_hz": f_tx, "tx": tx, "pass": d.get("pass"), "level_dbm": a.level,
           "min_el": a.min_el, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "track": [], "decodes": []}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as f:
            json.dump(res, f, indent=1)

    on = False
    loaded = False
    last_dec = time.time()
    t0 = time.time()
    try:
        wait_idle(phone)
        while True:
            d = phone.cmd(cmd="sat_detail")
            look = d.get("look")
            if not d.get("simulated"):
                break  # the phone left the simulated pass (LOS)
            if not look:
                time.sleep(0.25)
                continue
            f_sat = f_tx * (1 - look["range_rate_kms"] / C_KMS)
            st = phone.status()
            vfo = st["vfo_hz"]
            row = {"t": time.time() - t0, "sim_now": d["now"], "el": look["el"], "az": look["az"], "range_rate_kms": look["range_rate_kms"],
                   "sat_hz": f_sat, "vfo_hz": vfo, "app_rx_hz": d.get("rx_hz"), "error_hz": f_sat - vfo, "gen_on": on}
            res["track"].append(row)
            if look["el"] >= a.min_el:
                if not loaded:
                    gen.keyed(f_sat, a.level, a.text, a.wpm)  # loads and turns on
                    loaded = on = True
                    last_dec = time.time()
                elif not on:
                    gen.write(":OUTPut:STATe ON")
                    on = True
                gen.tune(f_sat)
            elif on:
                gen.write(":OUTPut:STATe OFF")
                on = False
            if on and time.time() - last_dec >= a.decode_every:
                c = phone.cw(int(a.decode_every) - 2)
                ok = a.text.replace(" ", "") in c["text"].replace(" ", "")
                res["decodes"].append({"t": time.time() - t0, "el": look["el"], "range_rate_kms": look["range_rate_kms"], "text": c["text"],
                                       "ok": ok, "cn0_dbhz": c["cn0_dbhz"], "error_hz": row["error_hz"]})
                phone.log(f"el {look['el']:4.1f}: {'OK ' if ok else 'BAD'} \"{c['text']}\" (tracking error {row['error_hz']:+.0f} Hz)")
                last_dec = time.time()
                save()
            time.sleep(0.25)
    finally:
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
