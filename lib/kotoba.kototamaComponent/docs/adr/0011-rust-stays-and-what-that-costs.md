# ADR 0011: the Rust host stays, and the bill it leaves

**Status**: accepted · **Date**: 2026-08-11

## Context

ADR-2607072000 (kotoba-lang, workspace-wide) says implementations that would
reach for Rust are written in `.cljc`. Four repositories were assessed against
it. Three were ported: `murakumo-studio` lost its Tauri crate outright,
`common-crawl` and `app-browser` moved their policy across and left transport
behind.

This repository was assessed last and is the one that does not move.

## Decision

**`native/component-host` stays in Rust.** Not as an exception grudgingly
granted, but because porting it would delete the thing it is for.

ADR 0010 qualifies **two independent implementations of the same closed host
contract** — the Rust/Wasmtime micro-TCB and pinned `jco` under Node — and
argues host correctness from their agreement. Rewriting one of them in
ClojureScript, which is what a port here would mean, does not produce a third
implementation; it replaces one of the two with something sharing a runtime
and an author with the rest of the stack. The qualification argument is worth
more than the uniformity.

The boundary also already holds. `kototama` owns the tender contracts, the
admission envelope, the provider boundary and aiueos grant translation; this
repository owns a process that executes an ALREADY ADMITTED Component over a
narrow JSON protocol. In 3,720 lines of Rust there is exactly one function
shaped like a decision, `allowed_binding`, and even that is a binding table
rather than a judgement.

## What the assessment found instead

`allowed_binding` and kototama's `component-import->kototama-import` are both
described as CLOSED sets of the aiueos imports a Component may have. Measured
2026-08-11 they overlap on three names and disagree on eleven:

| | |
|---|---|
| both | `clock-now`, `http-post`, `log-append` |
| resident host only | `llm-generate`, `storage-transact` |
| kototama only | `hash-sha256`, `http-get-stream`, `identity-sign`, `identity-verify`, `log-read`, `object-compare-and-set-ref`, `object-get-stream`, `object-put-block` |

A narrower resident set is explained — the README says it links only the HTTP,
storage and LLM imports for the cloud-itonami effect chain. What is not
explained is the other direction: `aiueos-llm-generate` and
`aiueos-storage-transact` are admitted by the resident host and appear nowhere
in kototama's source. And a Component importing `aiueos-identity-sign` is
translated upstream and refused here.

**Whether that is intended is written down nowhere**, which is the actual
defect. Two closed sets that gate the same thing, in two languages, with no
stated relationship, cannot be told apart from drift.

`test/tender/import_table_drift_test.cljk` pins the relationship as it stands.
It reads `allowed_binding` out of the Rust source rather than mirroring it —
a mirror would be a third copy and would drift from both — and asserts the
three groups above. It does not assert that the sets agree, because deciding
that is the owner's call. Adding one name to the Rust table turns it red.

## Consequences

- The `.cljc`-only rule now has one documented, reasoned exception in this
  workspace, and the reason is qualification rather than convenience.
- The import-set divergence is visible and change-detecting instead of latent.
  Someone still has to decide it: either kototama's map grows the two LLM and
  storage names, or the resident host stops admitting them.
- If `jco` is ever dropped as the second implementation, this ADR's premise
  goes with it and the Rust should be reassessed.
