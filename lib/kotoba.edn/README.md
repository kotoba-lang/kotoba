# kotoba-lang/edn

Bounded EDN and canonical structured-document codecs for Kotoba applications.

## Surfaces

- `kotoba.lang.edn` (`.cljc`) provides single-form `read-string` and
  `write-string` for immediate replacement of direct `clojure.edn` and
  `cljs.reader` dependencies. Tagged literals, reader discard, and reader eval
  are forbidden. Bytes, depth, tokens, nodes, and strings are bounded.
- `kotoba.lang.canonical-document` (`.kotoba`) provides sovereign,
  zero-capability canonical storage and textual EDN codecs for the compiler's
  bounded `:document` value.

`document-read` / `document-print` remain the canonical hexadecimal storage
format. `document-edn-read` / `document-edn-print` own textual syntax for nil,
booleans, i64/f64, strings, keywords, symbols, vectors, lists, sets, and maps
with arbitrary bounded document keys. Tags, discard forms, duplicate map/set
members, and reader eval fail closed. The completed compatibility profile is recorded in
`migration/bounded-edn-v1.edn`.

## Use

```clojure
(require '[kotoba.lang.edn :as edn])

(edn/read-string "{:goal \"migrate\"}")
(edn/write-string {:goal "migrate"})
```

## Verify

```sh
kbb -M:test
npm install
npm test
kbb -M:lint
```
