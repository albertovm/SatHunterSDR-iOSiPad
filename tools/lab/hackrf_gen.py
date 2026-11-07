"""HackRF One as the lab generator (same interface as lab.Vsg60Gen: cw, play, keyed, noise, tune, off).

Runs on the PC the HackRF is plugged into (hackrf_transfer from radioconda / PothosSDR on the PATH).
Every waveform is resampled to `RATE` (2 MS/s), shifted by `OFFSET` (+250 kHz: the HackRF's LO
leakage and DC stay out of the receiver's channel), scaled, written once as signed 8-bit IQ
(cached) and streamed to one `hackrf_transfer -t -` (stdin) that keeps running while the tone or the
waveform changes (restart only for another LO, txvga or amplifier setting).

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
import threading
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
        self.current = None  # (name, iq, rate, dbm)
        self.lo, self.tx, self.amp = None, None, None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._buf, self._reset = None, False
        self._zero = np.zeros(1 << 18, dtype=np.int8)
        self._feeder = None
        self.last = {}
        import shutil
        found = shutil.which(self.exe)
        if not found:
            conda = os.path.join(os.path.expanduser("~"), "radioconda", "Library", "bin", "hackrf_transfer.exe")
            found = conda if os.path.exists(conda) else None
        if not found:
            raise SystemExit(f"HackRF: {self.exe} not found (radioconda / PothosSDR on the PATH?)")
        self.exe = found

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
    def _file(self, name, iq, rate, dig, offset=None):
        offset = self.OFFSET if offset is None else offset
        key = "%s_%d_%+.1f_%+d.iq8" % (os.path.splitext(name)[0], int(rate), dig, round(offset))
        path = os.path.join(self.dir, key)
        if os.path.exists(path):
            return path
        # Linear interpolation to RATE, in blocks (a 127 s SSTV picture is 254 M samples at 2 MS/s).
        # Its images sit at multiples of the waveform rate (25 kHz and up for SSTV), outside the
        # receiver channel and 30+ dB down; waveforms at 100 kS/s and more put them further out.
        x = np.asarray(iq, dtype=np.complex64)
        m = len(x)
        n = int(round(m * self.RATE / rate))
        cyc = round(offset * n / self.RATE)  # whole offset cycles over the loop: no phase step
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

    # ---- streaming: one hackrf_transfer reading stdin; the PC feeds it, so a new tone or
    # waveform within +-SPAN of the LO needs no restart (stopping hackrf_transfer mid-stream on
    # Windows left it hung on the USB device, unkillable, until the HackRF was replugged)
    SPAN = 0.8e6

    def _start(self, lo_hz, tx, amp):
        self.off()
        ppm = self.cal.get("ppm") or 0.0
        lo = lo_hz / (1 + ppm * 1e-6)  # the HackRF's reference error, from the calibration
        cmd = [self.exe, "-t", "-", "-f", "%d" % round(lo), "-s", "%d" % self.RATE, "-x", str(tx), "-a", "1" if amp else "0"]
        if self.serial:
            cmd += ["-d", self.serial]
        err = ""
        for attempt in range(6):
            self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, bufsize=0)
            self._stop.clear()
            self._feeder = threading.Thread(target=self._feed, daemon=True)
            self._feeder.start()
            time.sleep(0.8)  # USB start, PLL lock
            if self.proc.poll() is None:
                break
            err = self.proc.stderr.read().decode(errors="replace")
            self._stop.set()
            time.sleep(0.5 + 0.5 * attempt)
        else:
            raise SystemExit(f"HackRF: hackrf_transfer stopped: {err.strip()[-300:]}")
        self.lo, self.tx, self.amp = lo_hz, tx, amp

    def _feed(self):
        pos = 0
        chunk = 1 << 18  # bytes (64 ms at 2 MS/s)
        proc = self.proc
        while not self._stop.is_set():
            with self._lock:
                buf = self._buf
                if self._reset:
                    pos, self._reset = 0, False
            if buf is None or len(buf) == 0:
                buf = self._zero
            if pos >= len(buf):
                pos = 0
            part = buf[pos:pos + chunk]
            pos += len(part)
            try:
                proc.stdin.write(part.tobytes() if hasattr(part, "tobytes") else bytes(part))
            except (BrokenPipeError, OSError, ValueError):
                return

    def _set(self, buf):
        with self._lock:
            self._buf = buf
            self._reset = True

    def _need(self, hz, tx, amp):
        """Start or restart hackrf_transfer when the LO, txvga or the amplifier must change."""
        if self.proc is None or self.proc.poll() is not None or tx != self.tx or amp != self.amp or abs(hz - self.lo) > self.SPAN:
            self._start(hz - self.OFFSET, tx, amp)

    def _play(self, hz, dbm, name, iq, rate):
        tx, amp, dig = self.settings(hz, dbm)
        dig = round(dig * 2) / 2
        lo = self.lo if (self.proc is not None and abs(hz - self.lo) <= self.SPAN and tx == self.tx and amp == self.amp) else hz - self.OFFSET
        path = self._file(name, iq, rate, dig, hz - lo)
        self._need(hz, tx, amp)
        self._set(np.memmap(path, dtype=np.int8, mode="r"))
        self.last = {"hz": hz, "dbm": dbm, "txvga": tx, "amp": amp, "digital_db": dig,
                     "p0": self.p0(hz, amp), "atten": self.atten, "lo": self.lo, "file": os.path.basename(path)}
        self.current = (name, iq, rate, dbm)
        return self.last

    # ---- the generator interface
    def off(self):
        self._stop.set()
        if self.proc is not None:
            try:
                self.proc.stdin.close()  # EOF: hackrf_transfer finishes and releases the device
            except OSError:
                pass
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                try:
                    self.proc.wait(3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        self.proc = None

    def silence(self):
        """Carrier off without stopping the HackRF (zeros)."""
        self._set(None)

    def cw(self, hz, dbm):
        # made in memory (no file per tone): a 1 s loop, the offset from the LO in whole cycles
        tx, amp, dig = self.settings(hz, dbm)
        dig = round(dig * 2) / 2
        self._need(hz, tx, amp)
        n = self.RATE
        cyc = round(hz - self.lo)
        ph = 2 * np.pi * ((cyc * np.arange(n, dtype=np.int64)) % n) / n
        k = 127 * 10 ** (dig / 20)
        buf = np.empty(2 * n, dtype=np.int8)
        buf[0::2] = np.round(k * np.cos(ph))
        buf[1::2] = np.round(k * np.sin(ph))
        self._set(buf)
        self.current = ("sathunter_cw", np.ones(100_000, dtype=np.complex64), 100e3, dbm)
        self.last = {"hz": hz, "dbm": dbm, "txvga": tx, "amp": amp, "digital_db": dig,
                     "p0": self.p0(hz, amp), "atten": self.atten, "lo": self.lo}
        return self.last

    def play(self, hz, dbm, name, iq, rate):
        """Any waveform; `dbm` is the waveform's peak level (as Auto Scale on the VSG60)."""
        return self._play(hz, dbm, name, iq, rate)

    def tune(self, hz):
        """The same waveform on another frequency (no restart within +-SPAN of the LO)."""
        if self.current:
            name, iq, rate, dbm = self.current
            self._play(hz, dbm, name, iq, rate)

    def noise(self, hz, dbm_mean, bw):
        iq, papr = awgn_band(100e3, bw)
        self._play(hz, dbm_mean + papr, "sathunter_awgn_%dk" % round(bw / 1e3), iq, 100e3)
        return papr

    def keyed(self, hz, dbm, text, wpm):
        name = "sathunter_key_%s_%dwpm" % ("".join(c for c in text if c.isalnum())[:16], wpm)
        return self._play(hz, dbm, name, np.asarray(cw_keying(text, wpm, 100e3), dtype=np.complex64), 100e3)

    def close(self):
        self.off()
