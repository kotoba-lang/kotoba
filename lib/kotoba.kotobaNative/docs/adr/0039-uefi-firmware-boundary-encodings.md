# ADR-0039: Encodings for the UEFI firmware boundary

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0008 added four privileged actions so a BOOTX64.EFI could be
written in Kotoba. This repository owns the bytes.

## Decision

| action | bytes | note |
|---|---|---|
| `:system-table` | `4d 8b 51 58` | `mov r10,[r9+0x58]`; `:boot-info`'s twin one slot along |
| `:load-ptr` | `4f 8b 14 1a` | `mov r10,[r10+r11]` after the two operand copies |
| `:jump-to` | `4c 89 df` `41 ff e2` | `mov rdi,r11` then `jmp r10` |
| `:uefi-call2` | see below | 22 instructions |

Every literal was cross-checked against `llvm-mc --show-encoding` before it
was written down.

`:uefi-call2` is the only one with a discipline worth stating. Three things
must hold at a Microsoft x64 call and none of them holds on arrival:

1. **RSP is 16-byte aligned.** The guest frame is `sub rsp, frame-bytes` from
   an alignment this encoder cannot know statically, so the alignment is
   computed at run time -- `mov r10,rsp; and rsp,-16` -- and the original RSP
   is parked at `[rsp+0x20]` rather than in a register, because R10 is
   volatile in MS x64 and the callee may destroy it.
2. **The callee owns 32 bytes of shadow space.** `sub rsp,0x50` reserves that
   plus six saved words at +0x20..+0x48. 0x50 is a multiple of 16, so the
   alignment established in (1) survives to the `call`.
3. **Every volatile register holds something the guest can lose.** MS x64
   preserves RBX, RBP, RDI, RSI and R12-R15, which is the whole of
   `kotoba.mir`'s leaf and preserved tiers. What it does NOT preserve is the
   four-register scratch tier (RAX, RCX, RDX, R8) and **R9, which carries the
   guest's hidden context** -- R9 is an argument register over there. All five
   are saved and restored here rather than at the MIR layer, because
   `:mir/x86-privileged` is not a `call-operation?`: the scanner does not
   treat it as a barrier and may hold a live value in the scratch tier across
   it.

The argument order is `R10 <- a; RDX <- b; RCX <- R10`, and it is not
cosmetic. `a` and `b` arrive in allocator registers that may BE RCX or RDX, so
writing RCX first destroys `b` whenever the allocator put `b` there. Staging
`a` through R10 -- outside every allocator tier -- makes every assignment
safe. Measured on the four-parameter fixture, the allocator does put `b` in
R8 and `a` in RDX, so the hazard is one allocation decision away.

## Consequences

- These four are x86-only, and `kotoba.native.isa-parity-test` pins that. The
  reason is NOT that AArch64 lacks the instructions: AArch64 UEFI exists, and
  its image entry takes `(ImageHandle, SystemTable)` in x0/x1 under AAPCS64.
  A counterpart would be a different operator set with a different ABI, and
  pinning the absence keeps a partial translation from being silent.
- The x86-64 backend's non-word-typed FALLBACK emitter (`kotoba.native.x86-64`
  `emit-expr`) does not implement these four. A function that mixes them with
  a value the MIR path cannot carry therefore fails as an unknown call target.
  That is a real limit, not an oversight; the UEFI entry paths this exists for
  are word-typed throughout.
- `:load-ptr` emits no bounds compare and no `ud2`, and the golden test
  asserts the ABSENCE of both. That is the decision from kotoba-sema ADR-0003
  made visible in bytes.
