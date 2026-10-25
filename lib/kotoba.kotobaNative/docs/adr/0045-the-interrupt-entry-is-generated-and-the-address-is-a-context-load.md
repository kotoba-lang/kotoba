# ADR 0045: The interrupt entry is generated, and its address is a context load

## Status

Accepted.

## Decision

`kotoba.native.interrupt-abi` owns the x86-64 interrupt entry: a fixed byte
sequence that turns the state the CPU leaves at an interrupt into an ordinary
four-argument SysV call to a Kotoba body, and turns the return back into
`iretq`. Two packagers lay it down, and one new operation names it.

An entry is declared in Kotoba as `aiueos-isr-<vector>`, takes
`[vector error-code rip rsp]` -- four `:i64` -- and returns `:i64`.

## Why this exists

aiueos writes this sequence by hand today, once per vector, in
`kernel/entry.S`. The K16 pure-native profile refuses a link containing a
handwritten object, and a *generated* entry is admitted because it is
reproducible: the same table and the same body offsets produce the same bytes.

## The frame

Offsets from RSP at the call site -- after the whole prologue, immediately
before `call`. Reading the arguments there is deliberate: it is the one point
where the layout is identical for a vector the CPU gives an error code and one
it does not, because the entry has already supplied the missing zero.

    +0    saved fuel
    +8    r15   +16 r14  +24 r13  +32 r12  +40 r11  +48 r10  +56 r9  +64 r8
    +72   rdi   +80 rsi  +88 rbp  +96 rbx  +104 rdx +112 rcx  +120 rax
    +128  error code        CPU-pushed, or the prologue's zero
    +136  rip   +144 cs   +152 rflags  +160 rsp  +168 ss

The five words from +136 are the frame the CPU builds (Intel SDM Vol 3A
6.14.1); the fifteen below are the entry's, pushed rax-first so `pop` in the
mirror order restores them. RSP is not among them -- the CPU already recorded
it. RBP is, because a body using it as a frame pointer would otherwise return
to interrupted code holding someone else's.

## The bytes

112 for a vector with no error code, 110 for one with. Every byte string below
came from the system assembler, not from a hand carry: `clang -target
x86_64-unknown-none` assembled the same sequence and `llvm-objcopy -O binary
--only-section=.text` produced a `.text` byte-identical to `entry-bytes`.

    6a 00                       push $0        (no-error-code vectors only)
    50 51 52 53 55 56 57
    41 50 41 51 41 52 41 53
    41 54 41 55 41 56 41 57     rax..r15, fifteen registers
    fc                          cld
    4c 8d 0d <rel32>            lea r9,[rip+context]
    41 ff 71 08                 push qword [r9+8]
    49 c7 41 08 00 10 00 00     mov qword [r9+8], 4096
    bf <imm32>                  mov edi, vector
    48 8b b4 24 80 00 00 00     mov rsi,[rsp+128]     error code
    48 8b 94 24 88 00 00 00     mov rdx,[rsp+136]     interrupted rip
    48 8b 8c 24 a0 00 00 00     mov rcx,[rsp+160]     interrupted rsp
    e8 <rel32>                  call body
    41 8f 41 08                 pop qword [r9+8]
    41 5f 41 5e 41 5d 41 5c
    41 5b 41 5a 41 59 41 58
    5f 5e 5d 5b 5a 59 58        r15..rax
    48 83 c4 08                 add rsp,8      drop the error code
    48 cf                       iretq

Four of those lines are decisions rather than transcription.

**`cld`.** The interrupted direction flag is unknown and compiled code assumes
it clear. It is not undone by hand -- `iretq` restores RFLAGS.

**`lea r9`, not an inherited r9.** An interrupt can arrive while the boot shim
is still running, or -- in the transitional image -- while C code holds r9 for
something else. Inheriting would work almost always, which is the worst
property an interrupt entry can have.

**The fuel save.** The counter is SHARED in the image route. Replenishing
without saving silently RAISES the remaining budget of whatever was
interrupted, and a bound an interrupt can lift is not a bound. The save also
supplies the 16-byte alignment the object wrapper gets from its `sub rsp,8` --
which is why there is deliberately no `sub rsp,8` here. Adding one would
mis-align by eight.

**RAX is discarded.** Acting on the body's return would mean the entry
deciding something: "bit 0 means the interrupt was acknowledged" is a protocol,
and a protocol is a judgement. The body acknowledges its own controller with
`kernel-out-u8`, where the decision is visible in Kotoba and the compiler can
see the effect. This is the boundary aiueos ADR-0015 draws around its C
mechanism, and a generated entry stays on the mechanism side of it.

## The name is the vector

`aiueos-isr-3` handles vector 3, because the generated sequence has to know its
own vector -- it passes it to the body -- and a mnemonic table would be a
second place to keep in sync across kotoba-sema, this repository and both
packagers, kept equal only by review. `aiueos-isr-bp`, `aiueos-isr-64` and
`aiueos-isr-03` are **refused**, not ignored: each reads as an entry, none
denotes a vector the packager lays an entry down for, and admitting one would
produce a function that looks installed and is not.

## The address is a load, not a `lea`

`kernel-isr-entry-address` answers `entry-base + vector * 128`, where the base
is a quadword the IMAGE packager publishes into the kernel context at offset
0x148. It lowers to a bound check, a shift and `add r11,[r9+0x148]`.

It is a load because **there is no relocation channel from a compiled artifact
into the image packager.** The entries are laid down after every byte of the
function has been emitted, and `package-kernel` concatenates `(:code artifact)`
unchanged -- it has export offsets and no marker offsets. A `lea rax,[rip+L]`
resolved at packaging time would need the packager to find L in the byte
stream, and finding an instruction by scanning for its opcode is how a
packager patches the wrong four bytes. The context is the channel that already
exists: `kernel-boot-info` reads one slot along it.

The ceiling is EMITTED, not assumed. The region is indexed by MULTIPLICATION
rather than by consulting a table, so an unbounded vector computes an address
past the region -- and the caller's next act is to write that address into an
IDT gate descriptor. `ud2` is the trap the bounded memory primitives already
raise.

## Where the entries live

**Image.** The region follows the compiled code, so nothing above it moves and
an image declaring no entry is byte-identical to what it was. It is the WHOLE
table -- 64 slots of 128 bytes -- because addresses are computed rather than
looked up, so a slot must exist for every vector the table admits. A vector
with no body gets `cli; hlt; jmp $-1` and `0xcc` filler: a spurious interrupt
there stops, rather than falling into its neighbour's prologue against the
wrong frame.

Vectors 0..63: the architectural exceptions are 0..31, and the rest is room for
the remapped legacy PIC (32..47) and a few message-signalled lines, which is
what a NIC driver needs. Widening it costs 128 bytes of text per vector in
every kernel image that has any entry at all, so it is an ADR and not a
constant to nudge.

**Object.** An entry object's public symbol IS the entry, replacing the SysV
wrapper. The linked shape aiueos's `verify-kotoba-kernel-object.py` requires is
unchanged -- one `R_X86_64_PC32` into the object's own `.data`, zero imports --
because the entry's `lea r9,[rip+ ]` IS that relocation. Only its offset within
the text moved, which is why the relocation offset is computed from the ABI
rather than written as the literal 3. Measured against that script:

    AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1
      export=kotoba_aiueos_isr_3 imports=0 relocations=1

`:stub-kind :interrupt-entry` is the field an aiueos build copies into the K16
pure-native gate's receipt `:stub` -- that gate's `:toolchain-stub` class exists
for exactly this shape ("an interrupt entry, a context switch"). **No aiueos
change is required**: the object also passes that gate's ordinary
`:kotoba-object` check unchanged, because it has Kotoba source, one global
function named `kotoba_aiueos_*`, and one PC32 relocation into its own `.data`.

## Two refusals

`kernel-isr-entry-address` in the object route: `:isr-address-needs-image`. An
object's context is its own private 80 bytes and the entry-base slot is at
0x148, past the end of it; reading there would answer with whatever follows the
object's `.data`.

The refusal is **scoped to what the object's one public symbol can reach**, not
to the whole artifact. One compile produces both forms -- amu's
`compile-source*` calls both packagers -- and a kernel image's `main` uses this
operation to build its IDT. A whole-artifact refusal would refuse the object
route to every image that installs an entry.

The portable twin's x86-64 kernel IMAGE refuses an artifact with an entry
(`:isr-image-needs-the-jvm-packager`): its context is 88 bytes and the base
slot is at 0x148. `kotoba.compiler.nbb.native-package` already refuses that
route for the divergence ADR-0036 records. Emitting with the base omitted would
produce an image that boots and triple-faults on the first interrupt.

## Executed

This repository does not run compiled programs, so its own suite is encodings
only. `test/fixtures/isr-qemu.kotoba` and `scripts/isr-qemu-fixture.cljk` are
what stands in for execution, and they are a FIXTURE rather than a test: they
need amu, QEMU and OVMF, none of which this repository depends on.

The fixture's `main` installs an IDT whose vector 6 gate names
`kernel-isr-entry-address 6`, then executes a bounded load with an index
outside its window. That emits `ud2`, the CPU raises #UD, and the IDT sends it
to the generated entry.

**#UD rather than a breakpoint** because there is no `int3` operator, and adding
one to reach this proof would be a privileged operation existing for the sake
of its own test. `ud2` is already emitted by the bounds check every bounded
load carries.

**The body does not return.** #UD is a fault, so the frame's RIP is the address
of the faulting `ud2` and `iretq` would re-execute it forever. Advancing that
RIP would mean the entry deciding how long the faulting instruction was --
exactly the judgement it refuses to make -- so the body writes the exit port
instead.

**Measured 2026-09-02**, qemu-system-x86_64 q35 + OVMF + TCG, the boot chain
built by `amu compile --artifact image` and `amu package-aiueos-boot`:

    console (port 0xe9): DISRP
    exit status:         33

verbatim. `D` is the IDT loading and reading back through `sidt`; `I S R P` are
the four arguments the generated entry passed, each checked separately by the
body -- vector 6, error code 0 (the synthetic push, because #UD supplies none),
an interrupted RIP inside this image's text and an interrupted RSP inside its
stack. A wrong argument prints `X` in its place rather than collapsing into one
exit code. The image's entry region began at `0x101cb0`, putting vector 6's
entry at `0x101fb0`.

That is the whole claim this fixture makes and it is the one the encodings
cannot make: the CPU entered a byte sequence this compiler generated, and the
sequence called a Kotoba function with the frame the CPU had built.

**Shown to discriminate.** Rebuilding the same fixture with the body comparing
its first argument against 7 instead of 6 changed the console to `DXSRP...` --
`X` where `I` was, and `S`, `R` and `P` unchanged. The letter that moved is the
letter the break targeted, and the runner refuses on the console mismatch.

**One thing that run did that is NOT explained here.** The broken image
repeated `XSRP` about sixty-six times before exiting, where the correct one
printed its five letters once and stopped. The body's last expression is the
exit-port write in both, so the correct image exits on its first interrupt and
the broken one evidently did not until much later. No explanation is offered
because none was measured; it is recorded rather than smoothed over, and it
does not bear on the green result, whose console and exit status are exact.

## A defect this fixture found, in code that is not this change

**A bounded store's answer is an undefined register on the machine.**
`x86-kernel-memory` (machine_ir.cljc) takes `result (if store? stored dst)` and
never writes `:mir/dst`, for every width. The KIR oracle answers with the
operand. Measured 2026-09-02 from an `emit-program` of
`(= (kernel-store-u32 base 512 0 255) 255)`: the emitted comparison is
`cmp rdi, rax` and nothing in the function defines `rdi`.

Confirmed **on the machine**, not only by reading the emitter. A probe image
built the same way as the fixture printed one character per clause:

    1234X6X800101:8008

`1234` are the four address and selector clauses. `X` is a `kernel-store-u64-4k`
whose answer did not equal the word it stored; `6` is the load-back of that
same word, which did. `X` again is `kernel-store-u8-4k`; `8` is its load-back.
So the stores WORK and only their answers are wrong. The trailing digits are
the probe reporting what it was given, as hex nibbles offset from `'0'`:
handler `0x00101A80` -- `base + 6 * 128` for that image -- and CS `0x08`.

This is not introduced here and is not repaired here -- repairing it moves the
bytes of shipped aiueos objects and needs its own ADR and its own break-checks.
It is recorded because the idiom it breaks is in use: aiueos's own
`kernel.kotoba` writes `(= (kernel-store-u8-4k page 4096 512 239) 239)`.

The first version of this fixture used the same idiom, every comparison was
false, and the image exited through its own guard having printed nothing. It
now checks every write by READING IT BACK, which is both the workaround and the
stronger claim: it says the byte reached memory, which is what an IDT needs.

## Evidence

`kbb -M:test`: 302 tests, 4096 assertions, 0 failures (after merging origin/main).

Five deliberate breaks, each producing the failure it names and no other:

| break | result |
|---|---|
| the fuel save and restore dropped | 327 assertions, including the byte-derived alignment row |
| the object relocation offset back to the literal 3 | the object relocation row only |
| the image call displacement aimed at the artifact base rather than the body | the image body-reach row only |
| the object refusal made whole-artifact rather than reachability-scoped | the scoping test errors on a valid entry object |
| absent slots filled with zero rather than a halt | the halt row and the per-vector region row |
