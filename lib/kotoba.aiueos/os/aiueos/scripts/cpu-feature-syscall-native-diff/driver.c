/* cpu-feature-syscall built on amu's native object route (JUN-552) against the committed kotoba-compiler/1 object: both are called on
   every processor of each CPU model and topology run.sh boots (../ap-run), and must answer the same. */
#include <stdint.h>
extern int64_t kotoba_aiueos_cpu_feature_syscall(void);
extern int64_t kotoba_aiueos_cpu_feature_syscall_native(void);
#define OLD kotoba_aiueos_cpu_feature_syscall
#define NEW kotoba_aiueos_cpu_feature_syscall_native
#include "ap.h"
