#!/usr/bin/env bash
# Build Fjellrune in one command:  sources/build.sh
#   1. sources/build_fjellrune.py draws every glyph and writes the UFO source
#   2. gftools builder compiles, hints and checks it into fonts/ttf and fonts/webfonts
#   3. the specimen page is rebuilt and the bind-rune medallion feature is smoke-tested
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d "venv/bin" ]; then
  export PATH="$PWD/venv/bin:$PATH"
fi
python3 sources/build_fjellrune.py --ufo sources/ufo
(cd sources && gftools builder config.yaml)
python3 sources/tools/add_stat.py fonts/ttf fonts/webfonts
python3 sources/build_specimen.py --fonts fonts/webfonts --ttf fonts/ttf --out documentation/specimen/index.html
python3 sources/tools/check_monograms.py fonts/ttf
