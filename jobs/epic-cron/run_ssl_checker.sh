#! /bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname "$0")" && pwd)

echo 'run invoke_jobs.py CHECK_SSL'
cd "$SCRIPT_DIR"
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$SCRIPT_DIR/src"
python3 invoke_jobs.py CHECK_SSL
