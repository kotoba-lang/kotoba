# Security model & threat model

aiueos is designed for **containment under mythos-class adversaries** — the
assumption that any individual component (an app, a driver, an AI-generated task)
may be hostile or compromised, and the OS's job is to ensure that this stays a
*contained* event rather than a system-wide one.

This document is deliberately honest: aiueos is an **architecture for
containment**, not a claim of invulnerability. It tells you both what the design
defends and what it explicitly does not (yet) defend.

## What "mythos-class" means here

A mythos-class adversary is the worst plausible case we design *toward*:

- supplies a malicious component (including via an AI agent that writes code),
- knows the source, manifests and policy,
- will try to reach capabilities it was not granted, exfiltrate secrets, escape
  the sandbox, or take down the whole system from one node.

The goal is that none of those succeed **from inside a component** without an
explicit grant, and that whatever does happen is **audited**.

## Defense layers

1. **Deny-by-default capabilities.** A component can touch *only* what its
   manifest is granted. Imports must resolve to a real provider, a kernel
   primitive, or an explicit policy grant; anything else is an
   `unresolved-capability` denial before launch.
2. **Runtime-enforced gates, not convention.** Capabilities aren't just a static
   claim — the `aiueos:host` ABI only links a host function for a capability the
   broker actually granted (`aiueos.execute/instantiate`, JVM/Chicory adapter);
   an ungranted capability's import is never linked, so `Instance.Builder/build`
   fails to link and the component never even starts running. This is coarser
   than a per-call runtime check (the gate fires once, at module-link time, not
   per invocation) but functionally equivalent under Wasm's own semantics: a
   component can only ever call a function it successfully imported, so an
   ungranted capability can never be reached, on any code path. (Fixed
   2026-07-13 — a prior version of this JVM adapter linked all kernel-cap host
   functions unconditionally for every component, with only quota counting and
   the per-topic-id check below actually gated per call; see
   `90-docs/adr/0149-link-time-capability-enforcement.md`.)
   Holding some capabilities never leaks the ones you weren't given (capability
   attenuation is tested). Kernel-primitive imports (`:random/bytes`,
   `:log/write`, the DMA-family quartet, ...) resolve ONLY through the
   broker's own grant decision (`aiueos.policy/granted-to`), never through a
   co-located component's self-declared `:aiueos/exports` — an exporter can
   still provide any non-reserved capability name it likes, but it cannot
   spoof a kernel primitive to smuggle it past a surface/kernel-caps
   restriction in a multi-component boot. (Fixed 2026-07-13 alongside the
   link-time gate above; found by independent review of that same fix —
   `aiueos.policy/verify-component`'s import resolution previously let ANY
   co-located component's export claim resolve ANY import, with zero
   authenticity check, including reserved kernel-primitive names.)
   Enforcement reaches **individual data channels**: a manifest declares the
   topic ids it may publish to / read (`:aiueos/publishes` / `:aiueos/subscribes`),
   and a publish/read to an undeclared topic traps even with the coarse
   `topic/*` capability held — so a compromised sensor cannot command the
   actuator's topic.
3. **Enumerated TCB.** The broker, policy/signing/manifest authority, Wasm
   runtime/host ABI, production admission/audit path and hardware adapters are
   trusted. Apps, services, Wasm drivers and agents live outside it. The
   versioned file/role/external-dependency inventory is SHA-256 drift checked
   by `kbb -M:tcb-check`; regulated admission binds its digest. See
   `docs/tcb-inventory.md`.
4. **Wasm isolation + resource limits.** Each component runs in its own linear
   memory under a **fuel** budget (bounds CPU) and a **memory-page cap** (bounds
   RAM). A runaway traps instead of hanging or starving the host.
5. **The IOMMU/DMA rule.** DMA is the one residual way a driver could escape its
   sandbox, so any component with the `:dma` effect, OR whose `:aiueos/imports`
   requests any of the device-access quartet (`:dma/map`/`:pci/config`/
   `:mmio/map`/`:irq/subscribe` — `aiueos.policy/dma-family-imports`), *must*
   declare `:requires #{:iommu}` **and** be granted `:iommu`, or it is denied.
   (Fixed 2026-07-13: the gate previously fired ONLY off the self-declared,
   unenforced `:aiueos/effects #{:dma}` field, with no structural link to the
   actual capability requested — a manifest could import `:dma/map` while
   simply omitting `:aiueos/effects #{:dma}` and skip the gate entirely; see
   `90-docs/adr/0149-link-time-capability-enforcement.md`.)
6. **Safe-kotoba subset.** Source-built components are screened for escape
   hatches (`eval`, runtime `require`, `slurp`/`spit`, reflection, dotted host
   classes like `java.util.*`) *before* compilation — a security-shaped error,
   not an opaque failure.
7. **AI-generated containment.** A component authored by an AI agent is
   `:ai-generated`: untrusted, ephemeral, and denied `:network`, `:secrets` and
   `:persistent-write` by default policy.
8. **Append-only audit.** Every grant, denial, compile and run is recorded as
   EDN — the same data model as everything else — so post-incident forensics and
   "who commanded the actuator, and why" are first-class.
9. **Manifest authenticity (ed25519 signatures).** A manifest may carry an
   `:aiueos/signature` over the canonical identity↔artifact binding
   (`"<id>\n<wasm-sha256>"`), verified against the policy's `:aiueos/signers`
   registry of trusted public keys. A valid signature elevates the component to
   `:verified` and records the signer in the audit log (provenance); a forged or
   unregistered signature is a hard denial — never downgraded to "unsigned". A
   `:aiueos/require-signed` policy rejects unsigned components outright. (ADR-0003.)
   Authenticity alone only proves *some* registered signer vouches for these
   bytes under this id, not that they're the signer *authorized* to claim that
   id — `:aiueos.policy/component-signers` binds specific component ids to
   authorized signer sets, enforced unconditionally for any id that declares a
   binding, and (under `:aiueos/require-signed`) by default for any id that
   doesn't: an unbound id's elevated grant no longer applies to *any* signer
   once a policy requires signatures at all. (ADR-0012.)

## Per-surface notes

The same component model runs on **edge, robotics, cloud, browser, client**. The
*capabilities offered differ per surface* (a robot grants `topic/*` and device
buses; a browser grants DOM/fetch shims; cloud grants storage/net brokers) but
the deny-by-default gate is identical. A component proven safe on one surface
carries its manifest's capability requirements to the next; the host simply
refuses to provide what that surface shouldn't.

## What aiueos does NOT defend (yet) — honest limitations

- **Side-channel assurance remains bounded.** Production admission now requires
  a versioned decision covering timing, cache and Spectre classes, baseline
  mitigations appropriate to the profile, and named residual-risk acceptance.
  This prevents silent omission but does not prove that host firmware,
  operating-system controls or hardware applied those mitigations. Power,
  electromagnetic, physical-probe and privileged-host attacks remain outside
  the software-only profile; `high-assurance` remains blocked.
- **The TCB itself.** A bug in wasmtime, the host adapters, or the broker is
  game over. The TCB is small by design, but it is trusted, not verified — there
  is no formal proof yet.
- **Signing authority is epoch distributed.** Regulated deployments use
  root-signed, predecessor-chained lifecycle epochs. Delegation scope and
  parent validity are checked; rotation can overlap keys; revoked,
  compromised, suspended, retired, expired and not-yet-valid signers receive
  no authority. Nodes accept exactly the next signed epoch, so replay,
  rollback, gaps and forks fail closed, and convergence is observable by epoch
  digest. The node checkpoint still depends on sealed monotonic storage and
  the root key on offline/HSM custody. Legacy bare-key entries remain available
  only for research compatibility. See `docs/key-lifecycle.md`.
- **Not a hard-real-time scheduler.** Per-cycle **IO quotas** now bound
  host-call rate (`:aiueos/quota {:host-calls N :publishes N}` — an over-budget
  call traps like any other), and a **deterministic cooperative scheduler**
  (`:aiueos/schedule`, ADR-0006) gives period-skipping and priority ordering
  within dependency depth. Every Chicory instantiation and run is now placed
  on a dedicated daemon worker with a bounded wall deadline; timeout interrupts
  the worker and is reported only after termination is observed. An infinite
  Wasm loop is covered by an end-to-end overrun test. This provides hard
  termination, not deterministic response latency: JVM scheduling, GC and host
  adapters remain non-real-time. True preemptive hard-real-time scheduling
  still needs the Phase-6 microkernel.
- **Lowest-level drivers.** Real MMIO/DMA/IRQ adapters (Phase 7) will contain
  small `unsafe` code; that code, once written, is part of the TCB and must be
  audited as such.
- **Network topic payload confidentiality is transport-dependent.** The local
  topic bus remains in-process, while `aiueos.network-topic` supplies bounded
  Ed25519-authenticated wire envelopes for cross-machine carriage. Channel and
  publisher identity, per-topic authorization, durable sequence anti-replay,
  and atomic partition/rejoin backlogs are enforced. The envelope is
  authenticated but not encrypted; deployments requiring traffic secrecy must
  use an authenticated encrypted carrier.
- **At-rest protection depends on external key custody.** Production profiles
  require AES-256-GCM sealed audit and component-state stores with external
  per-purpose keys. Audit records are predecessor chained and checked against
  an externally retained Ed25519-signed head, including valid-prefix
  truncation detection. Component snapshots bind identity and monotonic
  version. Both paths cover authenticated backup/restore, retention or
  deletion, and crypto-erasure. Software enforces the KMS/HSM adapter contract;
  deployment evidence must still identify the real custody provider. See
  `docs/sealed-storage.md`.
- **Entropy is profile-qualified, not universally FIPS validated.** The typed
  `:random/bytes` / `random_bytes(ptr,len)` capability is backed by the JVM
  strong OS entropy selection, is capability-gated and quota counted, and
  rejects zero, negative, or greater-than-4096-byte requests before allocation.
  Provider identity is attestable and each sample must pass continuous
  duplicate, repetition-count and adaptive-proportion checks before reaching
  guest memory. A FIPS claim remains forbidden without named module,
  cryptographic-boundary and provider-validation evidence. See
  `docs/entropy-profile.md`. Deterministic simulation PRNGs are visibly outside
  this ABI and are not security entropy.

If a deployment needs any of the above, it must add it above aiueos — the design
makes room for these (signing hooks, per-surface providers, scheduler) but
Phase-0 does not ship them.

## Deployment profiles

Security claims are deployment-profile specific. The default profile is
`research`: capability containment, Wasm limits, and audit, with no FIPS,
side-channel, hard-real-time, or formal-verification claim.

PID-1 resolves and admits the profile before starting the component graph.
Explicit profiles require versioned evidence; `sensitive-local` and
`regulated` reject every omitted required-control assertion, unknown profiles
are rejected, and `high-assurance` is unconditionally blocked. These assertions
are boot admission inputs, not cryptographic proof of the underlying controls;
signed evidence receipts and independent deployment verification remain open.

Profile definitions live in [`docs/deployment-profiles.md`](docs/deployment-profiles.md):

- `research`: local experiments and demos;
- `sensitive-local`: single-tenant local systems with host hardening and
  encrypted audit/data requirements;
- `regulated`: evidence, key lifecycle, SBOM/SLSA, monitoring, and provider
  policy requirements;
- `high-assurance`: blocked until formal and side-channel evidence exists.

## Reporting

This is a research substrate under active development. If you find a flaw in the
capability model or the TCB, please open an issue describing the component
manifest, the capability it reached, and the expected denial.
