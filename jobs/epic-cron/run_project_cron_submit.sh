#! /bin/sh
SUBMIT_SCHEMA_VERSION="${1:-v1}"
echo "run invoke_jobs.py SUBMIT ${SUBMIT_SCHEMA_VERSION}"
python3 invoke_jobs.py SUBMIT "${SUBMIT_SCHEMA_VERSION}"
