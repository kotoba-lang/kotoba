# usage: gen-new.py KOTOTAMA_RUNTIME_C OUT -- the current aiueos_kototama_runtime_management_command over prelude.h. JUN-554.
import sys
src = open(sys.argv[1]).read()
a = src.index('/* The management protocol -- which of the three commands')
open(sys.argv[2], 'w').write('#define aiueos_kototama_runtime_management_command new_management_command\n#include "prelude.h"\n' + src[a:])
