"""Terrestrial APRS field log: what the phone decodes on the local APRS network, over time.

    python tools/lab/aprs_log.py --ip 192.168.1.11 --pin 1027 --minutes 60 --name aprs-ground

The phone must be in the terrestrial APRS mode (Settings, or --start to switch it on here). Every
5 s the script reads the new frames (/aprs) and the receiver status (signal level, bad-CRC count,
dropped blocks). It writes frames.jsonl, status.csv and, at the end (or Ctrl+C), report.md with:
frames per hour, stations, digipeaters, packet types, positions with distance and bearing,
a map and a timeline. Folder: measurements/<date_time>_<name>/.
"""
import argparse
import csv
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from lab import Phone  # noqa: E402


def kind(info):
    """APRS data type from the first byte of the information field."""
    if not info:
        return "empty"
    c = info[0]
    return {
        "!": "position", "=": "position", "/": "position (time)", "@": "position (time)",
        ";": "object", ")": "item", ":": "message", ">": "status", "T": "telemetry",
        "`": "Mic-E", "'": "Mic-E", "_": "weather", "<": "capabilities", "}": "third party", "$": "NMEA",
    }.get(c, "other")


def dist_brg(lat1, lon1, lat2, lon2):
    r = math.pi / 180
    c = math.sin(lat1 * r) * math.sin(lat2 * r) + math.cos(lat1 * r) * math.cos(lat2 * r) * math.cos((lon2 - lon1) * r)
    d = 6371.0 * math.acos(max(-1.0, min(1.0, c)))
    y = math.sin((lon2 - lon1) * r) * math.cos(lat2 * r)
    x = math.cos(lat1 * r) * math.sin(lat2 * r) - math.sin(lat1 * r) * math.cos(lat2 * r) * math.cos((lon2 - lon1) * r)
    return d, (math.atan2(y, x) / r + 360) % 360


def report(out, frames, rows, st0, started):
    lat0, lon0 = (st0.get("station") or {}).get("lat"), (st0.get("station") or {}).get("lon")
    secs = max(1.0, (rows[-1]["t"] - rows[0]["t"]) if len(rows) > 1 else 1.0)
    srcs = Counter(f["src"] for f in frames)
    kinds = Counter(kind(f["info"]) for f in frames)
    digis = Counter(p.rstrip("*") for f in frames for p in f.get("path", []) if p.endswith("*"))
    direct = sum(1 for f in frames if not any(p.endswith("*") for p in f.get("path", [])))
    pos = {}
    for f in frames:
        if f.get("lat") is not None:
            pos[f["src"]] = (f["lat"], f["lon"], f["time"])
    bad = rows[-1]["bad_crc"] - rows[0]["bad_crc"] if rows else 0
    levels = [r["level_db"] for r in rows if r["level_db"] is not None]

    # charts
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(2, 1, figsize=(9, 5.5), sharex=True)
        t0 = rows[0]["t"]
        ax[0].plot([(r["t"] - t0) / 60 for r in rows], [r["level_db"] for r in rows], lw=0.8)
        ax[0].set_ylabel("level, dB")
        ax[0].set_title("Terrestrial APRS %.3f MHz" % (st0.get("ground_aprs", {}).get("hz", 0) / 1e6))
        ft = [(f["time"] - t0) / 60 for f in frames]
        ax[1].hist(ft, bins=max(1, int(secs / 300)), color="#c48a00")
        ax[1].set_ylabel("frames / 5 min")
        ax[1].set_xlabel("minutes")
        fig.tight_layout()
        fig.savefig(os.path.join(out, "timeline.png"), dpi=130)
        plt.close(fig)

        if pos and lat0 is not None:
            fig, ax = plt.subplots(figsize=(7, 7))
            ax.plot(lon0, lat0, "s", color="#1f77b4")
            ax.annotate("receiver", (lon0, lat0), xytext=(5, 5), textcoords="offset points")
            for s, (la, lo, _) in pos.items():
                ax.plot(lo, la, "o", color="#c48a00")
                d, _ = dist_brg(lat0, lon0, la, lo)
                ax.annotate("%s %.0f km" % (s, d), (lo, la), xytext=(4, 4), textcoords="offset points", fontsize=8)
            ax.set_aspect(1 / math.cos(lat0 * math.pi / 180))
            ax.set_xlabel("longitude")
            ax.set_ylabel("latitude")
            ax.grid(alpha=0.3)
            ax.set_title("Positions heard")
            fig.tight_layout()
            fig.savefig(os.path.join(out, "map.png"), dpi=130)
            plt.close(fig)
    except ImportError:
        pass

    L = [
        "# Terrestrial APRS field log",
        "",
        "Run: %s, %.0f min, `tools/lab/aprs_log.py`, source %s, %.3f MHz %s, gain %s dB, decimation %s." % (
            started, secs / 60, st0.get("source"), st0.get("vfo_hz", 0) / 1e6, st0.get("mode"),
            st0.get("gain"), st0.get("decimation")),
        "",
        "| | |",
        "|---|---|",
        "| Frames (good CRC) | %d (%.0f per hour) |" % (len(frames), len(frames) * 3600 / secs),
        "| Stations heard (source calls) | %d |" % len(srcs),
        "| Heard direct / via a digipeater | %d / %d |" % (direct, len(frames) - direct),
        "| Bad-CRC flags (noise and broken frames) | %d |" % bad,
        "| Signal level (channel), median / max | %s |" % (
            "%.1f / %.1f dB" % (sorted(levels)[len(levels) // 2], max(levels)) if levels else "-"),
        "| Dropped blocks | %d |" % ((rows[-1]["dropped"] - rows[0]["dropped"]) if rows else 0),
        "",
        "![Timeline](timeline.png)",
        "",
        "## Packet types",
        "",
        "| Type | Frames |",
        "|---|---|",
    ] + ["| %s | %d |" % (k, n) for k, n in kinds.most_common()] + [
        "",
        "## Stations",
        "",
        "| Station | Frames | Position | Distance, bearing |",
        "|---|---|---|---|",
    ]
    for s, n in srcs.most_common():
        p = pos.get(s)
        db = dist_brg(lat0, lon0, p[0], p[1]) if p and lat0 is not None else None
        L.append("| %s | %d | %s | %s |" % (s, n, "%.4f, %.4f" % (p[0], p[1]) if p else "-",
                                         "%.1f km, %.0f°" % db if db else "-"))
    L += ["", "## Digipeaters (frames repeated by)", "", "| Digipeater | Frames |", "|---|---|"]
    L += ["| %s | %d |" % (d, n) for d, n in digis.most_common()] or ["| - | - |"]
    if pos:
        L += ["", "![Positions](map.png)"]
    L += ["", "All frames: [frames.jsonl](frames.jsonl); receiver status every 5 s: [status.csv](status.csv)."]
    open(os.path.join(out, "report.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ip", default="192.168.1.11")
    ap.add_argument("--pin", default="1027")
    ap.add_argument("--minutes", type=float, default=60)
    ap.add_argument("--name", default="aprs-ground")
    ap.add_argument("--start", type=float, help="switch the terrestrial APRS mode on at this frequency (Hz)")
    ap.add_argument("--out")
    ap.add_argument("--report", metavar="DIR", help="only write the report of an earlier (stopped) run in DIR")
    a = ap.parse_args()
    ph = Phone(a.ip, a.pin)
    if a.report:
        frames = [json.loads(l) for l in open(os.path.join(a.report, "frames.jsonl"), encoding="utf-8") if l.strip()]
        rows = []
        for r in csv.DictReader(open(os.path.join(a.report, "status.csv"))):
            if r["t"] == "t":
                continue
            rows.append({"t": float(r["t"]), "level_db": float(r["level_db"]) if r["level_db"] else None,
                         "bad_crc": int(float(r["bad_crc"])), "dropped": int(float(r["dropped"])), "count": int(float(r["count"]))})
        st0 = ph.status()
        report(a.report, frames, rows, st0, time.strftime("%Y-%m-%d %H:%M", time.localtime(rows[0]["t"])))
        print("report:", os.path.join(a.report, "report.md"))
        return
    if a.start:
        ph.cmd(cmd="ground_aprs", on=True, hz=a.start)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out = a.out or os.path.join(root, "measurements", time.strftime("%Y-%m-%d_%H%M") + "_" + a.name)
    os.makedirs(out, exist_ok=True)
    st0 = ph.status()
    started = time.strftime("%Y-%m-%d %H:%M")
    since = ph._req("GET", "/aprs?since=0")["count"]
    frames, rows = [], []
    fj = open(os.path.join(out, "frames.jsonl"), "a", encoding="utf-8")
    fc = open(os.path.join(out, "status.csv"), "a", newline="")
    w = csv.writer(fc)
    w.writerow(["t", "level_db", "bad_crc", "dropped", "count"])
    end = time.time() + a.minutes * 60
    try:
        while time.time() < end:
            try:
                st = ph.status()
                r = ph._req("GET", "/aprs?since=%d" % since)
            except SystemExit as e:
                print("  (phone: %s)" % e)
                time.sleep(10)
                continue
            for f in r["frames"]:
                since = max(since, f["n"])
                frames.append(f)
                fj.write(json.dumps(f) + "\n")
                print(time.strftime("%H:%M:%S"), f["tnc2"][:110])
            row = {"t": time.time(), "level_db": st.get("level_db"), "bad_crc": r.get("bad_crc", 0),
                   "dropped": st.get("dropped", 0), "count": r.get("count", 0)}
            rows.append(row)
            w.writerow([round(row["t"], 1), row["level_db"], row["bad_crc"], row["dropped"], row["count"]])
            fj.flush()
            fc.flush()
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    if rows:
        report(out, frames, rows, st0, started)
    print("\n%d frames, report: %s" % (len(frames), os.path.join(out, "report.md")))


if __name__ == "__main__":
    main()
