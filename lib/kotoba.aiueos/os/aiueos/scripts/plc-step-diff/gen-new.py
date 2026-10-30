# usage: gen-new.py PLC_RUNTIME_C OUT -- kernel/plc_runtime.c's current definitions .. plc_call behind epilogue.h. JUN-554.
import sys
src = open(sys.argv[1]).read()
a = src.index('#define AIUEOS_PLC_INPUT_CAP'); b = src.index('static int plc_failure_vectors(void)')
open(sys.argv[2], 'w').write('#include <stdint.h>\n#define PFX(x) new_##x\n' +
  src[a:b].replace('extern volatile uint64_t aiueos_apic_timer_ticks;\n', '') + '#include "epilogue.h"\n')
