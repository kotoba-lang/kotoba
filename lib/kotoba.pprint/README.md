# kotoba-lang/pprint — `kotoba.pprint`

The kotoba stdlib's pretty printer (same family as `kotoba.test`,
`kotoba.json`, `kotoba.io`): ClojureScript's `cljs.pprint` pretty
printer, transcribed into portable `.cljk` so that `clojure.pprint/pprint`
call sites can move to a kotoba namespace **without a single output byte
changing**.

```clojure
(require '[kotoba.pprint :as pp])
(pp/pprint {:a 1 :b [1 2 3]})      ; prints exactly what clojure.pprint/pprint prints on kbb
(pp/pprint-str x)                  ; the same text as a string, trailing newline included
(binding [pp/*print-right-margin* 100] (pp/pprint x))
```

## Why a transcription and not a new printer

The workspace's `.cljk` sources run on kbb (SCI on Node), where
`clojure.pprint` is the host's `cljs.pprint` `simple-dispatch`. Callers write
that output into EDN files, compare it in tests and diff it in gates, so the
only acceptable replacement prints the same bytes -- quirks included (a blank
left before some newlines by the final flush, no `#:ns{}` map lifting, printer
bindings ignored). `test/kotoba/pprint_test.cljk` compares against
`clojure.pprint` itself over a generated corpus, in both directions.

## Boundary with `kotoba-lang/fmt`

`kotoba.lang.fmt` (`format-str`, `pprint`, `pprint-str`) is a *different*
printer: a canonical EDN formatter with its own indentation rule and an
`opts` map. Use it to canonicalize EDN text. Use this repository where the
output must stay what `clojure.pprint` printed. This repository has no
runtime dependencies on purpose (see `deps.edn`).

`kotoba-lang/fmt-pprint` (`kotoba.fmt.pprint`) is one definition of that
`kotoba.lang.fmt` family, not this printer.

The namespace is `kotoba.pprint` (owner instruction 2026-09-24), matching the
rest of the stdlib; it is on kbb's implicit stdlib classpath, and the fleet
codemod `scripts/migrate-clojure-pprint-to-kotoba-pprint.cljk` (com-junkawasaki/root)
moves `clojure.pprint` call sites to it (ADR-2609241200).

## Tests

```
kbb -M:test
```

## License

Eclipse Public License 1.0 (the license of the ClojureScript source it is
transcribed from).
