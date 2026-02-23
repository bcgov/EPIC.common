#! /bin/sh
echo 'run invoke_jobs.py EXTRACT_PROJECTS'
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
python3 invoke_jobs.py SUBMIT