#!/usr/bin/env python3
"""SatHunterSDR block diagram (RF chain, Rust core, Android UI, lab instruments) -> docs/img/sathunter-block-diagram.png/.svg

    python tools/lab/plot_block_diagram.py docs/img/sathunter-block-diagram
"""

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

RF = ("#fff4e6", "#e8590c")
CORE = ("#e7f0ff", "#2a6fdb")
UI = ("#ebfbee", "#2f9e44")
LAB = ("#f3f0ff", "#7048e8")
SKY = ("#e3fafc", "#1098ad")


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "docs/img/sathunter-block-diagram"
    fig, ax = plt.subplots(figsize=(18, 11.5))
    ax.set_xlim(-6, 181); ax.set_ylim(0, 115); ax.axis("off")
    B = {}

    def group(x, y, w, h, title, col, tx=1.2):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=2", fc="#f8f9fa", ec=col, lw=1.6, ls="--"))
        ax.text(x + tx, y + h - 1.6, title, fontsize=12, fontweight="bold", color=col, va="top")

    def box(key, x, y, w, h, title, body, c):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2", fc=c[0], ec=c[1], lw=1.6))
        ax.text(x + w / 2, y + h - 1.3, title, ha="center", va="top", fontsize=10.5, fontweight="bold", color="#212529")
        ax.text(x + w / 2, y + h - 4.4, body, ha="center", va="top", fontsize=8.6, color="#343a40", linespacing=1.35)
        B[key] = (x, y, w, h)

    def side(k, s):
        x, y, w, h = B[k]
        return {"l": (x, y + h / 2), "r": (x + w, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[s]

    def arrow(a, sa, b, sb, label="", style="-|>", col="#495057", lw=1.6, ls="-", rad=0.0, lx=0, ly=0, both=False):
        p0, p1 = side(a, sa), side(b, sb)
        ax.annotate("", xy=p1, xytext=p0, arrowprops=dict(arrowstyle="<|-|>" if both else style, color=col, lw=lw, ls=ls,
                                                            shrinkA=2, shrinkB=2, connectionstyle=f"arc3,rad={rad}"))
        if label:
            ax.text((p0[0] + p1[0]) / 2 + lx, (p0[1] + p1[1]) / 2 + ly, label, ha="center", va="center", fontsize=8.6,
                    color=col, bbox=dict(fc="white", ec="none", pad=0.6))

    def path(pts, label, col, lw=1.6, ls="-", lpos=None, both=False):
        xs, ys = zip(*pts)
        ax.plot(xs[:-1] + (xs[-1],), ys, color=col, lw=lw, ls=ls, solid_capstyle="round")
        ax.annotate("", xy=pts[-1], xytext=pts[-2], arrowprops=dict(arrowstyle="-|>", color=col, lw=lw, shrinkA=0, shrinkB=1))
        if both:
            ax.annotate("", xy=pts[0], xytext=pts[1], arrowprops=dict(arrowstyle="-|>", color=col, lw=lw, shrinkA=0, shrinkB=1))
        if label:
            ax.text(*lpos, label, ha="center", va="center", fontsize=8.8, color=col, bbox=dict(fc="white", ec="none", pad=0.8))

    ax.text(90, 113.5, "SatHunterSDR: from the satellite to the screen", ha="center", va="top", fontsize=17, fontweight="bold")

    # RF chain
    group(1, 82, 178, 26, "RF front end", RF[1])
    box("sat", 3, 85, 26, 19, "Satellite", "70 cm / 2 m beacons:\nCW, AFSK1200 / APRS, FM ...\nDoppler at 435 MHz:\nup to ±10 kHz, 120 Hz/s", SKY)
    box("ant", 37, 87, 22, 15, "Antenna", "yagi / turnstile /\nwhip", RF)
    box("lna", 67, 84, 40, 21, "Spacewalker LNA 434 v1.4", "SAW - LNA - SAW - LNA - SAW\ngain 45-51 dB (425-444 MHz)\nNF ~2 dB, IIP3 -19 dBm, OP1dB +16 dBm\n> 72 dB out-of-band rejection", RF)
    box("bt", 115, 87, 20, 15, "Bias tee", "5 V, 130 mA\nto the LNA", RF)
    box("rtl", 143, 84, 33, 21, "RTL-SDR Blog V3", "R820T2 tuner + RTL2832U\n8-bit IQ, 0.25-2.4 MS/s\ngain 0-49.6 dB, TCXO", RF)
    arrow("sat", "r", "ant", "l", "radio", ls="--")
    arrow("ant", "r", "lna", "l")
    arrow("lna", "r", "bt", "l")
    arrow("bt", "r", "rtl", "l")

    # phone
    group(1, 22, 178, 56.5, "Android phone (Xiaomi Mi 10): SatHunterSDR app", CORE[1], tx=42)
    ax.text(43, 71.2, "Rust core, libsh_android.so", fontsize=10, color=CORE[1], style="italic")
    box("src", 3, 46, 34, 22, "sh-sources", "RTL-SDR via rtl-sdr-rs (USB OTG)\nESP32-S3 ESP-SDR, rtl_tcp\ndemo / RF simulator\nown thread, bounded queue", CORE)
    box("eng", 45, 46, 38, 22, "sh-engine", "DSP thread, settings, JSON commands\nDoppler-corrected tuning, VFO glide\nIQ / audio recording\nlab link (HTTP :8765, PIN)", CORE)
    box("dsp", 91, 46, 44, 22, "sh-dsp", "decimation (FIR, /1 ... /64) -> FFT spectrum\nchannel: NCO shift + filter\ndemod NFM / AM / USB / LSB / CW\nCW decoder, AFSK1200 / APRS (AX.25) decoder", CORE)
    box("sat2", 45, 24, 38, 18, "sh-sat", "SatNOGS / CelesTrak TLEs, SGP4\npasses, look angles, range rate\nDoppler tracker: 200 ms loop,\nrate from the look 1 s ahead", CORE)
    box("plg", 91, 24, 26, 18, "sh-plugin", "decoder plugins\n(Luau runtime)\nsatellite catalog", CORE)
    box("jni", 143, 46, 33, 22, "sh-android", "JNI bridge\npanic-safe: core errors\nnever crash the app", CORE)
    box("ui", 125, 24, 51, 18, "Kotlin / Jetpack Compose UI", "Receiver: waterfall, frequency, mode, APRS panel\nSatellites: list, radar, next pass, Simulate\nSettings: source, rate, gain, ppm, decoders\nUpdates from GitHub releases, audio 48 kHz", UI)
    path([side("rtl", "b"), (159.5, 80.5), (20, 80.5), side("src", "t")], "USB OTG: IQ samples", RF[1], lw=2.6, lpos=(90, 80.5))
    arrow("src", "r", "eng", "l", "IQ")
    arrow("eng", "r", "dsp", "l", "IQ + tuning")
    arrow("sat2", "t", "eng", "b", "Doppler offset + rate", lx=12)
    arrow("plg", "t", "dsp", "b")
    arrow("dsp", "r", "jni", "l", "spectrum, audio,\ndecodes", ly=0)
    arrow("jni", "b", "ui", "t", "commands / state", both=True, lx=10)

    # lab
    group(1, 1, 178, 19, "Lab (tools/lab, G7 laptop) - replaces the sky for repeatable tests", LAB[1])
    box("vsg", 3, 3, 40, 11, "Signal Hound VSG60A", "CW, keyed CW, ARB with SGP4 Doppler,\ntwo-tone, 90-tone comb", LAB)
    box("py", 70, 3, 40, 11, "Python lab scripts", "lab.py, fast_pass.py, rx_extra.py, path_cal.py,\nlna_char.py, comb_sweep.py, lna_extra.py", LAB)
    box("bb", 137, 3, 39, 11, "Signal Hound BB60C", "gain, compression, IMD,\nnoise, spurs (C API)", LAB)
    arrow("py", "l", "vsg", "r", "SCPI")
    arrow("py", "r", "bb", "l", "C API")
    path([side("vsg", "l"), (-3.5, 8.5), (-3.5, 83), (63, 83), (63, 90), (67, 90)], "test signal via attenuators (instead of the antenna)",
         LAB[1], ls="--", lpos=(30, 83))
    path([(87, 14), (87, 50), (83, 50)], "HTTP lab link\n(PIN)", LAB[1], ls="--", lpos=(87, 30), both=True)

    fig.savefig(out + ".png", dpi=130, bbox_inches="tight", facecolor="white")
    fig.savefig(out + ".svg", bbox_inches="tight", facecolor="white")
    print(out)


if __name__ == "__main__":
    main()
