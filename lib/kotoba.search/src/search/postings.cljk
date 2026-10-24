(ns search.postings
  "Inverted index: term → sorted doc-ids.

  `search.model/search` scores every document (O(corpus)). This namespace
  is the :search serving plane (ADR-2608170200): retrieve by posting
  intersection, then let the caller score the hit set. Rebuildable from
  documents or from datoms — delete the index and the datoms still exist.

  Temporary: tokenize stays a regex over Unicode ranges (`search.model`),
  which kotoba's compiler does not expose as a code-point primitive
  (see bounded_index.kotoba). Intersection of sorted id vectors is a
  candidate for `kotoba/pure`; this file remains the oracle until a
  parity test exists."
  (:require [search.model :as model]))

(defn tokenize [s]
  (model/tokenize s))

(defn intersect
  "AND of two sorted unique id vectors. Linear in |a|+|b|, independent
  of corpus size. Empty input is empty output — not a pass on a scan
  that never ran."
  [a b]
  (loop [i 0 j 0 out (transient [])]
    (if (or (>= i (count a)) (>= j (count b)))
      (persistent! out)
      (let [x (nth a i)
            y (nth b j)
            c (compare x y)]
        (cond
          (zero? c) (recur (inc i) (inc j) (conj! out x))
          (neg? c) (recur (inc i) j out)
          :else (recur i (inc j) out))))))

(defn union
  "OR of two sorted unique id vectors. Present so AND-vs-OR can be
  discriminated; search query is AND."
  [a b]
  (loop [i 0 j 0 out (transient [])]
    (cond
      (and (>= i (count a)) (>= j (count b))) (persistent! out)
      (>= i (count a)) (recur i (inc j) (conj! out (nth b j)))
      (>= j (count b)) (recur (inc i) j (conj! out (nth a i)))
      :else
      (let [x (nth a i)
            y (nth b j)
            c (compare x y)]
        (cond
          (zero? c) (recur (inc i) (inc j) (conj! out x))
          (neg? c) (recur (inc i) j (conj! out x))
          :else (recur i (inc j) (conj! out y)))))))

(defn- field-terms [doc]
  (concat (tokenize (or (:search/title doc) (:title doc) ""))
          (tokenize (or (:search/body doc) (:body doc) ""))
          (mapcat tokenize (or (:search/tags doc) (:tags doc) []))))

(defn- empty-index []
  {:search/type :postings
   :docs 0
   :postings {}
   :df {}})

(defn build
  "Build postings from documents. Each doc needs `:search/id` (or `:id`)."
  [docs]
  (if (empty? docs)
    (empty-index)
    (let [postings
          (persistent!
           (reduce
            (fn [m doc]
              (let [id (or (:search/id doc) (:id doc))]
                (reduce (fn [m term]
                          (let [ids (get m term [])]
                            (if (= id (peek ids))
                              m
                              (assoc! m term (conj ids id)))))
                        m
                        (field-terms doc))))
            (transient {})
            docs))
          sorted (into {} (map (fn [[t ids]] [t (vec (sort ids))])) postings)]
      {:search/type :postings
       :docs (count docs)
       :postings sorted
       :df (into {} (map (fn [[t ids]] [t (count ids)])) sorted)})))

(def datom-fields
  "Predicate names that become searchable text. Unknown predicates are
  ignored — they are not silently treated as the document id."
  #{:search/title :search/body :search/tags :title :body :tags
    "search/title" "search/body" "search/tags" "title" "body" "tags"})

(defn from-datoms
  "Rebuild postings from quads `{:s doc-id :p field :o text}`.
  Projection: the datoms are the source; this index is disposable."
  [quads]
  (if (empty? quads)
    (empty-index)
    (let [docs
          (reduce
           (fn [m {:keys [s p o]}]
             (if (contains? datom-fields p)
               (let [doc (get m s {:search/id s :search/title "" :search/body "" :search/tags []})
                     doc (cond
                           (contains? #{:search/title :title "search/title" "title"} p)
                           (assoc doc :search/title (str o))
                           (contains? #{:search/body :body "search/body" "body"} p)
                           (assoc doc :search/body (str o))
                           :else
                           (update doc :search/tags conj (str o)))]
                 (assoc m s doc))
               m))
           {}
           quads)]
      (build (vals docs)))))

(defn query
  "AND of tokenized `q` against posting lists.

  Always reports `:docs`, `:terms`, `:posting-entries-read`, `:hits`,
  `:reason`. Empty index / empty query / missing term are distinct
  reasons — none of them look like a successful scan of zero rows."
  [idx q]
  (let [docs (or (:docs idx) 0)
        terms (tokenize q)]
    (cond
      (zero? docs)
      {:hits [] :terms terms :docs 0 :posting-entries-read 0 :reason :empty-index}

      (empty? terms)
      {:hits [] :terms [] :docs docs :posting-entries-read 0 :reason :empty-query}

      :else
      (let [lists (mapv #(get-in idx [:postings %]) terms)
            read (reduce + 0 (map count (remove nil? lists)))]
        (if (some nil? lists)
          {:hits [] :terms terms :docs docs :posting-entries-read read :reason :no-match}
          {:hits (reduce intersect lists)
           :terms terms
           :docs docs
           :posting-entries-read read
           :reason :ok})))))
