/* The #UD guard for the native-route differentials (JUN-552). Both object routes stop on `ud2` -- an index past a
   window, a window over its bound, a null base, an exhausted fuel budget -- and in the kernel that is a halt. Here a
   vector-6 handler resumes at the guarded call's return instead, so a differential can compare where the two objects
   trap as well as what they answer: guarded_call answers the object's result, or 0 with guard_trapped set. */
#include <stdint.h>
extern volatile int64_t guard_trapped;
void guard_init(void);
int64_t guarded_call(void *fn, int64_t a0, int64_t a1, int64_t a2, int64_t a3, int64_t a4);
