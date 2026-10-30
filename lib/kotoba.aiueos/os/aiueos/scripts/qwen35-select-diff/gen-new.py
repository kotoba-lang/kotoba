#!/usr/bin/env python3
# usage: gen-new.py QWEN35_INFER_C OUT -- the model-handoff select_view of kernel/qwen35_infer.c (the wrapper over
# kotoba/qwen35-select.o) as new_select_view, with the struct it uses. JUN-554.
import sys
src = open(sys.argv[1]).read()
start = src.index("#if defined(AIUEOS_QWEN38_MODEL_HANDOFF) && !defined(AIUEOS_QWEN35_TESTING)\nextern int64_t kotoba_aiueos_qwen35_select")
body = src[start:src.index("\n#else\n", start)].split("\n", 1)[1]
struct = src[src.index("struct qwen35_token_choice {"):]
struct = struct[:struct.index("};") + 2]
body = body.replace("static int select_view(", "int new_select_view(")
assert "new_select_view(" in body and "kotoba_aiueos_qwen35_select(" in body
open(sys.argv[2], "w").write("#include <stdint.h>\n" + struct + "\n" + body + "\n")
