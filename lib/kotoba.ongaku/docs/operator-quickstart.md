# Operator quickstart

From a fresh checkout to one BGM plan, one policy refusal, and one holdings
answer, with no JVM. Every step below was run as written on 2026-09-25
(kbb, Node 26, macOS).

## 0. Prerequisites

- `kbb` on `PATH` (the script host, engine `kotoba-lang/org-babashka-nbb`).
- Network access on the first run: kbb resolves the git deps named in
  `nbb.edn` (`kotoba-lang/edn`, `kotoba-lang/text`, `kotoba-lang/test`) into
  `.nbb/.cache/` (gitignored).

## 1. Run the suite

```bash
git clone https://github.com/kotoba-lang/ongaku.git && cd ongaku
kbb --backend sci --classpath src:test test/run_portable.cljk
```

Expected tail (the count grows as tests are added; failures and errors must
be 0):

```
Ran 30 tests containing 111 assertions.
0 failures, 0 errors.
```

## 2. Bring a catalog

The library ships no catalog — production catalogs are business data and live
in their private repos. Write one asset to `catalog.edn` in the checkout root:

```clojure
{:ongaku.catalog/version 1
 :ongaku.catalog/assets
 [{:asset/id "calm-01" :asset/title "Calm 01"
   :asset/local-path "assets/calm-01.mp3"
   :audio/duration-sec 180.0
   :music/moods #{:calm} :music/channels #{"demo"}
   :credit/text "BGM: Calm 01 / example"
   :license/id :license/dova-syndrome-license
   :policy/render-only? true
   :policy/raw-public-access? false
   :policy/ai-training? false
   :policy/content-id-registration? false}]}
```

## 3. Pick, refuse, explain

Save as `quickstart.cljk` **in the checkout root** and run it from there:

```clojure
(require '["fs" :as fs]
         '[kotoba.lang.edn :as edn]
         '[ongaku.compose :as compose]
         '[ongaku.holdings :as holdings])

(def cat (edn/read-string (fs/readFileSync "catalog.edn" "utf8")))

;; a channel the asset allows -> a render plan
(prn (compose/compose cat {:channel-id "demo" :mood :calm :duration/sec 120}))

;; a channel the asset does not list -> refused, never a fallback asset
(prn (try (compose/compose cat {:channel-id "other" :mood :calm})
          (catch :default e [:refused (ex-message e) (ex-data e)])))

;; what may be passed on to a client -> nothing, with the reason
(prn (holdings/explain (first (:ongaku.catalog/assets cat))))
```

```bash
kbb quickstart.cljk
```

Expected (abridged):

```
{:ongaku/plan :plan/background-music, :asset/id "calm-01", :asset/path "assets/calm-01.mp3", :credit/text "BGM: Calm 01 / example", :policy/raw-public-access? false, ...}
[:refused "no usable BGM asset" #:ongaku{:request {:usage-context :youtube-background, :mood :calm, :channel-id "other"}}]
{:license/id :license/dova-syndrome-license, :grantable [], :exclusive-possible? false, :checked "2026-06-29", ...}
```

The plan carries a local path and credit text, never a public URL: mux the
file into the render and publish the credit.

## Pitfalls hit while writing this

- **The script must sit in the checkout.** kbb finds `nbb.edn` next to the
  script, not in the current directory. A script elsewhere fails with
  `Could not find namespace: kotoba.lang.edn` even when run from the checkout.
- **Passing `--classpath` does not add the `nbb.edn` deps.** Step 1 works with
  `--classpath src:test` only because the suite never loads a catalog from disk.
- **No `slurp` on this host** (`Unable to resolve symbol: slurp`). Read with
  Node's `fs/readFileSync`, as above. `ongaku.catalog/load-catalog` throws on
  this host by design (it reads a JVM classpath resource). Pass the catalog map
  to the 2-arity functions.
