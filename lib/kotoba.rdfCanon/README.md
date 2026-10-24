# kotoba-lang/rdf-canon

Deterministic canonical string and SHA-256 helpers for RDF EDN quads —
portable `.cljc`, JVM and ClojureScript.

This is a pragmatic substrate, not a full URDNA2015 implementation. Blank-node
canonicalization beyond stable provided IDs is intentionally left for a later
processor layer.

```clojure
(require '[rdf-canon.core :as canon])

(canon/canonical quads)  ; => the sorted, newline-terminated N-Quads string
(canon/digest quads)     ; => lowercase hex SHA-256 of that string
```

## Portability

`java.security.MessageDigest` was replaced by
[`kotoba-lang/org-nist-sha2`](https://github.com/kotoba-lang/org-nist-sha2)
on 2026-08-18, and `.getBytes` by `kotoba.bytes/utf8-encode`. Both are one
implementation on both platforms rather than a `#?(:cljs …)` reaching for
`node:crypto`, which would work under nbb and not in a browser and would
leave two implementations of an identity that can disagree.

**Terms are lexical forms, not values.** `term` refuses a component that is
not already a string. ClojureScript has no distinct floating-point type — its
reader turns `1.0` into `1` before this library sees anything — so `(str v)`
on a whole-numbered double gives `"1.0"` on the JVM and `"1"` under
ClojureScript, and no reader conditional can recover the difference. A
canonicalizer whose output depends on which runtime read the EDN is not a
canonicalizer, so this one asks the caller for the lexical form RDF wants
anyway: `"1.0"^^xsd:double` and `"1"^^xsd:double` are different literals and
only the caller knows which it holds.

**The digests did not move.** `digest` is an identity — callers store it and
address content by it — so the suite pins the exact hex the JVM produced
before the swap, checked against `shasum -a 256`, including a Japanese
literal under a non-ASCII IRI where a wrong UTF-8 encoding would show.

## Test

```bash
kbb -M:test                                    # JVM
kbb --backend sci --classpath src:test:<deps> test/run_portable.cljk   # ClojureScript
```

The nbb run needs `org-nist-sha2/src` and `bytes/src` on the classpath;
`kbb -Spath` prints where `deps.edn` resolved them.

## Mutation testing

```bash
kbb --backend sci tools/check-mutations.cljk   # every :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # apply each, report what reddened
```

`tools/mutations.edn` states its scope: the portability invariants, not the
whole library.
