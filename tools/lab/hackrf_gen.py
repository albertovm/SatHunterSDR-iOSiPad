"""HackRF One as the lab generator (same interface as lab.Vsg60Gen: cw, play, keyed, noise, tune, off).

Runs on the PC the HackRF is plugged into (hackrf_transfer from radioconda / PothosSDR on the PATH).
Every waveform is resampled to `RATE` (2 MS/s), shifted by `OFFSET` (+250 kHz: the HackRF's LO
leakage and DC stay out of the receiver's channel), scaled, written once as signed 8-bit IQ
(cached) and looped with `hackrf_transfer -R`.

Level: the HackRF is not calibrated. Its output at full digital scale is modelled as
P0(f) + txvga (+ amp_db with the amplifier), P0 from a calibration file (hackrf_cal.json, made
against the BB60C, see hackrf_cal.py) or the nominal -48 dBm. The set level is reached with txvga
(0-47 dB, 1 dB steps) and the rest with the digital scale (0 ... -24 dB; below that the 8-bit DAC's
own noise and spurs grow). Every play logs the exact settings (`self.last`), so levels measured
uncalibrated can be corrected afterwards with a later calibration of the same HackRF and the same
attenuators.
"""
import json
import math
import os
import subprocess
import time

import numpy as np

from lab import awgn_band, cw_keying


class HackRfGen:
    name = "hackrf"
    fixed_freq = None
    can_level = True
    RATE = 2_000_000
    OFFSET = 250e3
    P0_NOMINAL = -48.0  # dBm at full scale, txvga 0, amp off (typical HackRF One, 100-500 MHz)
    AMP_DB = 11.0
    MAX_DIGITAL_DB = 24.0

    def __init__(self, atten, cache=None, cal=None, serial=None, exe="hackrf_transfer"):
        self.atten = atten
        self.dir = cache or os.path.join(os.path.expanduser("~"), "sathunter_hackrf")
        os.makedirs(self.dir, exist_ok=True)
        self.exe = exe
        self.serial = serial
        self.cal = {}
        cal = cal or os.path.join(os.path.dirname(__file__), "hackrf_cal.json")
        if cal != "-" and os.path.exists(cal):
            self.cal = json.load(open(cal))
            print(f"   HackRF: calibration {cal} ({len(self.cal.get('p0', {}))} points)")
        else:
            print(f"   HackRF: no calibration, nominal P0 {self.P0_NOMINAL} dBm (levels are approximate)")
        self.proc = None
        self.current = None  # (file, hz, txvga, amp)
        self.last = {}
        r = subprocess.run([self.exe, "-h"], capture_output=True, text=True)
        if "hackrf_transfer" not in (r.stdout + r.stderr):
            raise SystemExit(f"HackRF: {self.exe} not found (radioconda / PothosSDR on the PATH?)")

    # ---- level model
    def p0(self, hz, amp):
        pts = self.cal.get("p0_amp" if amp else "p0", {})
        if pts:
            fs = sorted(float(f) for f in pts)
            v = [pts[k] for k in sorted(pts, key=float)]
            return float(np.interp(hz, fs, v))
        return self.P0_NOMINAL + (self.AMP_DB if amp else 0.0)

    def settings(self, hz, dbm):
        """(txvga, amp, digital dB) for `dbm` at the receiver (after `atten`)."""
        want = dbm + self.atten
        for amp in (False, True):
            p0 = self.p0(hz, amp)
            tx = int(math.ceil(want - p0))
            if tx > 47:
                continue
            tx = max(0, tx)
            dig = want - (p0 + tx)  # <= 0
            if dig < -self.MAX_DIGITAL_DB:
                raise SystemExit(f"HackRF: {dbm:.1f} dBm needs {-dig:.0f} dB digital attenuation, more than "
                                 f"{self.MAX_DIGITAL_DB:.0f}: add about {-dig - 10:.0f} dB of attenuators (--atten)")
            return tx, amp, dig
        raise SystemExit(f"HackRF: {dbm:.1f} dBm + {self.atten} dB attenuation is above the HackRF's output")

    # ---- waveforms
    def _file(self, name, iq, rate, dig):
        key = "%s_%d_%+.1f.iq8" % (os.path.splitext(name)[0], int(rate), dig)
        path = os.path.join(self.dir, key)
        if os.path.exists(path):
            return path
        # Linear interpolation to RATE, in blocks (a 127 s SSTV picture is 254 M samples at 2 MS/s).
        # Its images sit at multiples of the waveform rate (25 kHz and up for SSTV), outside the
        # receiver channel and 30+ dB down; waveforms at 100 kS/s and more put them further out.
        x = np.asarray(iq, dtype=np.complex64)
        m = len(x)
        n = int(round(m * self.RATE / rate))
        cyc = round(self.OFFSET * n / self.RATE)  # whole offset cycles over the loop: no phase step
        peak = float(np.abs(x).max()) or 1.0
        k = 127 * 10 ** (dig / 20) / peak
        xe = np.append(x, x[0])  # periodic
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            for s0 in range(0, n, 1 << 22):
                j = np.arange(s0, min(n, s0 + (1 << 22)), dtype=np.float64)
                t = j * m / n
                i0 = t.astype(np.int64)
                fr = (t - i0).astype(np.float32)
                y = (xe[i0] * (1 - fr) + xe[i0 + 1] * fr) * np.exp(2j * np.pi * ((cyc * j) % n) / n) * k
                out = np.empty(2 * len(j), dtype=np.int8)
                out[0::2] = np.clip(np.round(y.real), -127, 127)
                out[1::2] = np.clip(np.round(y.imag), -127, 127)
                out.tofile(f)
        os.replace(tmp, path)
        return path

    def _run(self, path, hz, tx, amp):
        self.off()
        lo = hz - self.OFFSET  # the signal sits OFFSET above the LO
        ppm = self.cal.get("ppm") or 0.0
        lo = lo / (1 + ppm * 1e-6)  # the HackRF's reference error, from the calibration
        cmd = [self.exe, "-t", path, "-f", "%d" % round(lo), "-s", "%d" % self.RATE, "-x", str(tx), "-a", "1" if amp else "0", "-R"]
        if self.serial:
            cmd += ["-d", self.serial]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        time.sleep(0.6)  # USB start, PLL lock
        if self.proc.poll() is not None:
            err = self.proc.stderr.read().decode(errors="replace")
            raise SystemExit(f"HackRF: hackrf_transfer stopped: {err.strip()[-300:]}")
        self.current = (path, hz, tx, amp)

    def _play(self, hz, dbm, name, iq, rate):
        tx, amp, dig = self.settings(hz, dbm)
        path = self._file(name, iq, rate, round(dig * 2) / 2)
        self._run(path, hz, tx, amp)
        self.last = {"hz": hz, "dbm": dbm, "txvga": tx, "amp": amp, "digital_db": round(dig * 2) / 2,
                     "p0": self.p0(hz, amp), "atten": self.atten, "file": os.path.basename(path)}
        return self.last

    # ---- the generator interface
    def off(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def cw(self, hz, dbm):
        return self._play(hz, dbm, "sathunter_cw", np.ones(20_000, dtype=np.complex64), 100e3)

    def play(self, hz, dbm, name, iq, rate):
        """Any waveform; `dbm` is the waveform's peak level (as Auto Scale on the VSG60)."""
        return self._play(hz, dbm, name, iq, rate)

    def tune(self, hz):
        """Retune: hackrf_transfer has to restart (about 0.6 s without signal)."""
        if self.current:
            path, _, tx, amp = self.current
            self._run(path, hz, tx, amp)

    def noise(self, hz, dbm_mean, bw):
        iq, papr = awgn_band(100e3, bw)
        self._play(hz, dbm_mean + papr, "sathunter_awgn_%dk" % round(bw / 1e3), iq, 100e3)
        return papr

    def keyed(self, hz, dbm, text, wpm):
        name = "sathunter_key_%s_%dwpm" % ("".join(c for c in text if c.isalnum())[:16], wpm)
        return self._play(hz, dbm, name, np.asarray(cw_keying(text, wpm, 100e3), dtype=np.complex64), 100e3)

    def close(self):
        self.off()
