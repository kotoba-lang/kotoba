# ADR 0051: A bounded store answers with the word it stored

## Status

Accepted.

## Decision

Every bounded store -- `kernel-store-u8/u16/u32/u64` at each of the four window
tiers, and the four `slice-store-*` forms -- evaluates to the word it was
handed, on both ISAs, exactly as the KIR reference interpreter has always said.

`x86-kernel-memory`, `x86-slice-memory` and their AArch64 twins now emit one
register move after the access and before the jump over the trap:

    x86-64    REX.W  mov  dst, stored          three bytes
    AArch64          orr  Xdst, XZR, Xstored   one word

skipped when the allocator has already given the destination the same register
as the stored operand. Memory semantics, window checks, alignment checks and
trap behaviour are unchanged. Only the value the expression answers with is.

## The defect

The two functions computed

    result (if store? stored dst)

and handed `result` to the access encoder. For a load that is right: the access
writes `dst` itself. For a store the access writes MEMORY and no register, so
`:mir/dst` -- the register the allocator had already reserved as this
instruction's definition, and which the rest of the function reads -- was never
written at all.

Measured on this repository at `8a8c510`, `(kernel-store-u8 b l i v)`:

    48 89 f8     mov  rax, rdi          ; base
    49 89 c8     mov  r8,  rcx          ; stored
    48 89 f1     mov  rcx, rsi          ; length
    ...          window checks
    49 89 c3     mov  r11, rax
    49 01 d3     add  r11, rdx
    45 88 03     mov  byte ptr [r11], r8b
    e9 02 00 00 00
    0f 0b        ud2
    48 89 f8     mov  rax, rdi          ; the ANSWER: RDI, still the base
    c3           ret

and the same fixture on AArch64:

    03 02 00 39  strb w3, [x16]
    02 00 00 14  b    done
    00 00 20 d4  brk  #0
    e0 03 05 aa  mov  x0, x5            ; the ANSWER: X5, never written
    c0 03 5f d6  ret

On x86 the answer happened to be a defined value (the incoming base, because
the allocator gave the definition the register of an operand that died at the
same instruction). On AArch64 it was whatever the caller had left in X5. Both
are wrong and only one of them looks wrong.

The KIR oracle (`kotoba.kir`) is unambiguous, and is not changed by this ADR:

    (kernel-store-u8 ...)   (do (vswap! bytes assoc slot (word-byte-at operand 0))
                                operand)
    (kernel-store-u16 ...)  (do (write-word! operand) operand)

Run rather than read, through `kir/execute` with a real
`:memory {:base ... :bytes (volatile! ...)}` image (2026-09-02):

    (kernel-store-u8  base 512 0 7)          -> 7          image [7 0 0 0 ...]
    (kernel-store-u8  base 512 0 300)        -> 300        image [44 0 0 0 ...]
    (kernel-store-u32 base 512 0 305419896)  -> 305419896  image [120 86 52 18 ...]

The answer is the fourth argument, UNTRUNCATED: the second line stores 44 and
answers 300. That is why the move is REX.W and not a width-masked one.

## Why nobody noticed

The oracle's own comment says `;; RAX still holds the stored word after
`mov [rdx+rdi],al``. That is true -- of `emit-kernel-store-u8` in
`kotoba.native.x86-64`, the stack emitter, which evaluates the value into RAX
and stores AL out of it. That emitter is reachable only through the
non-word-typed fallback; `emit-program` is `machine-ir/compile-kir-module`, and
that is the path every shipped aiueos object takes. A remark about one emitter
was read as a property of the backend.

The three checks that could have caught it did not:

- **Byte goldens.** Every store instruction emitted was the right instruction
  with the right operands. `memwidth-x86-transfer-widths-are-the-instructions-they-name`
  passed throughout, and would have passed after any change that left the store
  itself alone.
- **The KIR interpreter.** It answers correctly, so oracle-only parity -- which
  is how the TLS objects were qualified -- cannot see the difference.
- **The register allocator.** `instruction-def` reads `:mir/dst` generically,
  so kotoba-mir already treated the store as a definition and allocated a
  register for it. Nothing in the MIR was wrong. The keyset already carries
  `:mir/dst` on all eight store operations, and `instruction-sources` already
  carries `:mir/stored`; no change was needed there, and none was made.

Found by the SYSOPS-D stream on 2026-09-02: a QEMU probe printed
`1234X6X800101:8008`, in which the load-backs (`6`, `8`) agree and the two
store ANSWERS (`X`, `X`) do not -- stores work and their answers are wrong.

## What this changes in shipped bytes

**Every aiueos object that contains a bounded store changes bytes**, whether or
not it read the answer, because the move is emitted unconditionally. This ADR
does NOT rebuild them; the AIUEOS-PROJECT-CLEANUP and attestation streams own
the roster (`qualification/jvm-free-object-parity.edn`) and the receipts.

Measured 2026-09-02 by `scripts/aiueos-store-answer-audit.cljk` over
`os/aiueos/kotoba/*.kotoba` (83 sources; 67 objects in today's K16 link list).
It is an audit, not a gate -- it takes the directory as an argument and refuses
with exit 2 if any file will not read. It propagates taint over `let` bindings
AND `defn` return values (required: the stores are wrapped in `store32`/
`store64` helpers) and asks of each store answer whether it reaches a
comparison or an `if` test rather than only a `(* 0 ...)` ordering idiom:

    18 sources contain a bounded store
    13 of those are objects in the K16 link list
    14 of the 18 let a store answer decide something

**In the link list, and the answer decides something (10):**

| object | stores | how the answer is read |
|---|---|---|
| `copy-in` | 1 | `(if (= written value) ... 0)` |
| `idt-gate-build` | 16 | sum of 16 answers vs `expected` |
| `journal-record-build` | 5 | `(= (kernel-store-u8 ...) b)` |
| `kernel-context-build` | 9 | `(if (>= evidence 160) ...)` over the sum |
| `mutable-object-build` | 5 | `(= (kernel-store-u8 ...) b)` |
| `service-registry-build` | 5 | `(= (kernel-store-u8 ...) b)` |
| `user-context-build` | 9 | `(if (>= evidence 160) ...)` over the sum |
| `user-object-journal-build` | 5 | `(= (kernel-store-u8 ...) b)` |
| `ecdsa-p256` | 3 | conservative: the taint reaches an `if` through `e-store` |
| `ecdsa-p256-sign` | 4 | same shape |

**In the link list, ordering only -- bytes change, behaviour does not (3):**
`sha256` (8), `rsa2048` (4), `x25519` (3). All three thread the answer as
`(+ i 1 (* 0 stored))` or `(* 0 (+ s0 ...))`, so the value is multiplied by
zero and only the data dependency survives. That is why `sha256.o` has been
hashing correctly on the machine all along while the arena-shaped objects
above have not.

**Not in the K16 link list (5):** `value-handle-arena` (6),
`value-runtime-capability-table` (3), `value-runtime-entry` (2),
`value-runtime-provider-transport` (7), `value-runtime-sha256` (8). The first
four compare the answer; the fifth is ordering-only.

The two `ecdsa-*` rows are the analysis being conservative rather than a
measured wrong answer: the taint crosses `e-store`, whose value flows into
chains that end in `(* 0 ...)` at most call sites. They are listed as
deciding because proving otherwise needs a per-call-site argument, and the
honest direction for a list like this is to over-report.

## Evidence

**Encodings.** `test/kotoba/native/store_result_test.cljk` decodes the emitted
store by its addressing form (`[r11]` on x86, `[x16]` on AArch64), reads the
stored register out of it, and asserts the next instruction moves that register
into the register the compiled expression answers with -- for all 20 store
forms on each ISA, with all 20 load forms as the control direction (a load must
NOT acquire a second move, and its access must be followed by the jump
directly). Plus a byte-for-byte golden of `(kernel-store-u8 b 512 0 7)` on both
ISAs.

Red/green, both directions, with the reason pinned:

| break | failures | reason literal |
|---|---|---|
| emission removed (the pre-fix program) | 82 | `the store's result register is not written -- the instruction after the store must be `mov dst, stored`, and instead the sequence continues with e9 02 00` (40x) |
| move sourced from `:mir/base` | 42 | `the answer move must read the STORED register` (40x) |
| unchanged | 0 | 5 tests, 365 assertions |

Full suite after the change: 307 tests, 4461 assertions, 0 failures.

**Execution.** `test/fixtures/store-answer-qemu.kotoba` stores 0xEF, 0xABCD,
0x12345678 and 0x0123456789ABCDEF at their natural alignments in a 4 KiB
window and prints, per width, whether the store's ANSWER equals the word it was
handed and whether a load back from the same address does too. Run by
`scripts/store-answer-qemu-fixture.cljk` (amu `compile --artifact image` +
`package-aiueos-boot`, QEMU q35 + OVMF, `isa-debugcon` at 0xe9, `isa-debug-exit`
at 0xf4). The load-backs are the control: they separate "the store did not run"
from "the store ran and answered wrong", and those two produce the same digit
if only one question is asked.

Measured 2026-09-02 on QEMU 10.1 with `edk2-x86_64-code.fd`, the same image
compiled twice through amu 8435eafb with only the kotoba-native pin changed:

    kotoba-native 24f43e2 (main, pre-fix)   console "X5X6X7X8"   exit 33
    kotoba-native f375181 (this change)     console "15263748"   exit 33

Every load-back agrees in both runs -- the stores ran and the bytes landed --
and the four ANSWERS are wrong in the first and right in the second. That is
the whole defect, isolated to one register move.

The fixture script discriminates in both directions and refuses a parameterised
expectation:

    --amu <fixed>                       exit 0  AIUEOS_KOTOBA_STORE_ANSWER_QEMU_OK
    --amu <fixed> --expect X5X6X7X8     exit 3  REFUSED: the console is neither
                                                the fixed nor the requested one
    --amu <fixed> --expect 12345678     exit 3  REFUSED: --expect must be
                                                15263748 or X5X6X7X8

**Not executed on AArch64, and the reason is a refusal rather than a
difficulty.** The kexe userland harness (`kototama.native.executor`, which is
what amu's `native_executor_test` uses on this arm64 host) runs
`aarch64-kotoba-v1`, and bounded kernel memory is admitted only on the aiueos
kernel targets. Measured 2026-09-02 on this host, both directions:

    (kernel-store-u8 1089536 512 0 7)   -> bounded kernel memory operation
    (kernel-load-u8  1089536 512 0)        requires the aiueos kernel target

That literal is `kotoba.verifier`'s (`verifier.cljc`, with the comment "Two
refusals, because a gate on one route is not a gate" -- amu's own target gate
says the same). So there is no store to observe on that route: the harness's
target refuses the operation before any address is chosen. The refusal is
sound -- the loader maps the guest's code and literal data `PROT_READ |
PROT_EXEC` and keeps every arena behind a context callback, so a kexe guest has
no writable address it could name.

The AArch64 claim in this ADR is therefore an ENCODING claim -- the goldens
above, and the `orr Xd, XZR, Xm` form this file already emits for the
compare-exchange comparand -- and the execution claim is x86-64 only. Making
AArch64 executable means either a writable scratch region in the kexe loader
ABI or an `aarch64-aiueos-kernel-v1` image booted under `qemu-system-aarch64`;
both are separate decisions.

## Alternatives considered

**Change the oracle to answer with something cheaper -- 0, or the address.**
Rejected: the oracle is the definition, guests are already written against it,
and the stack emitter already agrees with it. Changing it would break every
`(if (= (kernel-store-u8 ...) v) ...)` in aiueos in the other direction and
would still leave a register undefined.

**Drop `:mir/dst` from stores and make them statements.** Rejected: `.kotoba`
has no statement position. Every form is an expression, and `let` sequencing in
this language is exactly `(let [s (store ...)] ... (* 0 s))` -- taking the
value away removes the only sequencing tool the guests have.

**Emit the move only when the destination is live.** Rejected here: liveness is
not available at the encoder, and threading it through would put a second,
weaker copy of the allocator's knowledge in the backend. The cost is one
register move per store; the objects that need it most execute one per byte
written, and that is a real cost, but a conditional whose condition is
recomputed in the wrong layer is how the original defect got in.

**Mask the move to the transfer width.** Rejected: the oracle answers with the
whole operand.
