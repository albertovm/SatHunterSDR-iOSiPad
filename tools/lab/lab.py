#!/usr/bin/env python3
"""SatHunterSDR lab measurement: a signal generator -> the phone's receiver -> results on this PC.

The phone: Settings -> Debug mode. Its lab console shows the address and the PIN.
This PC (same LAN, Python 3 only, no packages):

    python tools/lab/lab.py --phone 192.168.1.23 --pin 123456 --gen demo         # self test, no generator
    python tools/lab/lab.py --phone 192.168.1.23 --pin 123456 --gen manual \\
        --freq 437.1e6 --atten 80                                               # you set the generator
    python tools/lab/lab.py --phone 192.168.1.23 --pin 123456 --gen vsg60 --vsg 192.168.1.199:5124 \\
        --freq 437.1e6 --atten 86 --levels=-60,-80,-100,-110,-120,-125,-130      # Signal Hound VSG60 (SCPI)

Phases (the phone's console shows each): connect, setup, noise floor, frequency accuracy,
level sweep (SNR, linearity, sensitivity), CW decode vs level. The report (report.md, CSV, JSON)
goes to docs/lab/<date_time>/ so it can be committed and read by everyone (and by Claude).

--atten is the attenuation between the generator and the receiver input (cables, fixed and step
attenuators, the 3-10 dB pad on the VSG60 output), so the levels in the report are at the receiver
input. Weak-signal levels need external attenuators and good shielding: below about -80 dBm the
leakage from the VSG60's case and USB cable matters (the noise-floor phase warns when the test
frequency is not clean with the generator off). Warm the VSG60 up for ~30 minutes.
"""

import argparse, csv, json, math, os, sys, time, urllib.request, urllib.error

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


def awgn_band(rate, bw, n=1 << 15, seed=1):  # noqa: E302
    """Periodic complex Gaussian noise, flat over +-bw/2 and zero outside (built in the frequency
    domain, so it loops in the ARB without a seam). Returns (samples, peak-to-average ratio dB)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(n, 1 / rate)
    spec = (rng.standard_normal(n) + 1j * rng.standard_normal(n)) * (np.abs(f) <= bw / 2)
    x = np.fft.ifft(spec)
    x /= np.abs(x).max()
    papr = 10 * math.log10(1.0 / np.mean(np.abs(x) ** 2))
    return [complex(v) for v in x], papr


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
    """Signal Hound VSG60A through the VSG software's SCPI server (TCP, port 5124 by default),
    ARB mode with .cf32 waveforms, as in the lab's VSG60 guide (VSG60_MERESI_SEGEDLET.md):

    - VSG software: Edit > Preferences > SCPI enabled, port 5124 (restart after a change); firewall
      rule for the port; one VSG software instance; only one SCPI client at a time.
    - ARB (not Streaming), Auto Scale ON, Output Signal Average OFF: |IQ| = 1.0 is the set level.
      Sample offset 0, count = period = file length (else only the start of the file plays).
    - Heavy commands are followed by *OPC and *ESR? polling; :SYSTem:ERRor? is read until empty.
    - Bring-up: RF OFF, set up the receiver, then RF ON.
    - The .cf32 files are written by this script into --vsg-dir; the VSG software opens them by
      the path it sees (--vsg-path, default the same folder: run lab.py on the VSG PC, or share
      the folder).
    """
    name = "vsg60"
    fixed_freq = None
    can_level = True
    RATE = 100e3  # waveform sample rate (CW needs little); the VSG upsamples

    def __init__(self, atten, host, port, vsg_dir, vsg_path):
        import socket
        self.atten = atten
        self.dir = vsg_dir
        self.path = vsg_path or vsg_dir
        os.makedirs(self.dir, exist_ok=True)
        try:
            self.s = socket.create_connection((host, port), timeout=10)
        except OSError as e:
            raise SystemExit(f"VSG60: no SCPI at {host}:{port} ({e}). VSG software running, SCPI on, firewall rule, one instance?")
        self.f = self.s.makefile("rwb")
        idn = self.query("*IDN?")
        print(f"   VSG: {idn}")
        self.write(":OUTPut:STATe OFF")
        self.check()
        self.loaded = None

    # --- SCPI basics
    def write(self, c):
        self.f.write((c + "\n").encode())
        self.f.flush()

    def query(self, c):
        self.write(c)
        line = self.f.readline()
        if not line:
            raise SystemExit(f"VSG60: no answer to {c} (another SCPI client connected?)")
        return line.decode(errors="replace").strip()

    def opc(self, timeout=30):
        self.write("*OPC")
        t = time.time()
        while time.time() - t < timeout:
            try:
                if int(float(self.query("*ESR?"))) & 1:
                    return
            except ValueError:
                pass
            time.sleep(0.05)
        raise SystemExit("VSG60: *OPC timeout (a zombie VSG instance on another port?)")

    def check(self):
        errs = []
        for _ in range(20):
            e = self.query(":SYSTem:ERRor?")
            if e.startswith("0") or "No error" in e:
                break
            errs.append(e)
        if errs:
            raise SystemExit(f"VSG60 errors: {errs}")

    # --- waveforms
    def _file(self, name, env):
        local = os.path.join(self.dir, name)
        import struct
        with open(local, "wb") as f:
            f.write(b"".join(struct.pack("<ff", complex(a).real, complex(a).imag) for a in env))
        sep = "\\" if "\\" in self.path or ":" in self.path[:3] else "/"
        return self.path.rstrip("\\/") + sep + name, len(env)

    def _load(self, name, env, rate=None):
        rate = rate or self.RATE
        if self.loaded == name:
            return
        remote, n = self._file(name, env)
        self.write(":OUTPut:STATe OFF")
        self.write(":SOURce:RADio:ARB:WAVeform:UNLOAD")
        self.write(f':SOURce:RADio:ARB:WAVeform:LOAD:BINFC "{remote}"')
        self.opc(60)
        if self.query(":SOURce:RADio:ARB:WAVeform:LOAD?").strip() != "1":
            raise SystemExit(f"VSG60: could not load {remote} (is that path valid on the VSG PC? --vsg-path)")
        length = int(float(self.query(":SOURce:RADio:ARB:WAVeform:LENgth?")))
        if length != n:
            raise SystemExit(f"VSG60: {remote} has {length} samples, expected {n}")
        for c in (f":SOURce:RADio:ARB:SRATe {rate:.0f}",
                  ":SOURce:RADio:ARB:IQ:SCALe:AUTO:STATe ON",
                  ":SOURce:RADio:ARB:IQ:SCALe:AVERage:STATe OFF",
                  ":SOURce:RADio:ARB:SAMPle:OFFSet 0",
                  f":SOURce:RADio:ARB:SAMPle:COUNt {n}",
                  f":SOURce:RADio:ARB:SAMPle:PERiod {n}",
                  ":SOURce:RADio:ARB:TRIGger:TYPE CONTinuous",
                  ":SOURce:RADio:ARB:STATe ON",
                  ":OUTPut:MODulation:STATe ON"):
            self.write(c)
        self.opc()
        self.check()
        self.loaded = name

    def _play(self, hz, dbm, name, env, rate=None):
        gen = dbm + self.atten
        self._load(name, env, rate)
        self.write(f":SOURce:FREQuency {hz:.0f}")
        self.write(f":SOURce:POWer {gen:.2f}")
        self.opc()
        self.check()
        self.write(":OUTPut:STATe ON")
        time.sleep(0.05)  # level settling (5 ms after a >20 dB step), well inside the dwell

    def off(self):
        self.write(":OUTPut:STATe OFF")
        self.opc()

    def cw(self, hz, dbm):
        self._play(hz, dbm, "sathunter_cw.cf32", [1.0] * 10_000)

    def play(self, hz, dbm, name, iq, rate):
        """Any waveform; `dbm` is the set level (the waveform's peak, Auto Scale)."""
        self._play(hz, dbm, name, iq, rate)

    def tune(self, hz):
        self.write(f":SOURce:FREQuency {hz:.0f}")
        self.opc()

    def noise(self, hz, dbm_mean, bw):
        """Band-limited AWGN, flat over +-bw/2, mean power `dbm_mean` at the receiver input.
        Auto Scale maps the file's peak |IQ| to the set level, so the set level is the mean
        plus the file's peak-to-average ratio."""
        name = "sathunter_awgn_%dk.cf32" % round(bw / 1e3)
        iq, papr = awgn_band(self.RATE, bw)
        self._play(hz, dbm_mean + papr, name, iq)
        return papr

    def keyed(self, hz, dbm, text, wpm):
        name = "sathunter_key_%s_%dwpm.cf32" % ("".join(c for c in text if c.isalnum())[:16], wpm)
        self._play(hz, dbm, name, cw_keying(text, wpm, self.RATE))

    def close(self):
        try:
            self.write(":OUTPut:STATe OFF")
            self.s.close()
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
    ap.add_argument("--vsg", default="192.168.1.199:5124", help="VSG software SCPI host:port")
    ap.add_argument("--vsg-dir", default=r"C:\sathunter_lab", help="folder the script writes the .cf32 waveforms into")
    ap.add_argument("--vsg-path", help="the same folder as the VSG PC sees it (default: --vsg-dir)")
    ap.add_argument("--passes", type=int, default=2, help="level sweep passes, each in a random order")
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
    ap.add_argument("--nf-gains", default="0,7.7,12.5,19.7,25.4,29.7,37.2,42.1,49.6",
                    help="receiver gains for the gain sweep / noise figure phase (empty = skip)")
    ap.add_argument("--nf-psd", default="-165,-158",
                    help="AWGN density(s) at the receiver input, dBm/Hz (the noise-rise method)")
    ap.add_argument("--nf-bw", type=float, default=80e3, help="AWGN bandwidth, Hz")
    ap.add_argument("--nf-cw", type=float, default=-110, help="CW level for C/N0 per gain, dBm")
    ap.add_argument("--nf-decimation", type=int, default=2)
    ap.add_argument("--name", default="lab", help="short run name for the report folder")
    ap.add_argument("--note", default="", help="free text for the report (antenna, cables, attenuators...)")
    ap.add_argument("--out", help="report folder (default docs/lab/<date_time>)")
    a = ap.parse_args()

    phone = Phone(a.phone, a.pin, a.port)
    gen = {"demo": lambda: DemoGen(), "manual": lambda: ManualGen(a.atten), "vsg60": lambda: Vsg60Gen(a.atten, a.vsg.split(":")[0], int(a.vsg.split(":")[1]) if ":" in a.vsg else 5124, a.vsg_dir, a.vsg_path)}[a.gen]()
    freq = gen.fixed_freq or a.freq
    levels = [float(x) for x in a.levels.split(",") if x.strip()]
    cw_levels = [float(x) for x in a.cw_levels.split(",") if x.strip()]
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = a.out or os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    nf_gains = [float(x) for x in a.nf_gains.split(",") if x.strip()] if gen.name == "vsg60" else []
    nf_psd = [float(x) for x in a.nf_psd.split(",") if x.strip()]
    total = 7
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
            if m["peak_snr_db"] > 6:
                phone.log(f"WARNING: {m['peak_snr_db']:.1f} dB at the test frequency with the generator OFF: another signal or leakage")
        else:
            phone.log("demo: the beacon cannot be switched off, skipped")

        # 4. frequency accuracy
        ref = a.nf_cw if gen.can_level else None  # a clean, unclipped level
        phone.phase("frequency accuracy", 4, total, f"CW at {ref} dBm" if ref is not None else "demo beacon")
        gen.cw(freq, ref if ref is not None else 0)
        time.sleep(1.0)
        m = phone.measure(freq, 5000, a.secs)
        res["frequency"] = m
        phone.log(f"offset {m['offset_hz']:+.1f} Hz = {m['offset_ppm']:+.2f} ppm (phone ppm setting {st.get('ppm')})")

        # 5. gain sweep: system noise figure (AWGN noise rise) and CW C/N0 per receiver gain
        if nf_gains:
            phone.cmd(cmd="decimation", factor=a.nf_decimation)
            time.sleep(1.0)
            chbw = 0.75 * a.nf_bw  # measure inside the flat part of the noise
            rows = {g: {"gain_db": g} for g in nf_gains}

            def each_gain(tag, fn):
                for g in nf_gains:
                    phone.phase("gain sweep / NF", 5, total, f"{tag}, gain {g:.1f} dB")
                    phone.cmd(cmd="gain", db=g)
                    time.sleep(0.8)
                    fn(rows[g], phone.measure(freq, chbw, a.secs))

            gen.off()
            each_gain("generator off", lambda r, m: r.update(off_noise_dbfs=m["noise_dbfs_per_bin"], bin_hz=m["bin_hz"]))
            for psd in nf_psd:
                mean = psd + 10 * math.log10(a.nf_bw)
                papr = gen.noise(freq, mean, a.nf_bw)
                res["nf_papr_db"] = papr

                def nf_row(r, m, psd=psd):
                    rise = m["channel_snr_db"]  # (P_ch - N_ch) / N_ch = AWGN / receiver noise, in the channel
                    r[f"rise_db@{psd:.0f}"] = rise
                    r[f"nf_db@{psd:.0f}"] = psd + 174.0 - rise
                    r[f"awgn_noise_dbfs@{psd:.0f}"] = m["noise_dbfs_per_bin"]
                each_gain(f"AWGN {psd:.0f} dBm/Hz", nf_row)
            gen.cw(freq, a.nf_cw)
            each_gain(f"CW {a.nf_cw:.0f} dBm", lambda r, m: r.update(cw_peak_dbfs=m["peak_dbfs"], cw_cn0_dbhz=m["cn0_dbhz"], cw_noise_dbfs=m["noise_dbfs_per_bin"]))
            gen.off()
            gs = []
            for g in nf_gains:
                r = rows[g]
                nfs = [r[f"nf_db@{p:.0f}"] for p in nf_psd]
                r["nf_db"] = sum(nfs) / len(nfs)
                r["nf_spread_db"] = max(nfs) - min(nfs)
                gs.append(r)
                phone.log(f"gain {g:4.1f}: NF {r['nf_db']:5.2f} dB (spread {r['nf_spread_db']:.2f}), CW C/N0 {r['cw_cn0_dbhz']:5.1f} dB-Hz, peak {r['cw_peak_dbfs']:6.1f} dBFS")
            res["gain_sweep"] = gs
            best = min(r["nf_db"] for r in gs)
            # the lowest gain within 0.3 dB of the best NF: same sensitivity, most headroom
            pick = min((r for r in gs if r["nf_db"] <= best + 0.3), key=lambda r: r["gain_db"])
            res["best_gain_db"] = pick["gain_db"]
            phone.log(f"best gain {pick['gain_db']:.1f} dB, system NF {pick['nf_db']:.2f} dB")
            phone.cmd(cmd="decimation", factor=a.decimation)
            phone.cmd(cmd="gain", db=a.gain if a.gain is not None else pick["gain_db"])
            time.sleep(1.0)
        else:
            phone.phase("gain sweep / NF", 5, total, "needs the VSG60, skipped")

        # 6. level sweep
        sweep = []
        if gen.can_level:
            import random
            order = []
            for p in range(max(1, a.passes)):
                lv_p = levels[:]
                random.shuffle(lv_p)  # random order per pass: slow drift does not bend the curve
                order += [(p + 1, lv) for lv in lv_p]
            for k, (pas, lv) in enumerate(order):
                phone.phase("level sweep", 6, total, f"{lv:.0f} dBm (pass {pas}, {k + 1}/{len(order)})")
                gen.cw(freq, lv)
                time.sleep(0.8)
                m = phone.measure(freq, 2000, a.secs)
                row = {"pass": pas, "level_dbm": lv, **{k2: m.get(k2) for k2 in ("peak_dbfs", "noise_dbfs_per_bin", "peak_snr_db", "channel_snr_db", "offset_hz", "cn0_dbhz", "bin_hz")}}
                sweep.append(row)
                phone.log(f"{lv:7.1f} dBm: peak {m['peak_dbfs']:6.1f} dBFS, SNR {m['peak_snr_db']:5.1f} dB, C/N0 {m['cn0_dbhz']:5.1f} dB-Hz")
            res["sweep"] = sweep
            # mean and spread per level over the passes
            by = {}
            for r in sweep:
                by.setdefault(r["level_dbm"], []).append(r)
            res["sweep_mean"] = [{"level_dbm": lv, "passes": len(rs),
                                  **{k2: sum(r[k2] for r in rs) / len(rs) for k2 in ("peak_dbfs", "peak_snr_db", "cn0_dbhz", "offset_hz")},
                                  "snr_spread_db": max(r["peak_snr_db"] for r in rs) - min(r["peak_snr_db"] for r in rs),
                                  "bin_hz": rs[0]["bin_hz"]} for lv, rs in sorted(by.items(), reverse=True)]
            res["mds_dbm"] = mds_from_sweep(res["sweep_mean"])
        else:
            phone.phase("level sweep", 6, total, "needs a generator, skipped")

        # 7. CW decode
        decodes = []
        lvls = cw_levels if gen.can_level else [None]
        for k, lv in enumerate(lvls):
            phone.phase("CW decode", 7, total, f"{lv:.0f} dBm" if lv is not None else "demo beacon")
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
    if res.get("gain_sweep"):
        with open(os.path.join(out, "gain_sweep.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(res["gain_sweep"][0].keys()))
            w.writeheader()
            w.writerows(res["gain_sweep"])
        L += ["## Gain sweep and system noise figure", "",
              f"AWGN {a.nf_bw / 1e3:.0f} kHz wide at {', '.join(f'{p:.0f}' for p in nf_psd)} dBm/Hz at the receiver input "
              f"(file peak-to-average {res['nf_papr_db']:.2f} dB), measured in the middle {0.75 * a.nf_bw / 1e3:.0f} kHz. "
              "NF = PSD + 174 - rise, rise = AWGN / receiver noise in the channel. "
              f"CW at {a.nf_cw:.0f} dBm for C/N0.", "",
              "| Gain dB | NF dB | NF spread dB | Noise off dBFS/bin | CW C/N0 dB-Hz | CW peak dBFS |", "|---|---|---|---|---|---|"]
        L += [f"| {r['gain_db']:.1f} | {r['nf_db']:.2f} | {r['nf_spread_db']:.2f} | {r['off_noise_dbfs']:.1f} | {r['cw_cn0_dbhz']:.1f} | {r['cw_peak_dbfs']:.1f} |" for r in res["gain_sweep"]]
        L += ["", f"Chosen gain for the level sweep: {res['best_gain_db']:.1f} dB (lowest gain within 0.3 dB of the best NF).", ""]
    if res.get("sweep_mean"):
        L += ["## Level sweep", "", "| Level dBm | Passes | Peak dBFS | SNR dB | SNR spread dB | C/N0 dB-Hz | Offset Hz |", "|---|---|---|---|---|---|---|"]
        L += [f"| {r['level_dbm']:.1f} | {r['passes']} | {r['peak_dbfs']:.1f} | {r['peak_snr_db']:.1f} | {r['snr_spread_db']:.1f} | {r['cn0_dbhz']:.1f} | {r['offset_hz']:+.1f} |" for r in res["sweep_mean"]]
        mds = res.get("mds_dbm")
        L += ["", f"Sensitivity (SNR 3 dB in a {res['sweep_mean'][0]['bin_hz']:.0f} Hz bin): " + (f"{mds:.1f} dBm" if mds is not None else "not reached in the sweep"),
              "", "Levels are at the receiver input (generator level minus --atten); the VSG60's absolute level is ±2 dB.", ""]
    L += ["| CW level dBm | Decoded | OK | WPM |", "|---|---|---|---|"]
    L += [f"| {d['level_dbm'] if d['level_dbm'] is not None else 'demo'} | `{d['text']}` | {'yes' if d['ok'] else 'no'} | {d['wpm']:.1f} |" for d in res["cw"]]
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print(f"\nReport: {out}/report.md")


if __name__ == "__main__":
    main()
