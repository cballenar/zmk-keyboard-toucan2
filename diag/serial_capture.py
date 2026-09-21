#!/usr/bin/env python3
"""Capture ZMK USB CDC-ACM console output, surviving device resets.

usage: serial_capture.py <port-glob> <seconds> [outfile]
e.g.   serial_capture.py '/dev/cu.usbmodem*' 30 out.log
Requires pyserial. Strips ANSI colour codes. Reconnects if the device
disappears (reset / re-enumeration) so boot logs are captured.
"""
import glob
import re
import sys
import time

import serial

pattern = sys.argv[1]
seconds = float(sys.argv[2])
out = sys.argv[3] if len(sys.argv) > 3 else None

end = time.time() + seconds
buf = b""
s = None
while time.time() < end:
    if s is None:
        ports = glob.glob(pattern)
        if '*' in pattern:
            # Wildcard: skip the left's Studio RPC CDC port.
            ports = [p for p in ports if '31201' not in p]
        if not ports:
            time.sleep(0.1)
            continue
        try:
            s = serial.Serial(ports[0], 115200, timeout=0.2)
            s.dtr = True
            s.rts = True
            buf += f"\n=== opened {ports[0]} at +{seconds - (end - time.time()):.1f}s ===\n".encode()
        except (serial.SerialException, OSError):
            s = None
            time.sleep(0.2)
            continue
    try:
        buf += s.read(4096)
    except (serial.SerialException, OSError):
        buf += b"\n=== port lost (device reset?) ===\n"
        try:
            s.close()
        except Exception:
            pass
        s = None
        time.sleep(0.3)

if s is not None:
    s.close()

txt = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", buf.decode("utf-8", "replace"))
if out:
    with open(out, "w") as f:
        f.write(txt)
lines = txt.splitlines()
print(f"--- captured {len(lines)} lines ---")
print("\n".join(lines))
