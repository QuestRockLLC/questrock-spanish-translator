#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
swiftc -parse-as-library -O -o AudioTap AudioTap.swift \
  -framework ScreenCaptureKit \
  -framework CoreMedia \
  -framework AudioToolbox \
  -framework CoreGraphics \
  -framework Foundation
