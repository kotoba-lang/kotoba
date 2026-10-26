#include <stdint.h>
#include <stddef.h>

#define ABI 0
#define LOG 1
#define EXIT 2
#define TRANSFER 3
#define CLAIM 4
#define ABI_V1 0x00010000ULL
#define BAD_HANDLE ((uint64_t)-9)
#define BAD_POINTER ((uint64_t)-14)
#define TOO_BIG ((uint64_t)-7)

struct __attribute__((packed)) tss64 {
  uint32_t reserved0; uint64_t rsp0, rsp1, rsp2; uint64_t reserved1;
  uint64_t ist[7]; uint64_t reserved2; uint16_t reserved3, iomap;
};
struct user_result {
  uint64_t handle, foreign_handle, domain;
  uint64_t abi, valid, too_big, stale, foreign_owner, wrong_type, no_rights;
  uint64_t bad_pointer, transfer, transfer_escalation, claimed;
  uint64_t transferred_valid, completed, scheduled_runs;
  uint64_t foreign_page;
  char message[8];
};

extern uint64_t aiueos_gdt_tss[2];
extern uint8_t aiueos_kernel_stack_top[];
extern void aiueos_syscall_entry(void);
extern uint64_t aiueos_sysret_count, aiueos_sysret_validation_count;
extern void aiueos_enter_user(void (*entry)(void), void *stack);
extern int aiueos_user_mapping_verify(void);
extern uint64_t aiueos_syscall_from_user;
extern volatile uint16_t aiueos_current_user_domain;
extern int aiueos_address_spaces_initialize(void);
extern uint64_t aiueos_address_space_enter(unsigned process);
extern void aiueos_address_space_leave(void);
extern uint64_t aiueos_address_space_private_va(unsigned process);
extern void *aiueos_address_space_private_backing(unsigned process);
extern uint64_t aiueos_capability_log_handle(uint16_t owner);
extern uint64_t aiueos_capability_ensure_log_handle(uint16_t owner);
extern uint64_t aiueos_capability_ensure_runtime_handle(uint16_t owner);
extern int aiueos_user_object_write_evidence_ready(void);
extern int aiueos_user_object_flush_pending(void);
extern int aiueos_scheduler_begin_user_runtime(void);
extern int aiueos_scheduler_create_user_task(unsigned address_space,uint16_t domain,
  void (*entry)(uint64_t),uint64_t argument,uint64_t user_stack);
extern int aiueos_user_scheduler_evidence_ready(void);
extern void aiueos_scheduler_request_user_exit(uint16_t domain);
extern int aiueos_scheduler_users_reaped(void);
extern int aiueos_scheduler_finalize_user_stacks(void);
extern int aiueos_scheduler_reap_evidence_ready(void);
extern unsigned aiueos_scheduler_task_capacity(void);
extern int aiueos_scheduler_task_slot_self_test(void);
extern uint64_t aiueos_capability_revoke_owner(uint16_t owner);
extern int aiueos_address_space_reclaim(unsigned process);
extern int aiueos_address_space_reuse(unsigned process);
extern uint64_t aiueos_physical_allocator_reuse_count(void);
extern unsigned aiueos_address_space_capacity(void);
extern int aiueos_address_space_slot_self_test(void);
extern int aiueos_address_space_claim(void);
extern int aiueos_address_space_user_entry_valid(unsigned process,uint64_t entry);
extern int aiueos_load_object_store_kotoba_process(unsigned process,const uint8_t app_id[16],uint64_t *entry,uint64_t **result);
#ifdef AIUEOS_PLC_RT_SMOKE
extern int aiueos_load_embedded_plc_process(unsigned process,uint64_t *entry,uint64_t **result);
extern int aiueos_reset_embedded_plc_context(uint64_t *result,uint64_t runtime_handle);
extern int aiueos_scheduler_rearm_plc_task(unsigned slot,void (*entry)(uint64_t),
  uint64_t argument,uint64_t user_stack);
#endif
extern int aiueos_kotoba_process_loader_evidence_ready(void);
extern int aiueos_kotoba_service_ipc_evidence_ready(void);
extern uint8_t aiueos_user_text_start[],aiueos_user_text_end[];
extern void aiueos_probe_cross_process(const void *address);
extern volatile uint64_t aiueos_page_fault_stage, aiueos_page_fault_error;
/* kotoba-lang/aiueos#108 diagnostics (2026-10-24): the ring-3 process phase
   can stop waking (the serial log used to end silently at
   AIUEOS_KOTOBA_ELF_PROCESS_OK). These bounded snapshots name the wait loop's
   silence point: how many wakeups arrived, whether the external timer still
   advances, and which exit condition is still false. Polled COM1 like
   main.c's own serial path, budgeted per byte. The marker prefix
   AIUEOS_PROCESS_PHASE_ is part of the smoke harness's #108 signature. */
extern volatile uint64_t aiueos_external_timer_ticks;
static void p108_out8(uint16_t port, uint8_t value) {
  __asm__ volatile("outb %0, %1" : : "a"(value), "Nd"(port));
}
static uint8_t p108_in8(uint16_t port) {
  uint8_t value;
  __asm__ volatile("inb %1, %0" : "=a"(value) : "Nd"(port));
  return value;
}
static void p108_byte(uint8_t value) {
  uint32_t budget = 1000000;
  while (!(p108_in8(0x3f8 + 5) & 0x20) && --budget) {}
  if (budget) p108_out8(0x3f8, value);
}
static void p108_str(const char *text) {
  while (*text) p108_byte((uint8_t)*text++);
}
static void p108_dec(uint32_t value) {
  char digits[10];
  unsigned count = 0;
  if (!value) { p108_byte((uint8_t)'0'); return; }
  while (value) { digits[count++] = (char)('0' + (value % 10)); value /= 10; }
  while (count) p108_byte((uint8_t)digits[--count]);
}
static struct tss64 tss;
uint64_t aiueos_syscall_kernel_stack_top;
static uint64_t syscall_transport_evidence;
__attribute__((section(".user.data"), aligned(4096), used))
static uint8_t user_mapping_anchor[4096];
static struct user_result *kernel_results[2];
#define PROCESS_CAPACITY 8U
#define AIUEOS_PROCESS_CREATE_IDENTITY 1U
#define AIUEOS_PROCESS_CREATE_EXECUTION 2U
#define AIUEOS_PROCESS_CREATE_RESULT 4U
#define AIUEOS_PROCESS_CREATE_TASK 8U
#define AIUEOS_PROCESS_CREATE_ACTIVE 16U
#define AIUEOS_PROCESS_CLEAR_EXECUTION 1U
#define AIUEOS_PROCESS_CLEAR_OWNERSHIP 2U
#define AIUEOS_PROCESS_CLEAR_TASK 4U
#define AIUEOS_PROCESS_CLEAR_ACTIVE 8U
#define AIUEOS_PROCESS_CLEAR_RESULT 16U
struct process_descriptor {
  uint64_t entry, argument, user_stack;
  uint16_t generation, domain, address_space, task_slot;
  uint8_t active;
  struct user_result *result;
};
static struct process_descriptor processes[PROCESS_CAPACITY];
_Static_assert(sizeof(struct process_descriptor)==48,"process descriptor ABI");
_Static_assert(offsetof(struct process_descriptor,generation)==24,"process generation ABI");
_Static_assert(offsetof(struct process_descriptor,domain)==26,"process domain ABI");
_Static_assert(offsetof(struct process_descriptor,active)==32,"process active ABI");
extern uint64_t kotoba_aiueos_process_create_plan(const void *table,
  uint64_t length,uint64_t domain,uint64_t count,uint64_t stride);
extern uint64_t kotoba_aiueos_process_teardown_plan(uint64_t domain,
  uint64_t reaped,uint64_t revoked,uint64_t reclaimed,uint64_t stage);
static uint64_t process_lifecycle_evidence;
static int process_results_valid;
static int catalog_lookup_rejection_evidence;
static const uint8_t hello_app_id[16]="app/hello";
static const uint8_t worker_app_id[16]="app/worker";
static const uint8_t missing_app_id[16]="app/missing";
int aiueos_process_result(void);
void aiueos_process_set_kernel_stack(uint64_t top) {
  tss.rsp0=top; aiueos_syscall_kernel_stack_top=top;
}

/* The SYSCALL MSRs are reached through kotoba/msr-read.kotoba and
   kotoba/msr-write.kotoba, which admit 0xc0000080/81/82/84 and nothing else.
   0xc0000083 (IA32_CSTAR) is deliberately NOT admitted: this kernel enters user
   mode in 64-bit mode only and never programs the compatibility-mode entry
   point, and an admitted "range" rather than a list would have let it through.
   Writes return 1 admitted / 0 refused; reads cannot signal, so the evidence
   check below stands as the read-back proof either way -- a refused read
   returns 0 and fails all four comparisons. */
extern uint64_t kotoba_aiueos_msr_read(uint64_t index);
extern uint64_t kotoba_aiueos_msr_write(uint64_t index, uint64_t value);
/* Whether `syscall` decodes on this CPU at all is leaf 0x80000001 EDX bit 11,
   behind a max-extended-leaf guard on leaf 0x80000000 -- and knowing that it is
   THAT leaf and THAT bit is the decision, so it lives in
   kotoba/cpu-feature-syscall.kotoba. Same leaf as the NX probe paging.c uses
   and a different bit, which is exactly why they are two objects rather than
   one taking the bit as an argument. */
extern uint64_t kotoba_aiueos_cpu_feature_syscall(void);
static int syscall_transport_initialize(void) {
  if (!kotoba_aiueos_cpu_feature_syscall()) return 0;
  uint64_t star=(0x10ULL<<48)|(0x08ULL<<32);
  if (!kotoba_aiueos_msr_write(0xc0000080ULL,
        kotoba_aiueos_msr_read(0xc0000080ULL)|1U)) return 0;
  if (!kotoba_aiueos_msr_write(0xc0000081ULL,star)) return 0;
  if (!kotoba_aiueos_msr_write(0xc0000082ULL,
        (uint64_t)(uintptr_t)aiueos_syscall_entry)) return 0;
  if (!kotoba_aiueos_msr_write(0xc0000084ULL,0x47700U)) return 0;
  aiueos_sysret_count=aiueos_sysret_validation_count=0;
  syscall_transport_evidence=(kotoba_aiueos_msr_read(0xc0000080ULL)&1U) &&
    kotoba_aiueos_msr_read(0xc0000081ULL)==star &&
    kotoba_aiueos_msr_read(0xc0000082ULL)==(uint64_t)(uintptr_t)aiueos_syscall_entry &&
    kotoba_aiueos_msr_read(0xc0000084ULL)==0x47700U;
  return (int)syscall_transport_evidence;
}
int aiueos_syscall_transport_evidence_ready(void) {
  return syscall_transport_evidence && aiueos_sysret_count>=18 &&
    aiueos_sysret_validation_count==aiueos_sysret_count;
}

static inline uint64_t call(uint64_t n, uint64_t h, const void *p, uint64_t l) {
  register uint64_t a __asm__("rax")=n;
  __asm__ volatile("syscall" : "+a"(a) : "D"(h), "S"(p), "d"(l) :
                   "rcx","r11","r8","r9","r10","memory");
  return a;
}

__attribute__((section(".user.text"), noreturn))
static void user_run(struct user_result *r, const void *foreign_page) {
  r->abi = call(ABI,0,0,0);
  r->valid = call(LOG,r->handle,r->message,5);
  r->too_big = call(LOG,r->handle,r,257);
  r->stale = call(LOG,r->handle ^ 0x10000ULL,r->message,1);
  r->foreign_owner = call(LOG,r->foreign_handle,r->message,1);
  r->wrong_type = call(LOG,r->handle ^ 0x100000000ULL,r->message,1);
  r->no_rights = call(LOG,r->handle ^ 0x1000000000000ULL,r->message,1);
  r->bad_pointer = call(LOG,r->handle,foreign_page,1);
  if (r->domain==2) {
    r->transfer_escalation=call(TRANSFER,r->handle,(void *)3,2);
    r->transfer=call(TRANSFER,r->handle,(void *)3,1);
  } else {
    do { r->claimed=call(CLAIM,0,0,0); }
    while (r->claimed==BAD_HANDLE);
    r->transferred_valid=call(LOG,r->claimed,r->message,5);
  }
  r->completed = 1;
  for (;;) { r->scheduled_runs++; __asm__ volatile("pause"); }
}
__attribute__((section(".user.text"), noreturn))
static void user_entry(uint64_t argument) {
  struct user_result *result=(struct user_result *)(uintptr_t)argument;
  user_run(result,(const void *)(uintptr_t)result->foreign_page);
}

int aiueos_process_address_space_for_domain(uint16_t domain) {
  for (unsigned slot=0;slot<PROCESS_CAPACITY;slot++)
    if (processes[slot].active && processes[slot].domain==domain)
      return processes[slot].address_space;
  return -1;
}
static int process_create_in_space(void (*entry)(uint64_t),uint16_t domain,int supplied_space) {
  uint64_t address=(uint64_t)(uintptr_t)entry;
  uint64_t plan=kotoba_aiueos_process_create_plan(processes,sizeof(processes),
    domain,PROCESS_CAPACITY,sizeof(processes[0]));
  if (!plan) return -1;
  unsigned descriptor=(unsigned)((plan&255U)-1U);
  uint16_t generation=(uint16_t)((plan>>8)&65535U);
  uint64_t recipe=plan>>32;
  if (descriptor>=PROCESS_CAPACITY || !generation ||
      recipe!=(AIUEOS_PROCESS_CREATE_IDENTITY|AIUEOS_PROCESS_CREATE_EXECUTION|
        AIUEOS_PROCESS_CREATE_RESULT|AIUEOS_PROCESS_CREATE_TASK|
        AIUEOS_PROCESS_CREATE_ACTIVE) || processes[descriptor].active) return -1;
  int address_space=supplied_space>=0 ? supplied_space : aiueos_address_space_claim();
  if (address_space<0) return -1;
  int linked_entry=address>=(uint64_t)(uintptr_t)aiueos_user_text_start &&
    address<(uint64_t)(uintptr_t)aiueos_user_text_end;
  if (!linked_entry && !aiueos_address_space_user_entry_valid((unsigned)address_space,address)) {
    aiueos_address_space_reclaim((unsigned)address_space); return -1;
  }
  struct user_result *result=aiueos_address_space_private_backing((unsigned)address_space);
  uint64_t private_va=aiueos_address_space_private_va((unsigned)address_space);
  uint64_t handle=aiueos_capability_ensure_log_handle(domain);
  if (!result || !private_va || !handle) { aiueos_address_space_reclaim((unsigned)address_space); return -1; }
  result->handle=handle; result->domain=domain;
  result->message[0]='r'; result->message[1]='i'; result->message[2]='n';
  result->message[3]='g'; result->message[4]=(char)('1'+descriptor); result->message[5]=0;
  struct process_descriptor *p=&processes[descriptor];
  if (recipe&AIUEOS_PROCESS_CREATE_IDENTITY) {
    p->generation=generation; p->domain=domain;
    p->address_space=(uint16_t)address_space;
  }
  if (recipe&AIUEOS_PROCESS_CREATE_EXECUTION) {
    p->entry=address; p->argument=private_va; p->user_stack=private_va+4096;
  }
  if (recipe&AIUEOS_PROCESS_CREATE_RESULT) p->result=result;
  int task=aiueos_scheduler_create_user_task((unsigned)address_space,domain,entry,
    p->argument,p->user_stack);
  if (task<1) {
    p->entry=p->argument=p->user_stack=0;
    p->domain=p->address_space=p->task_slot=0; p->result=0; p->active=0;
    aiueos_address_space_reclaim((unsigned)address_space); return -1;
  }
  if (recipe&AIUEOS_PROCESS_CREATE_TASK) p->task_slot=(uint16_t)task;
  if (recipe&AIUEOS_PROCESS_CREATE_ACTIVE) p->active=1;
  return (int)descriptor;
}
static int process_create(void (*entry)(uint64_t),uint16_t domain) {
  return process_create_in_space(entry,domain,-1);
}
static int process_create_kotoba_elf(const uint8_t app_id[16],uint16_t domain,uint64_t **result) {
  int address_space=aiueos_address_space_claim();
  uint64_t entry=0;
  if (address_space<0 || !aiueos_load_object_store_kotoba_process(
      (unsigned)address_space,app_id,&entry,result)) {
    if (address_space>=0) aiueos_address_space_reclaim((unsigned)address_space);
    return -1;
  }
  uint64_t runtime_handle=aiueos_capability_ensure_runtime_handle(domain);
  if (!runtime_handle || !*result) {
    aiueos_address_space_reclaim((unsigned)address_space); return -1;
  }
  (*result)[10]=runtime_handle;
  return process_create_in_space((void (*)(uint64_t))(uintptr_t)entry,domain,address_space);
}
#ifdef AIUEOS_PLC_RT_SMOKE
#define AIUEOS_PLC_RT_STRESS_SCANS 100U
volatile uint64_t aiueos_plc_process_stage;
int aiueos_process_enter_plc_rt(void) {
  aiueos_plc_process_stage=1;
  if (!aiueos_scheduler_begin_user_runtime()) return 0;
  int address_space=aiueos_address_space_claim();
  uint64_t entry=0,*result=0;
  aiueos_plc_process_stage=2;
  if (address_space<0 || !aiueos_load_embedded_plc_process(
      (unsigned)address_space,&entry,&result)) return 0;
  aiueos_plc_process_stage=3;
  uint64_t runtime_handle=aiueos_capability_ensure_runtime_handle(4);
  if (!runtime_handle || !result) return 0;
  result[10]=runtime_handle;
  extern int aiueos_plc_rt_begin_scan(int32_t enable,int32_t sensor);
  extern int aiueos_plc_rt_result_ready(int32_t output0,int32_t output1);
  extern int aiueos_plc_rt_failed(void);
  extern int aiueos_plc_rt_scheduler_evidence_ready(unsigned scans);
  int descriptor=-1;
  struct process_descriptor *p=0;
  for (unsigned scan=0;scan<AIUEOS_PLC_RT_STRESS_SCANS;scan++) {
    int32_t enable=(scan&1U)?0:1;
    int32_t sensor=(int32_t)(41U+scan);
    int32_t command=sensor+1;
    int32_t motor_on=enable && command<100;
    aiueos_plc_process_stage=4U+scan;
    if (scan && !aiueos_reset_embedded_plc_context(result,runtime_handle)) return 0;
    if (!aiueos_plc_rt_begin_scan(enable,sensor)) return 0;
    if (!scan) {
      descriptor=process_create_in_space(
        (void (*)(uint64_t))(uintptr_t)entry,4,address_space);
      if (descriptor<0) return 0;
      p=&processes[descriptor];
      *result=0;
    } else if (!aiueos_scheduler_rearm_plc_task(p->task_slot,
        (void (*)(uint64_t))(uintptr_t)p->entry,p->argument,p->user_stack)) return 0;
    __asm__ volatile("sti");
    /* Bounded (JUN-141, measured 2026-10-20): this wait froze the boot
       twice when the scan result never came -- an unbounded hlt on a
       timer race is indistinguishable from a dead machine. The caller
       reports the failure; the boot must be able to end. */
    { uint64_t waits = 0;
      /* pause, not hlt: hlt waits for an interrupt, and the very race
         being bounded can be the interrupt that never comes (measured
         2026-10-20). A spin always terminates. */
      while (!*result && !aiueos_plc_rt_failed()) {
        __asm__ volatile("pause");
        if (++waits > 2000000000ULL) return 0;
      } }
    __asm__ volatile("cli");
    if (*result!=1 || !aiueos_plc_rt_result_ready(motor_on,command)) return 0;
  }
  aiueos_plc_process_stage=104;
  return aiueos_plc_rt_scheduler_evidence_ready(AIUEOS_PLC_RT_STRESS_SCANS);
}
#endif

static int process_teardown(unsigned descriptor,int reaped) {
  if (descriptor>=PROCESS_CAPACITY || !processes[descriptor].active) return 0;
  struct process_descriptor *p=&processes[descriptor];
  if (kotoba_aiueos_process_teardown_plan(p->domain,reaped,0,0,0)!=1) return 0;
  uint64_t revoked=aiueos_capability_revoke_owner(p->domain);
  if (kotoba_aiueos_process_teardown_plan(p->domain,reaped,revoked,0,1)!=2)
    return 0;
  uint64_t commit=kotoba_aiueos_process_teardown_plan(
    p->domain,reaped,revoked,1,2);
  uint64_t recipe=commit>>32;
  if ((uint32_t)commit!=3U ||
      recipe!=(AIUEOS_PROCESS_CLEAR_EXECUTION|AIUEOS_PROCESS_CLEAR_OWNERSHIP|
        AIUEOS_PROCESS_CLEAR_TASK|AIUEOS_PROCESS_CLEAR_ACTIVE|
        AIUEOS_PROCESS_CLEAR_RESULT)) return 0;
  if (!aiueos_address_space_reclaim(p->address_space)) return 0;
  if (recipe&AIUEOS_PROCESS_CLEAR_EXECUTION)
    p->entry=p->argument=p->user_stack=0;
  if (recipe&AIUEOS_PROCESS_CLEAR_OWNERSHIP)
    p->domain=p->address_space=0;
  if (recipe&AIUEOS_PROCESS_CLEAR_TASK) p->task_slot=0;
  if (recipe&AIUEOS_PROCESS_CLEAR_ACTIVE) p->active=0;
  if (recipe&AIUEOS_PROCESS_CLEAR_RESULT) p->result=0;
  return 1;
}

int aiueos_process_initialize(void) {
  int mappings=aiueos_user_mapping_verify();
  /* Scheduler initialization already created both roots. Rebuilding them here
   * would clear live private pages after service execution. */
  if (mappings != 7) return 0x10 | mappings;
  tss.rsp0=(uint64_t)(uintptr_t)aiueos_kernel_stack_top;
  aiueos_syscall_kernel_stack_top=tss.rsp0;
  tss.iomap=sizeof(tss);
  if (!syscall_transport_initialize()) return 0x20;
  uint64_t b=(uint64_t)(uintptr_t)&tss, limit=sizeof(tss)-1;
  aiueos_gdt_tss[0]=(limit & 0xffff) | ((b & 0xffffff)<<16) |
    (0x89ULL<<40) | ((limit & 0xf0000)<<32) | ((b & 0xff000000)<<32);
  aiueos_gdt_tss[1]=b>>32;
  for (unsigned p=0;p<PROCESS_CAPACITY;p++) processes[p]=(struct process_descriptor){0};
  process_lifecycle_evidence=0;
  process_results_valid=0;
  return 1;
}
void aiueos_process_enter(void) {
  uint64_t allocator_reuse_before;
  uint64_t recreated_entry=0,*recreated_result=0,*worker_result=0;
  if (!aiueos_scheduler_begin_user_runtime()) return;
  uint64_t *kotoba_result=0;
  int first=process_create(user_entry,2),second=process_create(user_entry,3);
  int kotoba=process_create_kotoba_elf(hello_app_id,4,&kotoba_result);
  int worker=process_create_kotoba_elf(worker_app_id,5,&worker_result);
  uint64_t *missing_result=0;
  catalog_lookup_rejection_evidence=process_create_kotoba_elf(missing_app_id,6,&missing_result)<0;
  if (first<0 || second<0 || kotoba<0 || worker<0 || !kotoba_result || !worker_result ||
      !catalog_lookup_rejection_evidence) return;
  kernel_results[0]=processes[first].result; kernel_results[1]=processes[second].result;
  kernel_results[0]->foreign_handle=kernel_results[1]->handle;
  kernel_results[1]->foreign_handle=kernel_results[0]->handle;
  kernel_results[0]->foreign_page=processes[second].argument;
  kernel_results[1]->foreign_page=processes[first].argument;
  __asm__ volatile("sti");
  {
    /* #108: one breadcrumb that the creates passed, then a bounded snapshot
       after each wake's flush (wakes 1..8, then every 32nd). The last line
       before silence names the stuck exit condition; wakes and timer together
       show whether any wakeup arrives at all. */
    uint64_t wakes = 0;
    p108_str("AIUEOS_PROCESS_PHASE_ENTER first=");
    p108_dec((uint32_t)first);
    p108_str(" second=");
    p108_dec((uint32_t)second);
    p108_str(" kotoba=");
    p108_dec((uint32_t)kotoba);
    p108_str(" worker=");
    p108_dec((uint32_t)worker);
    p108_str("\r\n");
    while (!aiueos_process_result() || !aiueos_user_scheduler_evidence_ready() ||
           *kotoba_result!=42 || *worker_result!=42 ||
           !aiueos_kotoba_service_ipc_evidence_ready() ||
           !aiueos_user_object_write_evidence_ready()) {
      int flushed;
      __asm__ volatile("cli");
      flushed = aiueos_user_object_flush_pending();
      wakes++;
      if (wakes <= 8 || (wakes & 31) == 0) {
        p108_str("AIUEOS_PROCESS_PHASE_WAIT wakes=");
        p108_dec((uint32_t)wakes);
        p108_str(" timer=");
        p108_dec((uint32_t)aiueos_external_timer_ticks);
        p108_str(" flush=");
        p108_dec((uint32_t)flushed);
        p108_str(" result=");
        p108_dec(aiueos_process_result() ? 1U : 0U);
        p108_str(" sched=");
        p108_dec(aiueos_user_scheduler_evidence_ready() ? 1U : 0U);
        p108_str(" kotoba=");
        p108_dec((uint32_t)*kotoba_result);
        p108_str(" worker=");
        p108_dec((uint32_t)*worker_result);
        p108_str(" ipc=");
        p108_dec(aiueos_kotoba_service_ipc_evidence_ready() ? 1U : 0U);
        p108_str(" objwrite=");
        p108_dec(aiueos_user_object_write_evidence_ready() ? 1U : 0U);
        p108_str("\r\n");
      }
      __asm__ volatile("sti; hlt");
    }
  }
  aiueos_scheduler_request_user_exit(2); aiueos_scheduler_request_user_exit(3);
  aiueos_scheduler_request_user_exit(4);
  aiueos_scheduler_request_user_exit(5);
  {
    uint64_t rwakes = 0;
    while (!aiueos_scheduler_users_reaped()) {
      if (rwakes <= 8 || (rwakes & 31) == 0) {
        p108_str("AIUEOS_PROCESS_PHASE_REAP_WAIT wakes=");
        p108_dec((uint32_t)rwakes);
        p108_str(" timer=");
        p108_dec((uint32_t)aiueos_external_timer_ticks);
        p108_str("\r\n");
      }
      rwakes++;
      __asm__ volatile("hlt");
    }
  }
  __asm__ volatile("cli");
  allocator_reuse_before=aiueos_physical_allocator_reuse_count();
  unsigned space0=processes[first].address_space,space1=processes[second].address_space;
  unsigned space2=processes[kotoba].address_space;
  unsigned space3=processes[worker].address_space;
  int reaped=aiueos_scheduler_users_reaped();
  if (aiueos_scheduler_finalize_user_stacks() &&
      aiueos_scheduler_task_capacity()==8 &&
      aiueos_scheduler_task_slot_self_test() &&
      process_teardown((unsigned)first,reaped) &&
      process_teardown((unsigned)second,reaped) &&
      process_teardown((unsigned)kotoba,reaped) &&
      process_teardown((unsigned)worker,reaped) &&
      !aiueos_capability_log_handle(2) && !aiueos_capability_log_handle(3) &&
      !aiueos_capability_log_handle(4) && !aiueos_capability_log_handle(5) &&
      aiueos_kotoba_process_loader_evidence_ready())
    process_lifecycle_evidence|=1;
  if (!processes[first].active && !processes[second].active &&
      !processes[kotoba].active && !processes[worker].active &&
      aiueos_address_space_reuse(space0) && aiueos_address_space_reuse(space1) &&
      aiueos_address_space_reclaim(space0) && aiueos_address_space_reclaim(space1) &&
      aiueos_address_space_reuse(space2) && aiueos_load_object_store_kotoba_process(
        space2,hello_app_id,&recreated_entry,&recreated_result) && recreated_entry==0x1e1000ULL &&
      recreated_result && *recreated_result==0 && aiueos_address_space_reclaim(space2) &&
      aiueos_address_space_reuse(space3) && aiueos_load_object_store_kotoba_process(
        space3,worker_app_id,&recreated_entry,&recreated_result) && recreated_entry==0x1e1000ULL &&
      recreated_result && *recreated_result==0 && aiueos_address_space_reclaim(space3) &&
      aiueos_physical_allocator_reuse_count()-allocator_reuse_before>=24)
    process_lifecycle_evidence|=2;
  if (aiueos_address_space_capacity()==8 && aiueos_address_space_slot_self_test())
    process_lifecycle_evidence|=4;
}
int aiueos_process_lifecycle_evidence_ready(void) {
  return process_lifecycle_evidence==7 && aiueos_scheduler_reap_evidence_ready();
}
int aiueos_catalog_lookup_rejection_evidence_ready(void) { return catalog_lookup_rejection_evidence; }
int aiueos_process_result(void) {
  if (process_results_valid) return 1;
  for (unsigned p=0; p<2; p++) {
    struct user_result *r=kernel_results[p];
    if (!r || !r->completed || r->abi!=ABI_V1 || r->valid!=5 ||
        r->too_big!=TOO_BIG || r->stale!=BAD_HANDLE ||
        r->foreign_owner!=BAD_HANDLE || r->wrong_type!=BAD_HANDLE ||
        r->no_rights!=BAD_HANDLE || r->bad_pointer!=BAD_POINTER ||
        r->scheduled_runs<2) return 0;
  }
  if (!kernel_results[0]->transfer ||
      kernel_results[0]->transfer==BAD_HANDLE ||
      kernel_results[0]->transfer_escalation!=BAD_HANDLE ||
      kernel_results[1]->claimed!=kernel_results[0]->transfer ||
      kernel_results[1]->transferred_valid!=5) return 0;
  process_results_valid=aiueos_syscall_from_user==3;
  return process_results_valid;
}

int aiueos_address_space_self_test(void) {
  int first_space=aiueos_address_space_claim(),second_space=aiueos_address_space_claim();
  if (first_space<2 || second_space<2 || first_space==second_space) return 0;
  uint64_t first=aiueos_address_space_private_va((unsigned)first_space);
  uint64_t second=aiueos_address_space_private_va((unsigned)second_space);
  uint64_t cr3_first=aiueos_address_space_enter((unsigned)first_space);
  *(volatile uint64_t *)(uintptr_t)first=0x1111111111111111ULL;
  aiueos_page_fault_stage=3; aiueos_probe_cross_process((const void *)(uintptr_t)second);
  if (aiueos_page_fault_stage!=0x103 || (aiueos_page_fault_error&1)) { aiueos_address_space_leave(); return 0; }
  uint64_t cr3_second=aiueos_address_space_enter((unsigned)second_space);
  if (*(volatile uint64_t *)(uintptr_t)second!=0) { aiueos_address_space_leave(); return 0; }
  *(volatile uint64_t *)(uintptr_t)second=0x2222222222222222ULL;
  aiueos_page_fault_stage=3; aiueos_probe_cross_process((const void *)(uintptr_t)first);
  int isolated=aiueos_page_fault_stage==0x103 && !(aiueos_page_fault_error&1) && cr3_first!=cr3_second;
  if (isolated) { aiueos_address_space_enter((unsigned)first_space); isolated=*(volatile uint64_t *)(uintptr_t)first==0x1111111111111111ULL; }
  aiueos_address_space_leave();
  return isolated && aiueos_address_space_reclaim((unsigned)first_space) &&
    aiueos_address_space_reclaim((unsigned)second_space);
}
