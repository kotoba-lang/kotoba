# ADR-0212 — the C-free conversion order, and the one rule that blocks most of it

- Status: accepted
- Date: 2026-09-10
- Related: ADR-0013 (C-free hard-flip release rule and the 6-phase gap ledger),
  ADR-0110, ADR-0112 (superseded as C-free evidence)

## Context

ADR-0013 states the rule — the production bare-metal profile does not compile,
link, load or execute C — and carries a six-phase gap ledger of what remains.
What it does not carry is an ORDER: which file to convert first, and what
actually stops each one. Measured 2026-09-10.

## The surface

`os/aiueos` is 27,623 lines of `.c`, 1,188 of `.h`, 979 of `.S` against 23,166
of `.kotoba`. But the split is not even: **`os/aiueos/kernel` is 21,444 lines of
C and assembly and zero lines of `.kotoba`.** The `.kotoba` lives in
`os/aiueos/native` (7,157 lines) as objects the kernel links.

## Ordering: use the symbol graph, not the include graph

An `#include` graph gives four layers and is WRONG. `ioapic.c` includes nothing
local and declares `extern uint32_t aiueos_acpi_ioapic_address(void)` inline, so
an include-based sort puts it in layer 0 when it depends on `acpi.c`. Sorting by
which `aiueos_*` symbols each file defines and references gives eight layers:

| layer | files | lines |
|---|---:|---:|
| 0 (references nothing another `.c` defines) | 15 | 3,622 |
| 1 | 3 | 1,567 |
| 2 | 6 | 2,372 |
| 3 | 2 | 2,493 |
| 4 | 2 | 707 |
| 5 (`main.c`, 20 deps) | 1 | 3,699 |
| 6 (`pci.c`, 16 deps) | 1 | 5,482 |
| 7 (`loader.c`) | 1 | 86 |

Reproduce with the symbol scan in this ADR's commit message; it is the ordering
the conversion should follow, prerequisites first.

## The rule that blocks most of layer 0

Within layer 0, splitting by whether a file touches hardware
(`__asm__`/`volatile`) leaves 1,083 lines of pure logic — protocol formatting,
qualification, ACPI validation, AES-GCM. That is exactly the "judgment" the
workspace rule says belongs in `.kotoba` rather than C. **It does not follow
that those 1,083 lines convert.**

Measured, with a two-line probe:

    (let [ptr (slice-load-u64 base length 3)]
      (slice-load-u8 ptr 32 0))

    exit 65  :kotoba.error/kernel-region-provenance
             "kernel memory base must name a region, not compute one"

**A pointer loaded from memory cannot be a region root.** The frontend admits a
literal, `kernel-boot-info`, a parameter, or a `kernel-subregion` narrowing of
one — and a struct field holding a `const char *` is none of those. So any
component whose contract is "here is a pointer to a struct, validate what it
points at" is blocked at the language surface, not at the effort level:

| layer-0 pure-logic file | lines | `->` uses | status |
|---|---:|---:|---|
| `relay_protocol.c` | 63 | 0 | **convertible** |
| `tls_aes_gcm.c` | 180 | 0 | **convertible** |
| `inference_status.c` | 53 | 27 | blocked |
| `model_handoff.c` | 71 | 17 | blocked |
| `device_worker_protocol.c` | 77 | 11 | blocked |
| `qualification.c` | 154 | 12 | blocked |
| `job_protocol.c` | 181 | 8 | blocked |
| `acpi.c` | 304 | 21 | blocked |

**243 of 1,083 lines convert today. 840 are blocked on one rule.**

Per the whole-component migration rule, a blocked component is recorded blocked;
it is NOT reduced to the subset of its checks that avoid pointers in order to
make a gate green. `aiueos_inference_status_valid` validates three `const char *`
fields; a version of it that skips them is a different function that happens to
compile.

Two honest exits, neither taken here: re-express the public surface so the
strings arrive as parameters (a versioned API decision, which whole-component
migration explicitly permits), or add a provenance-preserving load to the
language surface plan. `kernel-load-ptr` exists in the operation table and is
the obvious place to look first.

## The binding constraint is arity 5, not the provenance rule

Measured 2026-09-10, twice and independently:

    (defn f [p0 p1 p2 p3 p4]    …)   exit 0
    (defn f [p0 p1 p2 p3 p4 p5] …)   exit 65
        :kotoba.error/max-parameters
        "function parameters exceed ABI-supported arity"

**Five parameters. Six is refused.** This reshapes the "C marshals, Kotoba
judges" convention that the rest of this ADR leans on: if every buffer arrives
as a `(base, length)` PAIR, a function gets two and a half buffers before it
runs out of arity. `aiueos_inference_status_valid` reads seventeen struct
fields including three `const char *`; flattened to parameters that is roughly
twenty, so it cannot be expressed that way at all.

The way through is not more parameters but fewer: **C flattens the struct into
one contiguous region and Kotoba reads it back by offset**, which is two
parameters (`base`, `length`) regardless of how many fields there are. That is
a different and larger marshalling job than "pass the spans", and every
conversion of a wide struct needs it.

## The coefficient is stable at ~2.15x — on JUDGMENT lines, not on file size

Three whole-surface conversions, all compiling for `x86_64-aiueos-kernel-v1`:

| file | C code lines | of which judgment | Kotoba code lines | ratio on judgment |
|---|---:|---:|---:|---:|
| `job_protocol.c` | 163 | ~163 (~100%) | 340 | **2.09x** |
| `inference_status.c` | 45 | 45 (100%) | 97 | **2.16x** |
| `qualification.c` | 121 | 19 (16%) | 42 | **2.21x** |

**The ratio barely moves: 2.09 / 2.16 / 2.21.** What moves enormously is the
JUDGMENT FRACTION — 100%, 100%, 16%. So the size of this refactor is not
"kernel C x some constant"; it is "judgment lines x 2.15", and judgment lines
have to be counted per file.

### Which means this ADR's own 13,481 figure is overstated

That number came from classifying whole functions by whether they touch
`__asm__`/`volatile`. `qualification.c` contains neither and lands in the
"judgment-shaped" column — and is **84% marshalling**: EFI ABI typedefs, the
`struct efi_runtime_services` layout, and seven indirect calls through function
pointers in it. **The asm/volatile heuristic does not see marshalling at all.**
Any projection built on it, including the ~28,000-line one below, is an upper
bound of unknown looseness until judgment fraction is sampled more widely.

### The boundary is ONE-WAY, and that is the real ordering constraint

C calls Kotoba: 99 symbols, 18 of 31 files. **Kotoba cannot call C.** Probed
directly — naming a C symbol from a `.kotoba` source gives
`unknown operation: kotoba_aiueos_aes128_gcm is not a builtin, a sugar head, or
a function of this module`, and there is no `extern` / FFI / foreign-call form
in the subset. Kotoba CAN call Kotoba across modules — `relay_line.kotoba` does
`(:require [native.relay-text :as text])` via the project route
(`--source-path` / `--module-lock`).

So a C file cannot become Kotoba while it still calls C. **Conversion is
bottom-up only**: move a leaf of the call graph, or move everything below a
file at once. That is a harder constraint than the eight dependency layers
above, because those layers were computed over C-to-C symbol references — and
this says every one of those edges must be eliminated *in order*, not merely
respected.

It also explains why marshalling stays C, and that it is not a style choice:
the side that can call both is the C side.

### The fuel model is about STATIC bounds, not loop size

An earlier draft of this work claimed "a self-recursive loop compiles at depth
100 and fails at 200". That is true and badly misleading. The same
`accumulate` function, changing only its bound:

    (accumulate 0 200 0)                                  exit 70  fuel-exhausted
    (accumulate 0 (bit-and (kernel-rdtsc) 1048575) 0)     exit 0

A LITERAL bound is statically charged against fuel and hits the ceiling almost
immediately. A RUNTIME bound compiles to a real loop and is effectively
unbounded — measured over a byte-compare loop at N = 8 … 2,000,000, every one
exit 0 and every one producing the identical 1,288-byte object. Separately,
NON-TAIL self-recursion is statically unrolled and dies at depth 52 whatever
the bound.

So: write loops tail-recursively with a runtime bound and fuel is a non-issue.
Fuel constrains static unrolling, not iteration.

### Bitwise: xor and or yes, variable-count shifts no

`bit-xor` and `bit-or` compile. `bit-shift-left` and
`unsigned-bit-shift-right` are refused —
`unknown operation: bit-shift-left is not a builtin … nearest defined:
i32-shift-left (builtin), i64-shift-left (builtin)` — and the builtins that do
exist take a LITERAL count only: `i32 shift count must be an integer literal in
[0,31]`. **Variable-count shift and rotate are not expressible**, which is
enough to put AES and GHASH proper out of reach today, though not the glue
around them.

### Four more language-surface facts, each measured

- **No `kernel-load-u64`.** The op table has u8/u16/u32 only, so every 64-bit
  field crosses as an `(hi, lo)` u32 pair.
- **Words are signed.** `native/relay_line.kotoba` already says so in its own
  comment — "a set bit 63 makes `quot` walk the wrong way". This is a
  CORRECTNESS hazard, not a size one: `inference_status.c` carries the comment
  `/* token bound above keeps tokens * 1e12 inside uint64_t. */`, true for C's
  unsigned multiply and false here. For `tokens` in [9223373, 10000000] — the
  top of the legal range — the product exceeds `INT64_MAX` and overflows
  silently. A faithful port needs multi-limb arithmetic.
- **No indirect call through a function pointer** with the firmware's `ms_abi`
  convention. That is why `qualification.c` is 84% marshalling: its EFI runtime
  services calls cannot move, and the struct describing them exists only to
  make them.
- **No preprocessor.** An `#ifdef` build branch becomes a runtime parameter the
  C shim passes as a fixed literal.

### And marshalling is sometimes new code, not moved code

`inference_status.c` contains **zero** marshalling lines: it only ever reads an
already-populated struct, never packs one. The flat-buffer shim its port
implies is **entirely new C to write**. So "C marshals, Kotoba judges" does not
always split an existing file — sometimes it adds a layer that did not exist.

## The first conversion coefficient, measured once

`kernel/job_protocol.c` was converted whole — all five public functions — and
compiles for `x86_64-aiueos-kernel-v1`. The artifact is
`native/job_protocol.kotoba`, landed unwired as evidence.

| | |
|---|---|
| C, code lines (excl. comment/blank) | 163 |
| Kotoba, code lines | 340 |
| **expansion** | **2.09x** |
| public functions | 5 C → 6 Kotoba |

The function count grows because `aiueos_job_request_parse` fills an out-struct
and there is no out-parameter across this boundary, so it splits into
`job-request-verdict` and `job-request-prompt`. Expect that split wherever the
C returns through a pointer.

Projected onto the 13,481 kernel C lines that sit in functions touching no
hardware, 2.09x is **roughly 28,000 lines of Kotoba to write**. Treat that as
an order of magnitude and not a plan: **n = 1**. Two sibling measurements on
`inference_status.c` and `qualification.c` were started and did not finish, so
there is no spread, and protocol parsing is plausibly the friendliest shape in
the tree.

## What is confirmed to work

Probed on `x86_64-aiueos-kernel-v1`, all compiling:

- string literals, and `string-code-point-at` over them — **compiled, not
  run: until kotoba-native #184 (ADR-0220) that operation was a host call and
  jumped to address 0 in a kernel object**
- `kernel-store-u8` / `-u16` / `-u32` into a parameter-rooted region
- `kernel-load-u8` / `-u16` / `-u32` / `-ptr`

So `relay_protocol.c` — which writes literal banners into a caller's buffer and
reads a 6-byte MAC parameter — has no missing primitive. It was the first
conversion (ADR-0215). Zero files were converted as of this record's date;
the order and the blocker were what it established. Two of the four
"language-surface facts" below have since moved: `kernel-load-u64` exists
(measured 2026-09-16, ADR-0219 uses it), and the 840-line block is answered
by the flat-record shape rather than by the language.

## Order of work

1. `relay_protocol.c` (63) — proven convertible, no missing primitive.
   **Done 2026-09-11 (ADR-0215).**
2. `tls_aes_gcm.c` (180) — proven convertible. Its cipher had already moved
   (ADR-0132); what is left is a 45-line marshalling shim and a selftest.
   Deferred behind step 4, not blocked.
3. decide the pointer question (API change or language surface), because 840
   lines of layer 0 and most of layers 1-4 wait behind it.
   **Decided 2026-09-16 (ADR-0219): the struct crosses as ONE flat
   fixed-layout record the C packs and the object reads by offset. No
   language change.**
4. the rest of layer 0, then layers 1-4 in order. **`inference_status.c`,
   `model_handoff.c`, `device_worker_protocol.c` done under ADR-0219**;
   **`job_protocol.c`, `micro_infer.c` and `tls_aes_gcm.c`'s self-test done
   under ADR-0220**; `qualification.c` and `acpi.c` remain, and ADR-0220
   carries the disposition of every file in the kernel.
5. `main.c`, `pci.c`, `loader.c` last — they depend on everything

## What this does not say

It does not say the refactor is small. 20,028 lines of kernel C, of which the
two provably-convertible files are 243. It does not say `pci.c` (5,482 lines,
16 deps) is reachable on this ordering without the hardware-mechanism question
being answered separately — the workspace rule currently permits C for
registers/MMIO/GDT/paging, and ADR-0013's hard flip does not. That tension is
real and is an owner decision, not a measurement.
