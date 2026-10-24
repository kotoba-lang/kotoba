(ns mokuroku.query
  "Sort, filter, group and search — the four things every one of these apps
  does to its items, written once.

  The whole namespace is pure and total. Two properties are load-bearing and
  are asserted in the test suite:

  1. **Determinism.** The same items and the same query produce the same order,
     every time, on every runtime. Attribute comparators are not total on their
     own (ties, mixed types, missing values), so every comparison falls through
     to `mokuroku.item/id-key`.
  2. **Totality.** No input throws. A filter against a missing attribute, a
     sort on a column of mixed strings and numbers, a search over an item with
     no attributes — each has a defined answer. An app browsing a live host
     source cannot afford a comparator that throws on the one row where the
     provider returned nil."
  (:require [kotoba.lang.text :as str]
            [mokuroku.item :as item]))

;; ---------------------------------------------------------------- ordering

(defn- type-rank
  "Order across types so a mixed column still has a total order.

  Missing values rank last here, and `comparator-for` additionally keeps them
  last under `:desc` — see the note there."
  [v]
  (cond
    (nil? v) 4
    (boolean? v) 0
    (number? v) 1
    (string? v) 2
    (keyword? v) 3
    :else 5))

(defn- same-rank-compare [a b]
  (cond
    (boolean? a) (compare a b)
    (number? a) (compare a b)
    (string? a) (compare (str/lower a) (str/lower b))
    (keyword? a) (compare (str (symbol a)) (str (symbol b)))
    :else (compare (pr-str a) (pr-str b))))

(defn compare-values
  "A total order over attribute values of any mix of scalar types."
  [a b]
  (let [ra (type-rank a) rb (type-rank b)]
    (if (= ra rb)
      (if (nil? a) 0 (same-rank-compare a b))
      (compare ra rb))))

(defn- key-fn [k]
  (case k
    :label :item/label
    :kind :item/kind
    :id :item/id
    (fn [it] (item/attr it k))))

(defn- extract [k it]
  (let [f (key-fn k)]
    (if (keyword? f) (get it f) (f it))))

(defn comparator-for
  "Build a comparator from a sort spec: a vector of `[attribute-key direction]`
  pairs, most significant first. Direction is `:asc` or `:desc`.

  The id tiebreak is appended unconditionally. It is not optional: without it
  two items with equal sort keys order by whatever the underlying collection
  did, and the same query answers differently on JVM and on ClojureScript.

  **Absent values are appended, not ranked, and this is direction-independent.**
  Negating the whole comparison under `:desc` — the obvious implementation —
  moves rows with no value to the *top*, which is the one place they must
  never be: `fullest volume first` would lead with the volume whose capacity
  could not be read, and `busiest process first` with the process whose CPU is
  unknown. The direction orders the values that exist; the ones that do not
  exist go last either way."
  [sort-spec]
  (fn [a b]
    (loop [[[k dir] & more] (seq sort-spec)]
      (if (nil? k)
        (compare (item/id-key a) (item/id-key b))
        (let [va (extract k a)
              vb (extract k b)
              c (cond
                  (and (nil? va) (nil? vb)) 0
                  (nil? va) 1
                  (nil? vb) -1
                  :else (let [c (compare-values va vb)]
                          (if (= :desc dir) (- c) c)))]
          (if (zero? c) (recur more) c))))))

;; ----------------------------------------------------------------- filters

(def operators
  "Filter operators. `:matches` is substring, case-insensitive; it is the only
  one that coerces, and it coerces to string on both sides."
  #{:= :not= :< :<= :> :>= :matches :in :exists})

(defn- passes? [it [k op v]]
  (let [x (extract k it)]
    (case op
      := (= x v)
      :not= (not= x v)
      :< (neg? (compare-values x v))
      :<= (not (pos? (compare-values x v)))
      :> (pos? (compare-values x v))
      :>= (not (neg? (compare-values x v)))
      :in (contains? (set v) x)
      :exists (if v (some? x) (nil? x))
      :matches (and (some? x)
                    (str/includes? (str/lower (str x))
                                   (str/lower (str v))))
      ;; An unknown operator excludes nothing. Silently dropping every row
      ;; because of a typo in a filter spec is worse than showing them all;
      ;; `problems` reports the typo.
      true)))

(defn- matches-text? [text it]
  (let [needle (str/lower (str/trim (str text)))]
    (or (str/blank? needle)
        (boolean (some #(str/includes? (str/lower %) needle)
                       (item/searchable-text it))))))

;; ------------------------------------------------------------------ query

(def default-query
  {:query/text ""
   :query/filters []
   :query/sort [[:label :asc]]
   :query/group-by nil
   :query/limit nil})

(defn query [m] (merge default-query m))

(defn problems
  "Report a query that will not do what its author meant, without refusing to
  run it. DESCRIPTOR may be nil when the source is unknown."
  ([q] (problems q nil))
  ([q descriptor]
   (let [known (when descriptor
                 (into #{:label :kind :id}
                       (map :attribute/key (:source/attributes descriptor))))]
     (vec
      (concat
       (for [[k op _] (:query/filters q)
             :when (not (contains? operators op))]
         {:query/problem :unknown-operator :query/key k :query/operator op})
       (for [[k op _] (:query/filters q)
             :when (and known (not (contains? known k)))]
         {:query/problem :unknown-attribute :query/key k :query/operator op})
       (for [[k _] (:query/sort q)
             :when (and known (not (contains? known k)))]
         {:query/problem :unknown-sort-attribute :query/key k})
       (when (and known (:query/group-by q)
                  (not (contains? known (:query/group-by q))))
         [{:query/problem :unknown-group-attribute
           :query/key (:query/group-by q)}]))))))

(defn- group [items k]
  (when k
    (->> items
         (group-by #(extract k %))
         (sort-by key compare-values)
         (mapv (fn [[v members]]
                 {:group/key k
                  :group/value v
                  :group/count (count members)
                  :group/item-ids (mapv :item/id members)})))))

(defn run
  "Apply a query to items.

  Returns `{:result/items :result/groups :result/total :result/matched
  :result/truncated? :result/problems}`.

  `:result/total` is the input size and `:result/matched` the post-filter size,
  both before any limit. A view that shows only `(count :result/items)` after a
  limit would tell the user 200 files exist when 40,000 do."
  ([items q] (run items q nil))
  ([items q descriptor]
   (let [q (query q)
         matched (->> items
                      (filter (fn [it]
                                (and (matches-text? (:query/text q) it)
                                     (every? #(passes? it %) (:query/filters q)))))
                      (sort (comparator-for (:query/sort q)))
                      vec)
         limit (:query/limit q)
         shown (if (and limit (< limit (count matched)))
                 (subvec matched 0 limit)
                 matched)]
     {:result/items shown
      :result/groups (group shown (:query/group-by q))
      :result/total (count items)
      :result/matched (count matched)
      :result/truncated? (< (count shown) (count matched))
      :result/problems (problems q descriptor)})))

(defn ordered-ids [result]
  (mapv :item/id (:result/items result)))
