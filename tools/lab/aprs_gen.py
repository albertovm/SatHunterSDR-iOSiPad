"""AX.25 / HDLC / AFSK 1200 generator for the lab (the same coding as sh-dsp/src/afsk.rs)."""

import math


def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b
        for _ in range(8):
            c = (c >> 1) ^ 0x8408 if c & 1 else c >> 1
    return c ^ 0xFFFF


def ui_frame(src, dst, path, info):
    def addr(call, last):
        h = call.endswith("*")
        call = call.rstrip("*")
        c, _, ssid = call.partition("-")
        b = [ord(x) << 1 for x in c[:6].ljust(6)]
        b.append(0x60 | (int(ssid or 0) << 1) | (0x80 if h else 0) | (1 if last else 0))
        return b
    out = addr(dst, False) + addr(src, not path)
    for n, p in enumerate(path):
        out += addr(p, n + 1 == len(path))
    return bytes(out + [0x03, 0xF0]) + info


def hdlc_nrzi(frame, pre_flags=40, post_flags=3):
    c = crc16(frame)
    data = list(frame) + [c & 0xFF, c >> 8]
    bits = []
    flag = [(0x7E >> k) & 1 for k in range(8)]
    bits += flag * pre_flags
    ones = 0
    for b in data:
        for k in range(8):
            bit = (b >> k) & 1
            bits.append(bit)
            ones = ones + 1 if bit else 0
            if ones == 5:
                bits.append(0)
                ones = 0
    bits += flag * post_flags
    level, out = 1, []
    for b in bits:
        if b == 0:
            level ^= 1
        out.append(level)
    return out


def afsk(levels, fs, baud=1200.0):
    spb = fs / baud
    ph, out = 0.0, []
    for i in range(int(len(levels) * spb)):
        f = 1200.0 if levels[int(i / spb)] else 2200.0
        ph += 2 * math.pi * f / fs
        out.append(math.sin(ph))
    return out
