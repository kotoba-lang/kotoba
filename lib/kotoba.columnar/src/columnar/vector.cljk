(ns columnar.vector
  "A typed column vector: values, and a validity mask beside them.

  The mask is the whole point. A null stored *in* the values — as nil, as
  NaN, as a sentinel like -1 or \"\" — is a value that has to be checked for
  at every operator, and the check is different per type. Worse, the sentinel
  is eventually a legitimate value: someone's `price` really is 0, someone's
  `note` really is the empty string. Keeping validity in a parallel structure
  means every operator handles nulls the same way, once, and no value is
  reserved.

  The representation here is a plain boolean vector, which is one entry per
  row rather than one bit. That is a naive encoding of a correct design: the
  decision that matters is mask-beside-values, and swapping the boolean
  vector for a bitset is a change local to this namespace. It is stated
  rather than left to be discovered from a memory profile."
  (:refer-clojure :exclude [count]))

(defn column
  "A column from `values`, where `nil` means null.

  Use this when the data already uses nil for absent. `of` is the explicit
  form for data where nil is a legitimate value."
  [type values]
  {:type type
   :values (vec values)
   :valid (vec (map some? values))})

(defn of
  "A column from `values` and an explicit validity mask.

  Required when nil is a real value in the data — the only way to say
  \"present, and it is nil\"."
  [type values valid]
  (let [values (vec values) valid (vec valid)]
    (when-not (= (clojure.core/count values) (clojure.core/count valid))
      (throw (ex-info "validity mask length must match values"
                      {:type :columnar/mask-length-mismatch
                       :values (clojure.core/count values)
                       :valid (clojure.core/count valid)})))
    {:type type :values values :valid valid}))

(defn count [col] (clojure.core/count (:values col)))

(defn valid-at? [col i] (boolean (nth (:valid col) i nil)))

(defn value-at
  "The value at `i`, or nil when null. A caller that must tell null from a
  nil value uses `valid-at?`."
  [col i]
  (when (valid-at? col i) (nth (:values col) i)))

(defn null-count [col]
  (reduce (fn [n v] (if v n (inc n))) 0 (:valid col)))

(defn take-rows
  "The column narrowed to `indices`, in that order. Selection is how a filter
  result travels between operators: it names rows rather than copying every
  column, so a predicate on one column does not cost a copy of the others."
  [col indices]
  {:type (:type col)
   :values (mapv #(nth (:values col) %) indices)
   :valid (mapv #(nth (:valid col) %) indices)})
