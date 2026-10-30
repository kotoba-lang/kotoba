/* aiueos_plc_rt_begin_scan's wait for the next release before JUN-554 moved it to kotoba/tick-wait.o: the loop verbatim
   from kernel/plc_runtime.c (main 4008b9d7), with plc.next_release a parameter, as old_wait. */
#include <stdint.h>
extern volatile uint64_t aiueos_apic_timer_ticks;
struct plc_state { uint64_t next_release; };
void old_wait(uint64_t next_release) {
  struct plc_state plc = {next_release};
  while (aiueos_apic_timer_ticks<plc.next_release) __asm__ volatile("sti; hlt; cli");
}
