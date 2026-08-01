#!/usr/bin/env bash
# Compile (and optionally flash) the camp-sign DMX bridge.
#   ./build.sh            compile only
#   ./build.sh flash      compile + upload over USB (/dev/ttyACM0)
#   ./build.sh ota [host] compile + upload over Wi-Fi (default lohp-sign-bridge.local)
#   ./build.sh monitor    serial monitor — '?' lists the bench commands
set -eu
cd "$(dirname "$0")"
PORT=${SIGN_PORT:-/dev/ttyACM0}
# XIAO ESP32-S3 board defaults are already right for this box: hardware-CDC USB
# with CDC on boot, default_8MB partitions = two OTA app slots.
FQBN="esp32:esp32:XIAO_ESP32S3"

[ -f secrets.h ] || ./gen_secrets.sh

case "${1:-compile}" in
  compile) arduino-cli compile --build-property compiler.optimization_flags=-O2 --fqbn "$FQBN" . ;;
  flash)   arduino-cli compile --build-property compiler.optimization_flags=-O2 --fqbn "$FQBN" .
           arduino-cli upload -p "$PORT" --fqbn "$FQBN" . ;;
  ota)     arduino-cli compile --build-property compiler.optimization_flags=-O2 --fqbn "$FQBN" --export-binaries .
           ESPOTA=$(ls "$HOME"/.arduino15/packages/esp32/hardware/esp32/*/tools/espota.py | head -1)
           AUTH=$(grep OTA_PASSWORD secrets.h | cut -d'"' -f2)
           python3 "$ESPOTA" -i "${2:-lohp-sign-bridge.local}" -p 3232 --auth="$AUTH" \
             -f build/esp32.esp32.XIAO_ESP32S3/sign.ino.bin ;;
  monitor) exec arduino-cli monitor -p "$PORT" -c baudrate=115200 ;;
  *) echo "usage: $0 [compile|flash|ota [host]|monitor]"; exit 1 ;;
esac
