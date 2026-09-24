#!/usr/bin/env sh
set -eu

python3 -m pytest -q
python3 -m compileall -q src benchmarks tests

