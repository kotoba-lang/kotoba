# ADR-0220 — the whole-kernel C-free program, and wave two: three more files, and the first kernel object to walk a literal

- Status: accepted
- Date: 2026-09-16
- Owner direction: "kernel C を全て kotoba に" (2026-09-16). Extends ADR-0219
  (flat records) and ADR-0212 (order); root authority ADR-0013 (C-free hard
  flip), root ADR-2607241100 (C is mechanism, Kotoba judges).

## What wave two moved

| C file | judgment retired | object | contract |
|---|---|---|---|
| `job_protocol.c` (163 code lines) | all four wire lines — request parse, result line, commit receipt, ping/pong | `job-protocol-dispatch` (one mode word) over `aiueos/job_protocol` — the module ADR-0212 landed **unwired** in `native/`, moved and wired, plus a `job-request-id` writer the out-struct needed | 55 vectors, 15 memory |
| `micro_infer.c` (62) | the bigram next-character decision | `micro-infer-next` over the **shared** `native.micro-infer` table — the C kernel and the pure-native kernel now answer from one table | 37 vectors, 37 memory |
| `tls_aes_gcm.c` (158 → 45 code lines) | the boot known-answer test (vectors + comparisons) | `aes128-gcm-selftest` over the shared `aiueos.lib.aes128-gcm-core` | 2 vectors, five prepares, four AEADs |

Every verdict, line and out-record was produced by the retired C at 3ab6147,
through the packers the kernel now uses. The transition matrix's source of
truth moved from the C array to `contracts/micro-infer-transitions-v1.edn`;
the generator, the drift gate and the relay's row model read it, and the
generated table did not change by a byte. The C host harnesses of the
retired decisions (`tests/job_protocol_model.c`, `tests/micro_infer_model.c`)
are gone; `smoke-micro-infer.sh` keeps the relay check.

The kernel: `os/aiueos/kernel` 21,434 → 21,294 lines; three files that were
163 + 62 + 158 code lines of decision are 278 lines of marshalling with no
comparison. 106 objects linked; 23 of 30 C files call into Kotoba.

## Two toolchain findings, both measured by a boot

**1. Four of the eight wave objects were packaged at the 1,024 fuel default.**
The first wave-2 boot died `AIUEOS_FATAL_EXCEPTION vector=6 ud2` inside the
AES-GCM known-answer test. kotoba-native's `kernel-object-entries` carries a
fuel tier per object and every new row fell to the default. Tiers were
bisected in the KIR oracle over every contract vector and landed as
kotoba-native #183: poll-response 10,000,000 (its response is unbounded —
a tier fitted to the 130-byte contract vectors would `ud2` on the first
real job), job-protocol 65,536, micro-infer-next 4,096,
aes128-gcm-selftest 250,000,000 (the aead arm's constant, same core, five
prepares); the four that fit the default are asserted at it so an arm
cannot move them silently.

**2. `string-code-point-at` over a literal was a host call, and a kernel
object has no host.** The second boot died `vector=14 #PF rip=0x0`. The
operation lowered to the slot-144 runtime call (a string value is
pair(offset, length) the host resolves); the packaged context's slots are
zero, so the call jumped to address 0. **Four objects landed earlier walk
literals exactly this way and had never executed as machine code**:
`relay-hello-payload`, `relay-ack-payload-valid` (ADR-0215 said so: "what
is not proved is the emitted machine code producing them on the K16"),
`job-protocol-dispatch` and `device-worker-poll-response` (ADR-0219). ADR-0212's
"confirmed working: string literals and `string-code-point-at` over them"
was a compile, not a run. kotoba-native #184 lowers the ASCII-literal case
to a bounded byte load from the rodata pool on both ISAs (no host, no new
GMIR); every committed object was recompiled and **no object in the tree
carries a slot-144 call** — the new gate `:cfree-wave-2-native` scans all
109 and fails on one hit. The relay pair's bytes changed; their contracts
and `:relay-parity` are unchanged and green.

With both fixes the selftest object runs its five steps as x86-64 machine
code in the kernel: `smoke-qemu-uefi.sh` → `AIUEOS_AES_GCM_OK`,
`AIUEOS_UEFI_SMOKE_OK`, 76 markers; with one expected tag byte flipped the
same boot prints `AIUEOS_AES_GCM_FAIL` and the smoke exits 1. This is the
first time a kernel object built under ADR-0212's programme has been
proved by execution rather than by the oracle plus a link.

Upstream: kotoba-native #182 (rows), #183 (tiers), #184 (literal walk);
amu #1006 (pin d2f1dca → 9cccd1b6, superseding #1005 after #1004 landed).

## The programme: every kernel file, its disposition, and what it waits on

Owner direction is the whole kernel. The C is 30 `.c` and 3 `.S` files,
21,294 lines. ADR-0212's rule stands — a C file cannot move while it calls
C, so conversion is bottom-up — and its layers were recomputed today over
the symbol graph (the first layer's 12 files are below; the rest are a
cycle around `main.c`/`pci.c` that the order has to break by moving leaves).
The four dispositions ADR-0213 named (already in Kotoba / write it / blocked
/ mechanism) are used as written.

**Done (judgment out of C):** `relay_protocol.c` (deleted), `tls_aes_gcm.c`,
`inference_status.c`, `model_handoff.c`, `device_worker_protocol.c`,
`job_protocol.c`, `micro_infer.c` — seven files, all marshalling or gone.

**Layer 0, remaining:**

| file | lines | disposition | waits on |
|---|---:|---|---|
| `qualification.c` | 155 | 19 judgment lines convertible as a flat record; the other 84% are EFI runtime-services calls through `ms_abi` function pointers | a Kotoba object cannot make an indirect `ms_abi` call — **the calls stay mechanism until the loader is Kotoba** (ADR-0131's refused BOOTX64.EFI). Convert the 19 lines next. |
| `acpi.c` | 305 | table walk (RSDP → XSDT → MADT) through pointers | ADR-0219's shape, iterated: the object returns the next physical address to fetch, the C copies that table into a record, the object continues. Two objects (`acpi-checksum-ok`, `acpi-table-valid`) already exist; the walk is what is left. |
| `qwen35_quant.c` | 638 | dequantisation tables and row decode | **already in Kotoba**: `qwen35-dequant-row` (four types) — the C is the reference the parity test compares against. Retire with the inference cutover below. |
| `qwen35_runtime.c` | 937 | GGUF header / KV scan / tensor table bind + the C-side model window | the three decisions are objects (`qwen35-gguf-header-valid`, `-kv-scan`, `-tensor-table-bind`, ADR-0145, wired); what remains is mapping and copying — mechanism, and the last of it goes with `paging.c`. |
| `device_result.c` | 542 | HTTP request/digest for the device worker | two objects already carry canonical + digest (`device-worker-canonical`, `device-worker-digest`); the remaining C is TLS plumbing → moves with `tls13.c`. |
| `plc_runtime.c` | 158 | PLC user-profile runtime | objects exist (`plc-user-elf-valid`, policy); remaining C is APIC release and the scan loop — mechanism, moves with `scheduler.c`. |
| `apic.c` / `ioapic.c` | 49 / 42 | MMIO register writes | mechanism; the pure-native kernel already does MMIO in Kotoba (`native/rtl8125.kotoba`, ADR-0036–0040). Move when the interrupt path moves. |
| `loader.c` | 87 | ELF admission | `user-elf-valid` object exists; the C is copy + jump. |

**Inference (`qwen35_infer.c`, 1,844 lines) — the owner's question.** The
arithmetic is already Kotoba, *in this repository*: thirteen `qwen35-*`
objects (4,515 lines — dequant, dot, matvec, norm, activation, attention,
recurrent-step, tokenizer, GGUF admission), each with a contract, and an
in-kernel parity self-test that runs the C reference against them at boot.
**Nothing is flipped** (ADR-0148): the live forward pass is C with AVX2 and
the objects are parity-checked only. The other repositories named —
`inference` (`kernel_math_core.kotoba`: f64 vector arithmetic for a host
that hands rows in, not the kernel target), `torch` (Clojure `.cljk`, host
side, GGUF parsing on the JVM/nbb), `num` (GPU / WGSL), `murakumo`
(planning and topology `.kotoba`) — are not kernel-target and not this
forward pass; the reuse target is the thirteen objects here. The cutover
is: (1) make the objects the live path with the C reference kept under the
parity flag, one stage at a time (dequant+dot+matvec, then norm+activation,
then attention, then recurrent-step), each stage measured by the existing
parity self-test and the K16 first-token benchmark (ADR-0116); (2)
`rope_heads` needs a sine/cosine — the C uses x87 `fsincos`, Amu emits no
x87, and `f64-sin-bounded` exists in the language; a Kotoba rope will not be
bit-identical to `fsincos`, so the reference for that stage becomes the
object; (3) the SMP split and the workspace stay C until `smp.c` moves.
**Expect a slower token rate**: the objects are scalar four-accumulator
loops and the C is AVX2. That number is to be measured before the C
reference is deleted, and reported, not hidden.
ADR-0222 (2026-09-22) adds the Ternary Bonsai 2 27B `PTQ1_0` artifact to
this cutover as a model stage — same `qwen35` graph, two new codecs and a
Hadamard basis change — and orders it before the C reference leaves.

**Layers 1–4 (network, TLS, scheduler, paging, process, syscall, SMP,
VT-d, memory, framebuffer):** `tls13.c` (883) has five objects behind it
(record layer, HKDF, AES-GCM, x25519, ECDSA) and is the next large
judgment mass after inference — its handshake state machine is a flat-record
conversion of ADR-0219's shape. `rtl8125.c` (654) is **already written**:
`native/rtl8125.kotoba` (41 KB) is the pure-native kernel's driver;
retirement means giving `pci.c` that driver's regions. `scheduler.c` /
`process.c` / `syscall.c` have their decisions as objects (dispatch plan,
task slot, teardown, syscall range, copy-in, capability); the C is
context switching and ring transitions — mechanism, and the last to go.
`paging.c` has `page-mapping-plan`; the pure-native kernel owns page tables
in Kotoba already (ADR-0036–0040).

**`main.c` (3,713) and `pci.c` (5,497):** the boot sequence and the
device/network glue. They are the cycle. They shrink as every leaf moves
and are converted last, per ADR-0212. `main.c`'s self-tests are the
natural first cut: each is a call into an object already.

**The three `.S` files** (`entry.S`, `ap_trampoline.S`,
`qualification_entry.S`; 635 lines): interrupt entry, AP start, the
firmware CR3 trampoline. The pure-native profile's own entry exists
(`native/kernel.kotoba`, ADR-0131 refuses `entry.S`); these move when the
production image switches to that entry, which is the same day the loader
does.

**What the language still refuses, per ADR-0212, and stands:** variable-
count shifts (AES/GHASH proper are in Kotoba already through literal-count
shifts), `ms_abi` indirect calls, the preprocessor (build flags become
runtime literals), and the five-argument ABI (flat records answer it).

## What this does not do

- No hardware. QEMU only. The poll parse and the job lines have still not
  executed as machine code — they are reached only through a physical
  relay — but their literal walks now cannot jump to 0.
- The inference cutover is designed, not started. The C forward pass is
  live.
- The programme above is an order and a set of dispositions, not a
  schedule. Each wave is measured the way waves 1 and 2 were: the retired
  C's own answers as the contract, the object recompiled by its recipe,
  a boot that falls when the object is wrong.
