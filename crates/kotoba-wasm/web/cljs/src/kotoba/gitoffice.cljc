(ns kotoba.gitoffice
  "GitOffice Phase 0 (doc e) — normalization + collaboration converters.

   Two jobs, both pure (.cljc, babashka/Clojure, no platform deps):

   1. NORMALIZE the DEPLOYED coarse blob model into the element-granular datom
      model that semantic diff/merge needs (doc e §13, option 1):
        - docs   :doc/bodyJson  ({elementId,kind,headingLevel?,text} list) <-> :block/* blocks
        - sheets :sheet/gridJson ({title [[cell]]})                        <-> :cell/* cells
        - revision bridge: :doc/revisionId \"rev-N\" / :sheet/revision N   <-> :rev/* + CommitDag seq
      The deployed body is FLAT (no nesting), so blocks are direct children of the doc.
      Block ordering uses a fractional-index string (insert-friendly, CRDT-migratable);
      cells are sparse (only non-empty), keyed by absolute A1 ref = the stable diff id.

   2. COLLABORATION metadata (doc e §2) <-> datoms: issue / pr / review / comment.
      Bijective like p0/office.cljc (vector of [e a v]); bodies are plain here
      (encrypted via assertEncrypted at write time in real use).

   Entity ids are caller-supplied LOGICAL ids (real ids = kotoba commit() CIDs).
   Blocks keep their bodyJson elementId as the stable id so re-normalize is idempotent."
  (:require [clojure.string :as str]
            [clojure.edn :as edn]))

;; ---------------------------------------------------------------------------
;; schema registry  (additive to p0/office.cljc; Datomic-style attribute meta)
;; ---------------------------------------------------------------------------

(def schema
  {;; --- block (element-granular doc body; flat under the doc) ---
   :block/kind          {:db/valueType :keyword :db/cardinality :one}
   :block/text          {:db/valueType :string  :db/cardinality :one
                         :db/encrypted true :doc "signal:v1: via assertEncrypted in real use"}
   :block/order         {:db/valueType :string  :db/cardinality :one
                         :doc "fractional-index string (insert-friendly)"}
   :block/parent        {:db/valueType :ref     :db/cardinality :one}
   :block/heading-level {:db/valueType :long    :db/cardinality :one}

   ;; --- cell (sparse spreadsheet cell; id = \"<sheet>!<A1>\") ---
   :cell/book           {:db/valueType :ref     :db/cardinality :one}
   :cell/sheet          {:db/valueType :string  :db/cardinality :one}
   :cell/ref            {:db/valueType :string  :db/cardinality :one :db/doc "A1, e.g. B2"}
   :cell/row            {:db/valueType :long    :db/cardinality :one :db/doc "0-based"}
   :cell/col            {:db/valueType :long    :db/cardinality :one :db/doc "0-based"}
   :cell/value          {:db/valueType :string  :db/cardinality :one :db/doc "no-float: string"}

   ;; --- revision <-> commit bridge (ETag/If-Match <-> CommitDag) ---
   :rev/of              {:db/valueType :ref     :db/cardinality :one :db/doc "doc/book entity"}
   :rev/label           {:db/valueType :string  :db/cardinality :one :db/doc "\"rev-N\" (docs) / \"N\""}
   :rev/seq             {:db/valueType :long    :db/cardinality :one :db/doc "monotone counter"}
   :rev/commit          {:db/valueType :string  :db/cardinality :one :db/doc "CommitDag commit CID"}

   ;; --- repo / ref (branch,tag) ---
   :repo/id             {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :repo/kind           {:db/valueType :keyword :db/cardinality :one}
   :repo/owner-org      {:db/valueType :ref     :db/cardinality :one}
   :repo/default-ref    {:db/valueType :string  :db/cardinality :one}
   :ref/name            {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :ref/repo            {:db/valueType :ref     :db/cardinality :one}
   :ref/kind            {:db/valueType :keyword :db/cardinality :one}
   :ref/commit          {:db/valueType :string  :db/cardinality :one}
   :ref/protected       {:db/valueType :boolean :db/cardinality :one}

   ;; --- issue ---
   :issue/id            {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :issue/repo          {:db/valueType :ref     :db/cardinality :one}
   :issue/number        {:db/valueType :long    :db/cardinality :one}
   :issue/title         {:db/valueType :string  :db/cardinality :one}
   :issue/body          {:db/valueType :string  :db/cardinality :one :db/encrypted true}
   :issue/author        {:db/valueType :did     :db/cardinality :one}
   :issue/state         {:db/valueType :keyword :db/cardinality :one}
   :issue/label         {:db/valueType :string  :db/cardinality :many}
   :issue/anchor        {:db/valueType :string  :db/cardinality :many}
   :issue/created-at    {:db/valueType :long    :db/cardinality :one}

   ;; --- pull request ---
   :pr/id               {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :pr/repo             {:db/valueType :ref     :db/cardinality :one}
   :pr/number           {:db/valueType :long    :db/cardinality :one}
   :pr/title            {:db/valueType :string  :db/cardinality :one}
   :pr/author           {:db/valueType :did     :db/cardinality :one}
   :pr/base-ref         {:db/valueType :string  :db/cardinality :one}
   :pr/head-ref         {:db/valueType :string  :db/cardinality :one}
   :pr/base-commit      {:db/valueType :string  :db/cardinality :one}
   :pr/head-commit      {:db/valueType :string  :db/cardinality :one}
   :pr/merge-base       {:db/valueType :string  :db/cardinality :one}
   :pr/state            {:db/valueType :keyword :db/cardinality :one}
   :pr/closes-issue     {:db/valueType :ref     :db/cardinality :many}
   :pr/merged-commit    {:db/valueType :string  :db/cardinality :one}

   ;; --- review ---
   :review/id           {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :review/pr           {:db/valueType :ref     :db/cardinality :one}
   :review/reviewer     {:db/valueType :did     :db/cardinality :one}
   :review/state        {:db/valueType :keyword :db/cardinality :one}
   :review/at-commit    {:db/valueType :string  :db/cardinality :one}
   :review/vc           {:db/valueType :string  :db/cardinality :one}

   ;; --- comment (element-anchored = GitHub line comment) ---
   :comment/id          {:db/valueType :string  :db/cardinality :one :db/unique :identity}
   :comment/on          {:db/valueType :ref     :db/cardinality :one}
   :comment/author      {:db/valueType :did     :db/cardinality :one}
   :comment/body        {:db/valueType :string  :db/cardinality :one :db/encrypted true}
   :comment/anchor      {:db/valueType :string  :db/cardinality :one}
   :comment/side        {:db/valueType :keyword :db/cardinality :one}
   :comment/resolved    {:db/valueType :boolean :db/cardinality :one}
   :comment/created-at  {:db/valueType :long    :db/cardinality :one}})

;; ---------------------------------------------------------------------------
;; small EAV helpers (same shape as p0/office.cljc)
;; ---------------------------------------------------------------------------

(defn v-one
  "First value for (e,a). Uses reduce (not `some`) so a stored boolean false is
   returned, not skipped as falsey."
  [datoms e a]
  (reduce (fn [_ [de da v]] (when (and (= de e) (= da a)) (reduced v))) nil datoms))
(defn v-many [datoms e a] (set (keep (fn [[de da v]] (when (and (= de e) (= da a)) v)) datoms)))

;; ---------------------------------------------------------------------------
;; fractional indexing (order keys are base-36 fractions, compared lexically)
;; ---------------------------------------------------------------------------

(def ^:private digits "0123456789abcdefghijklmnopqrstuvwxyz")
(def ^:private base (count digits))
(def ^:private dval (into {} (map-indexed (fn [i c] [c i]) digits)))
(defn- digs->str [vs] (apply str (map #(nth digits %) vs)))

(defn order-between
  "Fractional index strictly between a and b (lexicographic order).
   a nil/\"\" = lower bound (0); b nil = upper bound (1). Requires a < b.

   Keys must be CANONICAL (no trailing '0' digit): a trailing zero makes a key
   fraction-equal to its prefix (\"1\" == \"10\"), so no key can sit strictly between
   them and the midpoint walk would emit an out-of-range key. Generated keys are
   always canonical; a non-canonical key only enters via external/CRDT import, so we
   reject it loudly rather than corrupt the order silently."
  [a b]
  (let [a (or a "")]
    (when (and (seq a) (= \0 (last a)))
      (throw (ex-info "invalid order key (trailing zero)" {:key a})))
    (when (some? b)
      (when (or (= "" b) (= \0 (last b)))
        (throw (ex-info "invalid order key (trailing zero / empty)" {:key b})))
      (when-not (neg? (compare a b))
        (throw (ex-info "order keys not ascending" {:a a :b b}))))
    (let [av (vec a)
          bv (when (seq b) (vec b))]
      (loop [i 0 acc []]
        (let [da (if (< i (count av)) (dval (nth av i)) 0)
              db (if (and bv (< i (count bv))) (dval (nth bv i)) base)]
          (if (< (inc da) db)
            (digs->str (conj acc (quot (+ da db) 2)))
            (recur (inc i) (conj acc da))))))))

(defn initial-orders
  "n strictly-increasing order keys (one per list position)."
  [n]
  (loop [i 0 prev nil acc []]
    (if (= i n)
      acc
      (let [k (order-between prev nil)]
        (recur (inc i) k (conj acc k))))))

;; ---------------------------------------------------------------------------
;; A1 notation
;; ---------------------------------------------------------------------------

(defn col->a1 [c]
  (loop [n (inc c) s ""]
    (if (zero? n)
      s
      (recur (quot (dec n) 26)
             (str (char (+ 65 (mod (dec n) 26))) s)))))

(defn a1->col [letters]
  (dec (reduce (fn [acc ch] (+ (* acc 26) (- (int ch) 64))) 0 letters))) ; -> 0-based

(defn cell-id [sheet row col] (str sheet "!" (col->a1 col) (inc row)))

;; ===========================================================================
;; 1a. docs  bodyJson  <->  :block/* blocks
;; ===========================================================================

(def ^:private kind->kw
  {"paragraph" :block/paragraph "heading" :block/heading "listItem" :block/list-item})
(def ^:private kw->kind (into {} (map (fn [[k v]] [v k]) kind->kw)))

(defn body->blocks
  "bodyJson element list -> datoms. doc-id = parent. Element :elementId is the stable
   block id (re-normalize is idempotent). Order = fractional index from position."
  [doc-id body]
  (let [orders (initial-orders (count body))]
    (into []
          (mapcat (fn [{:keys [elementId kind headingLevel text]} ord]
                    (let [bid elementId]
                      (cond-> [[bid :block/parent doc-id]
                               [bid :block/kind (kind->kw (or kind "paragraph") :block/paragraph)]
                               [bid :block/order ord]
                               [bid :block/text (or text "")]]
                        (some? headingLevel) (conj [bid :block/heading-level headingLevel]))))
                  body orders))))

(defn blocks->body
  "datoms -> bodyJson element list (sorted by :block/order)."
  [datoms doc-id]
  (->> datoms
       (keep (fn [[e a v]] (when (and (= a :block/parent) (= v doc-id)) e)))
       distinct
       (sort-by (fn [e] [(v-one datoms e :block/order) e]))  ; [order id]: deterministic on ties
       (mapv (fn [bid]
               (let [hl (v-one datoms bid :block/heading-level)]
                 (cond-> {:elementId bid
                          :kind (kw->kind (v-one datoms bid :block/kind) "paragraph")
                          :text (v-one datoms bid :block/text)}
                   (some? hl) (assoc :headingLevel hl)))))))

;; ===========================================================================
;; 1b. sheets  gridJson  <->  :cell/* cells   (sparse, A1-keyed)
;; ===========================================================================

(defn- nonempty? [v] (not (or (nil? v) (= "" v))))

(defn bbox
  "Bounding rectangle [rows cols] over non-empty cells of one 2D grid (0,0 if none)."
  [grid]
  (let [coords (for [r (range (count grid))
                     c (range (count (nth grid r)))
                     :when (nonempty? (get-in grid [r c]))]
                 [r c])]
    (if (seq coords)
      [(inc (apply max (map first coords))) (inc (apply max (map second coords)))]
      [0 0])))

(defn trim-grid
  "Canonicalize one grid to its non-empty bounding rectangle (drops trailing
   empty rows/cols). The round-trip fixed point for sparse cells."
  [grid]
  (let [[rows cols] (bbox grid)]
    (vec (for [r (range rows)]
           (vec (for [c (range cols)]
                  (let [v (get-in grid [r c])] (if (nil? v) "" v))))))))

(defn grid->cells
  "gridJson {sheet [[cell]]} -> datoms (sparse: only non-empty cells)."
  [book-id grid-json]
  (into []
        (mapcat (fn [[sheet grid]]
                  (for [r (range (count grid))
                        c (range (count (nth grid r)))
                        :when (nonempty? (get-in grid [r c]))
                        :let [id (cell-id sheet r c)]
                        d [[id :cell/book book-id]
                           [id :cell/sheet sheet]
                           [id :cell/ref (str (col->a1 c) (inc r))]
                           [id :cell/row r]
                           [id :cell/col c]
                           [id :cell/value (get-in grid [r c])]]]
                    d)))
        grid-json))

(defn cells->grid
  "datoms -> gridJson {sheet [[cell]]} (each sheet trimmed to its bounding rect)."
  [datoms book-id]
  (let [cell-ids (->> datoms
                      (keep (fn [[e a v]] (when (and (= a :cell/book) (= v book-id)) e)))
                      distinct)
        by-sheet (group-by #(v-one datoms % :cell/sheet) cell-ids)]
    (into {}
          (for [[sheet ids] by-sheet]
            (let [rows (inc (apply max (map #(v-one datoms % :cell/row) ids)))
                  cols (inc (apply max (map #(v-one datoms % :cell/col) ids)))
                  m    (into {} (map (fn [id] [[(v-one datoms id :cell/row)
                                               (v-one datoms id :cell/col)]
                                              (v-one datoms id :cell/value)]) ids))]
              [sheet (vec (for [r (range rows)]
                            (vec (for [c (range cols)] (get m [r c] "")))))])))))

;; ===========================================================================
;; 1c. revision <-> commit bridge
;; ===========================================================================

(defn parse-rev
  "\"rev-7\" -> 7 ; \"7\" -> 7."
  [label]
  (let [s (str label)
        s (if (str/starts-with? s "rev-") (subs s 4) s)]
    (edn/read-string s)))

(defn rev->datoms
  "{:id :of :label :seq :commit} -> datoms (commit optional until commit() runs)."
  [{:keys [id of label seq commit]}]
  (cond-> [[id :rev/of of]
           [id :rev/label label]
           [id :rev/seq seq]]
    (some? commit) (conj [id :rev/commit commit])))

(defn datoms->rev [datoms id]
  (cond-> {:id id
           :of    (v-one datoms id :rev/of)
           :label (v-one datoms id :rev/label)
           :seq   (v-one datoms id :rev/seq)}
    (v-one datoms id :rev/commit) (assoc :commit (v-one datoms id :rev/commit))))

;; ===========================================================================
;; 2. collaboration metadata  <->  datoms   (issue / pr / review / comment)
;; ===========================================================================

(defn issue->datoms [{:keys [id repo number title body author state labels anchors created-at]}]
  (into (cond-> [[id :issue/repo repo]
                 [id :issue/number number]
                 [id :issue/title title]
                 [id :issue/author author]
                 [id :issue/state state]
                 [id :issue/created-at created-at]]
          (some? body) (conj [id :issue/body body]))
        (concat (map (fn [l] [id :issue/label l]) labels)
                (map (fn [a] [id :issue/anchor a]) anchors))))

(defn datoms->issue [datoms id]
  (cond-> {:id id
           :repo       (v-one datoms id :issue/repo)
           :number     (v-one datoms id :issue/number)
           :title      (v-one datoms id :issue/title)
           :author     (v-one datoms id :issue/author)
           :state      (v-one datoms id :issue/state)
           :created-at (v-one datoms id :issue/created-at)
           :labels     (v-many datoms id :issue/label)
           :anchors    (v-many datoms id :issue/anchor)}
    (v-one datoms id :issue/body) (assoc :body (v-one datoms id :issue/body))))

(defn pr->datoms [{:keys [id repo number title author base-ref head-ref
                          base-commit head-commit merge-base state
                          closes-issues merged-commit]}]
  (into (cond-> [[id :pr/repo repo]
                 [id :pr/number number]
                 [id :pr/title title]
                 [id :pr/author author]
                 [id :pr/base-ref base-ref]
                 [id :pr/head-ref head-ref]
                 [id :pr/base-commit base-commit]
                 [id :pr/head-commit head-commit]
                 [id :pr/state state]]
          (some? merge-base)    (conj [id :pr/merge-base merge-base])
          (some? merged-commit) (conj [id :pr/merged-commit merged-commit]))
        (map (fn [i] [id :pr/closes-issue i]) closes-issues)))

(defn datoms->pr [datoms id]
  (cond-> {:id id
           :repo          (v-one datoms id :pr/repo)
           :number        (v-one datoms id :pr/number)
           :title         (v-one datoms id :pr/title)
           :author        (v-one datoms id :pr/author)
           :base-ref      (v-one datoms id :pr/base-ref)
           :head-ref      (v-one datoms id :pr/head-ref)
           :base-commit   (v-one datoms id :pr/base-commit)
           :head-commit   (v-one datoms id :pr/head-commit)
           :state         (v-one datoms id :pr/state)
           :closes-issues (v-many datoms id :pr/closes-issue)}
    (v-one datoms id :pr/merge-base)    (assoc :merge-base (v-one datoms id :pr/merge-base))
    (v-one datoms id :pr/merged-commit) (assoc :merged-commit (v-one datoms id :pr/merged-commit))))

(defn review->datoms [{:keys [id pr reviewer state at-commit vc]}]
  (cond-> [[id :review/pr pr]
           [id :review/reviewer reviewer]
           [id :review/state state]
           [id :review/at-commit at-commit]]
    (some? vc) (conj [id :review/vc vc])))

(defn datoms->review [datoms id]
  (cond-> {:id id
           :pr        (v-one datoms id :review/pr)
           :reviewer  (v-one datoms id :review/reviewer)
           :state     (v-one datoms id :review/state)
           :at-commit (v-one datoms id :review/at-commit)}
    (v-one datoms id :review/vc) (assoc :vc (v-one datoms id :review/vc))))

(defn comment->datoms [{:keys [id on author body anchor side resolved created-at]}]
  (cond-> [[id :comment/on on]
           [id :comment/author author]
           [id :comment/body body]
           [id :comment/created-at created-at]]
    (some? anchor)   (conj [id :comment/anchor anchor])
    (some? side)     (conj [id :comment/side side])
    (some? resolved) (conj [id :comment/resolved resolved])))

(defn datoms->comment [datoms id]
  (cond-> {:id id
           :on         (v-one datoms id :comment/on)
           :author     (v-one datoms id :comment/author)
           :body       (v-one datoms id :comment/body)
           :created-at (v-one datoms id :comment/created-at)}
    (v-one datoms id :comment/anchor)   (assoc :anchor (v-one datoms id :comment/anchor))
    (v-one datoms id :comment/side)     (assoc :side (v-one datoms id :comment/side))
    (some? (v-one datoms id :comment/resolved)) (assoc :resolved (v-one datoms id :comment/resolved))))
