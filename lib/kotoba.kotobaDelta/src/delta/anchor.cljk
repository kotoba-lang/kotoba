(ns delta.anchor
  "⑱ Structural anchors for kotoba-delta ops (ADR-2607161325 / ADR-2607160005).

  DeltaDB's headline property is 'references survive as the code moves'.
  For a Clojure/EDN codebase the natural stable identity is not a line
  number but the DEFINITION: a top-level form's (kind, name) plus a content
  hash of its own text. An op anchored to a definition resolves to the same
  definition after unrelated code is inserted/removed elsewhere — a line
  anchor would break, this doesn't.

  Pure cljc. Uses a balanced-delimiter top-level splitter (robust across
  reader conditionals / metadata that trip a naive reader), not the full
  Clojure reader — we only need to locate top-level def forms."
  (:require [kotoba.lang.text :as str]))

(defn top-level-forms
  "Split source into top-level forms with their char offsets, skipping
  strings, chars, and ; line comments. -> [{:text :start :end} ...]"
  [src]
  (let [n (count src)]
    (loop [i 0 depth 0 start nil forms [] in-str? false esc? false]
      (if (>= i n)
        forms
        (let [c (nth src i)]
          (cond
            in-str? (recur (inc i) depth start forms
                           (not (and (not esc?) (= c \"))) (and (not esc?) (= c \\)))
            (= c \;) (recur (loop [j i] (if (or (>= j n) (= (nth src j) \newline)) j (recur (inc j))))
                            depth start forms false false)
            (= c \") (recur (inc i) depth (or start i) forms true false)
            (or (= c \() (= c \[) (= c \{))
            (recur (inc i) (inc depth) (if (zero? depth) i start) forms false false)
            (or (= c \)) (= c \]) (= c \}))
            (let [d (dec depth)]
              (if (zero? d)
                (recur (inc i) 0 nil (conj forms {:text (subs src start (inc i))
                                                  :start start :end (inc i)}) false false)
                (recur (inc i) d start forms false false)))
            :else (recur (inc i) depth start forms false false)))))))

(defn- def-form?
  "If a top-level form text is a (def...|defn...|defn-...|defmethod...) with a
  name, return {:kind :name}, else nil."
  [text]
  ;; optional metadata is only a ^-prefixed token; the name is the first
  ;; symbol after (defn / def / defn- / defmethod, possibly past one ^meta.
  (when-let [[_ kind nm] (re-find #"^\(\s*(def[a-z-]*|defmethod)\s+(?:\^\S+\s+)?([A-Za-z*!?<>=+_.-][\w*!?<>=+.:/-]*)" text)]
    {:kind kind :name nm}))

(defn definitions
  "All top-level definitions in src with content hashes. hash-fn injected.
  -> [{:kind :name :hash :start :end :text} ...]"
  [hash-fn src]
  (->> (top-level-forms src)
       (keep (fn [{:keys [text] :as f}]
               (when-let [d (def-form? text)]
                 (merge f d {:hash (hash-fn (str/trim text))}))))
       vec))

(defn anchor-of
  "Anchor for a definition by name. Carries :anchor/def-cid — the definition's
  content-addressed identity (hash of its canonical text), which is exactly
  what kotobase code_graph uses as a definition CID. So a delta op anchored to
  a definition and a code_graph definition of the same code share one CID: the
  op-log and the code graph join on :anchor/def-cid. hash-fn should be the
  same content-address function code_graph uses (sha256/CIDv1) for the CIDs to
  literally match."
  [hash-fn src def-name]
  (when-let [d (first (filter #(= def-name (:name %)) (definitions hash-fn src)))]
    {:anchor/kind (:kind d) :anchor/name (:name d)
     :anchor/hash (:hash d)            ;; back-compat alias
     :anchor/def-cid (:hash d)}))

(defn code-graph-ref
  "Map an anchor to a kotobase code_graph definition reference — the shape you
  look up in code_graph's `definitions` collection (store/-get s definitions
  cid). Lets 'which op touched this definition' be queried across the delta
  op-log AND the code graph via the shared definition CID."
  [anchor]
  {:code.definition/cid (:anchor/def-cid anchor)
   :code.definition/name (:anchor/name anchor)
   :code.definition/kind (:anchor/kind anchor)})

(defn resolve-anchor
  "Resolve an anchor against a (possibly changed) source.
  -> {:found? :status :start :end} where :status ∈
     :unchanged (name present, same hash)
     :moved     (name present, same hash, different offset — code moved)
     :edited    (name present, hash differs — definition body changed)
     :gone      (name absent)."
  [hash-fn src {:anchor/keys [name hash]} & [prev-start]]
  (if-let [d (first (filter #(= name (:name %)) (definitions hash-fn src)))]
    {:found? true
     :status (cond
               (not= hash (:hash d)) :edited
               (and prev-start (not= prev-start (:start d))) :moved
               :else :unchanged)
     :start (:start d) :end (:end d)}
    {:found? false :status :gone}))
