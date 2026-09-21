#!/usr/bin/env python3
"""Drive the Zephyr shell on ZMK's USB console to probe the Toucan right half.

usage: shell_probe.py <port-glob> [hold_seconds]
"""
import glob
import re
import sys
import time

import serial

pattern = sys.argv[1]
hold = float(sys.argv[2]) if len(sys.argv) > 2 else 8

ROWS = [("gpio@50000000", 19), ("gpio@50000000", 28), ("gpio@50000000", 29), ("gpio@50000300", 1)]
COLS = [("gpio@50000300", 12), ("gpio@50000300", 11), ("gpio@50000000", 5),
        ("gpio@50000000", 10), ("gpio@50000000", 4), ("gpio@50000000", 9)]
TP = {"RDY": ("gpio@50000000", 2), "RST": ("gpio@50000300", 14),
      "SDA": ("gpio@50000300", 13), "SCL": ("gpio@50000300", 15)}

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def open_port():
    while True:
        ports = [p for p in glob.glob(pattern) if '31201' not in p]
        if ports:
            try:
                s = serial.Serial(ports[0], 115200, timeout=0.1)
                s.dtr = True
                s.rts = True
                return s
            except (serial.SerialException, OSError):
                pass
        time.sleep(0.2)


def cmd(s, line, wait=0.4):
    s.reset_input_buffer()
    s.write((line + "\r\n").encode())
    time.sleep(wait)
    out = ANSI.sub("", s.read(8192).decode("utf-8", "replace"))
    # strip echo/prompt noise
    lines = [l.strip() for l in out.replace("\r", "\n").splitlines()]
    lines = [l for l in lines if l and not l.startswith("uart:~$") and l != line]
    return lines


def gpio_get(s, dev, pin):
    out = cmd(s, f"gpio get {dev} {pin}", 0.25)
    for l in out:
        m = re.match(r"Value ([01])$", l.strip())
        if m:
            return int(m.group(1))
    return "?"


def read_rows(s):
    return [gpio_get(s, d, p) for d, p in ROWS]


s = open_port()
print(f"opened {s.port}")
time.sleep(1.0)
print("\n--- shell sanity ---")
print("\n".join(cmd(s, "kernel version")))
print("\n".join(cmd(s, "kernel uptime")))

print("\n--- I2C scan (expect 0x74 = trackpad) ---")
print("\n".join(cmd(s, "i2c scan i2c@40003000", 1.5)))

print("\n--- trackpad control pins ---")
for name, (d, p) in TP.items():
    print(f"  {name:>3} {d} pin {p}: {gpio_get(s, d, p)}")

print("\n--- matrix rows, idle (expect all 0) ---")
print("  rows P0.19 P0.28 P0.29 P1.01 =", read_rows(s))

print("\n--- columns as currently driven by kscan (all 0 between scans is normal) ---")
print("  cols P1.12 P1.11 P0.05 P0.10 P0.04 P0.09 =", [gpio_get(s, d, p) for d, p in COLS])

print(f"\n### HOLD DOWN 2-3 KEYS on the right half now, for {hold:.0f}s ###", flush=True)
end = time.time() + hold
samples = []
while time.time() < end:
    samples.append(tuple(read_rows(s)))
seen = sorted(set(samples))
print("  distinct row readings while keys held:", seen)

print("\n--- force each column HIGH and read rows (HOLD keys still) ---")
for (cd, cp) in COLS:
    cmd(s, f"gpio conf {cd} {cp} o", 0.15)
    cmd(s, f"gpio set {cd} {cp} 1", 0.15)
    r = read_rows(s)
    cmd(s, f"gpio set {cd} {cp} 0", 0.1)
    print(f"  col {cd} pin {cp:>2} high -> rows {r}")

print(f"\n### NOW TOUCH / SWIPE THE TRACKPAD for {hold:.0f}s ###", flush=True)
s.reset_input_buffer()
time.sleep(hold)
out = ANSI.sub("", s.read(65536).decode("utf-8", "replace"))
tp_lines = [l for l in out.splitlines() if "tps43" in l or "kscan" in l.lower() or "Sending event" in l]
print(f"  {len(tp_lines)} tps43/kscan log lines during touch:")
print("\n".join("   " + l.strip() for l in tp_lines[:40]))
print("\n--- RDY pin after touching ---")
print("  RDY =", gpio_get(s, *TP["RDY"]))
s.close()
