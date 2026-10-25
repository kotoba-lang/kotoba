(ns adl.archetype
  "The whole-document ADL 1.4 grammar: the `archetype (adl_version=1.4)`
  header, the `concept` node id, and the section sequence
  (`language`/`description`/`definition`/`invariant`/`ontology`/
  `revision_history`/`annotations`), each dispatched to `adl.dadl` or
  `adl.cadl` as appropriate. Targets ADL **1.4** specifically (the
  Eiffel-flavoured plain-text syntax standardised as
  https://specifications.openehr.org/releases/AM/latest/ADL1.4.html) --
  NOT ADL 2.x, whose header/section grammar and archetype-XML/canonical
  serialization differ enough that treating them as one grammar would blur
  both. See this repo's README for the version boundary.

  `invariant` (OCL-like assertions) is parsed only as an opaque balanced
  block -- real OCL expression grammar is out of scope for this repo (an
  RM-path-and-constraint parser, not a full object-constraint-language
  one) -- captured and round-tripped verbatim rather than dropped."
  (:require [kotoba.lang.text :as str]
            [adl.lexer :as lex]
            [adl.dadl :as dadl]
            [adl.cadl :as cadl]))

(def section-keywords
  ["language" "description" "definition" "invariant" "ontology"
   "revision_history" "annotations"])

;; ---------------------------------------------------------------------
;; header: `archetype (adl_version=1.4)\n\t<archetype-id>`
;; ---------------------------------------------------------------------

(defn- read-archetype-id-token
  "Reads the archetype id line: dot/hyphen-joined segments
  (`openEHR-EHR-OBSERVATION.demo.v1`) up to the next whitespace/comment."
  [s i]
  (let [j (lex/skip-ws-and-comments s i)
        n (count s)
        end (loop [k j]
              (if (and (< k n) (not (lex/ws-ch? (lex/char-at s k))))
                (recur (inc k))
                k))]
    (when (= j end) (throw (lex/adl-error :adl/expected-archetype-id {:at j})))
    [(subs s j end) end]))

(defn- parse-header-params
  "The optional `(key=value; key=value...)` following `archetype`. Returns
  [{param-name value} next-index]."
  [s i]
  (if-not (lex/peek-lit? s i "(")
    [{} i]
    (let [j (lex/expect s i "(")
          n (count s)
          close (loop [k j] (if (and (< k n) (not= ")" (lex/char-at s k))) (recur (inc k)) k))
          raw (subs s j close)
          params (into {}
                       (keep (fn [clause]
                               (let [eq (str/index-of clause "=")]
                                 (when eq
                                   [(str/trim (subs clause 0 eq)) (str/trim (subs clause (inc eq)))]))))
                       (str/split raw #";"))]
      [params (lex/expect s close ")")])))

(defn- parse-header [s i]
  (let [j (lex/expect s i "archetype")
        [params j2] (parse-header-params s j)
        [archetype-id j3] (read-archetype-id-token s j2)]
    [{:params params :archetype-id archetype-id} j3]))

;; ---------------------------------------------------------------------
;; concept: `[at0000]` optional inline comment
;; ---------------------------------------------------------------------

(defn- parse-concept [s i]
  (let [j (lex/expect s i "concept")
        j2 (lex/expect s j "[")
        [node-id j3] (lex/read-dotted-code s j2)
        j4 (lex/expect s j3 "]")
        [comment j5] (lex/trailing-comment s j4)]
    [{:node-id node-id :comment comment} j5]))

;; ---------------------------------------------------------------------
;; invariant: opaque, bracket-depth-aware capture
;; ---------------------------------------------------------------------

(defn- next-section-keyword-at?
  "True when, after skipping only WHITESPACE (not comments -- a `--`
  inside invariant text is content, not something to look past) from i,
  one of `section-keywords` sits at the cursor."
  [s i]
  (let [j (lex/skip-ws s i)]
    (some #(lex/peek-lit? s j %) section-keywords)))

(defn- parse-invariant-raw
  "Captures the `invariant` section as opaque text: everything from i up
  to (not including) the next section keyword that occurs at bracket depth
  0, or EOF. Bracket-depth tracking (not just \"first matching keyword\")
  matters because OCL assertions freely use `(`/`{`/`[` internally and a
  keyword-shaped substring could in principle appear inside a quoted
  string -- tracked depth means this never mistakes nested content for the
  section boundary."
  [s i]
  (let [n (count s)]
    (loop [k i depth 0]
      (cond
        (>= k n) [(str/trim (subs s i k)) k]
        (and (zero? depth) (next-section-keyword-at? s k)) [(str/trim (subs s i k)) k]
        (contains? #{"(" "{" "["} (lex/char-at s k)) (recur (inc k) (inc depth))
        (contains? #{")" "}" "]"} (lex/char-at s k)) (recur (inc k) (max 0 (dec depth)))
        :else (recur (inc k) depth)))))

;; ---------------------------------------------------------------------
;; whole document
;; ---------------------------------------------------------------------

(defn parse
  "Parses a full ADL 1.4 archetype document. Returns `[:ok archetype]` or
  `[:error kw detail]` -- never throws.

  `archetype` shape:
    {:params {...} :archetype-id \"...\" :concept {...}
     :section-order [\"language\" \"definition\" \"ontology\" ...]
     :sections {\"language\" dadl-entries ... \"definition\" c-object
                \"invariant\" raw-string-or-nil ...}}

  `:section-order` is kept explicitly (rather than relying on map
  iteration order) so `serialize` reproduces the source archetype's own
  section sequence, which ADL does not fix -- `ontology` is always last in
  practice but nothing in the grammar requires it."
  [s]
  (try
    ;; A UTF-8 BOM (U+FEFF) at byte 0 is common in archetype files exported
    ;; by Windows-based CKM tooling -- seen verbatim in the published
    ;; `openEHR-EHR-OBSERVATION.demo.v1.adl` this parser is tested against.
    ;; It is not whitespace by any Unicode property this grammar otherwise
    ;; cares about, so it is stripped once here rather than taught to
    ;; every `skip-ws` call in adl.lexer.
    (let [s (if (str/starts-with? s "﻿") (subs s 1) s)
          [header j] (parse-header s 0)
          [concept j2] (parse-concept s j)]
      (loop [i j2 order [] sections {}]
        (let [i' (lex/skip-ws-and-comments s i)]
          (if (>= i' (count s))
            [:ok {:params (:params header) :archetype-id (:archetype-id header)
                  :concept concept :section-order order :sections sections}]
            (let [[kw j3] (lex/read-ident s i')]
              (when-not (some #{kw} section-keywords)
                (throw (lex/adl-error :adl/unknown-section {:at i' :section kw})))
              (case kw
                "definition"
                (let [[obj j4] (cadl/parse-c-object s j3)]
                  (recur j4 (conj order kw) (assoc sections kw obj)))

                "invariant"
                (let [[raw j4] (parse-invariant-raw s j3)]
                  (recur j4 (conj order kw) (assoc sections kw raw)))

                ("language" "description" "ontology" "revision_history" "annotations")
                (let [[entries j4] (dadl/parse-entries-until s j3)]
                  (recur j4 (conj order kw) (assoc sections kw entries)))))))))
    (catch #?(:clj Exception :cljs :default) e
      (if (lex/adl-error? (ex-data e))
        [:error (:adl/error (ex-data e)) (dissoc (ex-data e) :adl/error)]
        (throw e)))))

;; ---------------------------------------------------------------------
;; serializing
;; ---------------------------------------------------------------------

(defn- params-str [params]
  (if (empty? params)
    ""
    (str " (" (str/join "; " (map (fn [[k v]] (str k "=" v)) params)) ")")))

(defn- concept-str [{:keys [node-id comment]}]
  (str "concept\n\t[" node-id "]" (when (seq comment) (str "\t-- " comment)) "\n"))

(defn- section-str [kw sections]
  (let [body (get sections kw)]
    (str kw "\n"
         (case kw
           "definition" (str "\t" (cadl/c-object-str body 1) "\n")
           "invariant" (str body "\n")
           (dadl/entries-str body 1))
         "\n")))

(defn serialize
  "Serializes a parsed archetype back to ADL 1.4 text."
  [{:keys [params archetype-id concept section-order sections]}]
  (str "archetype" (params-str params) "\n\t" archetype-id "\n\n"
       (concept-str concept) "\n"
       (str/join "\n" (map #(section-str % sections) section-order))))
