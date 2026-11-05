#!/usr/bin/env python3
"""SSTV through the whole chain: the VSG60 plays an FM-modulated Robot 36 picture (colour bars and a
checkerboard), the phone decodes it (cmd sstv), the script fetches the picture (/sstv.ppm) and compares
it with the original, at several levels.

    python tools/lab/sstv_test.py --phone 192.168.1.11 --pin 1027 --atten 34.7 --levels=-100,-110,-115,-118,-120
"""

import argparse, json, math, os, sys, time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lab import Phone, Vsg60Gen, wait_idle  # noqa: E402

W, H = 320, 240


def test_image():
    bars = [(255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0), (255, 0, 255), (255, 0, 0), (0, 0, 255), (0, 0, 0)]
    img = np.zeros((H, W, 3), np.uint8)
    for y in range(H):
        for x in range(W):
            img[y, x] = bars[x * 8 // W] if y < H // 2 else ((230, 230, 230) if ((x // 20) + (y // 20)) % 2 == 0 else (20, 20, 120))
    return img


def ycc(p):
    r, g, b = (float(v) for v in p)
    y = 0.299 * r + 0.587 * g + 0.114 * b
    c = lambda v: int(round(min(255, max(0, v))))  # noqa: E731
    return c(y), c(128 + 0.713 * (r - y)), c(128 + 0.564 * (b - y))


def robot36_tones(img):
    """(frequency Hz, seconds) list: VIS + 240 lines (same as sh_dsp::sstv::sstv_audio)."""
    t = [(0, 0.1), (1900, 0.3), (1200, 0.01), (1900, 0.3), (1200, 0.03)]
    code, ones = 8, 0
    for b in range(7):
        one = (code >> b) & 1
        ones += one
        t.append((1100 if one else 1300, 0.03))
    t += [(1100 if ones % 2 else 1300, 0.03), (1200, 0.03)]
    lev = lambda v: 1500 + 800 * v / 255  # noqa: E731
    for y in range(H):
        t += [(1200, 0.009), (1500, 0.003)]
        t += [(lev(ycc(img[y, x])[0]), 0.088 / W) for x in range(W)]
        even = y % 2 == 0
        t += [(1500 if even else 2300, 0.0045), (1900, 0.0015)]
        pair = y - y % 2
        for x2 in range(W // 2):
            acc = 0
            for yy in (pair, pair + 1):
                for xx in (2 * x2, 2 * x2 + 1):
                    _, cr, cb = ycc(img[yy, xx])
                    acc += cr if even else cb
            t.append((lev(round(acc / 4)), 0.044 / (W // 2)))
    t.append((0, 0.3))
    return t


def fm_iq(tones, rate, dev, audio_fs=48000.0):
    """Audio of the tones (phase-continuous), then FM at `dev` Hz deviation, resampled to `rate`."""
    n_total = int(round(sum(s for _, s in tones) * audio_fs))
    f = np.zeros(n_total)
    t_acc, k0 = 0.0, 0
    for fr, s in tones:
        k1 = int(round((t_acc + s) * audio_fs))
        f[k0:k1] = fr
        k0, t_acc = k1, t_acc + s
    audio = np.sin(np.cumsum(2 * np.pi * f / audio_fs)) * (f > 0)
    # FM: integrate deviation x audio at the IQ rate (linear interpolation of the audio)
    n_iq = int(n_total * rate / audio_fs)
    a_iq = np.interp(np.arange(n_iq) * audio_fs / rate, np.arange(n_total), audio)
    ph = np.cumsum(2 * np.pi * dev * a_iq / rate)
    return np.exp(1j * ph).astype(np.complex64), n_total / audio_fs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--pin", required=True)
    ap.add_argument("--vsg", default="127.0.0.1:5124")
    ap.add_argument("--atten", type=float, default=0.0)
    ap.add_argument("--freq", type=float, default=436.6e6)
    ap.add_argument("--dev", type=float, default=3000.0)
    ap.add_argument("--levels", default="-100,-110,-115,-118,-120")
    ap.add_argument("--rate", type=float, default=25e3, help="ARB rate (25 kS/s plays at the right speed on the VSG60; 20 does not)")
    ap.add_argument("--name", default="sstv")
    a = ap.parse_args()
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
    out = os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    img = test_image()
    with open(os.path.join(out, "sent.ppm"), "wb") as fh:
        fh.write(f"P6\n{W} {H}\n255\n".encode() + img.tobytes())
    iq, secs = fm_iq(robot36_tones(img), a.rate, a.dev)
    print(f"Robot 36 waveform: {secs:.1f} s, {len(iq)} samples at {a.rate / 1e3:g} kS/s")
    phone = Phone(a.phone, a.pin)
    host, port = (a.vsg.split(":") + ["5124"])[:2]
    gen = Vsg60Gen(a.atten, host, int(port), r"C:\sathunter_lab", None)
    res = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "freq_hz": a.freq, "deviation_hz": a.dev, "mode": "Robot 36", "rows": []}

    def save():
        with open(os.path.join(out, "results.json"), "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)

    try:
        phone.cmd(cmd="rate", hz=1024000.0)
        phone.cmd(cmd="decimation", factor=8)
        phone.cmd(cmd="gain", db=12.5)
        phone.cmd(cmd="mode", mode="NFM", bw=12500.0)
        phone.cmd(cmd="tune", hz=a.freq)
        phone.cmd(cmd="sstv", on=False)
        phone.cmd(cmd="sstv", on=True)
        levels = [float(x) for x in a.levels.split(",")]
        for k, lv in enumerate(levels):
            phone.phase("SSTV", k + 1, len(levels), f"Robot 36 at {lv:.0f} dBm")
            wait_idle(phone)
            c0 = phone._req("GET", "/sstv")["count"]
            gen.play(a.freq, lv, "sathunter_sstv_r36.cf32", list(iq), a.rate)  # the ARB loops; the decoder waits for the next VIS
            t0 = time.time()
            got = None
            while time.time() - t0 < 2.4 * secs + 10:
                time.sleep(3)
                s = phone._req("GET", "/sstv")
                if s["count"] > c0:
                    got = s
                    break
            row = {"level_dbm": lv, "received": got is not None}
            if got:
                import urllib.request
                with urllib.request.urlopen(f"{phone.base}/sstv.ppm?pin={phone.pin}", timeout=30) as r:
                    ppm = r.read()
                hdr_end = ppm.index(b"255\n") + 4
                rx = np.frombuffer(ppm[hdr_end:], np.uint8).reshape(H, W, 3)
                with open(os.path.join(out, f"received_{int(-lv)}dBm.ppm"), "wb") as fh:
                    fh.write(ppm)
                inner = (slice(2, H - 2), slice(4, W - 4))
                row["mean_error"] = float(np.abs(rx[inner].astype(float) - img[inner].astype(float)).mean())
                row["mode"] = got.get("last", {}).get("mode")
            res["rows"].append(row)
            phone.log(f"SSTV {lv:.0f} dBm: " + (f"picture, mean error {row['mean_error']:.1f}" if got else "no picture"))
            save()
            gen.off()
            time.sleep(1)
    finally:
        gen.close()
        res["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
        save()
    print(f"Results: {out}")


if __name__ == "__main__":
    main()
