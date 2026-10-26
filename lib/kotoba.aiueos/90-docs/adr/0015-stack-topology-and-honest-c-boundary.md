# 0015 — Stack topology position, and an honest statement of the C mechanism boundary

Current architecture direction (2026-10-10): Wasm is one AMU target, target ABI
profiles are separate from neutral contracts, and distribution/consensus
profiles are independent of execution targets. Tier numbers are ownership
labels, not dependency ranks. The coordinated owner guide is
[stack architecture](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture-target-neutral.ja.md);
[current dependency measurements](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-dependency-observation.edn)
remain distinct from intended migration. Existing runtime schemas and historical
qualification evidence are not changed by this documentation.

Status: accepted
Date: 2026-07-24
Root authority: `com-junkawasaki/root` ADR-2607241100 (kotoba stack topology
and design cleanup). This ADR is the aiueos-repo mirror; the canonical
topology and the full cross-repo cleanup list live there.

## Position in the stack topology

Updated 2026-10-10 against fetched main manifests. The
[stack architecture](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/stack-architecture.md) and
[composition contract](https://github.com/kotoba-lang/kotoba-lang/blob/main/lang/stack-architecture.edn) distinguish responsibility, library,
artifact and runtime/service graphs.

```text
kotoba-lang = language contracts (T1)
kotoba      = CLI, libraries and Codebase
amu         = compiler and project linker (T2)
abi         = shared execution contract (T0)
kototama    = Lisp VM contract; engines implement it (T3)
grant       = pure permission decisions (T4); authority owns scope/delegation
aiueos      = operating system (T5); enforces grant's answer
sahai       = reusable placement (T6); murakumo operates its own inference fleet
kotobase    = database and persistent data plane
```

AiueOS is the OS for a modern Kotoba Lisp machine in development; Kototama is
its Lisp VM contract, also implemented by hosted engines. These are
architectural roles, not completion/qualification claims.

Library arrows mean consumer → dependency: Kotoba imports Amu and Kototama;
Kototama imports grant and abi; AiueOS imports grant; grant imports authority
and abi and does not import the OS. Amu imports contracts and multiple
backends. Alias-only dependencies must be labelled separately.
The booted kernel consumes verified compiler artifacts rather than linking
the compiler. Host build/conformance aliases may import compiler libraries.
The database/language boundary describes ownership, not a claim that every
database runtime directly imports the Kotoba CLI.

The July 2026 topology snapshot was corrected on 2026-10-10 after the grant
split and VM-contract separation; its old dependency counts and “AiueOS
decides” wording are not current invariants.

## Decision 1 — state the real C boundary instead of the "crt0 shim" story

The workspace-level rule (com-junkawasaki/root AGENTS.md, ADR-2607198300 era)
describes the permitted non-CLJC/non-Kotoba code as "the minimal crt0-style
entry shim an OS executable format requires." Measured reality in this repo
(2026-07-24): `os/aiueos/kernel/` carries ~5,000+ lines of C/asm — `pci.c`
1178, `main.c` 690, `scheduler.c` 570, `syscall.c` 501, `paging.c` 425,
`entry.S` 372, plus multiboot/UEFI loaders. That is not a crt0 shim; it is a
real mechanism kernel.

The **actual** boundary — which the code already honors and CI gates prove —
is better than the stale claim, and should be stated as-is:

> **C/asm owns mechanism only** (register/MMIO access, GDT/IDT, paging
> primitives, APIC/SMP bring-up, virtio queue plumbing, context switch).
> **Every decision is compiler-emitted Kotoba**: SHA-256 and RSA-2048
> signature verification, ELF/catalog/journal admission, capability
> encode/admit/derive/revoke planning (generation-safe), scheduler dispatch
> planning, pointer/length window admission, syscall-range validation. The C
> substrate contains no digest, signature, admission, or capability logic.

**Decision:** this ADR is the authoritative statement of the boundary.
"Decision-free C mechanism" is the reviewable property — enforced by the
existing pattern that every new admission/validation path lands as a
`kotoba/*.kotoba` object with QEMU-gate evidence, never as C logic. The
root-repo ADR ledger gets a corresponding amendment (ADR-2607198300's
"kgraph unsupported on the native backend" claim is also stale — the
compiler's x86-64/aarch64 backends now implement and test
`kgraph-assert!`/`kgraph-get`/`kgraph-count`/`kgraph-entity-at`).

Growth direction remains: when the native backend gains an op family that
lets a C mechanism block become a plan/validate split (as happened for
SHA-256, RSA-2048, catalog admission, capability planning), migrate it. The
C line count going down over time is desirable; pretending it is already ~0
is not.

## Decision 2 — grant vocabulary joins the canonical capability schema

kototama's `aiueos_adapter` can translate only the 3 kernel capabilities
(`log-write`/`clock-monotonic`/`random-bytes`) into `HostCaps`; the other
`actor:host` imports have no aiueos-decidable counterpart and fall back to
caller-supplied caps — a hole in "aiueos decides." As the canonical typed
capability-descriptor schema lands (root ADR-2607241100, kototama ADR-0009),
aiueos extends its grant vocabulary so every hosted import is decidable here,
and the adapter's coverage becomes a generated, mechanically-checkable
mapping instead of a hand-maintained partial one.
