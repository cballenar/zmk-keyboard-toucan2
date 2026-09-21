#!/usr/bin/env python3
"""Electrically characterise the suspect row P1.01 via the Zephyr gpio shell.

usage: pin_probe.py <port-glob>
Shell conf modes in this Zephyr: in | inu | ind | out ; set <pin> 0|1
"""
import glob
import re
import sys
import time

import serial

pattern = sys.argv[1]
P0, P1 = "gpio@50000000", "gpio@50000300"
ROWS = {"P0.19": (P0, 19), "P0.28": (P0, 28), "P0.29": (P0, 29), "P1.01": (P1, 1)}
COLS = {"P1.12": (P1, 12), "P1.11": (P1, 11), "P0.05": (P0, 5), "P0.10": (P0, 10), "P0.04": (P0, 4), "P0.09": (P0, 9)}
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def open_port():
    while True:
        for p in [p for p in glob.glob(pattern) if '31201' not in p]:
            try:
                s = serial.Serial(p, 115200, timeout=0.1)
                s.dtr = True; s.rts = True
                return s
            except (serial.SerialException, OSError):
                pass
        time.sleep(0.2)


def cmd(s, line, wait=0.25):
    s.reset_input_buffer()
    s.write((line + "\r\n").encode())
    time.sleep(wait)
    out = ANSI.sub("", s.read(16384).decode("utf-8", "replace"))
    return [l.strip() for l in out.replace("\r", "\n").splitlines()
            if l.strip() and not l.strip().startswith("uart:~$") and l.strip() != line]


def get(s, dev, pin):
    out = cmd(s, f"gpio get {dev} {pin}", 0.25)
    for l in out:
        m = re.match(r"Value ([01])$", l.strip())
        if m:
            return int(m.group(1))
    return "?"


def conf(s, dev, pin, mode):
    out = cmd(s, f"gpio conf {dev} {pin} {mode}", 0.15)
    assert any("Configuring" in l for l in out), f"conf failed: {out}"


def setv(s, dev, pin, v):
    cmd(s, f"gpio set {dev} {pin} {v}", 0.15)


s = open_port()
time.sleep(0.5)

print("=== all rows: reading under each input configuration ===")
print(f"  {'row':6s} {'no-pull':>8s} {'pull-up':>8s} {'pull-dn':>8s}")
for name, (d, p) in ROWS.items():
    r = []
    for mode in ("in", "inu", "ind"):
        conf(s, d, p, mode); time.sleep(0.05); r.append(get(s, d, p))
    print(f"  {name:6s} {r[0]:>8} {r[1]:>8} {r[2]:>8}")

print("\n=== drive test on P1.01 (decisive: can the MCU pull it low?) ===")
d, p = ROWS["P1.01"]
conf(s, d, p, "out")
setv(s, d, p, 0); time.sleep(0.05); lo = get(s, d, p)
setv(s, d, p, 1); time.sleep(0.05); hi = get(s, d, p)
print(f"  P1.01 driven LOW  reads {lo}   (healthy: 0; 1 = shorted to a high net or pin damaged)")
print(f"  P1.01 driven HIGH reads {hi}")
print("  other pins while P1.01 is driven LOW:")
setv(s, d, p, 0); time.sleep(0.05)
for name, (od, op) in {**ROWS, **COLS, "SDA P1.13": (P1, 13), "SCL P1.15": (P1, 15), "RST P1.14": (P1, 14), "RDY P0.02": (P0, 2)}.items():
    if (od, op) == (d, p): continue
    print(f"    {name:10s} = {get(s, od, op)}")
conf(s, d, p, "ind")

print("\n=== same drive test on healthy row P0.28 for comparison ===")
d2, p2 = ROWS["P0.28"]
conf(s, d2, p2, "out")
setv(s, d2, p2, 0); time.sleep(0.05); lo2 = get(s, d2, p2)
setv(s, d2, p2, 1); time.sleep(0.05); hi2 = get(s, d2, p2)
print(f"  P0.28 driven LOW reads {lo2}, driven HIGH reads {hi2}")
conf(s, d2, p2, "ind")

print("\n=== coupling: drive each column HIGH then LOW, watch P1.01 (input pull-down) ===")
for name, (cd, cp) in COLS.items():
    conf(s, cd, cp, "out")
    setv(s, cd, cp, 1); time.sleep(0.05); a = get(s, d, p)
    setv(s, cd, cp, 0); time.sleep(0.05); b = get(s, d, p)
    print(f"  col {name}: P1.01 = {a} (col high) / {b} (col low)")

print("\n=== coupling: hold SDA/SCL/RST low via GPIO, watch P1.01 ===")
for name, (xd, xp) in {"SDA P1.13": (P1, 13), "SCL P1.15": (P1, 15), "RST P1.14": (P1, 14)}.items():
    conf(s, xd, xp, "out"); setv(s, xd, xp, 0); time.sleep(0.05)
    print(f"  {name} low -> P1.01 = {get(s, d, p)}")
    setv(s, xd, xp, 1)
s.close()
print("\n(note: I2C pins were toggled; reboot the board before trusting trackpad again)")
