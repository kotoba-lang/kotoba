(ns cron.model
  "Cron 式を EDN データとして表現する正準モデル。5フィールドの cron 式
  (min hour dom month dow) を namespaced キーの plain map に parse する。
  No I/O, no third-party deps — portable .cljc (JVM, ClojureScript, SCI).

  Parse 結果の構造:
    {:cron/minute         #{0..59}
     :cron/hour           #{0..23}
     :cron/dom            #{1..31}
     :cron/month          #{1..12}
     :cron/dow            #{0..6}   ; 0=Sun, 1=Mon, …, 6=Sat
     :cron/dom-restricted? boolean  ; true iff dom field was not '*'
     :cron/dow-restricted? boolean} ; true iff dow field was not '*'

  Supported field syntax: *, n, a-b, a-b/s, */s, a,b,c (mixable).
  3-letter names: JAN-DEC (month), SUN-SAT (dow) — case-insensitive.
  Macro shorthands: @yearly/@annually/@monthly/@weekly/@daily/@hourly."
  (:require [kotoba.lang.text]))

;; --- name tables ---

(def ^:private month-names
  {"JAN" 1 "FEB" 2 "MAR" 3 "APR" 4 "MAY" 5 "JUN" 6
   "JUL" 7 "AUG" 8 "SEP" 9 "OCT" 10 "NOV" 11 "DEC" 12})

(def ^:private dow-names
  {"SUN" 0 "MON" 1 "TUE" 2 "WED" 3 "THU" 4 "FRI" 5 "SAT" 6})

;; --- macro expansions (expand before splitting) ---

(def ^:private macros
  {"@yearly"   "0 0 1 1 *"
   "@annually" "0 0 1 1 *"
   "@monthly"  "0 0 1 * *"
   "@weekly"   "0 0 * * 0"
   "@daily"    "0 0 * * *"
   "@hourly"   "0 * * * *"})

;; --- internal field parsers ---

(defn- parse-int [s]
  #?(:clj  (Long/parseLong s)
     :cljs (js/parseInt s 10)))

(defn- parse-num
  "Parse a token as either a plain integer or a 3-letter name looked up in
  `name-table`. Throws on unknown names."
  [s name-table]
  (if (re-matches #"[0-9]+" s)
    (parse-int s)
    (let [upper (kotoba.lang.text/upper s)]
      (or (get name-table upper)
          (throw (ex-info (str "Unknown name: " s) {:token s}))))))

(defn- expand-range [lo hi step]
  (into #{} (range lo (inc hi) step)))

(defn- parse-token
  "Parse a single comma-free cron token. Returns a set of integers.
  `lo`/`hi` are inclusive valid range; `name-table` maps 3-letter names to ints."
  [token lo hi name-table]
  (cond
    ;; plain wildcard
    (= token "*")
    (expand-range lo hi 1)

    ;; */step
    (kotoba.lang.text/starts-with? token "*/")
    (let [step (parse-int (subs token 2))]
      (when (<= step 0)
        (throw (ex-info "Step must be > 0" {:token token})))
      (expand-range lo hi step))

    ;; a-b  or  a-b/step
    (kotoba.lang.text/includes? token "-")
    (let [[range-part step-part] (kotoba.lang.text/split token #"/" 2)
          [a-tok b-tok]          (kotoba.lang.text/split range-part #"-" 2)
          start (parse-num a-tok name-table)
          end   (parse-num b-tok name-table)
          step  (if step-part (parse-int step-part) 1)]
      (when (<= step 0)
        (throw (ex-info "Step must be > 0" {:token token})))
      ;; `range` silently returns empty for start > end -- a reversed range
      ;; (a common transposed-bounds typo, e.g. "50-10") would otherwise
      ;; parse to an empty field-set instead of throwing, then silently
      ;; "never fire" downstream rather than surfacing the bad input.
      (when (> start end)
        (throw (ex-info "Range start must be <= end" {:token token})))
      (expand-range start end step))

    ;; a,b,c  — recurse on each sub-token
    (kotoba.lang.text/includes? token ",")
    (into #{} (mapcat #(parse-token % lo hi name-table)
                      (kotoba.lang.text/split token #",")))

    ;; single value: integer or name
    :else
    #{(parse-num token name-table)}))

;; --- public API ---

(defn parse
  "Parse a 5-field cron expression (or @macro shorthand) into a map with
  namespaced `:cron/*` keys. Fields are 'min hour dom month dow'.

  Throws ex-info on parse failure (unknown name, bad step, wrong field count)."
  [expr]
  (let [expr     (kotoba.lang.text/trim expr)
        expr     (get macros expr expr)
        parts    (kotoba.lang.text/split expr #"\s+")]
    (when (not= 5 (count parts))
      (throw (ex-info (str "Cron expression must have exactly 5 fields; got: " expr)
                      {:expr expr :fields (count parts)})))
    (let [[min-tok hour-tok dom-tok month-tok dow-tok] parts]
      {:cron/minute          (parse-token min-tok    0  59 {})
       :cron/hour            (parse-token hour-tok   0  23 {})
       :cron/dom             (parse-token dom-tok    1  31 {})
       :cron/month           (parse-token month-tok  1  12 month-names)
       :cron/dow             (parse-token dow-tok    0   6 dow-names)
       :cron/dom-restricted? (not= dom-tok "*")
       :cron/dow-restricted? (not= dow-tok "*")})))
