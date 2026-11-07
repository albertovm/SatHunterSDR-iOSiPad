"""HackRF generator server: keeps the HackRF open and transmitting for the whole session.

    python tools/lab/hackrf_server.py            (on the PC with the HackRF; leave it running)

Why: on Windows, stopping a HackRF transmission (hackrf_transfer killed, or at EOF) left the
process hung on the USB device, unkillable until the HackRF was replugged (2026-11-07, HackRF One
older than r6, firmware 2026.01.3, libhackrf 2024.02.1). This server opens it once through
SoapySDR, streams continuously (zeros when "off") and changes frequency, gain and waveform live;
it never stops the stream. lab scripts talk to it (hackrf_gen.HackRfGen) over TCP 127.0.0.1:5125,
one JSON object per line:

  {"cmd":"lo","hz":436350000}           LO frequency (the signal sits at LO + its offset)
  {"cmd":"gain","vga":20,"amp":false}   TX VGA 0-47 dB, RF amplifier
  {"cmd":"file","path":"...iq8","scale":0.5}  loop a signed 8-bit IQ file at 2 MS/s, scaled
  {"cmd":"cw","offset":250000,"scale":0.9}  a tone at LO + offset, amplitude 0-1
  {"cmd":"silence"}                     zeros (the stream keeps running)
  {"cmd":"status"}
  {"cmd":"quit"}                        stop the stream properly, close the HackRF and exit
                                        (never kill the server: a killed transmission hangs the
                                        HackRF on Windows until it is replugged)
Run it with libhackrf 2026.01 or newer (radioconda env hackrf2026): with 2024.02.1 even a proper
stop hung the device.
Every reply is one JSON line: {"ok":true,...} or {"ok":false,"error":...}.
"""
import json
import os
import socket
import socketserver
import sys
import threading
import time

import numpy as np

RATE = 2_000_000
PORT = 5125


class Tx:
    def __init__(self):
        import SoapySDR
        from SoapySDR import SOAPY_SDR_TX
        self.S, self.TX = SoapySDR, SOAPY_SDR_TX
        found = SoapySDR.Device.enumerate({"driver": "hackrf"})
        if not found:
            raise SystemExit("no HackRF found by SoapySDR")
        self.dev = SoapySDR.Device(found[0])
        self.dev.setSampleRate(self.TX, 0, RATE)
        self.dev.setBandwidth(self.TX, 0, 1.75e6)
        self.lo = 436.35e6
        self.vga, self.amp = 0, False
        self.dev.setFrequency(self.TX, 0, self.lo)
        self.dev.setGain(self.TX, 0, "VGA", 0)
        self.dev.setGain(self.TX, 0, "AMP", 0)
        self.stream = self.dev.setupStream(self.TX, "CS8")
        self.dev.activateStream(self.stream)
        self.lock = threading.Lock()
        self.buf, self.pos = None, 0
        self.zero = np.zeros(2 * 65536, dtype=np.int8)
        self.written = 0
        self.errors = 0
        self.desc = "silence"
        self.quit = False
        self.scale = 1.0
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        n = 65536  # samples per write
        while not self.quit:
            with self.lock:
                buf = self.buf
                if buf is None:
                    chunk = self.zero
                else:
                    if self.pos >= len(buf):
                        self.pos = 0
                    if len(buf) < 2 * n:
                        reps = (2 * n) // len(buf) + 1
                        buf = np.tile(np.asarray(buf), reps)
                    chunk = buf[self.pos:self.pos + 2 * n]
                    if len(chunk) < 2 * n:  # wrap around the loop
                        chunk = np.concatenate([chunk, buf[:2 * n - len(chunk)]])
                    self.pos = (self.pos + 2 * n) % len(buf)
            if buf is not None and self.scale != 1.0:
                chunk = np.clip(np.round(chunk.astype(np.float32) * self.scale), -127, 127).astype(np.int8)
            chunk = np.ascontiguousarray(chunk, dtype=np.int8)
            off = 0
            while off < n and not self.quit:
                sr = self.dev.writeStream(self.stream, [chunk[2 * off:]], n - off, timeoutUs=1_000_000)
                if sr.ret > 0:
                    off += sr.ret
                    self.written += sr.ret
                else:
                    self.errors += 1
                    time.sleep(0.01)

    def set_buf(self, buf, desc):
        with self.lock:
            self.buf, self.pos, self.desc = buf, 0, desc

    def handle(self, m):
        c = m.get("cmd")
        if c == "lo":
            self.lo = float(m["hz"])
            self.dev.setFrequency(self.TX, 0, self.lo)
        elif c == "gain":
            self.vga = int(m.get("vga", self.vga))
            self.amp = bool(m.get("amp", self.amp))
            self.dev.setGain(self.TX, 0, "VGA", self.vga)
            self.dev.setGain(self.TX, 0, "AMP", 14 if self.amp else 0)
        elif c == "file":
            self.scale = float(m.get("scale", 1.0))
            self.set_buf(np.memmap(m["path"], dtype=np.int8, mode="r"), "%s x%.3f" % (os.path.basename(m["path"]), self.scale))
        elif c == "cw":
            self.scale = 1.0
            off, k = float(m["offset"]), 127 * float(m.get("scale", 1.0))
            n = RATE  # 1 s loop, whole cycles
            cyc = round(off)
            ph = 2 * np.pi * ((cyc * np.arange(n, dtype=np.int64)) % n) / n
            b = np.empty(2 * n, dtype=np.int8)
            b[0::2] = np.round(k * np.cos(ph))
            b[1::2] = np.round(k * np.sin(ph))
            self.set_buf(b, "cw %+d Hz scale %.3f" % (cyc, k / 127))
        elif c == "silence":
            self.set_buf(None, "silence")
        elif c == "quit":
            self.quit = True
            with self.lock:
                self.buf = None
            time.sleep(0.3)
            self.dev.deactivateStream(self.stream)
            self.dev.closeStream(self.stream)
            self.dev = None
            threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0)), daemon=True).start()
            return {"ok": True, "quit": True}
        elif c != "status":
            return {"ok": False, "error": "unknown cmd %r" % c}
        return {"ok": True, "lo": self.lo, "vga": self.vga, "amp": self.amp, "playing": self.desc,
                "written_s": round(self.written / RATE, 1), "underruns": self.errors}


TX = None


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        for line in self.rfile:
            try:
                r = TX.handle(json.loads(line))
            except Exception as e:  # noqa: BLE001
                r = {"ok": False, "error": str(e)}
            self.wfile.write((json.dumps(r) + "\n").encode())


def main():
    global TX
    TX = Tx()
    print("HackRF open, streaming (silence); listening on 127.0.0.1:%d" % PORT, flush=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("127.0.0.1", PORT), Handler) as srv:
        srv.serve_forever()


if __name__ == "__main__":
    main()
