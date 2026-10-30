#include "trap.h"
uint8_t trap_regs[4096];
uint64_t trap_trace;
unsigned trap_accesses;
extern uint64_t pd[2048];
static uint64_t pt[512] __attribute__((aligned(4096)));
static uint8_t page[4096] __attribute__((aligned(4096)));
static uint8_t before[4096];
static unsigned fault_offset;
/* What the faulting instruction does to memory, so the trace records bus transactions, not instructions: a
   read-modify-write (orb $8, 20(%rdi)) is a read then a write, the same as a separate load and store. Only the forms
   the C compiler and the Amu object route emit are known; anything else halts rather than guessing. */
enum { K_READ = 1, K_WRITE = 2, K_RMW = 3 };
static int kind;
static int classify(const uint8_t *ip) {
  while (*ip == 0x66 || *ip == 0xf0 || (*ip >= 0x40 && *ip <= 0x4f)) ip++;
  uint8_t op = ip[0], reg = (uint8_t)((ip[1] >> 3) & 7);
  if (op == 0x0f) { op = ip[1]; return (op == 0xb6 || op == 0xb7 || op == 0xbe || op == 0xbf) ? K_READ : 0; }
  switch (op) {
  case 0x8a: case 0x8b: case 0x84: case 0x85: case 0x38: case 0x39: case 0x3a: case 0x3b: return K_READ;
  case 0x88: case 0x89: case 0xc6: case 0xc7: return K_WRITE;
  case 0x00: case 0x01: case 0x08: case 0x09: case 0x10: case 0x11: case 0x18: case 0x19:
  case 0x20: case 0x21: case 0x28: case 0x29: case 0x30: case 0x31: return K_RMW;
  case 0x80: case 0x81: case 0x83: return reg == 7 ? K_READ : K_RMW;
  case 0xf6: case 0xf7: return reg <= 1 ? K_READ : (reg <= 3 ? K_RMW : 0);
  case 0xfe: case 0xff: return reg <= 1 ? K_RMW : 0;
  }
  return 0;
}
struct idt_gate { uint16_t lo; uint16_t sel; uint8_t ist; uint8_t attr; uint16_t mid; uint32_t hi; uint32_t zero; } __attribute__((packed));
static struct idt_gate idt[32] __attribute__((aligned(16)));
void isr_db(void); void isr_pf(void);
static void gate(int v, void (*h)(void)) {
  uint64_t a = (uint64_t)(uintptr_t)h;
  idt[v] = (struct idt_gate){(uint16_t)a, 0x08, 0, 0x8e, (uint16_t)(a >> 16), (uint32_t)(a >> 32), 0};
}
static void invlpg(uint64_t a) { __asm__ volatile("invlpg (%0)" :: "r"(a) : "memory"); }
static void mix(uint64_t v) { trap_trace = (trap_trace ^ v) * 1099511628211ull; }
void trap_reset(void) { trap_trace = 14695981039346656037ull; trap_accesses = 0; }
void trap_init(void) {
  gate(1, isr_db); gate(14, isr_pf);
  struct { uint16_t limit; uint64_t base; } __attribute__((packed)) idtr = {sizeof idt - 1, (uint64_t)(uintptr_t)idt};
  __asm__ volatile("lidt %0" :: "m"(idtr));
  for (int i = 0; i < 512; i++) pt[i] = 0;
  pd[TRAP_WINDOW >> 21] = (uint64_t)(uintptr_t)pt | 3;     /* the 2 MiB slot at the window becomes 4 KiB pages */
  invlpg(TRAP_WINDOW);
  trap_reset();
}
void trap_pf(uint64_t *frame) {
  uint64_t cr2; __asm__ volatile("mov %%cr2, %0" : "=r"(cr2));
  if (cr2 < TRAP_WINDOW || cr2 >= TRAP_WINDOW + 4096) { for (;;) __asm__ volatile("hlt"); }
  fault_offset = (unsigned)(cr2 - TRAP_WINDOW);
  kind = classify((const uint8_t *)(uintptr_t)frame[15 + 1]);
  if (!kind) { for (;;) __asm__ volatile("hlt"); }
  for (int i = 0; i < 4096; i++) page[i] = before[i] = trap_regs[i];
  pt[0] = (uint64_t)(uintptr_t)page | 3; invlpg(TRAP_WINDOW);
  frame[15 + 1 + 2] |= 0x100;                                /* TF in rflags (past the error code, rip, cs) */
}
void trap_db(uint64_t *frame) {
  int wrote = 0; unsigned first = 0;
  if (kind & K_READ) mix(0x100000000ull | fault_offset);
  for (unsigned i = 0; i < 4096; i++) if (page[i] != before[i]) { if (!wrote) first = i; wrote = 1; mix(0x200000000ull | i << 8 | page[i]); }
  if ((kind & K_WRITE) && !wrote) mix(0x300000000ull | fault_offset);    /* a write of the value already there */
  if ((kind & K_WRITE) && !wrote) { wrote = 1; first = fault_offset; }
  trap_accesses += kind == K_RMW ? 2 : 1;                     /* bus transactions */
  for (int i = 0; i < 4096; i++) trap_regs[i] = page[i];
  pt[0] = 0; invlpg(TRAP_WINDOW);
  frame[15 + 2] &= ~0x100ull;                                /* TF off (rip, cs, rflags) */
  if (wrote) trap_model_after_write(first);
}
