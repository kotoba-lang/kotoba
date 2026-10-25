(ns adl.path
  "openEHR Reference Model path syntax: `/content[openEHR-EHR-SECTION.x.v1]
  /items[at0001]/value`, the addressing scheme used both to locate data in
  an actual EHR composition and, inside an archetype's own `definition`
  section, by `use_node` (reuse an already-constrained subtree) and archetype
  slot `include`/`exclude` rules (`archetype_id/value matches {/regex/}`).

  A path is `/`-separated segments, each an attribute name with an optional
  bracketed predicate. Three predicate shapes are in real use and are
  distinguished here by CONTENT, not position (all three are syntactically
  just \"whatever is between `[` and `]`\"):

    node-id       `[at0001]`, `[at0002, 'Any event']`  -- an archetype node
                  id, optionally with a quoted display-name disambiguator
    name/value    `[name/value='Systolic']`, chainable with ` and `
    archetype-id  `[openEHR-EHR-SECTION.laboratory_test.v1]` -- selects by
                  which archetype is at that node, not by node id

  The bracket scanner is quote-aware (a `'...'` inside a predicate can, in
  principle, contain a `/` or `]`) rather than a naive index-of search for
  the next `]` -- the naive version is the classic wrong way to do this and
  is exactly the failure mode a `str/split` sketch would have."
  (:require [kotoba.lang.text :as str]
            [adl.lexer :as lex]))

;; ---------------------------------------------------------------------
;; predicate content
;; ---------------------------------------------------------------------

(def ^:private node-id-re #"^(at|id|ac)[0-9]+(\.[0-9]+)*(,\s*'([^']*)')?$")
(def ^:private archetype-id-re
  #"^[A-Za-z][A-Za-z0-9]*(-[A-Za-z][A-Za-z0-9]*)+\.[A-Za-z][A-Za-z0-9_]*(-[A-Za-z][A-Za-z0-9_]*)*\.v[0-9]+$")

(defn- parse-name-value-clause [clause]
  (let [eq (str/index-of clause "=")
        attr-path (str/split (str/trim (subs clause 0 eq)) #"/")
        raw-val (str/trim (subs clause (inc eq)))
        quoted? (and (>= (count raw-val) 2)
                     (str/starts-with? raw-val "'")
                     (str/ends-with? raw-val "'"))]
    {:kind :name-value :path (vec attr-path)
     :value (if quoted? (subs raw-val 1 (dec (count raw-val))) raw-val)}))

(defn- classify-clause
  "One term of an `and`-joined predicate. Real archetype predicates mix
  shapes here -- `[at0001 and name/value='Systolic']` pairs a bare node-id
  term with a name/value term in the SAME bracket -- so classification
  happens per-clause, not once for the whole bracket content."
  [clause]
  (let [t (str/trim clause)]
    (cond
      (str/includes? t "=") (parse-name-value-clause t)
      (re-matches node-id-re t)
      (let [[node-part display] (str/split t #",\s*" 2)]
        (cond-> {:kind :node-id :node-id node-part}
          display (assoc :display-name (subs display 1 (dec (count display))))))
      (re-matches archetype-id-re t) {:kind :archetype-id :archetype-id t}
      :else {:kind :raw :text t})))

(defn parse-predicate-text
  "Classifies and parses the already-extracted text between `[` and `]`
  into `{:kind :node-id|:name-value|:archetype-id|:raw|:composite ...}`.
  `:composite` holds a `:clauses` vector (each itself one of the other
  kinds) for an `and`-joined predicate with more than one term; a single
  term collapses straight to that term's own shape, matching the common
  case (`[at0001]`) without a pointless one-element wrapper.

  Never throws on an unrecognized clause shape, falling back to `:raw` --
  an archetype path predicate space is open-ended; refusing to round-trip
  an unfamiliar one would make this parser reject valid paths it merely
  doesn't have a richer model for."
  [text]
  (let [clauses (mapv classify-clause (str/split (str/trim text) #"\s+and\s+"))]
    (if (= 1 (count clauses)) (first clauses) {:kind :composite :clauses clauses})))

(defn- clause-str [{:keys [kind] :as c}]
  (case kind
    :node-id (str (:node-id c) (when (:display-name c) (str ", '" (:display-name c) "'")))
    :name-value (str (str/join "/" (:path c)) "='" (:value c) "'")
    :archetype-id (:archetype-id c)
    :raw (:text c)))

(defn predicate-str [{:keys [kind] :as p}]
  (if (= kind :composite)
    (str/join " and " (map clause-str (:clauses p)))
    (clause-str p)))

;; ---------------------------------------------------------------------
;; segments
;; ---------------------------------------------------------------------

(defn- read-bracket-content
  "Reads raw text from i (s[i] right after the opening `[`) up to the
  matching `]`, treating any run inside `'...'` as opaque (so a `/` or `]`
  quoted inside a name/value predicate's string value doesn't terminate the
  scan early). Returns [text next-index-after-closing-bracket]."
  [s i]
  (let [n (count s)]
    (loop [k i out (transient [])]
      (cond
        (>= k n) (throw (lex/adl-error :adl/unterminated-predicate {:at i}))
        (= "]" (lex/char-at s k)) [(apply str (persistent! out)) (inc k)]
        (= "'" (lex/char-at s k))
        (let [close (loop [m (inc k)]
                      (cond (>= m n) (throw (lex/adl-error :adl/unterminated-predicate {:at i}))
                            (= "'" (lex/char-at s m)) m
                            :else (recur (inc m))))]
          (recur (inc close) (reduce conj! out (map #(lex/char-at s %) (range k (inc close))))))
        :else (recur (inc k) (conj! out (lex/char-at s k)))))))

(defn- parse-segment [s i]
  (let [[name j] (lex/read-dotted-ident s i)]
    (if (= "[" (lex/char-at s j))
      (let [[text k] (read-bracket-content s (inc j))]
        [{:name name :predicate (parse-predicate-text text)} k])
      [{:name name :predicate nil} j])))

(defn parse
  "Parses an RM path (absolute, leading `/`, or relative, as used in slot
  `include`/`exclude` clauses) into
  `{:absolute? bool :segments [{:name .. :predicate ..-or-nil} ...]}`.
  Returns `[:ok path]` or `[:error kw detail]`."
  [s]
  (try
    (let [s (str/trim s)
          absolute? (str/starts-with? s "/")
          start (if absolute? 1 0)]
      (when (empty? (subs s start))
        (throw (lex/adl-error :adl/empty-path {})))
      (loop [i start segments []]
        (let [[seg j] (parse-segment s i)
              segments (conj segments seg)]
          (cond
            (= j (count s)) [:ok {:absolute? absolute? :segments segments}]
            (= "/" (lex/char-at s j)) (recur (inc j) segments)
            :else (throw (lex/adl-error :adl/malformed-path {:at j}))))))
    (catch #?(:clj Exception :cljs :default) e
      (if (lex/adl-error? (ex-data e))
        [:error (:adl/error (ex-data e)) (dissoc (ex-data e) :adl/error)]
        (throw e)))))

(defn path-str
  "Serializes a parsed path back to text."
  [{:keys [absolute? segments]}]
  (str (when absolute? "/")
       (str/join "/" (map (fn [{:keys [name predicate]}]
                             (str name (when predicate (str "[" (predicate-str predicate) "]"))))
                           segments))))
