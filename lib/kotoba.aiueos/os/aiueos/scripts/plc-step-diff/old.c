/* kernel/plc_runtime.c's scan-cycle core before JUN-554 moved its decisions to kotoba/plc-step.o: the definitions,
   plc_safe, plc_reset, plc_release and plc_call, verbatim, behind epilogue.h's entry points. */
#include <stdint.h>
#define PFX(x) old_##x
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

static int plc_release(uint64_t now) {
  if (plc.fault_latched || plc.active || now!=plc.next_release) {
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
  if (!plc.active) { plc_safe(AIUEOS_PLC_FAULT_CAPABILITY); return 0; }
  if (capability==AIUEOS_PLC_INPUT_CAP) {
    unsigned index=(unsigned)argument;
    if (index>=AIUEOS_PLC_IO_COUNT) { plc_safe(AIUEOS_PLC_FAULT_CAPABILITY); return 0; }
    return (uint64_t)(int64_t)plc.input_image[index];
  }
  if (capability==AIUEOS_PLC_STAGE_CAP) {
    unsigned index=(unsigned)(argument>>32);
    if (index>=AIUEOS_PLC_IO_COUNT || (plc.staged&(1U<<index))) {
      plc_safe(AIUEOS_PLC_FAULT_STAGE); return 0;
    }
    plc.shadow_output[index]=(int32_t)argument;
    plc.staged|=1U<<index;
    return 1;
  }
  if (capability==AIUEOS_PLC_WATCHDOG_CAP) {
    if (argument!=1 || plc.watchdog) { plc_safe(AIUEOS_PLC_FAULT_WATCHDOG); return 0; }
    plc.watchdog=1; return 1;
  }
  if (capability==AIUEOS_PLC_COMMIT_CAP) {
    if (argument!=AIUEOS_PLC_IO_COUNT || plc.staged!=3U) {
      plc_safe(AIUEOS_PLC_FAULT_STAGE); return 0;
    }
    if (!plc.watchdog) { plc_safe(AIUEOS_PLC_FAULT_WATCHDOG); return 0; }
    if (now>plc.deadline) { plc_safe(AIUEOS_PLC_FAULT_DEADLINE); return 0; }
    if (now>plc.budget_end) { plc_safe(AIUEOS_PLC_FAULT_BUDGET); return 0; }
    for (unsigned i=0;i<AIUEOS_PLC_IO_COUNT;i++)
      plc.physical_output[i]=plc.shadow_output[i];
    plc.active=0; return 1;
  }
  plc_safe(AIUEOS_PLC_FAULT_CAPABILITY); return 0;
}

#include "epilogue.h"
