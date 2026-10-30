# Writes OUT: kernel/tls13.c's current consume_hs_messages .. process_record and aiueos_tls13_feed over prelude.h.
import sys
src = open(sys.argv[1]).read()
a = src.index('/* What to do with the next message or record is kotoba/tls13-hs.o')
b = src.index('void aiueos_tls13_reset(void) {')
fa = src.index('int aiueos_tls13_feed(const uint8_t *data, uint32_t len) {')
fb = src.index('int aiueos_tls13_saw_record(void)')
open(sys.argv[2], 'w').write('#define PFX(x) new_##x\n#include "prelude.h"\n' + src[a:b] + src[fa:fb] + '#include "epilogue.h"\n')
