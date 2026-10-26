# ADR-0001 — aiueos Phase-0: a capability-component OS substrate on kotoba/kototama

- Status: accepted
- Date: 2026-06-25

## Context

The design calls for **aiueos**: an OS where *“everything is a word (a declarable
structure)”* and *“everything is a Wasm component (an isolated unit of
execution).”* Two pieces already exist in the superproject:

- **kototama** compiles a Clojure/EDN subset to real wasm and runs it on
  `wasmtime` with a fuel budget (`kotoba-clj`’s `run`).
- **kotoba-edn** is the single source-of-truth EDN reader.

The temptation is to start at the bottom — write the microkernel and drivers in
kotoba first. That maximizes failure probability: MMIO/DMA/IRQ/timing is exactly
where a high-level language helps least, and *“the PCIe spec hits you before the
mythical AI agent does.”* The design’s own recommendation is to start at Phase 0
— the runtime, manifests, policy, broker, audit — on a host OS.

## Decision

Build Phase 0 as a single Rust crate `aiueos` that depends on `kotoba-edn`
(manifests/policy/audit as EDN) and, behind a default `wasm-runtime` feature, on
`kototama` + `wasmtime` (compile + execute). The OS is modeled as a **graph of
capability components**, not processes.

1. **Manifests are kotoba.** `:aiueos/...` EDN describes each component’s kind,
   trust, imports, exports, effects, requirements and limits. A manifest is
   *data the OS reasons over*.
2. **The broker is the only thing that confers capabilities**, and it audits
   every grant/deny/compile/run as one EDN map per line.
3. **Three policy rules are enforced now**: capability linking (imports must
   resolve), effect-vs-trust (AI-generated/untrusted lockdown), and the
   driver-DMA rule (`:dma` ⇒ `:requires #{:iommu}` + an `:iommu` grant).
4. **A safe-kotoba subset gate** (denylist over every symbol: no
   eval/require/slurp/reflection) runs before any source-based component is
   compiled, turning an escape attempt into a security-shaped error instead of
   an opaque compile failure.
5. **The runtime enforces limits, not requests them**: wasmtime fuel +
   linear-memory page cap; a runaway traps instead of harming the host.
6. **The TCB stays small**: only the broker, runtime, safe-checker and manifest
   reader are trusted. Drivers are components precisely so they can be evicted
   from the TCB — DMA is the one residual escape, hence the mandatory IOMMU gate.

### Native vs kotoba split (deferred but pre-modeled)

The microkernel will be native (Rust/Zig); services/drivers/apps will be
kototama→wasm components; the lowest MMIO/DMA/IRQ layer will be tiny kernel-
provided unsafe adapters. Phase 0 does not build the kernel, but it already
models its seams: kernel-provided capabilities (`dma/map`, `irq/subscribe`,
`mmio/map`, `pci/config`, `clock/monotonic`, …) and the `:requires #{:iommu}`
device-binding requirement. Later phases supply real implementations behind the
same capability names without reshaping the core.

## Consequences

- A working `aiueos` CLI today: `verify`, `inspect`, `run`, `compile`, `check`,
  `audit`. The demo system links a log service, fs service, virtio-blk driver
  and notes app; the driver’s DMA is denied without a policy that grants the
  IOMMU, and allowed with one.
- The semantic core builds with `--no-default-features` (no wasmtime), so the
  manifest/policy/graph engine is fast and dependency-light; execution is an
  opt-in feature.
- Hex integer literals (`0x1af4`) are **not** supported by kotoba-edn — device
  ids in schemas are written as strings (`"0x1af4"`). Noted so later device
  schemas don’t reintroduce unparseable literals.
- The workspace’s `.cargo/config` defaults the build target to
  `wasm32-unknown-unknown`; host builds/tests must pass `--target <host-triple>`.

## Alternatives considered

- **Write the kernel/drivers in kotoba first.** Rejected per the design: highest
  failure probability, lowest leverage for a high-level language.
- **A microkernel-first native OS with POSIX at the center.** Rejected: the
  design’s differentiator is putting *component + capability + manifest + proof +
  audit* at the center, not POSIX/Win32.
- **clap + serde_json for the CLI/manifests.** Rejected: hand-rolled arg parsing
  + kotoba-edn keeps the dependency surface small and keeps *everything as
  kotoba*.
