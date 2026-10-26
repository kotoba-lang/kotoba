# ADR-0146: The HKDF object was miscompiled, that is fixed, and it still does not return

- Status: accepted
- Date: 2026-09-02

## Context

ADR-0134 recorded that `kotoba_aiueos_hkdf_sha256` "does not return on this
machine": it exhausted its 10,000,000 fuel tier, and an object hand-patched to
2,147,483,647 exhausted that too. The object was removed from the link and
stage 4 (the handshake) was blocked on the diagnosis.

That reading named fuel. Fuel is not what was wrong first.

## What was measured

**The KIR reference interpreter runs the same program correctly.** RFC 4231
case 1 through `aiueos-hkdf-sha256` mode 0 returns 0 with a budget between
32,769 and 65,536 (exponential probe from 4,096: 32,768 traps
`:fuel-exhausted`, 65,536 answers `{:ok 0}`). The native backend charges one
fuel per non-leaf prologue and per loop back edge, which is *less* than the
interpreter charges per application, so nothing above the machine layer could
see a problem.

**The object read its own `ctx` argument back as the literal 92.** Disassembly
of the committed `hkdf-sha256.o` (byte-identical when recompiled at amu
`b1fdaad2` and at amu main `bb51dc14`, so not a stale artifact):

```
2962: movq %rax, (%rsp)     ; hmac-mode spills ctx into frame slot 0
...
2a04: movq %rcx, (%rsp)     ; the literal 92 into the SAME slot
2a0f: movq (%rsp), %rdx     ; 92 -> argument 3, as intended
2a17: movq (%rsp), %rdi     ; 92 -> argument 1, which is ctx
2a27: callq write-pad-block
```

The fourth of `hmac-mode`'s six calls wants 92 in `%rdx` and 0 in `%rcx` while
those two registers hold each other's values. That swap is a register cycle,
and a parallel copy breaks a cycle through one frame slot. The slot it used
was slot 0, which still held `ctx`. Every call after it -- `write-pad-block`,
`copy-into-msg`, `sha-run` -- received 92 as the context pointer and read and
wrote absolute addresses 92+i. `expand-label-mode` did the same twice, with 54
and 92; on today's `main` the split source does it **four** times in slot 0 and
twice in slot 8.

**The layer is kotoba-mir, in `allocate-without-spills`.**
`entry-argument-plan` returns the same number under two names --
`:stable-slot-count` and `:temp-slot` -- because at entry the two coincide. The
loop carried `:temp-slot` forward unconditionally, so when the entry parallel
copy had no cycle nothing stepped `:next-slot` past that number and the body's
first `spill-assigned` was handed the slot `:temp-slot` still named. A
function whose arguments all fit in registers at entry gets `:temp-slot` 0, and
slot 0 is what the first spill takes -- so the collision lands on the value
spilled earliest, which in practice is the first argument.

Not the source idiom: `aes128-gcm.kotoba` and `tls13-record.kotoba` use the
identical single-region `cl`/`cs` accessors and both run correctly on this
machine. Not kotoba-sema's multi-form `let` body: every `let` in this source
has a single-form body. Not the `quot`/`*` shift emulation: the rotations are
straight-line and constant-bounded. Not the undefined store-result register
(kotoba-native ADR 0049): every store answer in this source reaches a counter
only through `(* 0 s)`, and the emitted code multiplies by a materialised zero.

## Decision

**The fix is upstream and it landed.** kotoba-mir ADR-0017 / PR #50, merge
`e266a862a4b3c83013e3bd3995080ac3230503fd`: `:temp-slot` is carried into the
body only when something reserved it. Otherwise `emit-call` derives it from the
current `:next-slot` and pins it on first use, which is what both of its
`(or (:temp-slot state) (:next-slot state))` sites already assume.

kotoba-native PR #114, merge `4391d683a80f9d78d35a9c664f8966601ae5abc4`,
advances the pin (and kotoba-gmir with it: kotoba-mir now reads
`gmir/rodata-content?`). `kbb -M:test` there: 302 tests, 4096 assertions,
0 failures, no byte golden moved.

Rebuilt against that toolchain, the temporary moves to slot `0x18`
(`hmac-mode`) / `0x20` (`expand-label-mode`) and `(%rsp)` still holds `ctx` at
every call.

## Consequences, including the one that is not resolved

**The object still does not return.** Rebuilt from today's split source with
kotoba-mir `e266a86` + kotoba-native `279fbc3` (which also carries the
store-answer fix), linked, and booted under `smoke-qemu-uefi.sh`, the boot
still ends:

```
AIUEOS_AES_GCM_OK aes-128-gcm nist
AIUEOS_EXCEPTION_FAIL unexpected-vector vector=6
```

Vector 6 is `ud2`. `qemu -d int` puts RIP at `0x148e8f`, which is object offset
`0x18df` -- the fuel guard at the bottom of `copy-round`:

```
18c1: movq %r12, %rdx
18c4: addq $0x1, %rdx
18cb: imulq $0x0, %rax, %rcx
18d2: movq %rdx, %r12
18d5: addq %rcx, %r12
18d8: cmpq $0x0, 0x8(%r9)
18df: ud2
```

The register file at the trap says the machine is healthy, which is what makes
this a second defect rather than a consequence of the first:

- `RBX = RDI = 0x1bafb0` -- the real `ctx`. The miscompile above is gone.
- `R12 = 1`, `R13 = 0x48` -- `copy-round`'s first iteration, correctly.
- `RSP = 0x18ec70`, `RBP = 0x18ef20` -- 688 bytes of stack. No runaway recursion.
- `R9 = 0x17d688` -- the object's own context, never written by any instruction
  in the object outside the entry stub.

So fuel is being spent, not corrupted, and something above `copy-round` runs far
more than it should. What has been ruled out, each by measurement rather than
by reading:

| ruled out | how |
|---|---|
| fuel tier too small | patched to 2,147,483,647; same vector 6, and a boot left running spun for 9m53s without returning |
| the `quot`-derived block count | a variant with `(process-blocks ctx msg-len 0 2)` -- the same value for both call sites -- still traps, so the loop is INSIDE one 64-byte block |
| out-of-range memory | a window violation is a different `ud2` (`cl`'s, at object `0x98`), and every index is bounded by construction; the trap is at a fuel guard |
| a callee clobbering a caller's induction register | no function writes `rbx`/`r12`-`r15` without pushing it (43 functions scanned) |
| a callee clobbering `r9` | no instruction in the object writes `r9` |
| a frame slot outside its own frame | 43 functions scanned, 0 out-of-frame `(%rsp)` references |
| a return path that skips its epilogue | every `retq` and outbound `jmp` restores what its prologue pushed |

Every in-block loop bound (`prepare` 16, `extend` 64, `copy-working` 8,
`round-block` 64, `copy-round` 8, `add-state` 8) is a literal in the emitted
code and the induction register is compared against it correctly. The next step
is to bisect inside one block -- a variant whose entry runs `initialize`,
`prepare`, `extend`, `copy-working`, `round-block` and `add-state` once each and
returns, then narrowing to whichever of those does not come back.

**`hkdf-sha256.o` therefore stays out of the link** and `kernel/tls13.c` keeps
its C `hmac_sha256` / `hkdf_extract` / `hkdf_expand_label`. The flip was
written and measured against the object; it is not landed, because landing a
seam whose object traps would replace a working key schedule with a boot that
dies before the handshake.

**The committed `hkdf-sha256.o` on `main` carries the miscompile.** Regenerating
it needs the amu pin advanced past kotoba-native `4391d683`; that bump is the
store-answer stream's to make (kotoba-native `279fbc3` contains both fixes), and
this ADR does not make it. Until then the committed object is a build of a
compiler that mislays a context pointer, and nothing links it.

## Note on stage 4

The handshake port was blocked on this diagnosis and remains blocked. The shape
it needs -- SHA-256 inlined into an object that also does HMAC -- is the shape
that still does not return, so porting it now would reproduce the same failure
one layer up.
