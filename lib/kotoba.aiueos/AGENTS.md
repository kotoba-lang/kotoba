# AGENTS.md — aiueos

## Common OS and distributions

AIUEOS is the common OS foundation. Itonami OS is the Awai distribution in this
same repository (`distributions/awai`), using the same kernel/ABI/build path.
Keep generic OS mechanisms in the common core and Awai composition/branding
in distribution configuration. Distribution metadata neither grants authority
nor changes component qualification. See `distributions/README.md` and
`90-docs/adr/0274-awai-os-is-an-aiueos-distribution.md`.

## Shared Browser native progress (JUN-93)

See `90-docs/shared-browser-native-progress.md` and the source-bound native
qualification record. Shared text/DOM/text-edit component execution, kernel
desktop integration, dapps/broker consent and durable restore are separate
gates. The diagnostic Browser-frame2 cards do not execute registered services.
The legacy hosted maturity ladder and scores retain their original scope;
do not run KBB/NBB/JVM or count those receipts as current native acceptance.

## Native desktop/media candidate

The desktop entry `os/aiueos/scripts/build-kotoba-native-desktop.sh` no longer
invokes Node/nbb for bootstrap or packaging. It calls the native font,
locked kernel/EFI and GPT/FAT16 pipeline in `build-native-desktop.py`.
Python only stages, hashes and observes; the formats are emitted by Kotoba.
The legacy font generator and older hosted packagers do not qualify this
closure. The checked-in licensed bitmap is input data, copied/padded by a
native tool. See `90-docs/native-desktop-media-v1.md` for exact boundaries.
Local raw-media/QEMU desktop/input proofs do not qualify Browser/CSSOM
parity, dapp execution, preemptive scheduling or physical hardware. The
final compiler still requires native x86/controller/pin adoption evidence.

## CDCI migration: native only (2026-10-24)

Owner instruction and workspace `AGENTS.md` supersede the historical KBB,
NBB and JVM task commands below. Do not run those routes or restore them as
fallbacks. The final compiler, build graph, packaging and gate controller
must use canonical Kotoba and Amu selfhost native artifacts.

Removed `.github/workflows/ci.yml` in full: `bare-metal-uefi` invoked the
C/Zig reference image build and installed NBB/babashka; `test` installed
Java/Clojure/NBB and ran hosted contracts/lint/security-adoption; and
`edn-contracts` used babashka. No disabled legacy workflow remains.

Native consumer CI runs in the existing private `kotoba-lang/org-ietf-tcp`
repository because the final TCP dependency is private. Its workflow pins
the exact AIUEOS/Amu sources and all five owner revisions, using the repo's
existing read-only token without exporting private source to this public
repository. Native Linux x86 reproduces
the full kernel ELF/EFI and the full-graph DMA probe; QEMU must accept the
actual snapshot mechanism and reject a valid image lacking its receipts.
This is a component gate. Acceptance also requires the pinned Amu source's
native x86/controller CI. Removal of the old workflow is not
a passing check. Native kernel objects are a separate compiler capability;
they do not qualify a complete selfhost-built kernel/EFI/GPT image or boot.
The new gate does not replace coverage for hosted CLJC contracts, lint, security adoption,
example EDN reading, journal recovery, corrupted payload refusal, release
media and Multiboot/GRUB boots previously declared by that workflow.

Track the compiler/image/QEMU chain in JUN-31, base/tool migration in
JUN-64 and AWAI-23, and Browser/CSSOM plus app integration in JUN-93.
QEMU/OVMF and diagnostic orchestration are distinct from the native guest
and from the required loaderless x86_64-linux-static CDCI controller.

The kernel build wrapper now stages inputs with `build-native-kernel.py`
and invokes the pinned native Amu executable directly. It no longer loads
kotoba-native hosted sources or uses `--jvm-free` / `--unpinned`. Native
`modules` owns discovery; owner source pins and KSL1 bind the full graph.
Python only stages, hashes, invokes and records failures. A blocked compile
or reproduced image candidate is not a successful native runtime gate.

Nine ValueRuntime/arena sources now use their canonical namespace paths in
`os/aiueos/kotoba/aiueos/` with underscores. Their bytes were preserved in
the move. Historical hosted verifiers that name the old paths remain retired
migration inventory; do not execute them or recreate duplicate source copies.

The R2 reference claim below is historical C/reference-runtime evidence,
not acceptance of the current native selfhost chain. Amu #1547 is merged
with native x86/controller qualification; the whole AIUEOS kernel, live
runtime, native media and desktop/input still follow the open gates in
`90-docs/native-selfhost-integration.md`. New scratch constructors are
engineering candidates until their successor adoption gates pass.

Status: R2 — bare-metal boot and CPL3 execution are :implemented on QEMU/OVMF;
P5 real-machine boot is :spec. See the README's capability table for the
per-subsystem state; it is the authority and this file does not restate it.

Why R2 and not higher, and a warning about the scale itself. This line is not
decoration: `scripts/repo-maturity.cljs` parses it with
`(?i)status[^a-zA-Z0-9]{0,10}R([0-5])\b` and turns it into `:maturity/stage-score`
— R2 scores 0.4, R3 scores 0.6. **There is no published R0–R5 rubric anywhere in
this workspace.** Every occurrence found is `R<n> — <free text>`, with no scale
defining what any level requires, so the axis is scored against nothing and the
numbers are not comparable between repos. Given that, the only defensible anchor
is what peers declare: across the checked-out `kotoba-lang` repos the levels
actually claimed are R0 (2), R1 (2), R2 (6), and **nobody claims R3, R4 or R5**.
This file said R3 for about an hour on the strength of nothing, which is exactly
the failure the rest of it warns about. If you raise it, raise it against
evidence — and if you write the missing rubric, delete this paragraph.

Agent instructions for `kotoba-lang/aiueos`. Everything below was measured in
this repo, and most of it was measured *because an agent got it wrong first*.

## The five things that mislead readers of this repo

### 1. "C-free" forbids libc, a CRT, a JVM and Linux — not C

ADR-0013's rule is about what the bare-metal profile may *depend on*. It is not
a claim that the tree contains no C. Measured 2026-09-10:

    os/aiueos/kernel    21,294 lines of C, asm and headers,  0 lines of .kotoba   (2026-09-16 wave 2; 21,434 wave 1, 21,391 on 09-11)
    os/aiueos/native         0 lines of C,      7,157 lines of .kotoba   (job_protocol.kotoba moved to kotoba/aiueos/ when it was wired)

⚠ The kernel C count went UP on 2026-09-16 while three more files lost their
judgment (ADR-0219): a struct the object cannot walk is packed into a flat
record by new C. **Count judgment lines still in C, not C lines.**

The `.kotoba` lives in `native/` as objects the C kernel links. **Do not tell
anyone this OS is written only in Kotoba.** The end state is C-free; the
current state is a C kernel that calls Kotoba for judgment.

### 2. "superseded as C-free evidence" does not mean "does not run"

ADR-0112 is `superseded as C-free evidence` because its scheduler, loader and
provider were C-compiled — hybrid functional evidence, not C-free evidence.
The path itself works. Measured 2026-09-10:

    AIUEOS_PLC_RT_QEMU_OK scans=100 signed-elf tamper-rejected
                          fixed-priority-preemption native-provider
                          apic-release transactional-output safe-state

A signed CPL3 ELF making `cap-call 16/17/18/19` through
`kernel/entry.S:aiueos_syscall_entry`. Two separate sessions concluded "ring 3
does not exist" from the README's capability table plus that ADR's status word,
and both were wrong. **Run `:plc-rt-qemu-smoke` before saying a path is absent.**

### 3. C marshals, Kotoba judges — and that is what the provenance rule means

    kotoba objects linked by build-uefi.sh        106   (2026-09-16 wave 3; the two Qwen objects grew ~64 KiB, see ADR-0221 on the low-region budget)
    distinct kotoba_* symbols C declares extern   108
    C files that call into Kotoba                 23 of 30

The convention:

    extern int64_t kotoba_aiueos_device_worker_digest(uint8_t *st, int64_t st_len, …)

A flat base and a length. That matters because
`:kotoba.error/kernel-region-provenance` — "kernel memory base must name a
region, not compute one" — refuses a pointer *loaded from memory* as a region
root. So a Kotoba function cannot take `struct foo *` and walk its `char *`
fields. It can take `(base, length)`. **The rule dictates the signature; it does
not block the conversion.** Read a "blocked" note in ADR-0212 as "blocked while
keeping the current C signature". The signature that fits every width is ONE
flat record the C packs and the object reads by offset (ADR-0219): the layout
is the `.kotoba` header comment, and the contract's records are produced by
the C packer, so a drift between the two turns the contract red.

### 4. Before writing Kotoba for a C file, look in `native/` AND `kotoba/`

`relay_protocol.c` was ADR-0212's top conversion candidate. It was already
written: `native/relay_line.kotoba` + `native/relay_text.kotoba`, byte-identical
on the wire (gate `:relay-parity`), and *better attested* than the C — the
templates are generated by `tools/gen-relay-text.cljs`, which checks each one
against the relay's own regexes in `tools/k16-pxe-server.py`.

⚠ **"Already written" did not mean "already linkable."** The pair writes a frame
page from MMIO; `pci.c` held a stack buffer and a MAC. The C was retired on
2026-09-11 (ADR-0215) by emitting a kernel object with the C's *shape*
(`kotoba/relay-hello-payload.kotoba`, `kotoba/relay-ack-payload-valid.kotoba`),
not by wiring the pair in. Check the caller's signature before deciding which of
the three a file is. And the toolchain cost was the day: the .cljk rename had
broken amu's JVM-free route, the export table needed two rows in BOTH elf64
twins, and this repo's own provenance generator was silently demoting every
verified object. Budget for the road, not the file.

Every C file is one of three: already in Kotoba (retire the C), not in Kotoba
and expressible (write it), not in Kotoba and blocked (record it). Decide which
before writing a line. ADR-0220 carries the disposition of every remaining
file and what each waits on; read it before picking one.

⚠ **The production node image has 32 KiB of low-region headroom** (ADR-0222;
receipt `os/aiueos/qualification/low-region-budget.edn`). The kernel and
every Kotoba object it links must end below `aiueos_low_end <= 0x1f4000`, the
loader admits exactly two PT_LOAD segments, and objects are larger than the C
they replace. Before the next object lands, either move more `.bss` scratch to
`.high_bss` (zeroed at entry since ADR-0221) or give the loader a third R+X
segment for Kotoba text.

### 5. An object that links and passes its contract has not run

Two objects landed in ADR-0215 and two in ADR-0219 walked string literals
through `string-code-point-at` -- which lowered to a HOST CALL through context
slot 144, and a kernel object has no host. Every one of them linked, passed its
KIR contract, and would have jumped to address 0 the first time its path ran
(measured 2026-09-16 under QEMU on the first such object that did run,
ADR-0220). The oracle executes the SOURCE; the link proves the SYMBOL; neither
executes the machine code. **Until a boot reaches the object, say so.** The
same day showed the second shape: four objects packaged at the 1,024 fuel
default `ud2` on a real input while passing every contract vector. Bisect the
tier in the oracle and give kotoba-native the row (ADR-0220).

## Measuring things here

### A marker that is not `AIUEOS_<NAME>_OK` does not exist

`os-coverage.cljs` recognises exactly `/AIUEOS_[A-Z0-9_]+_OK/`. The TSC
calibration in `uefi/main.c` (`info.tsc_hz = elapsed * 10ULL`) is real, reaches
the kernel, and drives `aiueos_wait_seconds` — and scored nothing for as long
as it announced nothing.

⚠ **But it is `#ifdef AIUEOS_QWEN38_MODEL_HANDOFF`.** Measured 2026-09-10 by
emitting a marker and booting: it did not appear, because in the default smoke
build `tsc_hz` is zero — the calibration is compiled out. The TSC is calibrated
in the Qwen model-handoff profile and nowhere else, so **the profile that
usually boots here has no calibrated clock**, and ADR-0116's "raw TSC until a
calibrated frequency exists" is right about it. Do not say this OS calibrates
its clock without naming the build profile.

### `os-coverage.cljs` refuses without an evidence log, on purpose

It measures what a boot EMITTED, not what the sources declare. A run with no log
would report 0% and 0% would be a lie. Do not "fix" the refusal.

### A whole-run QEMU instruction total is noise

`-icount shift=0,sleep=off` makes the guest *clock* deterministic. It does not
make OVMF's device-polling loops spin the same number of times:

    same image, run 1   1,532,182,814 guest instructions
    same image, run 2   1,528,370,810          (3.8M apart)

An in-guest `kernel-rdtsc` bracket over a region that runs after boot and
touches no devices was byte-identical across three runs. **Bracket inside the
guest; never difference two whole runs.** `scripts/qemu-insn-count-plugin.c`
carries this at the top of the file.

### Read the EDN contracts with a reader, not a regex

A regex over `contracts/os-coverage-v1.edn` matched 8 of its 18 subsystems and
reported a clean "(none)" for the thing being audited. `cljs.reader` found the
hole. A zero from an incomplete scan and a zero from a complete one look
identical — always print the count of what you scanned.

## Landing

- `scripts/tasks.edn` is the task registry: `kbb --backend sci scripts/run-task.cljk <task>`.
  Register a new gate there and then *run it through the registry* — an entry is
  not a registration until something has invoked it that way.
- ADR numbers collide. Two sessions took `0210` forty minutes apart, and the
  collision is silent because two files named `0210-*.md` are two paths that
  merge cleanly. Check `git ls-tree origin/main -- 90-docs/adr` immediately
  before writing, and again before pushing.
- `CLJC contract tests` has been failing on `main` independently of any given
  branch. Check whether main is already red before attributing it to your work.
