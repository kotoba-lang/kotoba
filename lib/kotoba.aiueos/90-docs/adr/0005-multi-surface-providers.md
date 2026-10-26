# ADR-0005 — Multi-surface capability providers

- Status: partially implemented (Phase 3)
- Date: 2026-06-27

> **Implementation status.** The verify-level contract is in code: `surface::offered`
> defines each surface's backed caps, `Policy::granted_to` intersects `kernel_caps`
> with the active surface's offered set, and a `surface-mismatch` violation guards
> `:aiueos/surface`. The **`Surface`/`Provider` registry value** is in
> `src/surface.rs`: `Surface::{robot,browser,cloud}()` list their providers
> (capability + host import name), `offered()`/`is_known()` delegate to it as the
> single source of truth, and `Surface::union` composes them (e.g. an edge gateway
> = `robot ∪ cloud`). **Tooling:** `aiueos surface inspect <id>` prints the offered
> set (text or `--edn`). **Runtime providers** for both non-robot surfaces have
> landed, bound in `src/host.rs` as gated `aiueos:host` host functions over
> in-process, deterministic state (the Phase-0 stance: no real DOM, socket, or
> ambient credentials inside a host import):
>
> - **browser** — `dom/render` + `dom/event` + `input/event` +
>   `framebuffer/present` over a `DomSurface` (a render log + semantic event FIFO
>   fixture-loadable from `:aiueos/dom-events` + low-level input FIFO from
>   `:aiueos/input-events` + an in-memory framebuffer frame log);
>   `tests/browser.rs`.
> - **cloud** — `storage/kv` (`kv-set` / `kv-get`, an in-memory map threaded out
>   through `HostOutcome::cloud`) + `net/fetch` (`fetch`, a URL→response fixture map
>   from `:aiueos/fetch`) over a `CloudSurface`; `tests/cloud.rs`. This is the
>   "second real surface end to end" of Increment 4: a manifest moves between
>   surfaces unchanged, gated identically, backed by different providers.
>
> **CLI:** `aiueos run|up --surface <id>` selects the active surface;
> `--dom-events`, `--input-events`, `--cloud-fixture`, and `--browser-out`
> provide deterministic surface fixtures/bridges. `Provider::bind` and `Surface::install` are now the
> runtime installation path in `src/host.rs`: the registry allows multiple host
> imports for one capability (`poll`/`take`/`count` all gate on
> `topic/subscribe`; `kv-set`/`kv-get` both gate on `storage/kv`).

## Context

The same component+manifest+capability model is meant to run on **edge,
robotics, cloud, browser, and client**. Today only one surface exists in code:
the in-process robot. Its capabilities — `topic/publish`, `topic/subscribe`,
`clock/monotonic`, `log/write`, `random/bytes`, plus the device-broker
primitives (`pci/config`, `dma/map`, `irq/subscribe`, `mmio/map`) — are hard-wired
two ways. `src/host.rs` binds a fixed `aiueos:host` Linker with seven host
functions, and `Policy::default()` hands out a fixed `kernel_caps` set. Both are
*the robot surface, frozen as the only surface.*

The deny-by-default gate is already surface-independent: `gate(ctx, cap, what)`
in `src/host.rs` traps any call whose capability isn't in the conferred set, on
every surface, identically. What is *not* yet separated is the other half — **who
supplies the implementation** behind a capability. `net/fetch` means a real
socket broker on cloud, an XHR/`fetch` shim in the browser, and *nothing at all*
on a robot. `dom/render` exists only in a browser. `pci/config` exists only where
there is real hardware. Per the SECURITY.md "Per-surface notes": the capabilities
*offered* differ per surface, but the gate is the same, and a component proven
safe on one surface must carry its manifest's requirements to the next — with the
host **refusing to provide what that surface shouldn't.**

We need a seam that turns "the surface is the robot" into "the surface is a value
the broker is configured with," without reshaping the core capability model.

## Decision

Introduce a **Surface**: a registry that binds capability names to concrete host
implementations, layered *over* the existing wasmtime `Linker` + the
`gate()` check in `src/host.rs`. The broker still gates every call on the
conferred set; the surface only decides *which implementation* (or none) backs a
capability. The two questions stay orthogonal:

- **May this component call `net/fetch`?** — the conferred set (policy + manifest
  imports), unchanged, surface-independent.
- **What happens when it does?** — the surface's bound provider, or a hard
  `unresolved-capability` denial if this surface offers no such provider.

### The Provider / Surface abstraction

A `Provider` is one host function plus the capability it is gated on. A `Surface`
is the set a deployment offers. Sketch:

```rust
/// One host-function implementation, gated on `cap`. `name` is the
/// `aiueos:host` import the wasm calls; `cap` is checked via the existing
/// `gate()` before the closure runs.
pub struct Provider {
    pub name: &'static str,       // e.g. "fetch"
    pub cap: &'static str,        // e.g. "net/fetch"
}

/// A deployment target: the capabilities it *offers* and their impls.
pub struct Surface {
    pub id: String,               // "robot" | "browser" | "cloud" | ...
    providers: BTreeMap<String, Provider>,   // host import name -> provider
}

impl Surface {
    /// The capabilities this surface can back — generalizes `kernel_caps`.
    pub fn offered(&self) -> BTreeSet<String> {
        self.providers.values().map(|p| p.cap).collect()
    }
    /// Bind every provider into the Linker. Each closure still calls
    /// `gate(c.data(), provider.cap, provider.name)?` first, exactly as the
    /// seven built-ins do today — the gate is never bypassed.
    pub fn install(&self, linker: &mut Linker<HostCtx>) -> Result<()> { /* ... */ }
}

impl Provider {
    fn bind(&self, linker: &mut Linker<HostCtx>) -> Result<bool> { /* ... */ }
}
```

The base `aiueos:host` functions in `src/host.rs` install from the provider
registry. The robot surface's implemented providers are
(`log`→`log/write`, `clock`→`clock/monotonic`, `random`→`random/bytes`,
`publish`→`topic/publish`, `poll`/`count`/`take`→`topic/subscribe`).
Browser and cloud providers install from the same path.

### How `kernel_caps` generalizes to the offered set

Today `Policy::granted_to` unions `kernel_caps` (fixed) with per-component grants.
Per-surface, the kernel primitives a deployment can hand out are exactly
**`surface.offered()`** — the caps for which it has a provider. So:

```rust
fn granted_to(&self, m: &Manifest, surface: &Surface) -> BTreeSet<String> {
    let mut s: BTreeSet<String> = self.kernel_caps             // policy-declared floor
        .intersection(&surface.offered())                      // gated by what this surface backs
        .cloned().collect();
    if let Some(extra) = self.grants.get(&m.id) { s.extend(extra.iter().cloned()); }
    s
}
```

The crucial inversion: an import that resolves to a kernel cap is granted **only
if this surface offers a provider for it.** A robot manifest that imports
`dom/render` does not silently get a no-op — it is an `unresolved-capability`
denial, because `Surface::robot().offered()` has no `dom/render`. This is the
"the host refuses to provide what that surface shouldn't" rule, enforced at the
same `verify_component` checkpoint that already exists, with **no new violation
kind needed** — it reuses `UnresolvedCapability`, which is the honest meaning:
on this surface, that capability is unprovided.

A component proven safe on one surface therefore *carries its manifest
unchanged* to the next: its imports are its portable contract. The next surface
either offers providers for all of them (it runs, identically gated) or denies it
up front (a missing provider, surfaced loudly), never a silent degradation.

### Declaring / requiring a target surface in the manifest

A component may pin the surface(s) it is written for, consistent with the existing
fail-loud EDN schema (`:aiueos/imports`, `:aiueos/effects`, …):

```edn
{:aiueos/component :app/dashboard
 :aiueos/trust :verified
 :aiueos/surface #{:browser :client}   ; surfaces this component is built for
 :aiueos/imports [:dom/render :net/fetch :log/write]}
```

`:aiueos/surface` is a set of surface keywords. When present, the broker checks
the **active surface's id is a member** before launch; a mismatch is a loud
`surface-mismatch` denial (a new `ViolationKind`, parallel to `ForbiddenEffect`),
not a silent skip — running a browser-targeted component on a robot is a
configuration error worth failing on, even if (by coincidence) the imports happen
to resolve. Omitting `:aiueos/surface` keeps today's behavior: portable to any
surface whose offered set covers the imports. The policy may also name the active
surface so a single document is self-describing:

```edn
{:aiueos/policy true
 :aiueos/surface :cloud                 ; the surface this deployment runs
 :aiueos/kernel-caps [:storage/kv :net/fetch]}
```

Both keys are added to the closed `POLICY_KEYS` / manifest key allow-lists so a
typo like `:aiueos/surfce` is a hard `Schema` error, matching ADR-0003's
fail-loud stance. Surface ids themselves are a closed set the broker knows;
`Surface::parse` rejects an unknown id rather than constructing an empty surface.

### Concrete example surfaces

| surface   | offered capabilities (providers)                                  | backing impl                          |
|-----------|-------------------------------------------------------------------|---------------------------------------|
| `robot`   | `topic/publish`, `topic/subscribe`, `clock/monotonic`, `log/write`, `random/bytes`, `pci/config`, `dma/map`, `irq/subscribe`, `mmio/map` | the in-process bus + device brokers — **exists today** |
| `browser` | `dom/render`, `dom/event`, `net/fetch`, `log/write`, `clock/monotonic` | DOM/fetch shims over the host page    |
| `cloud`   | `storage/kv`, `net/fetch`, `log/write`, `clock/monotonic`, `random/bytes` | a KV store broker + a socket/HTTP broker |
| `edge`    | `topic/*`, `storage/kv`, `clock/monotonic`, `log/write`           | a constrained subset of robot ∪ cloud |
| `client`  | `dom/render`, `storage/kv`, `log/write`                           | local UI + local persistence          |
| `computer-virtual` | `display/frame`, `pointer/move`, `pointer/click`, `keyboard/key`, `keyboard/type`, `net/fetch`, `log/write`, `clock/monotonic` | **isolated container (Xvfb/headless Chromium) — exists today** (ADR-0007). The capability-isolated computer-use surface; **no host-HID provider** is offered. |
| `computer-vm` | same offered set as `computer-virtual` | a microVM (virtio-gpu) for GPU-accurate runs — future (ADR-0007) |
| `computer-host` | `computer-virtual` ∪ `pointer/host`, `keyboard/host`, `display/host` | the host WindowServer — the **signed, opt-in** escape hatch; host-HID providers stay unbound by default (ADR-0007) |

Each new provider is one `func_wrap` closure that calls `gate()` first — the
robot's seven are the template. A surface that lacks a provider for a cap simply
doesn't bind it; the gate plus the offered-set intersection do the rest. The
device-broker caps (`pci/config`, …) stay robot-only and keep the IOMMU/DMA rule
from ADR-0001 — that rule is a property of the providers a surface offers, not of
the surface mechanism.

### Why a registry, not a trait per surface

A `Surface` is **data** (a map of providers), not a `trait` each deployment
implements, for the same reason ADR-0003 chose a flat signer registry over a cert
chain: it is the smallest thing that separates *offered* from *gated*. Providers
compose (`Surface::robot().union(&Surface::cloud())` for an edge gateway), can be
audited as a flat list (`aiueos surface inspect <id>` prints the offered set), and
add zero coupling to the core graph/policy engine, which keeps building under
`--no-default-features`.

## Increments

1. **Data model + this ADR** — `Surface` / `Provider` types; refactor the
   implemented `src/host.rs` `aiueos:host` bindings into `Provider::bind` /
   `Surface::install`. Behavior identical to today for existing providers.
2. **Offered-set gating** — `granted_to` intersects `kernel_caps` with
   `surface.offered()`; an import resolving to a cap the surface doesn't offer is
   `unresolved-capability`. Audited with the active surface id.
3. **Manifest/policy surface keyword** — parse `:aiueos/surface` (manifest set +
   policy scalar); add to the closed key allow-lists; `surface-mismatch`
   violation; `Surface::parse` rejects unknown ids.
4. **A second real surface** — `Surface::cloud()` with `storage/kv` + `net/fetch`
   brokers (host-side, capability-gated), proving a non-robot surface end to end
   and that a manifest moves between surfaces unchanged.
5. **Tooling** — `aiueos surface inspect <id>` (offered set/providers),
   `aiueos up --surface <id>`, and audit lines carrying `:aiueos/surface`.

## Consequences

- Realizes the SECURITY.md "Per-surface notes" promise in code: capabilities
  *offered* differ per surface, the deny-by-default gate is identical, and a
  component carries its manifest's requirements across surfaces with the host
  refusing to provide what a surface shouldn't.
- The capability model is untouched. The gate, the conferred set, audit, the
  IOMMU rule and ADR-0003 signing all work unchanged; a surface only narrows
  *which* kernel caps are backed and supplies the closures behind them.
- A missing provider is a **loud denial, never a no-op.** This is the deliberate
  choice: a component that silently no-ops `net/fetch` on a robot is a worse
  failure than one that refuses to launch.
- New surfaces are additive — one `func_wrap` + one entry in `offered()` per
  capability — so browser/cloud/edge land incrementally without a flag day.
- **Future work.** Cross-machine / cross-surface messaging (the bus stays
  in-process per ADR-0002); per-surface *resource* policy (fuel/quota differing by
  surface); capability *attenuation across* surfaces (a `net/fetch` allow-list
  scoped to a host set, the surface analogue of per-topic `TopicAccess`);
  signing a manifest *to* a surface so provenance includes the intended target;
  and the real browser/cloud brokers themselves, whose host-side code (sockets,
  DOM bindings) becomes TCB and must be audited as such, exactly like the
  Phase-7 MMIO/DMA adapters.
