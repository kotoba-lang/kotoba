#include <stdint.h>

enum { AIUEOS_SYSCALL_ABI = 0, AIUEOS_SYSCALL_LOG_WRITE = 1,
       AIUEOS_SYSCALL_CAP_TRANSFER = 3, AIUEOS_SYSCALL_CAP_CLAIM = 4,
       AIUEOS_SYSCALL_RUNTIME_CALL = 5 };
#define AIUEOS_SYSCALL_ABI_V1 0x00010000ULL
#define AIUEOS_ERR_NO_SYSCALL ((uint64_t)-38)
#define AIUEOS_ERR_BAD_HANDLE ((uint64_t)-9)
#define AIUEOS_ERR_BAD_POINTER ((uint64_t)-14)
#define AIUEOS_ERR_TOO_BIG ((uint64_t)-7)
#define AIUEOS_SYSCALL_COPY_MAX 256ULL
#define AIUEOS_CAPABILITY_ACTIVE 0x10000U
#define AIUEOS_CAPABILITY_TYPE_LOG 1U
#define AIUEOS_CAPABILITY_TYPE_KOTOBA_RUNTIME 2U
#define AIUEOS_CAPABILITY_RIGHT_LOG_WRITE 1U
#define AIUEOS_CAPABILITY_RIGHT_OBJECT_READ 1U
#define AIUEOS_CAPABILITY_RIGHT_SERVICE_SEND 2U
#define AIUEOS_CAPABILITY_RIGHT_OBJECT_WRITE 4U
#define AIUEOS_CAPABILITY_RIGHT_RUNTIME \
  (AIUEOS_CAPABILITY_RIGHT_OBJECT_READ|AIUEOS_CAPABILITY_RIGHT_SERVICE_SEND| \
   AIUEOS_CAPABILITY_RIGHT_OBJECT_WRITE)
#define AIUEOS_DOMAIN_KERNEL 1U
#define AIUEOS_DOMAIN_USER_PROCESS 2U
#define AIUEOS_CAP_MUTATE_TYPE 1U
#define AIUEOS_CAP_MUTATE_STATE 2U
#define AIUEOS_CAP_MUTATE_OWNER 4U
#define AIUEOS_CAP_MUTATE_PARENT 8U
#define AIUEOS_CAP_MUTATE_GENERATION 16U
#define AIUEOS_CAP_MUTATE_PENDING 32U
volatile uint16_t aiueos_current_user_domain;

struct capability_slot {
  uint16_t generation;
  uint16_t type;
  uint32_t state_rights;
  uint16_t owner;
  uint16_t parent_slot;
  uint16_t parent_generation;
};
_Static_assert(sizeof(struct capability_slot)==16,"capability table must retain 256 slots");

static struct capability_slot *capability_table;
static uint16_t capability_capacity;
static volatile uint8_t capability_lock;
static uint64_t dynamic_capability_evidence;
static uint64_t capability_derivation_evidence;
static uint64_t pending_transfer_handle;
static uint16_t pending_transfer_owner;
static uint64_t kotoba_runtime_evidence;
extern void *aiueos_allocate_physical_page(void);

static void capability_lock_acquire(void) {
  while (__atomic_test_and_set(&capability_lock,__ATOMIC_ACQUIRE))
    __asm__ volatile("pause");
}
static void capability_lock_release(void) {
  __atomic_clear(&capability_lock,__ATOMIC_RELEASE);
}

extern uint64_t kotoba_aiueos_syscall_range_valid(
  uint64_t pointer, uint64_t length, uint64_t lower, uint64_t upper);
extern uint64_t kotoba_aiueos_copy_in(
  const void *source, uint64_t source_length, void *destination,
  uint64_t destination_length, uint64_t count);
extern uint64_t kotoba_aiueos_fnv1a(const uint8_t *bytes, uint64_t length);
extern uint64_t kotoba_aiueos_capability_plan(
  uint64_t slot, uint64_t generation, uint64_t type,
  uint64_t state_rights, uint64_t request);
extern uint64_t kotoba_aiueos_capability_mutation_plan(
  uint64_t action,uint64_t generation,uint64_t type,
  uint64_t state_rights,uint64_t request);

static uint8_t syscall_copy_buffer[AIUEOS_SYSCALL_COPY_MAX];
uint64_t aiueos_syscall_last_copy_length;
uint64_t aiueos_syscall_last_copy_hash;

extern uint8_t aiueos_user_data_start[], aiueos_user_data_end[];
extern uint64_t aiueos_syscall_from_user;
extern int aiueos_process_address_space_for_domain(uint16_t domain);
static int readable_user_range(uint64_t pointer, uint64_t length) {
  int process=aiueos_process_address_space_for_domain(aiueos_current_user_domain);
  if (process>=0) {
    extern uint64_t aiueos_address_space_private_va(unsigned process);
    uint64_t lower = aiueos_address_space_private_va((unsigned)process);
    return (int)kotoba_aiueos_syscall_range_valid(pointer,length,lower,lower + 4096);
  }
  return (int)kotoba_aiueos_syscall_range_valid(
    pointer, length, (uint64_t)(uintptr_t)aiueos_user_data_start,
    (uint64_t)(uintptr_t)aiueos_user_data_end);
}

static uint64_t capability_plan(uint16_t slot, uint16_t type, uint16_t rights,
                                uint16_t requester) {
  if (!capability_table || !slot || slot >= capability_capacity) return 0;
  struct capability_slot *entry = &capability_table[slot];
  uint64_t state = entry->state_rights | ((uint64_t)entry->owner << 17);
  uint64_t request = rights | ((uint64_t)type << 16) |
    ((uint64_t)requester << 32);
  return kotoba_aiueos_capability_plan(slot, entry->generation, entry->type,
                                      state, request);
}

static int capability_admit(uint64_t handle, uint16_t type, uint16_t rights,
                            uint16_t requester) {
  capability_lock_acquire();
  uint16_t slot = (uint16_t)handle;
  uint64_t planned = capability_plan(slot,type,rights,requester);
  int admitted = planned && planned == handle;
  capability_lock_release();
  return admitted;
}

static uint64_t capability_mutation_plan(uint64_t action,
    const struct capability_slot *entry,uint16_t type,uint16_t rights,
    uint16_t owner) {
  uint64_t state=entry->state_rights|((uint64_t)entry->owner<<17);
  uint64_t request=rights|((uint64_t)type<<16)|((uint64_t)owner<<32);
  return kotoba_aiueos_capability_mutation_plan(action,entry->generation,
    entry->type,state,request);
}

static uint16_t capability_revoke_slot_locked(uint16_t slot) {
  struct capability_slot *entry=&capability_table[slot];
  uint16_t old_generation=entry->generation;
  uint64_t plan=capability_mutation_plan(2,entry,0,0,0);
  uint64_t action=(plan>>16)&255U, recipe=plan>>24;
  if (!plan || action!=2 ||
      recipe!=(AIUEOS_CAP_MUTATE_STATE|AIUEOS_CAP_MUTATE_PARENT|
        AIUEOS_CAP_MUTATE_GENERATION|AIUEOS_CAP_MUTATE_PENDING)) return 0;
  if ((recipe&AIUEOS_CAP_MUTATE_PENDING) &&
      (uint16_t)pending_transfer_handle==slot &&
      (uint16_t)(pending_transfer_handle>>16)==old_generation) {
    pending_transfer_handle=0; pending_transfer_owner=0;
  }
  if (recipe&AIUEOS_CAP_MUTATE_STATE)
    entry->state_rights&=~AIUEOS_CAPABILITY_ACTIVE;
  if (recipe&AIUEOS_CAP_MUTATE_GENERATION) entry->generation=(uint16_t)plan;
  if (recipe&AIUEOS_CAP_MUTATE_PARENT)
    entry->parent_slot=entry->parent_generation=0;
  return old_generation;
}

static uint64_t capability_revoke_graph_locked(uint16_t root) {
  uint16_t slots[256],generations[256],head=0,tail=0;
  if (!root || root>=capability_capacity ||
      !(capability_table[root].state_rights&AIUEOS_CAPABILITY_ACTIVE)) return 0;
  uint16_t root_generation=capability_revoke_slot_locked(root);
  if (!root_generation) return 0;
  slots[tail]=root; generations[tail++]=root_generation;
  while (head<tail) {
    uint16_t parent=slots[head],generation=generations[head++];
    for (uint16_t slot=1;slot<capability_capacity;slot++) {
      struct capability_slot *entry=&capability_table[slot];
      if ((entry->state_rights&AIUEOS_CAPABILITY_ACTIVE) &&
          entry->parent_slot==parent && entry->parent_generation==generation) {
        if (tail>=256) return 0;
        uint16_t child_generation=capability_revoke_slot_locked(slot);
        if (!child_generation) return 0;
        slots[tail]=slot; generations[tail++]=child_generation;
      }
    }
  }
  return tail;
}

static int capability_revoke(uint16_t slot) {
  if (!capability_table || !slot || slot >= capability_capacity) return 0;
  capability_lock_acquire();
  uint64_t revoked=capability_revoke_graph_locked(slot);
  capability_lock_release();
  return revoked!=0;
}

static uint64_t capability_issue(uint16_t slot, uint16_t type, uint16_t rights,
                                 uint16_t owner) {
  if (!capability_table || !slot || slot >= capability_capacity ||
      !type || !rights || !owner) return 0;
  struct capability_slot *entry = &capability_table[slot];
  if (!entry->generation) return 0; /* exhausted/uninitialized slots fail closed */
  uint64_t plan=capability_mutation_plan(1,entry,type,rights,owner);
  uint64_t action=(plan>>16)&255U, recipe=plan>>24;
  if (!plan || (uint16_t)plan!=entry->generation || action!=1 ||
      recipe!=(AIUEOS_CAP_MUTATE_TYPE|AIUEOS_CAP_MUTATE_STATE|
        AIUEOS_CAP_MUTATE_OWNER|AIUEOS_CAP_MUTATE_PARENT)) return 0;
  if (recipe&AIUEOS_CAP_MUTATE_TYPE) entry->type=type;
  if (recipe&AIUEOS_CAP_MUTATE_STATE)
    entry->state_rights=AIUEOS_CAPABILITY_ACTIVE|rights;
  if (recipe&AIUEOS_CAP_MUTATE_OWNER) entry->owner=owner;
  if (recipe&AIUEOS_CAP_MUTATE_PARENT)
    entry->parent_slot=entry->parent_generation=0;
  return capability_plan(slot,type,rights,owner);
}

static uint64_t capability_allocate(uint16_t type, uint16_t rights,
                                    uint16_t owner) {
  capability_lock_acquire();
  for (uint16_t slot = 1; slot < capability_capacity; slot++) {
    struct capability_slot *entry = &capability_table[slot];
    if (entry->generation && !(entry->state_rights & AIUEOS_CAPABILITY_ACTIVE)) {
      uint64_t handle = capability_issue(slot,type,rights,owner);
      capability_lock_release();
      return handle;
    }
  }
  capability_lock_release();
  return 0;
}

int aiueos_capability_table_initialize(void) {
  capability_table = aiueos_allocate_physical_page();
  if (!capability_table) return 0;
  capability_capacity = (uint16_t)(4096U / sizeof(*capability_table));
  capability_lock = 0;
  dynamic_capability_evidence = 0;
  capability_derivation_evidence = 0;
  pending_transfer_handle = 0; pending_transfer_owner = 0;
  kotoba_runtime_evidence = 0;
  for (uint16_t slot = 1; slot < capability_capacity; slot++)
    capability_table[slot].generation = 1;
  return capability_capacity >= 256 &&
    capability_issue(1,AIUEOS_CAPABILITY_TYPE_LOG,
      AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_KERNEL) &&
    capability_issue(2,AIUEOS_CAPABILITY_TYPE_LOG,
      AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_USER_PROCESS);
}

static uint64_t capability_transfer_publish(uint64_t source_handle,
    uint16_t source_owner, uint16_t target_owner, uint16_t rights) {
  if (!target_owner || target_owner == source_owner || !rights) return 0;
  capability_lock_acquire();
  if (pending_transfer_handle) { capability_lock_release(); return 0; }
  uint16_t source_slot=(uint16_t)source_handle;
  uint64_t admitted=capability_plan(source_slot,AIUEOS_CAPABILITY_TYPE_LOG,
                                    rights,source_owner);
  if (!admitted || admitted!=source_handle) { capability_lock_release(); return 0; }
  for (uint16_t slot=1; slot<capability_capacity; slot++) {
    struct capability_slot *entry=&capability_table[slot];
    if (entry->generation && !(entry->state_rights&AIUEOS_CAPABILITY_ACTIVE)) {
      uint64_t target=capability_issue(slot,AIUEOS_CAPABILITY_TYPE_LOG,rights,target_owner);
      if (target) {
        uint16_t parent_generation=(uint16_t)(source_handle>>16);
        uint64_t state=entry->state_rights|((uint64_t)entry->owner<<17);
        uint64_t request=source_slot|((uint64_t)parent_generation<<16);
        uint64_t parent_plan=kotoba_aiueos_capability_mutation_plan(3,
          entry->generation,entry->type,state,request);
        if (!parent_plan || (uint16_t)parent_plan!=entry->generation ||
            ((parent_plan>>16)&255U)!=3 ||
            (parent_plan>>24)!=AIUEOS_CAP_MUTATE_PARENT) {
          capability_revoke_slot_locked(slot);
          capability_lock_release(); return 0;
        }
        entry->parent_slot=source_slot;
        entry->parent_generation=parent_generation;
        pending_transfer_handle=target; pending_transfer_owner=target_owner;
      }
      capability_lock_release(); return target;
    }
  }
  capability_lock_release(); return 0;
}

static uint64_t capability_claim_transfer(uint16_t owner) {
  capability_lock_acquire();
  uint64_t handle=0;
  if (pending_transfer_owner==owner) {
    handle=pending_transfer_handle; pending_transfer_handle=0; pending_transfer_owner=0;
  }
  capability_lock_release(); return handle;
}

uint16_t aiueos_capability_table_capacity(void) { return capability_capacity; }
int aiueos_dynamic_capability_evidence_ready(void) {
  return dynamic_capability_evidence == 3;
}
int aiueos_capability_derivation_evidence_ready(void) {
  return capability_derivation_evidence==3;
}
uint64_t aiueos_capability_log_handle(uint16_t owner) {
  capability_lock_acquire();
  for (uint16_t slot = 1; slot < capability_capacity; slot++) {
    struct capability_slot *entry = &capability_table[slot];
    if (entry->owner == owner && entry->type == AIUEOS_CAPABILITY_TYPE_LOG &&
        (entry->state_rights & AIUEOS_CAPABILITY_ACTIVE)) {
      uint64_t handle = capability_plan(slot,AIUEOS_CAPABILITY_TYPE_LOG,
        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,owner);
      capability_lock_release();
      return handle;
    }
  }
  capability_lock_release();
  return 0;
}
uint64_t aiueos_capability_ensure_log_handle(uint16_t owner) {
  uint64_t handle=aiueos_capability_log_handle(owner);
  return handle ? handle : capability_allocate(AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,owner);
}
uint64_t aiueos_capability_ensure_runtime_handle(uint16_t owner) {
  capability_lock_acquire();
  for (uint16_t slot=1;slot<capability_capacity;slot++) {
    struct capability_slot *entry=&capability_table[slot];
    if (entry->owner==owner && entry->type==AIUEOS_CAPABILITY_TYPE_KOTOBA_RUNTIME &&
        (entry->state_rights&AIUEOS_CAPABILITY_ACTIVE)) {
      uint64_t handle=capability_plan(slot,AIUEOS_CAPABILITY_TYPE_KOTOBA_RUNTIME,
        AIUEOS_CAPABILITY_RIGHT_RUNTIME,owner);
      capability_lock_release(); return handle;
    }
  }
  capability_lock_release();
  return capability_allocate(AIUEOS_CAPABILITY_TYPE_KOTOBA_RUNTIME,
    AIUEOS_CAPABILITY_RIGHT_RUNTIME,owner);
}
uint64_t aiueos_capability_revoke_owner(uint16_t owner) {
  uint64_t revoked=0;
  capability_lock_acquire();
  for (uint16_t slot=1;slot<capability_capacity;slot++) {
    struct capability_slot *entry=&capability_table[slot];
    if (entry->owner==owner && (entry->state_rights&AIUEOS_CAPABILITY_ACTIVE)) {
      revoked+=capability_revoke_graph_locked(slot);
    }
  }
  if (pending_transfer_owner==owner) { pending_transfer_handle=0; pending_transfer_owner=0; }
  capability_lock_release(); return revoked;
}

uint64_t aiueos_syscall_dispatch(uint64_t number, uint64_t handle,
                                 uint64_t pointer, uint64_t length) {
  if (number == AIUEOS_SYSCALL_ABI) return AIUEOS_SYSCALL_ABI_V1;
  if (number == 2) return 2; /* assembly consumes this completion token */
  uint16_t requester = aiueos_syscall_from_user == 3 ?
    aiueos_current_user_domain : AIUEOS_DOMAIN_KERNEL;
  if (number == AIUEOS_SYSCALL_CAP_TRANSFER) {
    uint64_t transferred=capability_transfer_publish(handle,requester,
      (uint16_t)pointer,(uint16_t)length);
    return transferred ? transferred : AIUEOS_ERR_BAD_HANDLE;
  }
  if (number == AIUEOS_SYSCALL_CAP_CLAIM) {
    uint64_t claimed=capability_claim_transfer(requester);
    return claimed ? claimed : AIUEOS_ERR_BAD_HANDLE;
  }
  if (number == AIUEOS_SYSCALL_RUNTIME_CALL) {
    if (!capability_admit(handle,AIUEOS_CAPABILITY_TYPE_KOTOBA_RUNTIME,
                          AIUEOS_CAPABILITY_RIGHT_RUNTIME,requester))
      return AIUEOS_ERR_BAD_HANDLE;
#ifdef AIUEOS_PLC_RT_SMOKE
    if (requester==4 && pointer>=16 && pointer<=19) {
      extern uint64_t aiueos_plc_capability_call(uint64_t,uint64_t);
      return aiueos_plc_capability_call(pointer,length);
    }
#endif
    /* Capability 2 is the bounded service-registry object read. The compiler
       admits the literal ID, and the kernel still checks both the domain-owned
       handle and the scalar object index on every transition. */
    if (pointer==2 && length<2) {
      extern uint64_t aiueos_object_store_service_state(unsigned service);
      uint64_t state=aiueos_object_store_service_state((unsigned)length);
      if (state && requester>=4 && requester<=5)
        kotoba_runtime_evidence|=1ULL<<(requester-4);
      return state ? state : AIUEOS_ERR_BAD_HANDLE;
    }
    if (pointer==3 && requester>=4 && requester<=5) {
      extern uint64_t aiueos_kotoba_service_send(uint16_t domain,uint64_t payload);
      return aiueos_kotoba_service_send(requester,length) ? 1 : AIUEOS_ERR_BAD_HANDLE;
    }
    if (pointer==4 && requester>=4 && requester<=5) {
      extern uint64_t aiueos_user_object_write(uint16_t domain,uint64_t value);
      uint64_t sequence=aiueos_user_object_write(requester,length);
      return sequence ? sequence : AIUEOS_ERR_BAD_HANDLE;
    }
    if (pointer==5 && !length && requester>=4 && requester<=5) {
      extern uint64_t aiueos_user_object_receipt(uint16_t domain);
      uint64_t value=aiueos_user_object_receipt(requester);
      return value ? value : AIUEOS_ERR_BAD_HANDLE;
    }
    return AIUEOS_ERR_NO_SYSCALL;
  }
  if (number != AIUEOS_SYSCALL_LOG_WRITE) return AIUEOS_ERR_NO_SYSCALL;
  if (!capability_admit(handle,AIUEOS_CAPABILITY_TYPE_LOG,
                        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,requester))
    return AIUEOS_ERR_BAD_HANDLE;
  if (length > AIUEOS_SYSCALL_COPY_MAX) return AIUEOS_ERR_TOO_BIG;
  if (aiueos_syscall_from_user ? !readable_user_range(pointer,length) :
      !kotoba_aiueos_syscall_range_valid(pointer,length,0x1000,0x40000000ULL))
    return AIUEOS_ERR_BAD_POINTER;
  if (!kotoba_aiueos_copy_in((const void *)(uintptr_t)pointer, length,
                             syscall_copy_buffer, sizeof(syscall_copy_buffer), length))
    return AIUEOS_ERR_BAD_POINTER;
  aiueos_syscall_last_copy_length = length;
  aiueos_syscall_last_copy_hash = kotoba_aiueos_fnv1a(syscall_copy_buffer,length);
  return length;
}
int aiueos_kotoba_runtime_evidence_ready(void) {
  return kotoba_runtime_evidence==3;
}

static uint64_t invoke(uint64_t number, uint64_t handle,
                       const void *pointer, uint64_t length) {
  register uint64_t rax __asm__("rax") = number;
  register uint64_t rdi __asm__("rdi") = handle;
  register const void *rsi __asm__("rsi") = pointer;
  register uint64_t rdx __asm__("rdx") = length;
  __asm__ volatile("int $0x80" : "+a"(rax) : "D"(rdi), "S"(rsi), "d"(rdx)
                   : "rcx", "r8", "r9", "r10", "r11", "memory");
  return rax;
}

int aiueos_syscall_self_test(void) {
  static const char message[] = "capability-bound";
  uint64_t log_handle = capability_plan(1,AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_KERNEL);
  if (log_handle != 0x0001000100010001ULL) return 0;
  if (invoke(AIUEOS_SYSCALL_ABI, 0, 0, 0) != AIUEOS_SYSCALL_ABI_V1) return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle, message,
             sizeof(message) - 1) != sizeof(message) - 1) return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle ^ 0x10000ULL, message, 1) !=
      AIUEOS_ERR_BAD_HANDLE) return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle ^ 0x100000000ULL, message, 1) !=
      AIUEOS_ERR_BAD_HANDLE) return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, 0x0001000100010004ULL, message, 1) !=
      AIUEOS_ERR_BAD_HANDLE) return 0;
  capability_table[1].state_rights = AIUEOS_CAPABILITY_ACTIVE | 2;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, 0x0002000100010001ULL, message, 1) !=
      AIUEOS_ERR_BAD_HANDLE) return 0;
  capability_table[1].state_rights =
    AIUEOS_CAPABILITY_ACTIVE | AIUEOS_CAPABILITY_RIGHT_LOG_WRITE;
  if (!capability_revoke(1) ||
      invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle, message, 1) !=
        AIUEOS_ERR_BAD_HANDLE) return 0;
  log_handle = capability_issue(1,AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_KERNEL);
  if (log_handle != 0x0001000100020001ULL ||
      invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle, message, 1) != 1) return 0;
  uint64_t user_handle = capability_plan(2,AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_USER_PROCESS);
  if (user_handle != 0x0001000100010002ULL ||
      invoke(AIUEOS_SYSCALL_LOG_WRITE,user_handle,message,1) !=
        AIUEOS_ERR_BAD_HANDLE || !capability_revoke(2)) return 0;
  user_handle = capability_issue(2,AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_USER_PROCESS);
  if (user_handle != 0x0001000100020002ULL ||
      invoke(AIUEOS_SYSCALL_LOG_WRITE,user_handle,message,1) !=
        AIUEOS_ERR_BAD_HANDLE) return 0;
  uint64_t domain3_handle = capability_allocate(AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,3);
  uint16_t domain3_slot = (uint16_t)domain3_handle;
  if (domain3_slot < 3 || !capability_plan(domain3_slot,
      AIUEOS_CAPABILITY_TYPE_LOG,AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,3) ||
      capability_plan(domain3_slot,AIUEOS_CAPABILITY_TYPE_LOG,
        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_USER_PROCESS)) return 0;
  if (!capability_revoke(domain3_slot)) return 0;
  uint64_t domain3_reissued = capability_issue(domain3_slot,
    AIUEOS_CAPABILITY_TYPE_LOG,AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,3);
  if (!domain3_reissued || domain3_reissued == domain3_handle ||
      capability_plan(domain3_slot,AIUEOS_CAPABILITY_TYPE_LOG,
        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,3) != domain3_reissued) return 0;
  dynamic_capability_evidence |= 1;
  uint16_t exhausted = capability_capacity - 1;
  capability_table[exhausted].generation = 0xffffU;
  capability_table[exhausted].type = AIUEOS_CAPABILITY_TYPE_LOG;
  capability_table[exhausted].state_rights =
    AIUEOS_CAPABILITY_ACTIVE | AIUEOS_CAPABILITY_RIGHT_LOG_WRITE;
  capability_table[exhausted].owner = AIUEOS_DOMAIN_KERNEL;
  if (!capability_revoke(exhausted) || capability_issue(exhausted,AIUEOS_CAPABILITY_TYPE_LOG,
      AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_KERNEL) != 0) return 0;
  dynamic_capability_evidence |= 2;
  uint64_t graph_root=capability_allocate(AIUEOS_CAPABILITY_TYPE_LOG,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,AIUEOS_DOMAIN_KERNEL);
  uint64_t graph_child=capability_transfer_publish(graph_root,AIUEOS_DOMAIN_KERNEL,2,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE);
  if (!graph_root || !graph_child || capability_claim_transfer(2)!=graph_child) return 0;
  uint64_t graph_grandchild=capability_transfer_publish(graph_child,2,3,
    AIUEOS_CAPABILITY_RIGHT_LOG_WRITE);
  if (!graph_grandchild || capability_claim_transfer(3)!=graph_grandchild ||
      !capability_plan((uint16_t)graph_grandchild,AIUEOS_CAPABILITY_TYPE_LOG,
        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,3)) return 0;
  capability_lock_acquire();
  uint64_t graph_revoked=capability_revoke_graph_locked((uint16_t)graph_root);
  capability_lock_release();
  if (graph_revoked!=3 || capability_plan((uint16_t)graph_root,
        AIUEOS_CAPABILITY_TYPE_LOG,AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,1) ||
      capability_plan((uint16_t)graph_child,AIUEOS_CAPABILITY_TYPE_LOG,
        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,2) ||
      capability_plan((uint16_t)graph_grandchild,AIUEOS_CAPABILITY_TYPE_LOG,
        AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,3)) return 0;
  capability_derivation_evidence|=1;
  uint64_t graph_reissued=capability_issue((uint16_t)graph_root,
    AIUEOS_CAPABILITY_TYPE_LOG,AIUEOS_CAPABILITY_RIGHT_LOG_WRITE,1);
  if (!graph_reissued || graph_reissued==graph_root ||
      capability_table[(uint16_t)graph_child].parent_slot ||
      capability_table[(uint16_t)graph_grandchild].parent_slot ||
      !capability_revoke((uint16_t)graph_reissued)) return 0;
  capability_derivation_evidence|=2;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle,
             (const void *)0x0000800000000000ULL, 1) != AIUEOS_ERR_BAD_POINTER)
    return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle,
             (const void *)0x3fffffffULL, 2) != AIUEOS_ERR_BAD_POINTER)
    return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle, message, 0) !=
      AIUEOS_ERR_BAD_POINTER) return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle, message, 257) !=
      AIUEOS_ERR_TOO_BIG) return 0;
  if (invoke(AIUEOS_SYSCALL_LOG_WRITE, log_handle, message,
             sizeof(message) - 1) != sizeof(message) - 1) return 0;
  return aiueos_syscall_last_copy_length == sizeof(message) - 1 &&
    (uint32_t)aiueos_syscall_last_copy_hash == 0x51bda436U;
}
