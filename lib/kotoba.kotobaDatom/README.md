# kotoba-datom

`kotoba.datom` — the **kotoba Datom-log codec**: a content-addressed,
append-only commit-DAG. Each transaction is hashed (sha-256 over its canonical
datoms + the previous tx's CID → a commit-DAG), so tampering with any earlier
transaction breaks every later CID. CIDs are byte-compatible with the Python
implementation (canonical JSON: sorted keys, compact separators,
`ensure_ascii=false`), so a log written by either verifies under the other.

Zero-dependency, portable `.cljc`. The only host seam is sha-256
(`kotoba.datom/*sha256-hex*`, bound by default on JVM/babashka via
`MessageDigest`; rebind on other hosts). The file-backed append/read/verify edge
is `#?(:clj)` only.

ADRs: ADR-2606112300 + ADR-2605312345 (the kotoba Datom log as first-class
canonical state).

> **Not** `kotoba-lang/datom` (namespace `datom.core`) — that is a separate EAVT
> *data-representation* library for the CAE / vehicle-design stack, with a
> different API (`entity`/`eavt`/`log`). This repo is the content-addressed
> *log codec* (`canonical-json`, `add`, `tx-cid`, `make-tx`, `append-tx!`,
> `read-log`, `verify-chain`).

## Origin

Extracted verbatim (byte-identical, ns unchanged) from the monorepo path
`etzhayyim/root/20-actors/kotodama/src/kotoba/datom.cljk` as part of the
`20-actors` monorepo→multirepo (west) split. Consumers that used to reach it via
a relative `:paths`/`:source-paths` into `20-actors/kotodama/src` repoint to this
repo with no source edits (the namespace stays `kotoba.datom`).

## Use

```clojure
;; deps.edn
io.github.kotoba-lang/kotoba-datom {:git/url "https://github.com/kotoba-lang/kotoba-datom" :git/sha "<sha>"}
;; or, in this monorepo, a relative :paths entry to orgs/kotoba-lang/kotoba-datom/src
```

```clojure
(require '[kotoba.datom :as kd])

(def d [(kd/add "entity-1" ":name/full" "Ada")])
(kd/tx-cid d)                      ;; => "b<sha256hex>" (content id)
(def tx (kd/make-tx d {:tx-id "t1" :as-of 1 :prev-cid ""}))
;; JVM edge:
(kd/append-tx! tx "log.edn")       ;; append-only
(kd/verify-chain "log.edn")        ;; => {:ok true :length 1 :broken-at -1}
```

## Test / lint

```bash
kbb -M:test    # cognitect test-runner (kotoba.datom-test)
kbb -M:lint    # clj-kondo (fail on error)
```
