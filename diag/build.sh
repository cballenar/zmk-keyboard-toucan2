#!/bin/sh
# Local ZMK build via docker, mirroring zmkfirmware/zmk's build-user-config.yml.
#
#   ./build.sh <name> <shield...> [-S <snippet>] [-- <extra cmake args>]
#
# Examples:
#   ./build.sh right         "toucan_right rgbled_adapter"
#   ./build.sh diag_log      "toucan_right rgbled_adapter" -S toucan-diag-log
#   ./build.sh left          "toucan_left rgbled_adapter nice_view_gem" -S studio-rpc-usb-uart -- -DCONFIG_ZMK_STUDIO=y
#
# Output: artifacts/<name>.uf2
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)
TOUCAN="$HERE/../zmk-keyboard-toucan2"
BOARD=${BOARD:-seeeduino_xiao_ble}

NAME=$1; shift
SHIELD=$1; shift

SNIPPET_ARG=""
while [ "${1:-}" = "-S" ]; do
  SNIPPET_ARG="$SNIPPET_ARG -S $2"; shift 2
done
if [ "${1:-}" = "--" ]; then shift; fi

mkdir -p "$HERE/artifacts"

docker run --rm \
  -v "$HERE":/ws \
  -v "$TOUCAN":/ws/toucan \
  -w /ws \
  -e ZEPHYR_BASE=/ws/zephyr \
  zmkfirmware/zmk-build-arm:3.5 \
  bash -c "git config --global --add safe.directory '*' >/dev/null;
    west zephyr-export >/dev/null;
    west build -p auto -s zmk/app -d build/$NAME -b $BOARD $SNIPPET_ARG -- \
      -DZMK_CONFIG=/ws/toucan/config \
      -DZMK_EXTRA_MODULES=/ws/toucan \
      -DSHIELD=\"$SHIELD\" $* \
    && cp build/$NAME/zephyr/zmk.uf2 artifacts/$NAME.uf2"

echo "==> artifacts/$NAME.uf2"
