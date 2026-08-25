#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
swiftc -parse-as-library -O -o AudioTap AudioTap.swift \
  -framework CoreAudio \
  -framework AVFoundation \
  -framework CoreGraphics \
  -framework Foundation
