(ns toshokan.quad
  "Read/append helpers for this repo's `80-data/public/*.journal.edn` files —
  the git-authoritative EDN quad-log convention from ADR-2607072300. A
  journal file's whole contents is ONE top-level EDN vector of
  `[entity attr value tx op]` tuples (op is :add or :retract), matching the
  shape `scripts/kotobase-ingest-cloud-itonami-lei.cljs` already reads."
  (:require ["node:fs" :as fs]
            [cljs.reader :as edn]))

(defn read-journal [path]
  (if (fs/existsSync path)
    (edn/read-string (fs/readFileSync path "utf8"))
    []))

(defn next-tx [existing-quads]
  (inc (reduce max 0 (map #(nth % 3) existing-quads))))

(defn write-journal! [path quads]
  (fs/writeFileSync path (str (pr-str (vec quads)) "\n")))

(defn append-journal!
  "Reads `path`, appends `new-quads` (tx numbers already stamped by the
  caller via next-tx), writes back. Returns the full merged vector."
  [path new-quads]
  (let [existing (read-journal path)
        merged (into (vec existing) new-quads)]
    (write-journal! path merged)
    merged))

(defn record->quads
  "field-map is {attr value-or-nil-or-coll ...}; nil values are dropped,
  collection values fan out to one quad per element (cardinality-many)."
  [entity tx field-map]
  (into []
        (mapcat (fn [[attr v]]
                  (cond
                    (nil? v) []
                    (sequential? v) (for [item v :when (some? item)]
                                      [entity attr item tx :add])
                    :else [[entity attr v tx :add]])))
        field-map))
