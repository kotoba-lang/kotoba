# usage: gen-new.py DEVICE_RESULT_C OUT -- the current text-building segment of aiueos_device_result_http_request over
# prelude.h. JUN-554.
import sys
src = open(sys.argv[1]).read()
a = src.index('  /* The signed canonical text and the JSON body are kotoba/device-result-text.kotoba')
b = src.index('  struct bounded_buffer request = {out, 0, capacity, 1};', a)
open(sys.argv[2], 'w').write('#define SEGMENT_NAME new_segment\n#include "prelude.h"\n' + src[a:b] + '#include "epilogue.h"\n')
