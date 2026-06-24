(ns kotoba.gitoffice-node
  "CLJS interop: drive the wasm KotobaNode with the GitOffice converters.

   The portable logic lives in kotoba.gitoffice / gitdiff / gitmerge / gitpolicy
   (pure .cljc, babashka-tested). This namespace is the thin transact / commit /
   datomicQ glue — it mirrors kotoba.office exactly (same v_edn wire codec), so a
   normalized doc/book and its PR metadata land on the same local kotoba node the
   office editor already uses.

   Diff/merge across two commits: pull the head node-set with `doc-datoms`/`book-datoms`
   and the base node-set from a hydrated snapshot (kotoba.node/hydrate-and-query-verified!),
   then call the pure gitdiff/gitmerge fns. As-of wiring is the caller's choice of
   snapshot; this ns does not hide it."
  (:require [kotoba.gitoffice :as g]
            [kotoba.gitdiff :as d]
            [kotoba.gitmerge :as m]
            [kotoba.gitpolicy :as p]
            [kotoba.node :as node]
            [clojure.string :as str]))

;; ---------------------------------------------------------------------------
;; v_edn codec over the GitOffice schema (mirrors kotoba.office encode/decode)
;; ---------------------------------------------------------------------------

(def schema (merge g/schema p/schema))
(defn- value-type [a] (get-in schema [a :db/valueType] :string))

(defn- encode [a v]
  (case (value-type a)
    (:string :ref :did)       (js/JSON.stringify (str v))
    (:keyword :long :boolean) (str v)
    (js/JSON.stringify (str v))))

(defn- decode [a s]
  (case (value-type a)
    (:string :ref :did) s
    :keyword            (keyword s)
    :long               (js/parseInt s 10)
    :boolean            (= "true" s)
    s))

(defn- a->kw [a] (keyword (cond-> a (str/starts-with? a ":") (subs 1))))

;; ---------------------------------------------------------------------------
;; write: [e a v] datoms -> local transact + commit
;; ---------------------------------------------------------------------------

(defn tx-json
  "[[e a v]...] -> JSON string for KotobaNode.transact (same shape as kotoba.office)."
  [datoms]
  (js/JSON.stringify
   (clj->js (mapv (fn [[e a v]] {:e e :a (str a) :v_edn (encode a v)}) datoms))))

(defn write-datoms!
  "Transact datoms locally and commit. Returns the root CID."
  [^js node datoms]
  (.transact node (tx-json datoms))
  (.commit node))

(defn store-doc!
  "Normalize a Google-Docs-shaped body (vector of {:elementId :kind :headingLevel? :text})
   into :block/* datoms under doc-id and commit. Returns root CID."
  [^js node doc-id body]
  (write-datoms! node (g/body->blocks doc-id body)))

(defn store-book!
  "Normalize a Sheets gridJson ({sheet [[cell]]}) into sparse :cell/* datoms and commit."
  [^js node book-id grid]
  (write-datoms! node (g/grid->cells book-id grid)))

;; ---------------------------------------------------------------------------
;; read: datomicQ -> typed [e a v] datoms (mirrors kotoba.office all-rows)
;; ---------------------------------------------------------------------------

(defn- all-rows
  "All [e a-str scalar] triples from the local engine (decoded scalars)."
  [^js node]
  (js->clj (js/JSON.parse (.datomicQ node "[:find ?e ?a ?v :where [?e ?a ?v]]" "[]"))))

(defn- typed-datoms
  "all-rows -> [e a-kw typed-v] keeping only rows whose entity passes `keep-e?`."
  [^js node keep-e?]
  (->> (all-rows node)
       (keep (fn [[e a s]]
               (when (keep-e? e a)
                 (let [ak (a->kw a)] [e ak (decode ak s)]))))
       vec))

(defn doc-datoms
  "Current :block/* (+ doc) datoms for one doc — feed to gitdiff/gitmerge."
  [^js node doc-id]
  (let [block? (->> (all-rows node)
                    (keep (fn [[e a s]] (when (and (= a ":block/parent") (= s doc-id)) e)))
                    set)]
    (typed-datoms node (fn [e _a] (or (block? e) (= e doc-id))))))

(defn book-datoms
  "Current :cell/* datoms for one book."
  [^js node book-id]
  (let [cell? (->> (all-rows node)
                   (keep (fn [[e a s]] (when (and (= a ":cell/book") (= s book-id)) e)))
                   set)]
    (typed-datoms node (fn [e _a] (cell? e)))))

(defn pr-datoms
  "Every datom relevant to merge-gating a PR (pr/review/policy/ci/issue/ref)."
  [^js node]
  (typed-datoms node
                (fn [_e a] (some #(str/starts-with? a %)
                                 [":pr/" ":review/" ":policy/" ":ci/" ":issue/" ":ref/"]))))

;; ---------------------------------------------------------------------------
;; convenience: diff / merge / gate against the live node
;; ---------------------------------------------------------------------------

(defn diff-doc
  "Semantic diff of one doc between two datom snapshots (base, head)."
  [base-datoms head-datoms doc-id]
  (d/diff-doc base-datoms head-datoms doc-id))

(defn merge-doc
  "3-way merge of one doc across three datom snapshots."
  [base-datoms ours-datoms theirs-datoms doc-id]
  (m/merge-doc base-datoms ours-datoms theirs-datoms doc-id))

(defn evaluate-merge!
  "Pull PR-related datoms from the live node and decide mergeability of pr-id."
  [^js node pr-id]
  (p/evaluate-merge (pr-datoms node) pr-id))

;; ---------------------------------------------------------------------------
;; JS-facing exports (wrap clj data -> js for non-cljs callers)
;; ---------------------------------------------------------------------------

(defn ^:export storeDocumentBody [^js node doc-id body-json]
  (store-doc! node doc-id (js->clj body-json :keywordize-keys true)))

(defn ^:export storeWorkbookGrid [^js node book-id grid-json]
  (store-book! node book-id (js->clj grid-json :keywordize-keys true)))

(defn ^:export evaluateMerge [^js node pr-id]
  (clj->js (evaluate-merge! node pr-id)))
