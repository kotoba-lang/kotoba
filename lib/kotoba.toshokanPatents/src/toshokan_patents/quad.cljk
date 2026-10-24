(ns toshokan-patents.quad
  "EDN quad-log codec — the git-authoritative journal convention of ADR-2607072300
  (same shape as kotoba-lang/toshokan and cloud-itonami-lei-*).

  A journal file's whole contents is ONE top-level EDN vector of
  `[entity attr value tx op]` tuples (op is `:add` or `:retract`).
  Cardinality-many attrs fan out to one tuple per element.

  ## This namespace is PURE — that is now enforced by the file, not by a comment

  It used to say the top half was pure and portable and then `:require`
  `node:fs` for the file legs at the bottom. Which meant that the moment a
  Cloudflare Worker tried to use the pure half — the parser and the codec, the
  whole reason this is a library — the build failed on a filesystem dependency
  a Worker does not have and does not want.

  The file legs now live in `toshokan-patents.quad.fs`. Consumers with a
  filesystem require that; consumers without one (Workers, browsers) require
  this and are unaffected.

  ## This is a library, not a runner

  **Who owns the loop is not this repo's business** (2026-08-10 owner decision:
  kotoba-lang holds libraries only). The residency, the seed policy, the cursor,
  and the git commits live in the actor that consumes this —
  `cloud-itonami/hirameki`."
  (:refer-clojure :exclude []))

(defn next-tx
  "The tx number a fresh append should carry: one past the highest already in
  `existing-quads`. 1 for an empty journal."
  [existing-quads]
  (inc (reduce max 0 (map #(nth % 3) existing-quads))))

(defn record->quads
  "field-map is `{attr value-or-nil-or-coll ...}`.

  - `nil` values are DROPPED — a source page that omits a field costs nothing
    and never writes a null into the log.
  - sequential values FAN OUT to one quad per element (cardinality-many). This
    is what turns `:patent/cites` into a walkable citation graph.

  Pure: the caller supplies `tx`, so the same inputs always give the same quads."
  [entity tx field-map]
  (into []
        (mapcat (fn [[attr v]]
                  (cond
                    (nil? v) []
                    (sequential? v) (for [item v :when (some? item)]
                                      [entity attr item tx :add])
                    :else [[entity attr v tx :add]])))
        field-map))

(defn entities
  "The distinct entity ids present in a quad vector — the dedupe key a harvester
  checks before spending a request."
  [quads]
  (into #{} (map first) quads))

(defn merge-quads
  "Append `new-quads` after `existing`. Pure counterpart of `append-journal!`."
  [existing new-quads]
  (into (vec existing) new-quads))

(defn render-journal
  "Quads → the on-disk text: ONE top-level EDN vector, one quad per line.

  Still a single `edn/read-string`-able form, so every existing reader keeps
  working — but line-oriented, which is what makes it survive a long-running
  harvest. The original writer emitted `(pr-str (vec quads))`, i.e. the whole
  journal on ONE line; at 618 patents that was a single 691 KB line. Git stores
  a fresh blob per commit either way, but a one-line file also defeats delta
  compression and makes `git diff` and `git blame` useless on the exact artifact
  that is supposed to be the authoritative record (ADR-2607072300).

  PURE, and it has to be: the Cloudflare Worker writes journal shards through
  the GitHub API with no filesystem in sight."
  [quads]
  (str "[" (reduce str (map #(str "\n" (pr-str %)) quads)) "\n]\n"))


;; ── sharded journal: the pure half ───────────────────────────────────────────
;;
;; A journal that a resident loop appends to forever cannot be one file. Not
;; because of disk — because every commit stores a new copy of the WHOLE file,
;; so a 44 MB journal appended to 120 times a day writes 5 GB of git objects a
;; day for 8 KB a day of new facts.
;;
;; Shards are sealed once full: an old shard is byte-identical forever, so git
;; stores it exactly once and DataLad/annex can take it if it ever needs to.
;; Only the ACTIVE shard is rewritten, and it is bounded.
;;
;; Shards live in the same directory with a `<source>.NNNN.journal.edn` name
;; rather than a subdirectory, so every existing consumer — the query plane's
;; "read *.journal.edn in this dir", the corpus fold, verify — keeps working
;; with no change at all.

(def default-shard-max-bytes
  "Seal a shard past 1 MiB. Small enough that an append rewrites little and a
  diff stays reviewable; large enough that a million patents is ~1,000 files
  rather than a directory nobody can list."
  (* 1024 1024))

(defn shard-name [source n]
  (str source "." (subs (str "0000" n) (- (count (str "0000" n)) 4)) ".journal.edn"))

(defn shard-index
  "The index in a shard filename, or nil if the name is not one of `source`'s."
  [source filename]
  (when-let [m (re-matches (re-pattern (str "^" source "\\.(\\d{4})\\.journal\\.edn$")) filename)]
    #?(:clj (Long/parseLong (second m))
       :cljs (js/parseInt (second m) 10))))
