#!/bin/sh
# Wait for the XIAO UF2 bootloader drive, flash a UF2, then capture the USB
# console (CDC-ACM) across the reboot so the boot log is not lost.
#
#   ./flash_and_capture.sh artifacts/diag_right_log.uf2 [capture_seconds]
#
# Double-tap the XIAO reset button so XIAO-BOOT mounts, then run this.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
UF2=$1
SECS=${2:-60}
PY=${PYTHON:-"$TMPDIR/venv/bin/python"}
[ -x "$PY" ] || PY=python3

echo "waiting for /Volumes/XIAO-BOOT ..."
i=0
while [ ! -f /Volumes/XIAO-BOOT/INFO_UF2.TXT ]; do
  sleep 1; i=$((i+1))
  if [ $i -ge 300 ]; then echo "timed out waiting for bootloader"; exit 1; fi
done
sleep 1
cp "$UF2" /Volumes/XIAO-BOOT/
echo "flashed $(basename "$UF2"); capturing console for ${SECS}s (press keys / touch trackpad)"
"$PY" "$HERE/serial_capture.py" '/dev/cu.usbmodem*' "$SECS" "$HERE/artifacts/last_capture.log"
echo "log saved to $HERE/artifacts/last_capture.log"
