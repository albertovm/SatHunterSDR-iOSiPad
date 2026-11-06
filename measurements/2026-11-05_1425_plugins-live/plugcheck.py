import sys, time, json
sys.path.insert(0, r"C:\Users\RF\SatHunter-SDR\tools\lab")
from lab import Phone, Vsg60Gen
from rx_extra import aprs_waveform

p = Phone("192.168.1.11", "1027")
g = Vsg60Gen(34.7, "127.0.0.1", 5124, r"C:\sathunter_lab", None)
try:
    p.cmd(cmd="mode", mode="NFM", bw=12500.0)
    p.cmd(cmd="tune", hz=436.6e6)
    p.cmd(cmd="aprs", on=True)
    p.cmd(cmd="plugins", on=True)
    p.cmd(cmd="aprs_clear")
    iq, loop_s = aprs_waveform(50e3, 3000.0)
    g.play(436.6e6, -105, "sathunter_aprs_3000.cf32", iq, 50e3)
    time.sleep(40)
    a = p._req("GET", "/aprs?since=0")
    pl = p._req("GET", "/plugins?since=0")
    print("frames", a["count"], "bad", a["bad_crc"])
    print("plugins", pl["plugins"], "errors", pl["errors"], "outputs", pl["count"])
    for o in pl["out"][-6:]:
        print(o["plugin"], o["line"])
    json.dump({"aprs": a, "plugins": pl}, open(r"D:\Measurements\plugcheck.json", "w"), indent=1)
finally:
    g.close()
