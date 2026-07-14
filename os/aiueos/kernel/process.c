#include <stdint.h>

#define ABI 0
#define LOG 1
#define EXIT 2
#define ABI_V1 0x00010000ULL
#define LOG_HANDLE 0xa105ca7e00010001ULL
#define BAD_HANDLE ((uint64_t)-9)
#define BAD_POINTER ((uint64_t)-14)

struct __attribute__((packed)) tss64 {
  uint32_t reserved0; uint64_t rsp0, rsp1, rsp2; uint64_t reserved1;
  uint64_t ist[7]; uint64_t reserved2; uint16_t reserved3, iomap;
};
extern uint64_t aiueos_gdt_tss[2];
extern uint8_t aiueos_kernel_stack_top[];
extern void aiueos_load_task_register(void);
extern void aiueos_enter_user(void (*entry)(void), void *stack);
extern int aiueos_user_mapping_verify(void);
extern uint64_t aiueos_syscall_from_user;
extern int aiueos_address_spaces_initialize(void);
extern uint64_t aiueos_address_space_enter(unsigned process);
extern void aiueos_address_space_leave(void);
extern uint64_t aiueos_address_space_private_va(unsigned process);
extern void aiueos_probe_cross_process(const void *address);
extern volatile uint64_t aiueos_page_fault_stage, aiueos_page_fault_error;
static struct tss64 tss;
static uint8_t syscall_stack[16384] __attribute__((aligned(4096)));

struct user_result { uint64_t abi, valid, bad_handle, bad_pointer, completed; };
__attribute__((section(".user.data"), aligned(4096)))
static volatile struct user_result result;
__attribute__((section(".user.data"))) static uint8_t user_stack[2048];
__attribute__((section(".user.data"))) static char user_message[] = "ring3";

static inline uint64_t call(uint64_t n, uint64_t h, const void *p, uint64_t l) {
  register uint64_t a __asm__("rax")=n;
  __asm__ volatile("int $0x80" : "+a"(a) : "D"(h), "S"(p), "d"(l) : "memory");
  return a;
}
__attribute__((section(".user.text"), noreturn))
static void user_entry(void) {
  result.abi = call(ABI,0,0,0);
  result.valid = call(LOG,LOG_HANDLE,user_message,5);
  result.bad_handle = call(LOG,LOG_HANDLE ^ 0x10000,user_message,1);
  result.bad_pointer = call(LOG,LOG_HANDLE,(void *)0x180000,1); /* RX, not readable user data policy */
  result.completed = 1;
  call(EXIT,0,0,0);
  for (;;) __asm__ volatile("ud2");
}

int aiueos_process_initialize(void) {
  int mappings=aiueos_user_mapping_verify();
  if (mappings != 7) return 0x10 | mappings;
  tss.rsp0=(uint64_t)(uintptr_t)(syscall_stack + sizeof(syscall_stack)); tss.iomap=sizeof(tss);
  uint64_t b=(uint64_t)(uintptr_t)&tss, limit=sizeof(tss)-1;
  aiueos_gdt_tss[0]=(limit & 0xffff) | ((b & 0xffffff)<<16) |
    (0x89ULL<<40) | ((limit & 0xf0000)<<32) | ((b & 0xff000000)<<32);
  aiueos_gdt_tss[1]=b>>32;
  return 1;
}
void aiueos_process_enter(void) {
  aiueos_enter_user(user_entry, user_stack + sizeof(user_stack));
}
int aiueos_process_result(void) {
  return aiueos_syscall_from_user == 3 && result.completed &&
    result.abi==ABI_V1 && result.valid==5 &&
    result.bad_handle==BAD_HANDLE && result.bad_pointer==BAD_POINTER;
}

int aiueos_address_space_self_test(void) {
  if (!aiueos_address_spaces_initialize()) return 0;
  uint64_t first = aiueos_address_space_private_va(0);
  uint64_t second = aiueos_address_space_private_va(1);
  uint64_t cr3_first = aiueos_address_space_enter(0);
  *(volatile uint64_t *)(uintptr_t)first = 0x1111111111111111ULL;
  aiueos_page_fault_stage = 3;
  aiueos_probe_cross_process((const void *)(uintptr_t)second);
  if (aiueos_page_fault_stage != 0x103 || (aiueos_page_fault_error & 1)) {
    aiueos_address_space_leave(); return 0;
  }
  uint64_t cr3_second = aiueos_address_space_enter(1);
  if (*(volatile uint64_t *)(uintptr_t)second != 0) {
    aiueos_address_space_leave(); return 0;
  }
  *(volatile uint64_t *)(uintptr_t)second = 0x2222222222222222ULL;
  aiueos_page_fault_stage = 3;
  aiueos_probe_cross_process((const void *)(uintptr_t)first);
  int isolated = aiueos_page_fault_stage == 0x103 &&
    !(aiueos_page_fault_error & 1) && cr3_first != cr3_second;
  if (isolated) {
    aiueos_address_space_enter(0);
    isolated = *(volatile uint64_t *)(uintptr_t)first ==
      0x1111111111111111ULL;
  }
  aiueos_address_space_leave();
  return isolated;
}
