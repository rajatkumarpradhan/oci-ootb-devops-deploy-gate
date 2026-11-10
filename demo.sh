#!/bin/sh
# Checks the ungated pipeline (prod deploy with no effective approval -> exit 2),
# then the gated pipeline (approval + rollback -> exit 0).
set -u
export PYTHONPATH="$(dirname "$0")/src"

echo "=== Checking samples/ungated-pipeline.json ==="
python3 -m oci_ootb_devops_deploy_gate samples/ungated-pipeline.json
echo "exit code: $? (2 = production deploy without an effective approval gate, expected)"
echo
echo "=== Checking samples/gated-pipeline.json ==="
python3 -m oci_ootb_devops_deploy_gate samples/gated-pipeline.json
echo "exit code: $? (0 = gated pipeline, expected)"
