/* The MMIO trap harness (JUN-598). A 4 KiB device window at TRAP_WINDOW is not present; every access to it faults (#PF),
   the handler maps a scratch page holding the device model's registers and single-steps the one instruction (#DB),
   then records what the instruction did on the bus -- a read at the faulting address for a load, the changed bytes (or a
   same-value write) for a store, both for a read-modify-write -- into an FNV trace, copies the page back into the model, lets the model react, and unmaps the page again. Two
   implementations that make the same accesses in the same order produce the same trace and leave the same registers. */
#include <stdint.h>
#define TRAP_WINDOW 0x40000000ull
extern uint8_t trap_regs[4096];          /* the device model's registers, offset = address - TRAP_WINDOW */
extern uint64_t trap_trace;              /* FNV-1a over (kind, offset, value) of every access */
extern unsigned trap_accesses;          /* bus transactions (a read-modify-write is 2) */
/* called after each write with the offset of the first changed byte; the model reacts by editing trap_regs */
extern void trap_model_after_write(unsigned offset);
void trap_init(void);
void trap_reset(void);                    /* trace and count to their start; the model's registers are the caller's */
