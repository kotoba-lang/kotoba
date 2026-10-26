# ADR-0149 — Link-time capability enforcement in the JVM/Chicory execution path

- Status: accepted
- Date: 2026-07-13

## Context

ADR-2607022900 moved this repo's execution layer from a retired Rust/wasmtime
adapter to a pure-JVM one (`aiueos.execute`, `com.dylibso.chicory`). SECURITY.md
defense layer 2 claims: "the `aiueos:host` ABI checks the conferred set on
every host call." A security audit (2026-07-13) found this did not hold for
the JVM/Chicory adapter: `aiueos.execute/instantiate` linked ALL 11 kernel-cap
host imports (7 real: `log_write`/`clock_monotonic`/`random_bytes`/
`topic_publish`/`topic_poll`/`topic_take`/`topic_count`, plus 4 device-access
stubs: `pci_config`/`dma_map`/`irq_subscribe`/`mmio_map`) for EVERY component,
unconditionally, with no parameter representing which capabilities the broker
had actually decided to grant. Only two things were real per-call gates:
ADR-0006 quota counting (`count-and-check!`) and the per-topic-id allow-list
(`assert-topic-allowed!`). Capability POSSESSION itself was never checked at
the host-import boundary — a component granted (and importing) only
`:topic/publish` could still reach `random_bytes`, `mmio_map`, or any other
kernel-cap host function, as long as its wasm binary happened to import it,
regardless of what its manifest declared or the broker decided.

Verified empirically (not just by code reading): stashed the fix, ran a
component whose manifest declared/was granted only `:topic/publish` against a
hand-built wasm module whose SOLE import was `random_bytes`, and confirmed the
pre-fix code linked and executed it successfully.

## Decision

`aiueos.execute/instantiate` now takes the component's actually-granted
capability set (`aiueos.broker/verify-one`'s `:aiueos/capabilities`, computed
by `aiueos.policy/verify-component`) as an explicit parameter, and links a
host function only when its capability is in that set
(`host-field->capability`, `host-function-granted?`). A capability outside the
granted set is simply never added to the `ImportValues` Chicory links
against — if the wasm binary imports it anyway, `Instance.Builder/build`
throws `UnlinkableException` and the component never even starts running (not
just "traps" mid-execution; `main` never gets called at all). `run-if-granted`
catches this alongside the existing quota/fuel/topic-forbidden aborts and
surfaces it as `:aiueos.execute/capability-unlinked {:message "..."}` instead
of propagating an uncaught JVM exception.

This is the SAME "unresolved import fails to link" mechanism
`kotoba-lang/kototama` already relies on for its own capability gating — a
proven-sound pattern in this org, not a novel design, and it mirrors the
original wasmtime-`Linker`-style gating ADR-0002 assumed before the JVM port.

It is coarser than a true per-call runtime check: the gate fires once, at
module-link time, for the whole set of declared imports, rather than
re-checking on every individual invocation the way quota counting and the
topic-id allow-list do. This is accepted as functionally equivalent for Wasm:
once a module is instantiated, it can only ever call functions it
successfully imported — there is no mechanism for a linked-in host function to
become "callable sometimes, not others" within one instantiation. An
ungranted capability that was never linked can never be called on any code
path, so the coarser link-time gate provides the same security property the
finer-grained per-call gate would, for this specific kind of check (unlike
quota/topic-id, which are inherently per-call state, not a fixed yes/no over
the whole run).

`has_capability` (an ABI stub that has always returned `1` unconditionally)
was deliberately left OUT of scope for this fix — it stays a permissive stub,
always linked regardless of the granted set. Its own docstring justified the
permissive stub because "the static capability gate already ran at
compile/broker-decision time"; with this fix that reasoning is strictly
stronger, not weaker: the real per-capability host functions are now gated at
link time regardless of what `has_capability` reports, so a false "yes" from
it can no longer let anything ungranted actually execute (the ungranted
import simply fails to link, independent of whatever `has_capability` said).
Making `has_capability` consult the granted set for real would require
inventing a numeric capability-id encoding for its single `i32` argument that
no ADR or caller in this codebase defines today — deferred as a follow-up
rather than guessed at here.

## Consequences

- `aiueos.execute/instantiate`'s signature gained a `granted-caps` parameter;
  its only caller (`aiueos.execute/run-if-granted`) threads
  `(:aiueos/capabilities decision)` through automatically, so `aiueos.execute/
  execute`/`execute-admission` (and therefore `aiueos.launcher/run-command`,
  `admit-command`, and `up-command`, all of which call those) are fixed for
  free — no launcher-level plumbing changes were needed beyond recognizing the
  new `:aiueos.execute/capability-unlinked` result key in `up-command`'s
  boot-continuation check and CLI output formatting.
- A new failure shape, `:aiueos.execute/capability-unlinked
  {:message "..."}`, joins `:aiueos.execute/quota-exceeded`/`fuel-exceeded`/
  `topic-forbidden` as a `:failed` run-receipt outcome distinct from a
  `:deny`ed policy decision — the capability DECISION can still be `:grant`
  (the manifest's declared imports all resolved) while the actual wasm binary
  fails to link because it imports something outside that decision's granted
  set. This is intentional: it is a different failure than "the broker denied
  this component" and callers/printers should be able to tell them apart.
- No change to `aiueos.broker`/`aiueos.policy` — the fix consumes their
  existing `:aiueos/capabilities` output, it does not change how that set is
  computed.

## Related, adjacent fixes (same PR)

Two more gaps found by the same audit were fixed alongside this one, best
effort:

- **Artifact integrity** (`aiueos.manifest/verify-wasm-integrity` +
  `aiueos.signing/sha256-hex`): `:aiueos/wasm-sha256` was previously used only
  as an input string to `signed-message` (the signing construction), never
  recomputed from or compared against the actual wasm bytes that get
  executed — ADR-0003's "the broker rejects the component if the loaded bytes
  don't match" claim had no code performing that comparison anywhere. `
  aiueos.execute/execute`/`execute-admission` now recompute SHA-256 of the
  actually-loaded `wasm-bytes` and reject on mismatch, fail-closed, before
  `aiueos.broker/verify-one` ever runs.
- **DMA/IOMMU gating** (`aiueos.policy/verify-component`'s `dma?` check):
  previously keyed solely on the self-declared, unenforced `:aiueos/effects
  #{:dma}` field, with no structural link to whether `:aiueos/imports`
  actually requested a DMA-family capability (`:dma/map`/`:pci/config`/
  `:mmio/map`/`:irq/subscribe`) — a manifest could import one of those while
  simply omitting `:aiueos/effects #{:dma}`, skipping the IOMMU gate entirely.
  `dma?` now also fires when `:aiueos/imports` intersects the DMA-family
  capability ids, treating `:aiueos/effects` as an additional declaration that
  must be consistent with imports rather than the sole trigger.

A fourth finding — policy grants keyed by a bare, unauthenticated
`:aiueos/component` id with no binding to signer identity even under
`:aiueos.policy/require-signed` (the signer registry is flat: any registered
signer can sign for any component id) — was NOT fixed here; it needed an
owner decision on the binding scheme, not a guess. That decision was made
and implemented separately: see **ADR-0012 — Binding `:aiueos/component`
ids to authorized signers**.
