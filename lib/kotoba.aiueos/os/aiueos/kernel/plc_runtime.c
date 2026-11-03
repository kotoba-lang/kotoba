#include <stdint.h>

#define AIUEOS_PLC_INPUT_CAP 16U
#define AIUEOS_PLC_STAGE_CAP 17U
#define AIUEOS_PLC_COMMIT_CAP 18U
#define AIUEOS_PLC_WATCHDOG_CAP 19U
#define AIUEOS_PLC_IO_COUNT 2U
#define AIUEOS_PLC_CYCLE_TICKS 10U
#define AIUEOS_PLC_DEADLINE_TICKS 8U
#define AIUEOS_PLC_BUDGET_TICKS 4U

enum aiueos_plc_fault {
  AIUEOS_PLC_FAULT_NONE = 0,
  AIUEOS_PLC_FAULT_RELEASE = 1,
  AIUEOS_PLC_FAULT_CAPABILITY = 2,
  AIUEOS_PLC_FAULT_STAGE = 3,
  AIUEOS_PLC_FAULT_WATCHDOG = 4,
  AIUEOS_PLC_FAULT_BUDGET = 5,
  AIUEOS_PLC_FAULT_DEADLINE = 6,
  AIUEOS_PLC_FAULT_PROGRAM = 7
};

struct aiueos_plc_runtime {
  int32_t physical_input[AIUEOS_PLC_IO_COUNT];
  int32_t input_image[AIUEOS_PLC_IO_COUNT];
  int32_t shadow_output[AIUEOS_PLC_IO_COUNT];
  int32_t physical_output[AIUEOS_PLC_IO_COUNT];
  int32_t safe_output[AIUEOS_PLC_IO_COUNT];
  uint64_t next_release, release, deadline, budget_end;
  uint32_t staged;
  uint8_t active, watchdog, fault_latched, fault;
};

static struct aiueos_plc_runtime plc;
static uint8_t plc_initialized;
static uint64_t plc_scan_count,plc_release_expected,plc_release_observed;
extern volatile uint64_t aiueos_apic_timer_ticks;

static void plc_safe(enum aiueos_plc_fault fault) {
  for (unsigned i=0;i<AIUEOS_PLC_IO_COUNT;i++)
    plc.physical_output[i]=plc.safe_output[i];
  plc.active=0;
  if (!plc.fault_latched) plc.fault=(uint8_t)fault;
  plc.fault_latched=1;
}

static void plc_reset(void) {
  plc=(struct aiueos_plc_runtime){0};
  plc.next_release=AIUEOS_PLC_CYCLE_TICKS;
}

/* What a release or a capability call may do is kotoba/plc-step.kotoba (JUN-554); this file keeps the runtime struct and
   performs the step the object names. */
extern int64_t kotoba_aiueos_plc_release_step(uint64_t, uint64_t, uint64_t, uint64_t);
extern int64_t kotoba_aiueos_plc_call_step(uint64_t, uint64_t, uint64_t, uint64_t, uint64_t, uint64_t);
extern uint64_t kotoba_aiueos_tick_wait(uint64_t ticks, uint64_t ticks_length, uint64_t target, uint64_t rounds);

static int plc_release(uint64_t now) {
  if (kotoba_aiueos_plc_release_step(plc.fault_latched, plc.active, now, plc.next_release) != 1) {
    plc_safe(AIUEOS_PLC_FAULT_RELEASE); return 0;
  }
  for (unsigned i=0;i<AIUEOS_PLC_IO_COUNT;i++) {
    plc.input_image[i]=plc.physical_input[i];
    plc.shadow_output[i]=plc.safe_output[i];
  }
  plc.release=now;
  plc.deadline=now+AIUEOS_PLC_DEADLINE_TICKS;
  plc.budget_end=now+AIUEOS_PLC_BUDGET_TICKS;
  plc.next_release+=AIUEOS_PLC_CYCLE_TICKS;
  plc.staged=0; plc.watchdog=0; plc.active=1;
  return 1;
}

static uint64_t plc_call(uint64_t capability,uint64_t argument,uint64_t now) {
  uint64_t state=(plc.active?1U:0U)|(plc.watchdog?2U:0U)|((uint64_t)(plc.staged&3U)<<2);
  int64_t r=kotoba_aiueos_plc_call_step(capability,argument,now,state,plc.deadline,plc.budget_end);
  unsigned index=(unsigned)((uint64_t)r>>16)&0xffU;
  switch ((int)(r&0xff)) {
    case 1: return (uint64_t)(int64_t)plc.input_image[index];
    case 2: plc.shadow_output[index]=(int32_t)argument; plc.staged|=1U<<index; return 1;
    case 3: plc.watchdog=1; return 1;
    case 4:
      for (unsigned i=0;i<AIUEOS_PLC_IO_COUNT;i++)
        plc.physical_output[i]=plc.shadow_output[i];
      plc.active=0; return 1;
    default:
      plc_safe((enum aiueos_plc_fault)(((uint64_t)r>>8)&0xffU)); return 0;
  }
}

static int plc_failure_vectors(void) {
  plc_reset(); plc.physical_output[0]=plc.physical_output[1]=7;
  if (!plc_release(10) || plc_call(17,1,10)!=1) return 0;
  if (plc_call(18,2,10)!=0 || plc.fault!=AIUEOS_PLC_FAULT_STAGE ||
      plc.physical_output[0]!=0 || plc.physical_output[1]!=0) return 0;

  plc_reset(); if (!plc_release(10)) return 0;
  if (plc_call(17,1,10)!=1 || plc_call(17,1ULL<<32,10)!=1 ||
      plc_call(18,2,10)!=0 || plc.fault!=AIUEOS_PLC_FAULT_WATCHDOG) return 0;

  plc_reset(); if (!plc_release(10)) return 0;
  if (plc_call(17,1,10)!=1 || plc_call(17,1ULL<<32,10)!=1 ||
      plc_call(19,1,10)!=1 || plc_call(18,2,15)!=0 ||
      plc.fault!=AIUEOS_PLC_FAULT_BUDGET) return 0;

  plc_reset(); if (!plc_release(10)) return 0;
  plc.budget_end=30;
  if (plc_call(17,1,10)!=1 || plc_call(17,1ULL<<32,10)!=1 ||
      plc_call(19,1,10)!=1 || plc_call(18,2,19)!=0 ||
      plc.fault!=AIUEOS_PLC_FAULT_DEADLINE) return 0;

  plc_reset(); if (!plc_release(10)) return 0;
  plc_safe(AIUEOS_PLC_FAULT_PROGRAM);
  return plc.fault_latched && plc.fault==AIUEOS_PLC_FAULT_PROGRAM &&
    plc.physical_output[0]==0 && plc.physical_output[1]==0;
}

int aiueos_plc_rt_begin_scan(int32_t enable,int32_t sensor) {
  if (!plc_initialized) {
    if (!plc_failure_vectors()) return 0;
    plc_reset();
    plc.next_release=((aiueos_apic_timer_ticks/AIUEOS_PLC_CYCLE_TICKS)+1U)*
      AIUEOS_PLC_CYCLE_TICKS;
    plc_initialized=1;
  }
  if (plc.active || plc.fault_latched) return 0;
  /* kotoba/tick-wait.o: look, then sti; hlt; cli, until the tick counter
     reaches the release; it answers 2 when its rounds run out, 0 on refusal
     (plc_release below then refuses the scan). */
  for (uint64_t got=2; got==2;)
    got=kotoba_aiueos_tick_wait((uint64_t)(uintptr_t)&aiueos_apic_timer_ticks,8,plc.next_release,65536);
#ifdef AIUEOS_PLC_RT_FORCE_MISS_SCAN
  /* Negative control (JUN-736): stay in the kernel past this scan's release
     tick, so the release the provider sees is one tick late -- the same
     observation a host stall under an unpinned QEMU clock produced. */
  if (plc_scan_count==(uint64_t)(AIUEOS_PLC_RT_FORCE_MISS_SCAN)) {
    __asm__ volatile("sti");
    while (aiueos_apic_timer_ticks<=plc.next_release) __asm__ volatile("pause");
    __asm__ volatile("cli");
  }
#endif
  plc_scan_count++;
  /* JUN-736: the release is the tick the kernel observes now, not the tick it
     waited for. A late release (the counter already past next_release, e.g.
     two timer interrupts inside one sti; hlt; cli window) is refused by
     plc-step's release_step, which latches FAULT_RELEASE and drives the safe
     outputs -- the contract for every other refused scan. This used to return
     0 before plc_release, so a missed release left no fault and no safe state. */
  plc_release_expected=plc.next_release;
  plc_release_observed=aiueos_apic_timer_ticks;
  plc.physical_input[0]=enable; plc.physical_input[1]=sensor;
  if (!plc_release(plc_release_observed)) return 0;
  /* Mutating the physical source after release proves the input image is
   * immutable during this scan. */
  plc.physical_input[0]=!enable; plc.physical_input[1]=sensor+1000;
  return plc.active && !plc.fault_latched;
}

uint64_t aiueos_plc_capability_call(uint64_t capability,uint64_t argument) {
  return plc_call(capability,argument,aiueos_apic_timer_ticks);
}

int aiueos_plc_rt_result_ready(int32_t output0,int32_t output1) {
  return !plc.active && !plc.fault_latched &&
    plc.physical_output[0]==output0 && plc.physical_output[1]==output1;
}

int aiueos_plc_rt_failed(void) { return plc.fault_latched; }

/* JUN-736: what a failed run reports -- the latched fault, and for the last
   scan the release tick it waited for and the tick it observed. */
uint64_t aiueos_plc_rt_fault(void) { return plc.fault_latched ? plc.fault : 0; }
uint64_t aiueos_plc_rt_release_expected(void) { return plc_release_expected; }
uint64_t aiueos_plc_rt_release_observed(void) { return plc_release_observed; }
