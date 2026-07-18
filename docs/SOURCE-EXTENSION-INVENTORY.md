# Source extension inventory

Kotoba-only executable source uses `.kotoba`. `.cljc` is retained only when
one namespace is intentionally shared across Clojure, ClojureScript, and
Kotoba targets.

## Canonical Kotoba source

- `src/*.kotoba`: capability-checked programs compiled by the Kotoba/Kototama
  compiler. `src/demo.kotoba` replaces the former production `src/demo.cljc`.
- Web builds read `.kotoba` with the `:cljs` target.

## Intentionally shared CLJC

- `src/kotoba/{kami_host,sensing_host}.cljc`: native WebAssembly JS host and
  existing CLJ host wiring share one pure implementation.
- `src/kotoba/{did_adapter,git_adapter,rad_adapter}.cljc`: CLJC host adapters;
  they are not guest programs and use host protocols/dependencies outside the
  Kotoba Wasm subset.
- `docs/eda/*.cljc`: shared CLJ documentation build and browser application
  model.
- `test/fixtures/source/demo_shared.cljc`: conformance evidence for all three
  reader targets; it is not production source.

Do not rename these shared namespaces mechanically. A `.cljc` file moves to
`.kotoba` when it stops serving its CLJ/CLJS consumers and passes Kotoba check,
Wasm emission, and (when applicable) Web compilation.
