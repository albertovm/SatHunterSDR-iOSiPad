"""Signal Hound SA44(B) through its C API (sa_api.dll from the Spike folder) with ctypes.

    from sa44 import SA44
    sa = SA44(); level_dbm, freq_hz = sa.peak(436.6e6, span=20e3, rbw=100, ref_dbm=0)

Used as a third reference next to the VSG60A and the BB60C (2026-11-10: the two disagree by 2.7 dB on 70 cm).
The SA44 covers 1 Hz - 4.4 GHz; it enumerates as an FTDI FT2232 (VID 0403, PID 6010).
"""
import ctypes
import os

import numpy as np

DLL_DIR = r"C:\Program Files\Signal Hound\Spike"
SA_MIN_MAX, SA_AVERAGE = 0, 1
SA_LOG_SCALE = 0
SA_SWEEPING = 0


class SA44:
    def __init__(self, dll_dir=DLL_DIR):
        os.add_dll_directory(dll_dir)
        self.api = ctypes.CDLL(os.path.join(dll_dir, "sa_api.dll"))
        a = self.api
        a.saConfigCenterSpan.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double]
        a.saConfigLevel.argtypes = [ctypes.c_int, ctypes.c_double]
        a.saConfigSweepCoupling.argtypes = [ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_bool]
        a.saConfigAcquisition.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        a.saInitiate.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int]
        a.saGetErrorString.restype = ctypes.c_char_p
        dev = ctypes.c_int(-1)
        self._ok(a.saOpenDevice(ctypes.byref(dev)), "saOpenDevice")
        self.dev = dev.value
        sn = ctypes.c_int(0)
        if hasattr(a, "saGetSerialNumber"):
            a.saGetSerialNumber(self.dev, ctypes.byref(sn))
        self.serial = sn.value

    def _ok(self, st, what):
        if st < 0:
            raise RuntimeError("%s: %d %s" % (what, st, self.api.saGetErrorString(st).decode()))

    def trace(self, center, span, rbw, ref_dbm=0.0, detector=SA_AVERAGE):
        a, d = self.api, self.dev
        self._ok(a.saConfigCenterSpan(d, center, span), "saConfigCenterSpan")
        self._ok(a.saConfigLevel(d, ref_dbm), "saConfigLevel")
        self._ok(a.saConfigSweepCoupling(d, rbw, rbw, True), "saConfigSweepCoupling")
        self._ok(a.saConfigAcquisition(d, detector, SA_LOG_SCALE), "saConfigAcquisition")
        self._ok(a.saInitiate(d, SA_SWEEPING, 0), "saInitiate")
        n, start, step = ctypes.c_int(), ctypes.c_double(), ctypes.c_double()
        self._ok(a.saQuerySweepInfo(d, ctypes.byref(n), ctypes.byref(start), ctypes.byref(step)), "saQuerySweepInfo")
        lo = (ctypes.c_float * n.value)()
        hi = (ctypes.c_float * n.value)()
        self._ok(a.saGetSweep_32f(d, lo, hi), "saGetSweep_32f")
        f = start.value + step.value * np.arange(n.value)
        return f, np.array(hi, dtype=float)

    def peak(self, center, span=20e3, rbw=100.0, ref_dbm=0.0, sweeps=3):
        best = None
        for _ in range(sweeps):
            f, p = self.trace(center, span, rbw, ref_dbm)
            i = int(np.argmax(p))
            v = (float(p[i]), float(f[i]))
            best = v if best is None else (max(best[0], v[0]), v[1] if v[0] >= best[0] else best[1])
        return best

    def close(self):
        self.api.saCloseDevice(self.dev)
