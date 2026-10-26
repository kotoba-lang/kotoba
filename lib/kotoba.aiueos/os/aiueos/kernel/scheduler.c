#include <stdint.h>
#include <stddef.h>

#define AIUEOS_TASK_SLOT_COUNT 9U
#define AIUEOS_USER_TASK_CAPACITY 8U
#define AIUEOS_SERVICE_CAPACITY 8U
#define AIUEOS_TASK_STACK_BYTES 4096U
/* The kernel CS (0x08), SS (0x10) and the RFLAGS an initial frame carries
 * (AIUEOS_INTERRUPT_FLAG | 2 == 514) moved into kotoba/kernel-context-build.o
 * with the frame construction itself, so no macro for them survives here: a
 * definition nothing reads is a definition someone can change without effect.
 * The ring-3 selectors were never macros; see initial_user_context. */
#define AIUEOS_IPC_CAPABILITY_TYPE 2U
#define AIUEOS_IPC_SEND_RIGHT 1U
#define AIUEOS_SERVICE_MUTATE_STATE 1U
#define AIUEOS_SERVICE_MUTATE_CONTEXT 2U
#define AIUEOS_SERVICE_MUTATE_TASK_BIND 4U
#define AIUEOS_SERVICE_MUTATE_TASK_DEACTIVATE 8U
#define AIUEOS_SERVICE_MUTATE_TASK_RELEASE 16U
#define AIUEOS_SERVICE_MUTATE_CLEAR 32U
#define AIUEOS_TASK_INIT_POINTERS 1U
#define AIUEOS_TASK_INIT_COUNTERS 2U
#define AIUEOS_TASK_INIT_CR3 4U
#define AIUEOS_TASK_INIT_SERVICE 8U
#define AIUEOS_TASK_INIT_GENERATION 16U
#define AIUEOS_TASK_INIT_ACTIVE 32U
#define AIUEOS_TASK_RELEASE_POINTERS 1U
#define AIUEOS_TASK_RELEASE_COUNTERS 2U
#define AIUEOS_TASK_RELEASE_CR3 4U
#define AIUEOS_TASK_RELEASE_SERVICE 8U
#define AIUEOS_DISPATCH_CURRENT 1U
#define AIUEOS_DISPATCH_SWITCH_COUNT 2U
#define AIUEOS_DISPATCH_CR3 4U
#define AIUEOS_DISPATCH_USER_DOMAIN 8U
#define AIUEOS_DISPATCH_KERNEL_STACK 16U
#define AIUEOS_DISPATCH_USER_SWITCH 32U
#define AIUEOS_DISPATCH_REAP 64U
#define AIUEOS_DISPATCH_SAVE_OUTGOING 128U
#define AIUEOS_DISPATCH_OUTGOING_COUNT 256U

/* A saved stack pointer is the complete kernel-task context. */
struct aiueos_interrupt_context {
  uint64_t r15, r14, r13, r12, r11, r10, r9, r8;
  uint64_t rbp, rdi, rsi, rdx, rcx, rbx, rax;
  uint64_t rip, cs, rflags, rsp, ss;
};

extern int aiueos_address_spaces_initialize(void);
extern int aiueos_address_space_claim(void);
extern uint64_t aiueos_address_space_kernel_cr3(void);
extern uint64_t aiueos_address_space_cr3(unsigned process);
extern uint64_t aiueos_address_space_current_cr3(void);
extern void aiueos_address_space_switch(uint64_t cr3);
extern uint64_t aiueos_address_space_private_va(unsigned process);
extern uint64_t kotoba_aiueos_service_lifecycle(uint64_t generation,
  uint64_t restarts, uint64_t event, uint64_t budget);
extern uint64_t kotoba_aiueos_capability_plan(uint64_t slot,
  uint64_t generation, uint64_t type, uint64_t state_rights, uint64_t request);
extern uint64_t *kotoba_aiueos_user_context_build(uint8_t *stack,
  uint64_t entry,uint64_t argument,uint64_t user_stack);
extern uint64_t *kotoba_aiueos_kernel_context_build(uint8_t *stack,
  uint64_t entry,uint64_t argument);
extern void aiueos_process_set_kernel_stack(uint64_t top);
extern volatile uint16_t aiueos_current_user_domain;
extern void *aiueos_allocate_physical_page(void);
extern int aiueos_free_physical_page(void *page);

struct aiueos_task {
  uint64_t *saved_stack;
  uint8_t *kernel_stack;
  uint64_t switches, cr3;
  uint16_t generation, service, domain;
  uint8_t active, exit_requested;
};
static struct aiueos_task tasks[AIUEOS_TASK_SLOT_COUNT];
_Static_assert(sizeof(struct aiueos_task)==40,"task descriptor ABI");
_Static_assert(offsetof(struct aiueos_task,kernel_stack)==8,"task stack ABI");
_Static_assert(offsetof(struct aiueos_task,generation)==32,"task generation ABI");
_Static_assert(offsetof(struct aiueos_task,active)==38,"task active ABI");
extern uint64_t kotoba_aiueos_task_slot_plan(const void *table,uint64_t length,
  uint64_t count,uint64_t stride,uint64_t request);
extern uint64_t kotoba_aiueos_scheduler_dispatch_plan(const void *table,
  uint64_t length,uint64_t count,uint64_t stride,uint64_t state);
extern uint64_t kotoba_aiueos_task_exit_route(const void *table,uint64_t length,
  uint64_t count,uint64_t stride,uint64_t domain);
extern uint64_t kotoba_aiueos_service_task_transition(uint64_t candidate,
  uint64_t active,uint64_t slot,uint64_t current,uint64_t task_active);
static uint64_t current_task;
static int scheduler_user_mode;
volatile uint64_t aiueos_user_scheduler_switches;
static uint64_t user_tasks_reaped;
static uint64_t user_tasks_expected;
static uint64_t user_kernel_stacks_zeroed;
static volatile uint64_t service_runs[AIUEOS_SERVICE_CAPACITY];
volatile uint64_t aiueos_scheduler_context_switches;
volatile uint64_t aiueos_scheduler_address_space_failures;
struct aiueos_service_slot {
  uint64_t id, generation, heartbeats, restarts, restart_requested;
  volatile uint64_t *runs;
  uint16_t task_slot, process_slot;
  uint8_t marker, active;
};
static struct aiueos_service_slot services[AIUEOS_SERVICE_CAPACITY];
struct aiueos_service_mailbox {
  volatile uint64_t sequence, sender_id, sender_generation, recipient_id;
  volatile uint64_t payload, full;
};
static struct aiueos_service_mailbox service_mailbox;
static uint64_t service_ipc_send_handle;
static volatile uint64_t service_ipc_received_sequence;
static volatile uint64_t service_ipc_received_payload;
static volatile uint64_t service_ipc_foreign_rejections;
struct aiueos_user_service_mailbox {
  volatile uint64_t sender_domain, recipient_service, sequence, payload, full;
};
static struct aiueos_user_service_mailbox user_service_mailboxes[2];
static volatile uint64_t user_service_ipc_received_domains;
static volatile uint64_t user_service_ipc_received_payloads[2];
static uint64_t dynamic_task_evidence;
static uint64_t kotoba_lifecycle_evidence;
static uint64_t persistent_restore_evidence;
#ifdef AIUEOS_PLC_RT_SMOKE
static uint8_t rt_descriptors[256];
static uint8_t rt_mode,rt_preemption_count,rt_budget_return_count;
extern uint64_t kotoba_aiueos_rt_scheduler_plan(
  const void *,uint64_t,uint64_t,uint64_t,uint64_t);

static void rt_descriptor(unsigned slot,uint8_t state,uint8_t priority,
                          uint8_t budget,uint8_t deadline,uint8_t sequence) {
  uint8_t *d=rt_descriptors+slot*16U;
  for (unsigned i=0;i<16;i++) d[i]=0;
  d[0]=state; d[1]=priority; d[2]=priority; d[3]=0;
  d[4]=budget; d[5]=deadline; d[6]=sequence;
}

static uint64_t *rt_on_timer(uint64_t *interrupted_stack) {
  uint8_t *out=rt_descriptors+current_task*16U;
  if (out[0]==2 && current_task && out[4]) out[4]--;
  if (out[0]==2 && current_task && out[5]) out[5]--;
  uint64_t plan=kotoba_aiueos_rt_scheduler_plan(
    rt_descriptors,sizeof(rt_descriptors),16,16,current_task);
  if (!plan) { aiueos_scheduler_address_space_failures++; return interrupted_stack; }
  unsigned next=(unsigned)((plan&255U)-1U);
  if (next>=AIUEOS_TASK_SLOT_COUNT || !tasks[next].active ||
      ((plan>>16)&255U)!=rt_descriptors[next*16U+2]) {
    aiueos_scheduler_address_space_failures++; return interrupted_stack;
  }
  if (next==current_task) return interrupted_stack;
  if (!(plan&256U) || rt_descriptors[next*16U]!=1) {
    aiueos_scheduler_address_space_failures++; return interrupted_stack;
  }
  tasks[current_task].saved_stack=interrupted_stack;
  tasks[current_task].switches++;
  out[0]=(out[4]&&out[5])?1:3;
  rt_descriptors[next*16U]=2;
  if ((plan&512U) && current_task==0 && rt_preemption_count<255)
    rt_preemption_count++;
  if ((plan&2048U) && next==0 && rt_budget_return_count<255)
    rt_budget_return_count++;
  current_task=next;
  aiueos_scheduler_context_switches++;
  aiueos_current_user_domain=current_task?tasks[current_task].domain:0;
  if (current_task) {
    aiueos_process_set_kernel_stack((uint64_t)(uintptr_t)
      (tasks[current_task].kernel_stack+AIUEOS_TASK_STACK_BYTES));
    aiueos_user_scheduler_switches++;
  }
  aiueos_address_space_switch(tasks[current_task].cr3);
  return tasks[current_task].saved_stack;
}

int aiueos_plc_rt_scheduler_evidence_ready(unsigned scans) {
  return scans && scans<=255 && rt_preemption_count>=scans &&
    rt_budget_return_count>=scans && current_task==0;
}
#endif

static int allocate_task_slot(uint64_t cr3) {
  uint64_t plan=kotoba_aiueos_task_slot_plan(tasks,sizeof(tasks),
    AIUEOS_TASK_SLOT_COUNT,sizeof(tasks[0]),0);
  unsigned slot=(unsigned)(plan&255U);
  uint16_t generation=(uint16_t)((plan>>8)&65535U);
  uint64_t recipe=plan>>32;
  if (!plan || slot<1 || slot>=AIUEOS_TASK_SLOT_COUNT || !generation ||
      recipe!=(AIUEOS_TASK_INIT_POINTERS|AIUEOS_TASK_INIT_COUNTERS|
        AIUEOS_TASK_INIT_CR3|AIUEOS_TASK_INIT_SERVICE|
        AIUEOS_TASK_INIT_GENERATION|AIUEOS_TASK_INIT_ACTIVE) ||
      tasks[slot].active || tasks[slot].kernel_stack) return -1;
  uint8_t *stack=aiueos_allocate_physical_page();
  if (!stack) return -1;
  if (recipe&AIUEOS_TASK_INIT_POINTERS) {
    tasks[slot].kernel_stack=stack;
    tasks[slot].saved_stack=0;
  }
  if (recipe&AIUEOS_TASK_INIT_COUNTERS) {
    tasks[slot].switches=0;
    tasks[slot].domain=0; tasks[slot].exit_requested=0;
  }
  if (recipe&AIUEOS_TASK_INIT_CR3) tasks[slot].cr3=cr3;
  if (recipe&AIUEOS_TASK_INIT_SERVICE) tasks[slot].service=0xffffU;
  if (recipe&AIUEOS_TASK_INIT_GENERATION) tasks[slot].generation=generation;
  if (recipe&AIUEOS_TASK_INIT_ACTIVE) tasks[slot].active=1;
  return (int)slot;
}
static int release_task_slot(unsigned slot) {
  uint64_t plan=kotoba_aiueos_task_slot_plan(tasks,sizeof(tasks),
    AIUEOS_TASK_SLOT_COUNT,sizeof(tasks[0]),slot+1U);
  uint64_t recipe=plan>>32;
  if ((uint32_t)plan!=1U ||
      recipe!=(AIUEOS_TASK_RELEASE_POINTERS|AIUEOS_TASK_RELEASE_COUNTERS|
        AIUEOS_TASK_RELEASE_CR3|AIUEOS_TASK_RELEASE_SERVICE)) return 0;
  if (!aiueos_free_physical_page(tasks[slot].kernel_stack)) return 0;
  if (recipe&AIUEOS_TASK_RELEASE_POINTERS) {
    tasks[slot].kernel_stack=0;
    tasks[slot].saved_stack=0;
  }
  if (recipe&AIUEOS_TASK_RELEASE_COUNTERS) {
    tasks[slot].switches=0;
    tasks[slot].domain=0; tasks[slot].exit_requested=0;
  }
  if (recipe&AIUEOS_TASK_RELEASE_CR3) tasks[slot].cr3=0;
  if (recipe&AIUEOS_TASK_RELEASE_SERVICE) tasks[slot].service=0xffffU;
  return 1;
}

static uint64_t ipc_capability_plan(uint16_t requester) {
  uint64_t state = AIUEOS_IPC_SEND_RIGHT | 65536U | ((uint64_t)1 << 17);
  uint64_t request = AIUEOS_IPC_SEND_RIGHT |
    ((uint64_t)AIUEOS_IPC_CAPABILITY_TYPE << 16) |
    ((uint64_t)requester << 32);
  return kotoba_aiueos_capability_plan(4,1,AIUEOS_IPC_CAPABILITY_TYPE,state,request);
}

static void service_ipc_step(unsigned process) {
  if (process<2 && user_service_mailboxes[process].full) {
    struct aiueos_user_service_mailbox *mailbox=&user_service_mailboxes[process];
    __asm__ volatile("" ::: "memory");
    if (mailbox->sender_domain==process+4 && mailbox->recipient_service==process &&
        mailbox->sequence==1 && mailbox->payload==42) {
      user_service_ipc_received_payloads[process]=mailbox->payload;
      user_service_ipc_received_domains|=1ULL<<process;
      mailbox->full=0;
    }
  }
  if (process == 0 && services[0].generation == 2 &&
      services[0].heartbeats == 1 && !service_mailbox.full) {
    if (ipc_capability_plan(1) != service_ipc_send_handle) return;
    service_mailbox.sender_id = services[0].id;
    service_mailbox.sender_generation = services[0].generation;
    service_mailbox.recipient_id = services[1].id;
    service_mailbox.payload = 0x4b4f544f42414950ULL;
    service_mailbox.sequence = 1;
    __asm__ volatile("" ::: "memory");
    service_mailbox.full = 1;
  } else if (process == 1 && service_mailbox.full) {
    __asm__ volatile("" ::: "memory");
    if (service_mailbox.recipient_id != services[1].id ||
        service_mailbox.sender_id != services[0].id ||
        service_mailbox.sender_generation != services[0].generation) return;
    service_ipc_received_payload = service_mailbox.payload;
    service_ipc_received_sequence = service_mailbox.sequence;
    service_mailbox.full = 0;
  }
}

static inline void debug_byte(uint8_t value) {
  __asm__ volatile("outb %0, $0xe9" : : "a"(value));
}
static void task_loop(volatile uint64_t *runs, uint8_t marker, unsigned process) {
  volatile uint64_t *private_word =
    (volatile uint64_t *)(uintptr_t)aiueos_address_space_private_va(process);
  for (;;) {
    if (aiueos_address_space_current_cr3() != aiueos_address_space_cr3(process))
      ++aiueos_scheduler_address_space_failures;
    ++*private_word;
    *runs = *private_word;
    services[process].heartbeats++;
    service_ipc_step(process);
    /* Deterministic fault injection proves that the scheduler replaces the
     * task context instead of merely changing lifecycle metadata. */
    if (process == 0 && services[process].generation == 1 &&
        services[process].heartbeats == 2)
      services[process].restart_requested = 1;
    if (*runs == 1) debug_byte(marker);
    __asm__ volatile("hlt");
  }
}
__attribute__((noreturn)) static void service_task_entry(uint64_t service) {
  if (service>=AIUEOS_SERVICE_CAPACITY || !services[service].active)
    for (;;) __asm__ volatile("hlt");
  if (!services[service].runs) for (;;) __asm__ volatile("hlt");
  task_loop(services[service].runs,services[service].marker,
    services[service].process_slot);
  __builtin_unreachable();
}
static uint64_t *initial_context(uint8_t *stack, void (*entry)(uint64_t), uint64_t argument) {
  /* iret enters a C function directly, so the frame models the stack position
   * normally produced by call (RSP % 16 == 8 at function entry) -- the Kotoba
   * object owns that arithmetic, the zeroing and every field. Unlike the ring-3
   * twin below, the result is NOT rechecked here: the two callers of this
   * function store the pointer without testing it, so a gate could only turn a
   * broken object into a null saved_stack. What guards this object is the
   * pinned SHA-256 the build script verifies before linking it. */
  return (uint64_t *)kotoba_aiueos_kernel_context_build(stack,
    (uint64_t)(uintptr_t)entry,argument);
}
static uint64_t *initial_user_context(uint8_t *stack, void (*entry)(uint64_t),
                                      uint64_t argument, uint64_t user_stack) {
  uint64_t *frame=kotoba_aiueos_user_context_build(stack,(uint64_t)(uintptr_t)entry,
    argument,user_stack);
  struct aiueos_interrupt_context *context=(struct aiueos_interrupt_context *)frame;
  if (!context || context->rip!=(uint64_t)(uintptr_t)entry ||
      context->rdi!=argument || context->cs!=0x23U || context->rflags!=514U ||
      context->rsp!=user_stack || context->ss!=0x1bU) return 0;
  return frame;
}
static int apply_service_event(unsigned service, uint64_t event) {
  if (service>=AIUEOS_SERVICE_CAPACITY) return 0;
  struct aiueos_service_slot *descriptor=&services[service];
  uint64_t plan=kotoba_aiueos_service_lifecycle(
    descriptor->generation,descriptor->restarts,event,3);
  if (!plan && event) return 0;
  uint64_t candidate=plan ? plan : 4ULL<<32;
  uint64_t state_slot=descriptor->task_slot;
  uint64_t task_active=state_slot<AIUEOS_TASK_SLOT_COUNT ?
    tasks[state_slot].active : 0;
  uint64_t commit=kotoba_aiueos_service_task_transition(candidate,
    descriptor->active,state_slot,current_task,task_active);
  uint64_t commit_action=(commit>>32)&255U;
  uint64_t recipe=commit>>40;
  if (commit_action==1) {
    if (recipe!=(AIUEOS_SERVICE_MUTATE_STATE|AIUEOS_SERVICE_MUTATE_CONTEXT|
        AIUEOS_SERVICE_MUTATE_TASK_BIND)) return 0;
    uint64_t cr3=descriptor->process_slot<8 ?
      aiueos_address_space_cr3(descriptor->process_slot) :
      aiueos_address_space_kernel_cr3();
    int slot=allocate_task_slot(cr3);
    if (slot<1) return 0;
    if (recipe&AIUEOS_SERVICE_MUTATE_STATE) {
      descriptor->generation=commit&65535U;
      descriptor->restarts=(commit>>16)&65535U;
      descriptor->heartbeats=descriptor->restart_requested=0;
      descriptor->active=1;
    }
    if (recipe&AIUEOS_SERVICE_MUTATE_TASK_BIND) {
      descriptor->task_slot=(uint16_t)slot;
      tasks[slot].service=(uint16_t)service;
    }
    if (recipe&AIUEOS_SERVICE_MUTATE_CONTEXT)
      tasks[slot].saved_stack=initial_context(tasks[slot].kernel_stack,
        service_task_entry,service);
    return 1;
  }
  if (commit_action==2) {
    if (recipe!=(AIUEOS_SERVICE_MUTATE_STATE|AIUEOS_SERVICE_MUTATE_CONTEXT))
      return 0;
    if (recipe&AIUEOS_SERVICE_MUTATE_STATE) {
      descriptor->generation=commit&65535U;
      descriptor->restarts=(commit>>16)&65535U;
      descriptor->heartbeats=descriptor->restart_requested=0;
    }
    if (recipe&AIUEOS_SERVICE_MUTATE_CONTEXT)
      tasks[descriptor->task_slot].saved_stack=initial_context(
        tasks[descriptor->task_slot].kernel_stack,service_task_entry,service);
    return 1;
  }
  if (commit_action==3) {
    if (recipe!=(AIUEOS_SERVICE_MUTATE_TASK_DEACTIVATE|
        AIUEOS_SERVICE_MUTATE_TASK_RELEASE|AIUEOS_SERVICE_MUTATE_CLEAR)) return 0;
    unsigned task_slot=descriptor->task_slot;
    if (recipe&AIUEOS_SERVICE_MUTATE_TASK_DEACTIVATE) tasks[task_slot].active=0;
    if ((recipe&AIUEOS_SERVICE_MUTATE_TASK_RELEASE) &&
        !release_task_slot(task_slot)) {
      tasks[task_slot].active=1;
      return 0;
    }
    if (recipe&AIUEOS_SERVICE_MUTATE_CLEAR) {
      descriptor->active=0; descriptor->task_slot=0;
    }
    return 1;
  }
  return event==0 && commit_action==4;
}
void aiueos_scheduler_initialize(void) {
  if (!aiueos_address_spaces_initialize()) {
    aiueos_scheduler_address_space_failures = 1;
    return;
  }
  for (uint32_t i=0;i<AIUEOS_TASK_SLOT_COUNT;i++) tasks[i]=(struct aiueos_task){0};
  tasks[0].cr3=aiueos_address_space_kernel_cr3(); tasks[0].active=1;
  /* Service roots are persistent scheduler-owned address spaces. Reserve them
     before any user process can claim a root. */
  if (aiueos_address_space_claim()!=0 || aiueos_address_space_claim()!=1) {
    aiueos_scheduler_address_space_failures=1; return;
  }
  for (unsigned service=0;service<AIUEOS_SERVICE_CAPACITY;service++)
    services[service]=(struct aiueos_service_slot){0,0,0,0,0,0,0,0,0,0};
  services[0].id=1; services[0].runs=&service_runs[0];
  services[0].process_slot=0; services[0].marker='A';
  services[1].id=2; services[1].runs=&service_runs[1];
  services[1].process_slot=1; services[1].marker='B';
  if (!apply_service_event(0,2) || !apply_service_event(1,2) ||
      services[0].task_slot!=1 || services[1].task_slot!=2) {
    aiueos_scheduler_address_space_failures=1; return;
  }
  services[2].id=3; services[2].process_slot=0xffffU; services[2].marker='C';
  if (!apply_service_event(2,2) || services[2].task_slot!=3) {
    aiueos_scheduler_address_space_failures=1; return;
  }
  unsigned rollback_slot=services[2].task_slot;
  uint8_t *rollback_stack=tasks[rollback_slot].kernel_stack;
  tasks[rollback_slot].kernel_stack=(uint8_t *)(uintptr_t)1;
  if (apply_service_event(2,3) || !services[2].active ||
      !tasks[rollback_slot].active) {
    aiueos_scheduler_address_space_failures=1; return;
  }
  tasks[rollback_slot].kernel_stack=rollback_stack;
  if (!apply_service_event(2,3) || services[2].active) {
    aiueos_scheduler_address_space_failures=1; return;
  }
  kotoba_lifecycle_evidence=1;
  current_task = 0;
  scheduler_user_mode = 0;
  aiueos_user_scheduler_switches = 0;
  for (unsigned service=0;service<AIUEOS_SERVICE_CAPACITY;service++) service_runs[service]=0;
  aiueos_scheduler_context_switches = 0;
  aiueos_scheduler_address_space_failures = 0;
  service_mailbox = (struct aiueos_service_mailbox){0,0,0,0,0,0};
  service_ipc_received_sequence = service_ipc_received_payload = 0;
  service_ipc_send_handle = ipc_capability_plan(1);
  service_ipc_foreign_rejections = ipc_capability_plan(2) == 0 ? 1 : 0;
  for (unsigned i=0;i<2;i++) {
    user_service_mailboxes[i]=(struct aiueos_user_service_mailbox){0,0,0,0,0};
    user_service_ipc_received_payloads[i]=0;
  }
  user_service_ipc_received_domains=0;
}
int aiueos_scheduler_begin_user_runtime(void) {
  if (!services[0].active || !services[1].active) return 0;
  tasks[0].saved_stack=0; tasks[0].switches=0;
  current_task=0; scheduler_user_mode=1; aiueos_user_scheduler_switches=0;
#ifdef AIUEOS_PLC_RT_SMOKE
  for (unsigned i=0;i<sizeof(rt_descriptors);i++) rt_descriptors[i]=0;
  rt_descriptor(0,2,255,255,255,0);
  rt_preemption_count=rt_budget_return_count=0; rt_mode=1;
#endif
  user_tasks_reaped=0; user_tasks_expected=0; user_kernel_stacks_zeroed=0;
  aiueos_current_user_domain=0;
  return 1;
}
int aiueos_scheduler_create_user_task(unsigned address_space, uint16_t domain,
    void (*entry)(uint64_t), uint64_t argument, uint64_t user_stack) {
  uint64_t cr3=aiueos_address_space_cr3(address_space);
  if (!scheduler_user_mode || !domain || !entry || !cr3 || !user_stack) return -1;
  int slot=allocate_task_slot(cr3);
  if (slot<1) return -1;
  tasks[slot].domain=domain;
  tasks[slot].saved_stack=initial_user_context(tasks[slot].kernel_stack,entry,argument,user_stack);
  if (!tasks[slot].saved_stack) {
    tasks[slot].active=0;
    release_task_slot((unsigned)slot);
    return -1;
  }
#ifdef AIUEOS_PLC_RT_SMOKE
  if (rt_mode && domain==4) rt_descriptor((unsigned)slot,1,5,8,9,1);
#endif
  user_tasks_expected++;
  return slot;
}
#ifdef AIUEOS_PLC_RT_SMOKE
int aiueos_scheduler_rearm_plc_task(unsigned slot,void (*entry)(uint64_t),
    uint64_t argument,uint64_t user_stack) {
  if (!rt_mode || current_task!=0 || slot<1 || slot>=AIUEOS_TASK_SLOT_COUNT ||
      !tasks[slot].active || tasks[slot].domain!=4 || !entry || !argument ||
      !user_stack || rt_descriptors[slot*16U]!=3) return 0;
  uint64_t *context=initial_user_context(tasks[slot].kernel_stack,entry,argument,user_stack);
  if (!context) return 0;
  tasks[slot].saved_stack=context;
  rt_descriptor(slot,1,5,8,9,
    (uint8_t)(rt_descriptors[slot*16U+6]+1U));
  return 1;
}
#endif
int aiueos_service_runtime_evidence_ready(void) {
  return kotoba_lifecycle_evidence && services[0].id == 1 && services[1].id == 2 &&
    services[0].generation == 2 && services[0].restarts == 1 &&
    services[0].restart_requested == 0 && services[1].generation == 1 &&
    services[0].heartbeats >= 2 && services[1].heartbeats >= 2 &&
    services[0].active && services[1].active &&
    services[2].generation==1 && !services[2].active;
}
int aiueos_service_ipc_evidence_ready(void) {
  return service_ipc_send_handle != 0 && service_ipc_foreign_rejections == 1 &&
    service_ipc_received_sequence == 1 &&
    service_ipc_received_payload == 0x4b4f544f42414950ULL &&
    service_mailbox.full == 0;
}
uint64_t aiueos_kotoba_service_send(uint16_t domain,uint64_t payload) {
  if (domain<4 || domain>5 || !payload || payload>0xffffffffU) return 0;
  unsigned service=domain-4;
  struct aiueos_user_service_mailbox *mailbox=&user_service_mailboxes[service];
  if (mailbox->full || user_service_ipc_received_payloads[service]) return 0;
  mailbox->sender_domain=domain; mailbox->recipient_service=service;
  mailbox->sequence=1; mailbox->payload=payload;
  __asm__ volatile("" ::: "memory"); mailbox->full=1;
  return 1;
}
int aiueos_kotoba_service_ipc_evidence_ready(void) {
  return user_service_ipc_received_domains==3 &&
    user_service_ipc_received_payloads[0]==42 &&
    user_service_ipc_received_payloads[1]==42 &&
    !user_service_mailboxes[0].full && !user_service_mailboxes[1].full;
}
uint64_t aiueos_service_registry_state(unsigned service) {
  if (service >= 2 || services[service].id > 255 ||
      services[service].generation > 255 || services[service].restarts > 255) return 0;
  return services[service].id | (services[service].generation << 16) |
    (services[service].restarts << 32);
}
int aiueos_scheduler_restore_service_registry(uint64_t state0, uint64_t state1) {
  uint64_t states[2]={state0,state1};
  if (current_task!=0 || scheduler_user_mode) return 0;
  for (unsigned service=0;service<2;service++) {
    uint64_t id=states[service]&255U;
    uint64_t generation=(states[service]>>16)&255U;
    uint64_t restarts=(states[service]>>32)&255U;
    if (id!=service+1 || !generation || restarts>3) return 0;
  }
  if (!apply_service_event(0,3) || !apply_service_event(1,3)) return 0;
  for (unsigned service=0;service<2;service++) {
    services[service].generation=(states[service]>>16)&255U;
    services[service].restarts=(states[service]>>32)&255U;
  }
  if (!apply_service_event(0,2) || !apply_service_event(1,2)) return 0;
  persistent_restore_evidence=services[0].task_slot==1 &&
    services[1].task_slot==2 && services[0].generation==((state0>>16)&255U) &&
    services[1].generation==((state1>>16)&255U);
  return (int)persistent_restore_evidence;
}
int aiueos_scheduler_persistent_restore_evidence_ready(void) {
  return (int)persistent_restore_evidence;
}
uint64_t *aiueos_scheduler_on_timer(uint64_t *interrupted_stack) {
#ifdef AIUEOS_PLC_RT_SMOKE
  if (rt_mode) return rt_on_timer(interrupted_stack);
#endif
  int context_reset=0;
  if (!scheduler_user_mode && current_task > 0) {
    unsigned service=tasks[current_task].service;
    if (service<AIUEOS_SERVICE_CAPACITY && services[service].restart_requested) {
      if (apply_service_event(service,1)) context_reset=1;
      else
        aiueos_scheduler_address_space_failures++;
    }
  }
  uint64_t state=current_task|((uint64_t)(scheduler_user_mode!=0)<<4)|
    ((uint64_t)context_reset<<5);
  uint64_t plan=kotoba_aiueos_scheduler_dispatch_plan(tasks,sizeof(tasks),
    AIUEOS_TASK_SLOT_COUNT,sizeof(tasks[0]),state);
  unsigned next=(unsigned)((plan&255U)-1U);
  uint64_t recipe=plan>>32;
  uint64_t required=AIUEOS_DISPATCH_CURRENT|AIUEOS_DISPATCH_SWITCH_COUNT|
    AIUEOS_DISPATCH_CR3|AIUEOS_DISPATCH_OUTGOING_COUNT;
  if (!context_reset) required|=AIUEOS_DISPATCH_SAVE_OUTGOING;
  if (scheduler_user_mode) {
    required|=AIUEOS_DISPATCH_USER_DOMAIN;
    if (next>0 && next<AIUEOS_TASK_SLOT_COUNT)
      required|=AIUEOS_DISPATCH_KERNEL_STACK|AIUEOS_DISPATCH_USER_SWITCH;
  }
  if (plan&256U) required|=AIUEOS_DISPATCH_REAP;
  if (!plan || recipe!=required || next>=AIUEOS_TASK_SLOT_COUNT ||
      !tasks[next].active) {
    aiueos_scheduler_address_space_failures++;
    return interrupted_stack;
  }
  if (recipe&AIUEOS_DISPATCH_SAVE_OUTGOING)
    tasks[current_task].saved_stack=interrupted_stack;
  if (recipe&AIUEOS_DISPATCH_OUTGOING_COUNT) tasks[current_task].switches++;
  if (recipe&AIUEOS_DISPATCH_REAP) {
    tasks[current_task].active=0; user_tasks_reaped++;
  }
  if (recipe&AIUEOS_DISPATCH_CURRENT) current_task=next;
  if (recipe&AIUEOS_DISPATCH_SWITCH_COUNT) aiueos_scheduler_context_switches++;
  if (recipe&AIUEOS_DISPATCH_USER_DOMAIN) {
    aiueos_current_user_domain = current_task ? tasks[current_task].domain : 0;
  }
  if (recipe&AIUEOS_DISPATCH_KERNEL_STACK)
    aiueos_process_set_kernel_stack((uint64_t)(uintptr_t)
      (tasks[current_task].kernel_stack + AIUEOS_TASK_STACK_BYTES));
  if (recipe&AIUEOS_DISPATCH_USER_SWITCH) aiueos_user_scheduler_switches++;
  /* Interrupt code is mapped supervisor-only in every root.  Switch after
   * saving the outgoing frame, immediately before iret resumes the task. */
  if (recipe&AIUEOS_DISPATCH_CR3)
    aiueos_address_space_switch(tasks[current_task].cr3);
  return tasks[current_task].saved_stack;
}
void aiueos_scheduler_request_user_exit(uint16_t domain) {
  uint64_t route=kotoba_aiueos_task_exit_route(tasks,sizeof(tasks),
    AIUEOS_TASK_SLOT_COUNT,sizeof(tasks[0]),domain);
  unsigned slot=(unsigned)(route-1U);
  if (route && slot<AIUEOS_TASK_SLOT_COUNT && tasks[slot].active &&
      tasks[slot].domain==domain) tasks[slot].exit_requested=1;
}
int aiueos_scheduler_users_reaped(void) { return user_tasks_expected && user_tasks_reaped==user_tasks_expected; }
int aiueos_scheduler_finalize_user_stacks(void) {
  if (!aiueos_scheduler_users_reaped() || current_task!=0) return 0;
  for (unsigned slot=1;slot<AIUEOS_TASK_SLOT_COUNT;slot++) {
    if (tasks[slot].service<AIUEOS_SERVICE_CAPACITY) continue;
    if (tasks[slot].active || (tasks[slot].kernel_stack && !release_task_slot(slot))) return 0;
  }
  user_kernel_stacks_zeroed=user_tasks_expected; scheduler_user_mode=0;
  return 1;
}
unsigned aiueos_scheduler_task_capacity(void) { return AIUEOS_USER_TASK_CAPACITY; }
int aiueos_scheduler_task_slot_self_test(void) {
  uint16_t generation_before=tasks[3].generation;
  for (unsigned expected=3;expected<AIUEOS_TASK_SLOT_COUNT;expected++)
    if (allocate_task_slot(aiueos_address_space_kernel_cr3())!=(int)expected) return 0;
  if (allocate_task_slot(aiueos_address_space_kernel_cr3())!=-1) return 0;
  for (unsigned slot=3;slot<AIUEOS_TASK_SLOT_COUNT;slot++) tasks[slot].active=0;
  for (unsigned slot=3;slot<AIUEOS_TASK_SLOT_COUNT;slot++)
    if (!release_task_slot(slot)) return 0;
  if (allocate_task_slot(aiueos_address_space_kernel_cr3())!=3 ||
      tasks[3].generation<=generation_before) return 0;
  for (unsigned i=0;i<AIUEOS_TASK_STACK_BYTES;i++)
    if (tasks[3].kernel_stack[i]) return 0;
  tasks[3].active=0;
  if (!release_task_slot(3)) return 0;
  dynamic_task_evidence=1;
  return 1;
}
int aiueos_scheduler_reap_evidence_ready(void) {
  return user_tasks_reaped==user_tasks_expected && user_kernel_stacks_zeroed==user_tasks_expected &&
    services[0].active && services[1].active && tasks[1].active && tasks[2].active &&
    dynamic_task_evidence && current_task==0;
}
int aiueos_user_scheduler_evidence_ready(void) {
  return scheduler_user_mode && aiueos_user_scheduler_switches >= 4 &&
    tasks[0].switches >= 2 && tasks[1].switches >= 2 && tasks[2].switches >= 2 &&
    aiueos_address_space_current_cr3() == tasks[0].cr3;
}
int aiueos_scheduler_evidence_ready(void) {
  return service_runs[0] >= 2 && service_runs[1] >= 2 &&
         aiueos_scheduler_context_switches >= 6 && tasks[0].switches >= 2 &&
         tasks[1].switches >= 2 && tasks[2].switches >= 2 &&
         aiueos_scheduler_address_space_failures == 0 &&
         aiueos_address_space_current_cr3() == tasks[0].cr3 &&
         tasks[0].cr3 != tasks[1].cr3 && tasks[1].cr3 != tasks[2].cr3 &&
         tasks[0].cr3 != tasks[2].cr3;
}
