"""Start and stop a HackRF transmission in several ways and check the device is free after each
(on Windows, stopping TX hung the old libhackrf 2024.02.1 with firmware 2026.01.3).

    <env>\\python.exe tools/lab/hackrf_stoptest.py     (hackrf_transfer / hackrf_info of that env)
"""
import os
import subprocess
import sys
import time

import numpy as np

BIN = os.path.join(os.path.dirname(sys.executable), "Library", "bin")
TX = os.path.join(BIN, "hackrf_transfer.exe")
INFO = os.path.join(BIN, "hackrf_info.exe")
F = os.path.join(os.path.expanduser("~"), "stoptest.iq8")
if not os.path.exists(F):
    np.zeros(2 * 2_000_000, dtype=np.int8).tofile(F)
BASE = [TX, "-f", "436350000", "-s", "2000000", "-x", "0", "-a", "0"]


def free():
    r = subprocess.run([INFO], capture_output=True, text=True, timeout=20)
    return "Serial number" in r.stdout and "failed" not in (r.stdout + r.stderr)


def alive(p, secs=8):
    try:
        p.wait(secs)
        return False
    except subprocess.TimeoutExpired:
        return True


print("lib:", subprocess.run([INFO], capture_output=True, text=True).stdout.splitlines()[:2], flush=True)
results = []
for k in range(3):
    p = subprocess.Popen(BASE + ["-t", F, "-n", "4000000"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hung = alive(p, 15)
    results.append(("self-end", k, not hung, free()))
    print(results[-1], flush=True)
    if hung:
        break
    p = subprocess.Popen(BASE + ["-t", "-"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        p.stdin.write(bytes(1 << 18))
    p.stdin.close()
    hung = alive(p)
    results.append(("stdin-EOF", k, not hung, free()))
    print(results[-1], flush=True)
    if hung:
        break
    p = subprocess.Popen(BASE + ["-t", F, "-R"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    p.terminate()
    hung = alive(p)
    time.sleep(1)
    results.append(("killed", k, not hung, free()))
    print(results[-1], flush=True)
    if hung:
        break
print("ALL OK" if all(r[2] and r[3] for r in results) else "PROBLEM", results, flush=True)
