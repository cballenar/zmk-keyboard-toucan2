#!/bin/sh
# Reboot the right half into the UF2 bootloader via the diag shell's `dfu`
# command, flash a UF2, and (optionally) capture the console afterwards.
#
#   ./dfu_flash.sh <uf2> [capture_seconds]
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
UF2=$1
SECS=${2:-0}
PORT=${PORT:-/dev/cu.usbmodem31101}
PY=${PYTHON:-"$TMPDIR/venv/bin/python"}
[ -x "$PY" ] || PY=python3

if [ ! -f /Volumes/XIAO-BOOT/INFO_UF2.TXT ]; then
  if [ -e "$PORT" ]; then
    echo "sending 'dfu' to $PORT"
    "$PY" - "$PORT" <<'EOF'
import serial, sys, time
s = serial.Serial(sys.argv[1], 115200, timeout=0.2); s.dtr = True
time.sleep(0.3); s.write(b"\r\ndfu\r\n"); time.sleep(0.3)
try: s.close()
except Exception: pass
EOF
  else
    echo "no console at $PORT; double-tap reset manually"
  fi
  i=0
  while [ ! -f /Volumes/XIAO-BOOT/INFO_UF2.TXT ]; do
    sleep 1; i=$((i+1))
    [ $i -ge 120 ] && { echo "timed out waiting for XIAO-BOOT"; exit 1; }
  done
  echo "bootloader up after ${i}s"
fi
sleep 1
cp "$UF2" /Volumes/XIAO-BOOT/
echo "flashed $(basename "$UF2")"
if [ "$SECS" -gt 0 ]; then
  echo "capturing $PORT for ${SECS}s"
  "$PY" "$HERE/serial_capture.py" "$PORT" "$SECS" "$HERE/artifacts/last_capture.log"
fi
