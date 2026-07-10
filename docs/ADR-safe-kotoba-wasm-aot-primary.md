# ADR — safe Kotoba → WASM AOT is the primary language path

- **Status**: Accepted (partial land)
- **Date**: 2026-07-10
- **Related**: `ADR-kotoba-wasm-clj-execution.md`, ADR-2607100100 (runtime priority),
  ADR-2607062330 (kototama tender)

## Context

Users and agents were told “kotoba is JVM Clojure.” That confuses:

1. **Guest language** — safe Kotoba (Clojure/EDN subset + capability gates)
2. **Bootstrap host** — today’s CLI/compiler process (JVM Clojure + Chicory)

The intended product story is always:

```text
.kotoba  →  kotoba wasm emit / safe-build  →  .wasm  →  tender / browser host
```

not “run on the JVM as Clojure.”

## Decision

1. **Product split (ADR-2607022400):**  
   - **kotoba** = language (check + `wasm emit` / `safe-build` / `build`)  
   - **kototama** = `.kotoba` WASM **runtime** (canonical `run guest.wasm`)
2. **Primary language path** is safe Kotoba grammar → **WASM AOT** (`wasm emit`
   and aliases). Guests are not “JVM Clojure programs.”
3. **Canonical execute** is **kototama**, not `kotoba wasm run`. Language-repo
   Chicory (`wasm run`, `run --engine wasm`) is **compat bootstrap only**.
4. **`kotoba run` without `--engine wasm`** remains a JVM tree-walk interpreter
   for debug / scripts without a package-lock — not the language story.
5. **Portable AOT artifact** is `:kotoba.wasm/bytes` (unsigned 0–255 vector)
   plus golden digests under `test/kotoba/wasm/goldens/`. Platform packing
   (`:kotoba.wasm/binary`) is a host edge concern.
6. **JVM in kotoba** is bootstrap for the compiler CLI, not the guest runtime.
   Follow-ups: full `.cljc` emit peel; self-host admission guest run on kototama.

## Consequences

- Docs and `lang/cli.edn` describe `wasm emit` as the language surface.
- Execute docs point at kototama; language README demotes `wasm run`.
- Golden digests lock byte-identity of AOT modules across refactors.
