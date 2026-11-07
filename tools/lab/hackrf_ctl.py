"""Send one command to hackrf_server.py:  python tools/lab/hackrf_ctl.py status|quit|silence"""
import json
import socket
import sys

c = socket.create_connection(("127.0.0.1", 5125), timeout=10)
c.sendall((json.dumps({"cmd": sys.argv[1] if len(sys.argv) > 1 else "status"}) + "\n").encode())
print(c.makefile("r").readline().strip())
