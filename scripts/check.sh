#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"
export PYTHONPYCACHEPREFIX="$repo_root/__pycache__"

python3 -m compileall -q pipeline scripts
python3 scripts/check_structure.py
python3 -m unittest discover -s scripts -p 'test_*.py'
python3 -m unittest discover -s pipeline
node pipeline/test_pulse_ui.js
node pipeline/test_pulse_sources.js
node pipeline/test_pulse_trends.js
node pipeline/test_pulse_trend_ui.js
node pipeline/test_page_boot.js
node pipeline/test_reads.js
