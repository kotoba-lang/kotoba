# usage: gen-new.py PCI_C OUT -- kernel/pci.c's current userauth wrappers over the built-in authorized key. JUN-552.
import sys
src = open(sys.argv[1]).read()
auth = src[src.index('static const uint8_t ssh_auth_x[32] = {'):]
auth = auth[:auth.index('#endif')]
a = src.index('/* The publickey userauth parsing is kotoba/ssh-userauth.kotoba'); b = src.index('/* Drive publickey userauth after NEWKEYS.')
fns = src[a:b].replace('static int ssh_userauth_method_is(', 'int new_method_is(').replace(
  'static int ssh_userauth_publickey_fields(', 'int new_publickey_fields(').replace(
  'static int ssh_authorized_publickey_blob(', 'int new_authorized_blob(')
open(sys.argv[2], 'w').write('#include <stdint.h>\n' + auth + fns)
