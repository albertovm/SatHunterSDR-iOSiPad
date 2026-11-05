"""SatHunterSDR + Spacewalker LNA: lab and field summary (3 pages A4) -> docs/report/SatHunterSDR-lab-field-summary.pdf

    python docs/report/make_report.py      (from the repository root; charts from tools/lab and docs/report/make_fix_chart.py)
"""
import json

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DVB")

BLUE = colors.HexColor("#2a6fdb")
GREY = colors.HexColor("#495057")
LIGHT = colors.HexColor("#f1f3f5")
H1 = ParagraphStyle("h1", fontName="DVB", fontSize=16, leading=19, textColor=colors.black, spaceAfter=2)
SUB = ParagraphStyle("sub", fontName="DV", fontSize=8.5, leading=11, textColor=GREY, spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="DVB", fontSize=11, leading=14, textColor=BLUE, spaceBefore=6, spaceAfter=3)
P = ParagraphStyle("p", fontName="DV", fontSize=8.4, leading=11, alignment=TA_LEFT, spaceAfter=3)
T = ParagraphStyle("t", fontName="DV", fontSize=7.3, leading=9)
TB = ParagraphStyle("tb", parent=T, fontName="DVB")
CAP = ParagraphStyle("cap", fontName="DV", fontSize=7.2, leading=9, textColor=GREY, spaceAfter=4)

W = A4[0] - 30 * mm
NF = json.load(open("docs/report/nf_final.json"))  # written after the input-path measurement


def img(path, width, aspect=None):
    from PIL import Image as PI
    w, h = PI.open(path).size
    return Image(path, width=width, height=width * h / w)


def table(rows, widths, header=True):
    data = [[Paragraph(str(c), TB if (header and i == 0) else T) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ced4da")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
          ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5)]
    if header:
        st.append(("BACKGROUND", (0, 0), (-1, 0), LIGHT))
    t.setStyle(TableStyle(st))
    return t


def footer(c, d):
    c.saveState()
    c.setFont("DV", 7)
    c.setFillColor(GREY)
    c.drawString(15 * mm, 8 * mm, "SatHunterSDR + Spacewalker LNA 434 - lab and field summary, November 2026 - github.com/z2labs/SatHunter-SDR")
    c.drawRightString(A4[0] - 15 * mm, 8 * mm, f"{d.page} / 3")
    c.restoreState()


s = []
s.append(Paragraph("SatHunterSDR + Spacewalker LNA 434: what the lab and the field showed", H1))
s.append(Paragraph("Zoltan Doczi, Z2Labs / RF Sparkling - 1-5 November 2026 - all runs, scripts and raw data in the repository "
                   "(measurements/, tools/lab/)", SUB))
s.append(Paragraph(
    "SatHunterSDR is an Android app that turns a phone, an RTL-SDR and the Spacewalker LNA 434 (Decent Labs) into a CubeSat "
    "receiver: it picks the satellite, predicts the pass with SGP4, follows the Doppler and decodes CW and APRS on the phone. "
    "Over five days we heard satellites in the field, then rebuilt the sky in the lab (Signal Hound VSG60A playing whole passes with "
    "their Doppler, BB60C measuring the LNA alone), fixed what the measurements exposed, and measured again.", P))
s.append(img("docs/img/sathunter-block-diagram.png", W))
s.append(Paragraph("System block diagram: RF chain, Rust core, Android UI and the lab instruments that replace the sky.", CAP))
s.append(Paragraph("Key results", H2))
s.append(table([
    ["", "Quantity", "Result"],
    ["Field", "ITUPSAT 1, 70 cm CW, 19° pass, 6-el. yagi", "callsign decoded at 12 WPM, C/N0 ~41 dB-Hz, Doppler tracked"],
    ["Field", "CUBEBUG-2, AFSK1200, IQ recording", "3 of 5 frames with good CRC, C/N0 ~55 dB-Hz; burst kept as a test vector"],
    ["Lab", "System noise figure (LNA + RTL-SDR, 436.6 MHz)", "2.0 dB"],
    ["Lab", "Sensitivity / CW decode", "MDS -154.4 dBm in 31 Hz; 15 WPM CW decoded down to -145 dBm (29 dB-Hz)"],
    ["Lab", "APRS (AFSK1200)", "90 % packets at -122.5 dBm (3 kHz dev.), -123.2 dBm (1 kHz dev., 6 kHz channel)"],
    ["Lab", "Simulated 79° LEO pass, 116 Hz/s Doppler", "receiver within ±9 Hz (1σ) of the satellite; CW decoded through the closest point at -130 dBm"],
    ["Lab", "Orbit model check", "phone vs independent SGP4: 0.16 Hz apart at 435 MHz"],
    ["Lab", "Frequency accuracy / decimation", "0.09 ppm at every sample rate; alias rejection > 48 dB in the central 84 % of the span"],
    ["Lab", "Spacewalker LNA 434 v1.4 (alone, 5.0 V, 131 mA)",
     f"gain 45-51 dB in 425-444 MHz, NF {NF['range']} dB (two methods, see p. 3), OP1dB +15.5...+21 dBm, IIP3 about -18 dBm, "
     "> 72 dB out-of-band rejection, gain stable 0.15 dB over 10 min, no oscillation"],
], [12 * mm, 62 * mm, W - 74 * mm]))
s.append(PageBreak())

s.append(Paragraph("Bugs and weak spots found, and what was done", H2))
s.append(table([
    ["Found", "How it showed up", "Fix", "Result"],
    ["Frequency error depended on the sample rate", "VSG60 CW at every rate: +10 / +155 / +210 Hz", "R820T2 fractional-N (SDM) residual computed in Hz and applied as an IF correction in rtl-sdr-rs", "+40 Hz (0.09 ppm) at every rate"],
    ["Weak beacons hard to see", "Field: ITUPSAT 1 barely visible", "Spectrum averages every FFT between frames (one FFT per frame skipped ~97 % of the samples)", "a beacon 10 dB weaker is visible"],
    ["Choppy audio, jumpy waterfall", "Field: CW demodulator took a whole CPU core, blocks dropped silently", "CW 10x, SSB / FM 3x lighter; dropped blocks reported", "no silent drops"],
    ["AM audio capped at 4 kHz; NFM volume depended on the filter", "DSP check, modes x bandwidths", "AM audio cut follows the bandwidth (1-15 kHz); NFM full scale fixed at 5 kHz deviation", "flat response, constant level"],
    ["Doppler applied in 200 ms steps", "Doppler ramps: up to 23 Hz tone jumps at 116 Hz/s", "VFO glides at the rate predicted 1 s ahead", "±9 Hz (1σ) through a 79° pass"],
    ["APRS limited by the FM-discriminator detector", "APRS sweeps: Eb/N0 ~19 dB at 90 %", "650 Hz post-detection filter, DPLL, soft repair of the 24 least confident bits", "+1.0 ... +1.5 dB"],
    ["Build crashed at start", "lab7: engine pulled plugin code needing libc++_shared.so", "APRS position code moved to sh-dsp (the plugin runtime must package libc++)", "fixed in lab8"],
    ["Retune lost while the RTL-SDR was opening", "Field: right frequency shown, wrong one received", "retune queued until the device is open", "fixed (beta 9)"],
    ["Lab: generator could not follow a LEO pass", "VSG60 retune over SCPI interrupts the output (up to 13.5 s); 20 kS/s ARB plays 16 % slow", "whole pass Doppler written into one ARB at 25 kS/s, started on the phone's simulated clock", "valid fast-pass test"],
    ["LNA: 0.22 V drop in the bias feed", "supply sweep: 5.22 V needed at the supply for 5.0 V on the board", "documented; compensate on long or thin feeds", "only 0.2 dB gain at 4.8 V"],
    ["LNA: 60 dB dropouts, rare", "1 in 315 readings, often at high drive; 0 in 5027 with the LNA out", "open: LNA, supply or bias-tee DC path", "readings re-checked"],
    ["LNA noise figure: two methods disagree", "BB60C gain method 2.6-4.1 dB vs 2.0 dB for the whole chain (phone)", "both absolute references checked (input path measured, 50 Ω load = generator off); a calibrated noise source (Y-factor) is next", "quoted as 2-4 dB"],
    ["LNA: 5.5 dB passband ripple, dip at 436 MHz", "comb sweep in 200 kHz steps", "property of the SAW - LNA - SAW - LNA - SAW cascade; OP1dB is lowest (+15.5 dBm) at the dip", "feedback to the design"],
], [32 * mm, 45 * mm, 62 * mm, W - 139 * mm]))
s.append(Spacer(1, 4))
s.append(img("docs/report/fixes.png", W))
s.append(Paragraph("Left: frequency error before and after the R820T2 PLL fix (the remaining +40 Hz is the RTL / generator reference "
                   "difference, the same at every rate). Right: APRS packet success, decoder v1 and v2.", CAP))
s.append(PageBreak())

s.append(Paragraph("A satellite pass, replayed in the lab", H2))
s.append(img("docs/img/pass-simulation.png", W))
s.append(Paragraph("CAPE-1, 79° pass over Budapest. The VSG60A plays the beacon with the Doppler computed by an independent SGP4; "
                   "the phone tracks with its own orbit model. Tracking error ±9 Hz (1σ) at 116 Hz/s; CW decoded in all four windows.", CAP))
s.append(Paragraph("Spacewalker LNA 434 v1.4 on its own", H2))
lna = table([
    ["Parameter", "Result"],
    ["Gain 435-438 MHz", "45.3-50.4 dB"],
    ["Passband (-10 dB)", "425.1-443.7 MHz"],
    ["Out-of-band rejection", "72 to > 80 dB"],
    ["Noise figure", "2.6-4.1 dB (BB60C gain method, 50 Ω load); 2.0 dB from the chain; Y-factor next"],
    ["IP1dB / OP1dB", "-27...-32 / +15.5...+21 dBm"],
    ["IIP3 / OIP3, 436 MHz", "about -18 / +27 dBm"],
    ["Blocker ±15-18 MHz, -18 dBm", "< 0.25 dB desense"],
    ["Harmonics (2f, 3f)", "< -64 dBc"],
    ["4.5 / 5.0 / 5.5 V on the board", "117 / 131 / 146 mA"],
], [33 * mm, W * 0.37 - 35 * mm])
two = Table([[img("docs/report/lna.png", W * 0.62), lna]], colWidths=[W * 0.63, W * 0.37])
two.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
s.append(two)
s.append(Paragraph("Transfer function from a 90-tone comb (380-490 MHz, 200 kHz steps) with the CW points; levels at the LNA's connectors, "
                   "path calibrated without the LNA.", CAP))
s.append(Paragraph("Next", H2))
s.append(Paragraph("Track down the LNA dropouts (supply, bias tee, LNA); RTL-SDR warm-up drift from a cold start; a coherent AFSK detector "
                   "for a few more dB on APRS; S11 / S22 with a VNA; more field passes with the campaign hardware.", P))

doc = SimpleDocTemplate("docs/report/SatHunterSDR-lab-field-summary.pdf", pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm,
                        topMargin=12 * mm, bottomMargin=14 * mm, title="SatHunterSDR + Spacewalker LNA: lab and field summary",
                        author="Zoltan Doczi")
doc.build(s, onFirstPage=footer, onLaterPages=footer)
print("ok")
