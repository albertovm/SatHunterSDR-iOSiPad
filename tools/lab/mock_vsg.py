#!/usr/bin/env python3
"""A stand-in for the VSG software's SCPI server: answers like the VSG60 does and logs every
command, so lab.py's generator control can be checked without the hardware.

    python tools/lab/mock_vsg.py [port]      (default 5124)
"""
import os, socket, sys, threading

def serve(conn, log):
    f = conn.makefile("rwb")
    state = {"loaded": None, "len": 0, "esr": 0}
    for raw in f:
        c = raw.decode().strip()
        log.write(c + "\n"); log.flush()
        u = c.upper()
        ans = None
        if u == "*IDN?":
            ans = "SignalHound,VSG60,MOCK,6"
        elif u == "*OPC":
            state["esr"] = 1
        elif u == "*ESR?":
            ans, state["esr"] = str(state["esr"]), 0
        elif u.startswith(":SYSTEM:ERROR?"):
            ans = '0,"No error"'
        elif u.startswith(":SOURCE:RADIO:ARB:WAVEFORM:LOAD:BINFC"):
            path = c.split('"')[1]
            # the mock runs on the same machine: read the file to know its length
            try:
                state["len"] = os.path.getsize(path) // 8
                state["loaded"] = path
            except OSError:
                state["loaded"] = None
        elif u == ":SOURCE:RADIO:ARB:WAVEFORM:LOAD?":
            ans = "1" if state["loaded"] else "0"
        elif u == ":SOURCE:RADIO:ARB:WAVEFORM:LENGTH?":
            ans = str(state["len"])
        if ans is not None:
            f.write((ans + "\n").encode()); f.flush()
    conn.close()

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5124
    log = open(sys.argv[2] if len(sys.argv) > 2 else os.devnull, "w")
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", port)); s.listen(1)
    print(f"mock VSG60 SCPI on 127.0.0.1:{port}", flush=True)
    while True:
        c, _ = s.accept()
        threading.Thread(target=serve, args=(c, log), daemon=True).start()

if __name__ == "__main__":
    main()
