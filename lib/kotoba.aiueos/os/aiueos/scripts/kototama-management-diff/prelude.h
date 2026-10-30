/* What aiueos_kototama_runtime_management_command reads and calls, for scripts/kototama-management-diff: the runtime
   state, a restart whose result the driver scripts (and counts), and the reboot-pxe flag. */
#include <stdint.h>
#include "kototama_runtime.h"
struct prelude_runtime { struct aiueos_kototama_runtime_status status; };
extern struct prelude_runtime runtime;
extern int reboot_pxe_requested;
int aiueos_kototama_runtime_restart(void);
