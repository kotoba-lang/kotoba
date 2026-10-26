#!/usr/bin/env python3
"""Keep the Mac relay's verifier identical to the frozen K16 C model."""

import importlib.util
import re
import sys
from pathlib import Path


repo = Path(__file__).resolve().parents[3]
server_path = repo / "os/aiueos/tools/k16-pxe-server.py"
spec = importlib.util.spec_from_file_location("k16_pxe_server", server_path)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

# The matrix's source of truth is the EDN contract (ADR-0220; it was the C
# array in kernel/micro_infer.c until that file's decision moved to Kotoba).
# Read with a real reader would be better than a regex; the rows are the only
# bracketed integer runs after `:rows`, and the count is asserted.
source = (repo / "os/aiueos/contracts/micro-infer-transitions-v1.edn").read_text(encoding="utf-8")
body = source[source.index(":rows"):]
rows = [list(map(int, re.findall(r"\d+", row)))
        for row in re.findall(r"\[([0-9 ]+)\]", body)]
assert len(rows) == 27 and all(len(row) == 27 for row in rows), len(rows)

vocabulary = " abcdefghijklmnopqrstuvwxyz"
projection = {}
for input_index, row in enumerate(rows):
    score = max(row)
    total = sum(row)
    if score and total:
        output_index = row.index(score)
        projection[vocabulary[input_index]] = (
            vocabulary[output_index], score, total)

assert projection == server.MURAKUMO_MICRO_INFER_ROWS
for input_value, expected in projection.items():
    assert server.micro_infer_expected("probe" + input_value) == expected
assert server.micro_infer_expected("ends-in-b") is None
assert server.micro_infer_expected("UPPER") is None
print("AIUEOS_MICRO_INFER_RELAY_OK rows=27 verifier=exact continuous-jobs=admitted")
