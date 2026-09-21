# Toucan2 right-half "dead" — diagnosis notes / handoff

Board: beekeeb Toucan2, ZMK v0.3, Seeeduino XIAO nRF52840 **Plus** ×2, Azoteq TPS43
trackpad on right, nice!view on left, USB power only (no batteries).
Symptom: right (BLE peripheral) registers **no keys and no trackpad**; left (central)
shows it "connected"; reflashing old firmware and `settings_reset` on both didn't help.

## ROOT CAUSE (confirmed 2026-09-21)

**Bond mismatch on the split link.** The left half holds a bond (LTK) for the right,
but the right no longer has the matching key. Encryption therefore fails, and every
GATT operation that requires encryption fails — which is exactly the split
position-state (keys) and input (trackpad) characteristics, whose CCC descriptors
require `BT_GATT_PERM_WRITE_ENCRYPT`. Battery Service needs no encryption, so it
"works", which is why the left shows the right as connected/with battery.

Evidence, left half log (`artifacts/left_capture.log`, central with BT debug):

```
split_central_process_connection: Current security for connection: 1
Found battery level characteristics -> [SUBSCRIBED]
gatt_write_ccc: handle 0x0013 value 0x0001      (BAS CCC)
gatt_write_ccc_rsp: err 0x00                    (OK)
Found position state characteristic -> [SUBSCRIBED]
gatt_write_ccc: handle 0x001f value 0x0001      (position-state CCC)
gatt_write_ccc_rsp: err 0x05                    (ATT Insufficient Authentication)
split_central_notify_func: [UNSUBSCRIBED]
<err> zmk: Security failed: FF:C2:D1:52:E8:50 (random) level 1 err 2
```

`err 2` = `BT_SECURITY_ERR_PIN_OR_KEY_MISSING`. Right half log (`artifacts/last_capture.log`)
shows the matching symptom: every key press reaches the split layer and dies with
`send_position_state_callback: Error notifying -128` (`-ENOTCONN`, no subscriber) and
no `Security changed` line ever appears after "Peripheral connected".

Why earlier `settings_reset` attempts didn't fix it: Flashing `settings_reset` to only one half at a time (or allowing one half to reboot on normal firmware before the other half is wiped) is a known ZMK anti-pattern. If one half turns its Bluetooth radio on while the other half holds a "stale" bond, it triggers an asymmetrical pairing state. The ZMK documentation explicitly requires flashing `settings_reset` to both halves simultaneously before flashing standard firmware to either side to prevent this exact issue.

## RESOLVED 2026-09-21 — Postmortem

**What happened.** After a routine settings-reset/re-pair cycle (during which the right
half's reset button was not reliably registering double-taps), the right half stopped
sending any key/trackpad input while the left still reported it connected. Several
reflashes of known-good firmware and further `settings_reset` attempts didn't help.

**What caused it.** A split-link **bond mismatch**. The left (central) retained an LTK
for the right, but the right (peripheral, `CONFIG_BT_MAX_PAIRED=1`) no longer had the
matching key — because they were not `settings_reset` simultaneously in the same session, causing them to re-pair asymmetrically. This is a common and known issue in ZMK split configurations if standard firmware is booted on either side before both halves have been fully wiped. On every connection
the left subscribed to Battery Service (unencrypted, so "connected + battery" looked
fine), then tried to write the position-state CCC, got ATT `0x05` Insufficient
Authentication, tried to encrypt with the stale key, and got `Security failed ... err 2`
(PIN_OR_KEY_MISSING). The encrypted key/trackpad notifications were therefore never
subscribed; the right logged `Error notifying -128 (-ENOTCONN)` on each key press.
Reflashing firmware never clears the settings partition, so the stale bond persisted.

**The fix.** Flash `settings_reset` to BOTH halves back-to-back (right via the `dfu`
shell command, left via double-tap), let each boot, then flash real firmware to both.
Verified afterwards on the left console: `Security changed ... level 2`,
`gatt_write_ccc_rsp: err 0x00` for handle `0x001f`, and right-half key events arriving
(`artifacts/left_after_fix.log`).

**How to prevent / recover faster next time.**
- Always settings-reset **both** halves in the same session, and don't boot either half
  on real firmware until both have run it. This is standard ZMK protocol for any split connection issues.
- Symptom signature to recognise: left shows right connected and shows its battery,
  but no keys/trackpad → it is a bond/encryption problem, not hardware. Skip the
  hardware probing and go straight to a dual settings reset.
- Keep a local `settings_reset.uf2` built (`./build.sh settings_reset settings_reset`).
- Consider keeping an opt-in shell/`dfu` snippet so the right can enter the bootloader
  without the reset button.

## Hardware verified healthy (right half, via Zephyr shell over USB)

- I2C scan finds trackpad at 0x74; tps43 inits and streams motion on touch.
- All 4 rows (P0.19/P0.28/P1.01/P0.29) and 6 cols (P1.12/P1.11/P0.05/P0.10/P0.04/P0.09)
  read/drive correctly; kscan emits `Sending event at r,c` in IRQ and polling modes.
- Boot LED green→blue when left is on (BLE + event manager OK).
- `qspi_nor JEDEC id` error is benign (Plus variant). Battery ADC bounce is benign (no battery).
- The earlier "P1.01 stuck high" finding was a log-parser bug; retracted.

## FIX PROCEDURE (do this next)

Goal: clear bonds on **both** halves in the **same session**, then let them pair fresh.

1. Build `settings_reset` locally (may already be done — check
   `artifacts/settings_reset.uf2`; build log in `artifacts/settings_reset_build.log`):
   `./build.sh settings_reset "settings_reset"`
2. Flash `settings_reset.uf2` to the RIGHT (right currently runs a shell build, so
   `PORT=/dev/cu.usbmodem31101 ./dfu_flash.sh artifacts/settings_reset.uf2` works
   without the button). Let it boot ≥5 s.
3. Flash `settings_reset.uf2` to the LEFT (double-tap reset → `XIAO-BOOT` →
   `cp artifacts/settings_reset.uf2 /Volumes/XIAO-BOOT/`). Let it boot ≥5 s.
   **Do not power either half with real firmware until both have run settings_reset.**
4. Flash real firmware: RIGHT first (double-tap reset; settings_reset has no `dfu`),
   e.g. `artifacts/diag_right_shell_irq.uf2` for one more verified run, or stock
   `artifacts/right.uf2`. Then LEFT (`artifacts/diag_left_shell.uf2` to verify, or stock).
5. Power both, wait ~10 s. Verify on the left console (`/dev/cu.usbmodem31201`):
   expect `Security changed: ... level 2`, `gatt_write_ccc_rsp: err 0x00` for
   handle `0x001f`, and `Trigger key position state change` on right key presses.
   Capture: `$TMPDIR/venv/bin/python serial_capture.py /dev/cu.usbmodem31201 30 artifacts/left_after_fix.log`
6. If it still fails with `Security failed ... err 2`: also delete the left's
   host bonds/profile (`&bt BT_CLR_ALL` in keymap) and confirm the right actually
   ran settings_reset (its LED pattern / re-enumeration). As a last resort, consider
   raising `CONFIG_BT_MAX_PAIRED` on the right (in `toucan_right.conf`) is NOT the
   fix — keep it 1; the fix is a simultaneous clean pair.
7. Once working, restore stock builds:
   - Left: `./build.sh left "toucan_left rgbled_adapter nice_view_gem" -S studio-rpc-usb-uart -- -DCONFIG_ZMK_STUDIO=y`
   - Right: `./build.sh right "toucan_right rgbled_adapter"`
   Optionally keep the `dfu` shell command as an opt-in snippet (`toucan-diag-shell*`).

## Secondary / unexplained

- USB battery bank shuts off instantly with the right half: likely just low current
  draw (no battery charging, radio idle) tripping the bank's auto-off. Re-test after fix.

## Tooling (all local, Docker)

Repo copy of the tooling lives in `diag/` (scripts + `west.yml` manifest + scrubbed logs). Workspace: `keyboard/zmk-build/` (gitignored west workspace; toucan repo mounted at
`/ws/toucan`). Image must be `zmkfirmware/zmk-build-arm:3.5`.

- `build.sh <name> "<shields>" [-S snip]... [-- cmake args]` → `artifacts/<name>.uf2`
- `dfu_flash.sh <uf2> [capture_s]` — sends `dfu` to a shell build (default port
  `/dev/cu.usbmodem31101`), waits for `XIAO-BOOT`, copies, optional capture.
- `serial_capture.py <port|glob> <secs> [out]` — pyserial at `$TMPDIR/venv/bin/python`.
  Wildcard skips `31201`; pass an explicit port to read the left.
- `shell_probe.py`, `pin_probe.py` — GPIO/I2C probes via Zephyr shell.
- Ports: right = `/dev/cu.usbmodem31101`, left = `/dev/cu.usbmodem31201`.
  Both enumerate as "Toucan"; right serial `F11D7F7048430FBB`, left `C20EAAD7D0A5AA58`
  (`ioreg -p IOUSB -l -w0 -r -n Toucan`).

Toucan repo (`keyboard/zmk-keyboard-toucan2`, branch `diag/right-half`, uncommitted):
`zephyr/module.yml` (module + snippet_root), `Kconfig`/`CMakeLists.txt`/`src/diag_shell.c`
(`dfu` command), snippets `toucan-diag-log`, `toucan-diag-notp`, `toucan-diag-shell`,
`toucan-diag-shell-irq`, `toucan-diag-bt` (BT GATT/SMP debug — prints keys, never ship),
`build.yaml` diag entries.

Current state of hardware: RIGHT runs `diag_right_shell_irq`, LEFT runs `diag_left_shell`
(console+shell, no Studio). Both are diagnostic builds.

## Pitfalls

- **Double-check which half is in bootloader**: both mount as `XIAO-BOOT`. Earlier the
  right was accidentally flashed with the left image (harmless, recovered via `dfu`).
- `zmk-build-arm:stable` (Zephyr 4.1) fails; use `:3.5`. Run `west zephyr-export` per container.
- Disabling `tps43_trackpad` alone breaks linking; also disable `trackpad_split`.
- `CONFIG_SENSOR_SHELL=n` is required when enabling `CONFIG_SHELL` in ZMK.
- CDC console needs the port opened RW with DTR asserted; macOS `screen` is too old.
- Sandbox blocks `/dev/cu.*` writes and `/tmp`; run unsandboxed, use `$TMPDIR`.
