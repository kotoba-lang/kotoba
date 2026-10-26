#!/bin/sh
set -eu

aiueos=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python3 "$aiueos/scripts/test_compile_plc_st.py"
python3 "$aiueos/scripts/test_make_plc_native_receipt.py"
python3 "$aiueos/scripts/test_make_plc_signature_material.py"
python3 "$aiueos/scripts/test_verify_plc_native_receipt.py"
printf 'AIUEOS_PLC_TESTS_OK frontend=6 deployment-input=5 signature=3 receipt=7\n'
