#!/usr/bin/env python3
# usage: gen-new.py QWEN35_INFER_C OUT -- the model-handoff image's residual_add over kotoba/qwen35-residual.o (as it is
# now in kernel/qwen35_infer.c) as new_add. JUN-554.
import sys
src = open(sys.argv[1]).read()
a = src.index("extern int64_t kotoba_aiueos_qwen35_residual_add(")
hi = src.index("#else\n", a)
body = src[a:hi]
assert "static int residual_add(float *state, const float *x) {" in body
open(sys.argv[2], "w").write("#include <stdint.h>\n#define EMBED 5120U\n" + body +
  "int new_add(float *state, const float *x) { return residual_add(state, x); }\n")
