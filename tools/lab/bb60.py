"""Signal Hound BB60C through its C API (bb_api.dll from the Spike folder, API 5.x) with ctypes:
power of a CW signal at a frequency. Spike must not run at the same time (one program per device)."""

import ctypes, os

DLL_DIR = r"C:\Program Files\Signal Hound\Spike"

# bb_api.h (5.x)
BB_AVERAGE = 1
BB_LOG_SCALE = 0
BB_RBW_SHAPE_FLATTOP = 1  # best amplitude accuracy for a CW tone
BB_NO_SPUR_REJECT = 0
BB_SPUR_REJECT = 1
BB_SWEEPING = 0


class BB60:
    def __init__(self, dll_dir=DLL_DIR):
        os.add_dll_directory(dll_dir)
        self.api = ctypes.CDLL(os.path.join(dll_dir, "bb_api.dll"))
        self.api.bbGetAPIVersion.restype = ctypes.c_char_p
        self.dev = ctypes.c_int(-1)
        st = self.api.bbOpenDevice(ctypes.byref(self.dev))
        if st != 0:
            raise SystemExit(f"BB60: bbOpenDevice status {st} (Spike running? USB?)")
        sn = ctypes.c_uint(0)
        self.api.bbGetSerialNumber(self.dev, ctypes.byref(sn))
        self.serial = sn.value
        self.version = self.api.bbGetAPIVersion().decode()

    def _ok(self, st, what):
        if st < 0:
            raise SystemExit(f"BB60: {what} failed, status {st}")

    def peak(self, hz, span=200e3, rbw=1e3, ref_dbm=-20.0, spur_reject=True):
        """Highest level (dBm, average detector) within +-span/2 of `hz`, and its frequency."""
        a, d = self.api, self.dev
        self._ok(a.bbConfigureRefLevel(d, ctypes.c_double(ref_dbm)), "ref level")
        self._ok(a.bbConfigureCenterSpan(d, ctypes.c_double(hz), ctypes.c_double(span)), "centre/span")
        self._ok(a.bbConfigureSweepCoupling(d, ctypes.c_double(rbw), ctypes.c_double(rbw), ctypes.c_double(0.01),
                                            ctypes.c_uint(BB_RBW_SHAPE_FLATTOP), ctypes.c_uint(BB_SPUR_REJECT if spur_reject else BB_NO_SPUR_REJECT)), "coupling")
        self._ok(a.bbConfigureAcquisition(d, ctypes.c_uint(BB_AVERAGE), ctypes.c_uint(BB_LOG_SCALE)), "acquisition")
        self._ok(a.bbInitiate(d, ctypes.c_uint(BB_SWEEPING), ctypes.c_uint(0)), "initiate")
        n, bin_hz, start = ctypes.c_uint(0), ctypes.c_double(0), ctypes.c_double(0)
        self._ok(a.bbQueryTraceInfo(d, ctypes.byref(n), ctypes.byref(bin_hz), ctypes.byref(start)), "trace info")
        tmin = (ctypes.c_float * n.value)()
        tmax = (ctypes.c_float * n.value)()
        best = None
        for _ in range(3):  # a few sweeps, keep the highest (the first after a change can be stale)
            self._ok(a.bbFetchTrace_32f(d, ctypes.c_int(n.value), tmin, tmax), "fetch")
            k = max(range(n.value), key=lambda i: tmax[i])
            if best is None or tmax[k] > best[0]:
                best = (float(tmax[k]), start.value + k * bin_hz.value)
        return best

    def noise(self, hz, span=200e3, rbw=1e3, ref_dbm=-20.0):
        """Median level in the span (dBm per RBW)."""
        a, d = self.api, self.dev
        self.peak(hz, span, rbw, ref_dbm)  # configures
        n, bin_hz, start = ctypes.c_uint(0), ctypes.c_double(0), ctypes.c_double(0)
        a.bbQueryTraceInfo(d, ctypes.byref(n), ctypes.byref(bin_hz), ctypes.byref(start))
        tmin = (ctypes.c_float * n.value)()
        tmax = (ctypes.c_float * n.value)()
        a.bbFetchTrace_32f(d, ctypes.c_int(n.value), tmin, tmax)
        v = sorted(tmax)
        return float(v[len(v) // 2])

    def close(self):
        try:
            self.api.bbCloseDevice(self.dev)
        except Exception:
            pass
