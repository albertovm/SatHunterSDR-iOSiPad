#!/usr/bin/env python3
"""SatHunterSDR lab measurement: a signal generator -> the phone's receiver -> results on this PC.

The phone: Settings -> Debug mode. Its lab console shows the address and the PIN.
This PC (same LAN, Python 3 only, no packages):

    python tools/lab/lab.py --phone 192.168.1.23 --pin 123456 --gen demo         # self test, no generator
    python tools/lab/lab.py --phone 192.168.1.23 --pin 123456 --gen manual \\
        --freq 437.1e6 --atten 80                                               # you set the generator
    python tools/lab/lab.py --phone 192.168.1.23 --pin 123456 --gen vsg60 \\
        --freq 437.1e6 --atten 80 --levels -40,-50,-60,-70,-80                   # Signal Hound VSG60

Phases (the phone's console shows each): connect, setup, noise floor, frequency accuracy,
level sweep (SNR, linearity, sensitivity), CW decode vs level. The report (report.md, CSV, JSON)
goes to docs/lab/<date_time>/ so it can be committed and read by everyone (and by Claude).

--atten is the attenuation between the generator and the receiver input (cables, fixed and step
attenuators), so the levels in the report are at the receiver input. The VSG60's own output
range is limited (around -40 dBm at the bottom; check its data sheet): weak-signal levels need
external attenuators and good shielding, otherwise leakage around the attenuators dominates.
"""

import argparse, csv, ctypes, json, math, os, sys, time, urllib.request, urllib.error

# ---------------------------------------------------------------------------------------------
# Phone


class Phone:
    def __init__(self, ip, pin, port=8765):
        self.base = f"http://{ip}:{port}"
        self.pin = pin

    def _req(self, method, path, body=None, timeout=60):
        url = f"{self.base}{path}{'&' if '?' in path else '?'}pin={self.pin}"
        data = json.dumps(body).encode() if body is not None else None
        rq = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(rq, timeout=timeout) as r:
                raw = r.read()
                return raw if r.headers.get("Content-Type", "").startswith("audio/") else json.loads(raw)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            raise SystemExit(f"phone: {method} {path}: HTTP {e.code} {msg}")
        except urllib.error.URLError as e:
            raise SystemExit(f"phone not reachable at {self.base}: {e.reason}\n"
                             "Same Wi-Fi / LAN? Debug mode on? Address and PIN as on the phone's lab console?")

    def status(self):
        return self._req("GET", "/status")

    def cmd(self, **c):
        r = self._req("POST", "/cmd", c)
        if not r.get("ok"):
            raise SystemExit(f"phone refused {c}: {r.get('error')}")
        return r

    def measure(self, hz, bw=2000, secs=3):
        return self._req("GET", f"/measure?hz={hz:.0f}&bw={bw:.0f}&secs={secs}")

    def cw(self, secs):
        return self._req("GET", f"/cw?secs={secs}")

    def iq(self, secs):
        return self._req("GET", f"/iq?secs={secs}", timeout=secs + 30)

    def phase(self, name, step, total, detail=""):
        print(f"\n== [{step}/{total}] {name} {detail}")
        self._req("POST", "/phase", {"phase": name, "step": step, "total": total, "detail": detail})

    def log(self, line):
        print("   " + line)
        self._req("POST", "/log", {"line": line})


# ---------------------------------------------------------------------------------------------
# Generators


def cw_keying(text, wpm, rate):
    """On/off envelope of a Morse message (1.0 = key down), `rate` samples per second."""
    codes = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..",
             "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
             "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
             "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....",
             "7": "--...", "8": "---..", "9": "----.", "/": "-..-."}
    units = []
    for wi, word in enumerate(text.upper().split()):
        if wi:
            units += [0] * 7
        for ci, ch in enumerate(word):
            if ci:
                units += [0] * 3
            for ei, e in enumerate(codes.get(ch, "")):
                if ei:
                    units += [0]
                units += [1] * (1 if e == "." else 3)
    units += [0] * 14  # a pause before the message repeats
    spu = int(rate * 1.2 / wpm)
    env = []
    for u in units:
        env += [float(u)] * spu
    # soft edges (5 ms), no key clicks
    n = max(1, int(0.005 * rate))
    out = env[:]
    for k in range(1, len(env)):
        if env[k] != env[k - 1]:
            for j in range(n):
                a = j / n
                idx = k + j if env[k] else k - n + j
                if 0 <= idx < len(out):
                    out[idx] = a if env[k] else 1 - a
    return out


class DemoGen:
    """No generator: the phone's demo source has a CW beacon on 432.400 MHz (self test of the chain)."""
    name = "demo"
    fixed_freq = 432.4e6
    can_level = False

    def off(self): pass
    def cw(self, hz, dbm): pass
    def keyed(self, hz, dbm, text, wpm): pass
    def close(self): pass


class ManualGen:
    """You set the generator by hand; the script tells you what and waits."""
    name = "manual"
    fixed_freq = None
    can_level = True

    def __init__(self, atten):
        self.atten = atten

    def _ask(self, what):
        input(f"\n   >>> {what}  -- then press Enter ")

    def off(self):
        self._ask("Generator RF OFF")

    def cw(self, hz, dbm):
        self._ask(f"CW carrier {hz / 1e6:.6f} MHz, level {dbm + self.atten:.1f} dBm at the generator ({dbm:.1f} dBm at the receiver)")

    def keyed(self, hz, dbm, text, wpm):
        self._ask(f"Keyed CW '{text}' at {wpm} WPM, {hz / 1e6:.6f} MHz, {dbm + self.atten:.1f} dBm at the generator")

    def close(self): pass


class Vsg60Gen:
    """Signal Hound VSG60 through its C API (vsg_api.dll / libvsg_api.so from the Signal Hound SDK).

    The calls follow the VSG API (vsgOpenDevice, vsgSetFrequency, vsgSetLevel, vsgSetSampleRate,
    vsgRepeatWaveform, vsgAbort, vsgCloseDevice). If your SDK version names them differently,
    adjust them here: everything else in the script stays the same.
    """
    name = "vsg60"
    fixed_freq = None
    can_level = True
    RATE = 100e3  # waveform sample rate

    def __init__(self, atten, lib=None):
        self.atten = atten
        names = [lib] if lib else ["vsg_api.dll", "libvsg_api.so", "./vsg_api.dll"]
        last = None
        for n in names:
            try:
                self.dll = ctypes.CDLL(n)
                break
            except OSError as e:
                last = e
        else:
            raise SystemExit(f"VSG60 API library not found ({last}); copy vsg_api.dll next to lab.py or pass --vsg-lib")
        self.h = ctypes.c_int(-1)
        self._ok(self.dll.vsgOpenDevice(ctypes.byref(self.h)), "vsgOpenDevice")
        self._ok(self.dll.vsgSetSampleRate(self.h, ctypes.c_double(self.RATE)), "vsgSetSampleRate")

    def _ok(self, status, what):
        if status < 0:
            raise SystemExit(f"VSG60: {what} failed (status {status})")

    def _play(self, hz, dbm, env):
        gen_dbm = dbm + self.atten
        self._ok(self.dll.vsgAbort(self.h), "vsgAbort")
        self._ok(self.dll.vsgSetFrequency(self.h, ctypes.c_double(hz)), "vsgSetFrequency")
        self._ok(self.dll.vsgSetLevel(self.h, ctypes.c_double(gen_dbm)), f"vsgSetLevel {gen_dbm:.1f} dBm (out of range? change --atten)")
        iq = (ctypes.c_float * (2 * len(env)))()
        for k, a in enumerate(env):
            iq[2 * k] = a
            iq[2 * k + 1] = 0.0
        self._ok(self.dll.vsgRepeatWaveform(self.h, iq, len(env)), "vsgRepeatWaveform")

    def off(self):
        self.dll.vsgAbort(self.h)

    def cw(self, hz, dbm):
        self._play(hz, dbm, [1.0] * 10_000)

    def keyed(self, hz, dbm, text, wpm):
        self._play(hz, dbm, cw_keying(text, wpm, self.RATE))

    def close(self):
        try:
            self.dll.vsgAbort(self.h)
            self.dll.vsgCloseDevice(self.h)
        except Exception:
            pass


# ---------------------------------------------------------------------------------------------
# Measurement


def mds_from_sweep(rows, key="peak_snr_db", at=3.0):
    """Level where the SNR crosses `at` dB (linear interpolation between sweep points)."""
    pts = sorted((r["level_dbm"], r[key]) for r in rows if r.get(key) is not None)
    for (l0, s0), (l1, s1) in zip(pts, pts[1:]):
        if (s0 - at) * (s1 - at) <= 0 and s1 != s0:
            return l0 + (at - s0) * (l1 - l0) / (s1 - s0)
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True, help="the phone's LAN address (lab console)")
    ap.add_argument("--pin", required=True, help="the PIN on the lab console")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--gen", choices=["demo", "manual", "vsg60"], default="demo")
    ap.add_argument("--vsg-lib", help="path of vsg_api.dll / libvsg_api.so")
    ap.add_argument("--freq", type=float, default=437.1e6, help="test frequency, Hz")
    ap.add_argument("--atten", type=float, default=0.0, help="dB between the generator and the receiver input")
    ap.add_argument("--levels", default="-60,-70,-80,-90,-100,-110,-115,-120,-125,-130",
                    help="receiver input levels for the sweep, dBm")
    ap.add_argument("--cw-levels", default="-100,-110,-120,-125", help="levels for the CW decode test, dBm")
    ap.add_argument("--wpm", type=float, default=15)
    ap.add_argument("--text", default="VVV DE HG0LAB TEST")
    ap.add_argument("--gain", type=float, help="receiver gain dB (default: leave as set on the phone)")
    ap.add_argument("--decimation", type=int, default=8)
    ap.add_argument("--secs", type=float, default=3.0, help="averaging per measurement")
    ap.add_argument("--note", default="", help="free text for the report (antenna, cables, attenuators...)")
    ap.add_argument("--out", help="report folder (default docs/lab/<date_time>)")
    a = ap.parse_args()

    phone = Phone(a.phone, a.pin, a.port)
    gen = {"demo": lambda: DemoGen(), "manual": lambda: ManualGen(a.atten), "vsg60": lambda: Vsg60Gen(a.atten, a.vsg_lib)}[a.gen]()
    freq = gen.fixed_freq or a.freq
    levels = [float(x) for x in a.levels.split(",") if x.strip()]
    cw_levels = [float(x) for x in a.cw_levels.split(",") if x.strip()]
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = a.out or os.path.join(root, "docs", "lab", time.strftime("%Y-%m-%d_%H%M"))
    os.makedirs(out, exist_ok=True)
    total = 6
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "generator": gen.name, "freq_hz": freq, "atten_db": a.atten, "note": a.note}

    try:
        # 1. connect
        phone.phase("connect", 1, total, a.phone)
        st = phone.status()
        res["phone"] = {k: st.get(k) for k in ("source", "source_status", "rate", "gain", "ppm", "bias_tee", "decimation", "bins")}
        phone.log(f"connected: {st.get('source_name')} · {st.get('source_status')}")

        # 2. setup
        phone.phase("setup", 2, total, f"{freq / 1e6:.4f} MHz, /{a.decimation}, CW")
        if gen.name == "demo":
            phone.cmd(cmd="source", id="demo")
        elif st.get("source") != "rtl":
            phone.log("warning: the phone's source is not the RTL-SDR")
        if not st.get("running"):
            phone.cmd(cmd="start")
        phone.cmd(cmd="decimation", factor=a.decimation)
        phone.cmd(cmd="mode", mode="CW")
        if a.gain is not None:
            phone.cmd(cmd="gain", db=a.gain)
        phone.cmd(cmd="tune", hz=freq)
        time.sleep(1.5)

        # 3. noise floor
        phone.phase("noise floor", 3, total, "generator off")
        gen.off()
        if gen.name != "demo":
            m = phone.measure(freq, 2000, a.secs)
            res["noise"] = m
            phone.log(f"noise {m['noise_dbfs_per_bin']:.1f} dBFS per {m['bin_hz']:.0f} Hz bin")
        else:
            phone.log("demo: the beacon cannot be switched off, skipped")

        # 4. frequency accuracy
        ref = levels[0] if gen.can_level else None
        phone.phase("frequency accuracy", 4, total, f"CW at {ref} dBm" if ref is not None else "demo beacon")
        gen.cw(freq, ref if ref is not None else 0)
        time.sleep(1.0)
        m = phone.measure(freq, 5000, a.secs)
        res["frequency"] = m
        phone.log(f"offset {m['offset_hz']:+.1f} Hz = {m['offset_ppm']:+.2f} ppm (phone ppm setting {st.get('ppm')})")

        # 5. level sweep
        sweep = []
        if gen.can_level:
            for k, lv in enumerate(levels):
                phone.phase("level sweep", 5, total, f"{lv:.0f} dBm ({k + 1}/{len(levels)})")
                gen.cw(freq, lv)
                time.sleep(0.8)
                m = phone.measure(freq, 2000, a.secs)
                row = {"level_dbm": lv, **{k2: m.get(k2) for k2 in ("peak_dbfs", "noise_dbfs_per_bin", "peak_snr_db", "channel_snr_db", "offset_hz", "cn0_dbhz", "bin_hz")}}
                sweep.append(row)
                phone.log(f"{lv:7.1f} dBm: peak {m['peak_dbfs']:6.1f} dBFS, SNR {m['peak_snr_db']:5.1f} dB, C/N0 {m['cn0_dbhz']:5.1f} dB-Hz")
            res["sweep"] = sweep
            res["mds_dbm"] = mds_from_sweep(sweep)
        else:
            phone.phase("level sweep", 5, total, "needs a generator, skipped")

        # 6. CW decode
        decodes = []
        lvls = cw_levels if gen.can_level else [None]
        for k, lv in enumerate(lvls):
            phone.phase("CW decode", 6, total, f"{lv:.0f} dBm" if lv is not None else "demo beacon")
            gen.keyed(freq, lv if lv is not None else 0, a.text, a.wpm)
            msg_secs = len(cw_keying(a.text, a.wpm, 100)) / 100
            time.sleep(max(8.0, 2.2 * msg_secs))
            c = phone.cw(max(8, int(2.2 * msg_secs)))
            expected = a.text if gen.name != "demo" else "DE HG0DEMO"
            ok = expected.replace(" ", "") in c["text"].replace(" ", "")
            decodes.append({"level_dbm": lv, "text": c["text"], "ok": ok, "wpm": c["wpm"], "cn0_dbhz": c["cn0_dbhz"]})
            phone.log(f"{'OK ' if ok else 'BAD'} \"{c['text']}\" {c['wpm']:.1f} WPM")
        res["cw"] = decodes
        gen.off()
        phone.phase("done", total, total, f"report: {os.path.relpath(out, root)}")
    finally:
        gen.close()

    # Report
    res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(out, "results.json"), "w") as f:
        json.dump(res, f, indent=1)
    if res.get("sweep"):
        with open(os.path.join(out, "sweep.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(res["sweep"][0].keys()))
            w.writeheader()
            w.writerows(res["sweep"])
    L = [f"# Lab measurement {res['started']}", "",
         f"Generator: {gen.name}, {freq / 1e6:.6f} MHz, attenuation {a.atten:.1f} dB. {a.note}", "",
         f"Phone: {res['phone']}", ""]
    if res.get("noise"):
        L += [f"Noise floor: {res['noise']['noise_dbfs_per_bin']:.1f} dBFS per {res['noise']['bin_hz']:.0f} Hz bin", ""]
    fr = res["frequency"]
    L += [f"Frequency: offset {fr['offset_hz']:+.1f} Hz ({fr['offset_ppm']:+.2f} ppm) at {fr['peak_snr_db']:.1f} dB SNR", ""]
    if res.get("sweep"):
        L += ["| Level dBm | Peak dBFS | SNR dB | C/N0 dB-Hz | Offset Hz |", "|---|---|---|---|---|"]
        L += [f"| {r['level_dbm']:.1f} | {r['peak_dbfs']:.1f} | {r['peak_snr_db']:.1f} | {r['cn0_dbhz']:.1f} | {r['offset_hz']:+.1f} |" for r in res["sweep"]]
        mds = res.get("mds_dbm")
        L += ["", f"Sensitivity (SNR 3 dB in a {res['sweep'][0]['bin_hz']:.0f} Hz bin): " + (f"{mds:.1f} dBm" if mds is not None else "not reached in the sweep"), ""]
    L += ["| CW level dBm | Decoded | OK | WPM |", "|---|---|---|---|"]
    L += [f"| {d['level_dbm'] if d['level_dbm'] is not None else 'demo'} | `{d['text']}` | {'yes' if d['ok'] else 'no'} | {d['wpm']:.1f} |" for d in res["cw"]]
    with open(os.path.join(out, "report.md"), "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"\nReport: {out}/report.md")


if __name__ == "__main__":
    main()
