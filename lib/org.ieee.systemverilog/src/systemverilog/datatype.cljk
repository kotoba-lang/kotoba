(ns systemverilog.datatype
  "SystemVerilog (IEEE 1800) 4-state vs 2-state data types, and the
  packed struct/union field-list model.

  Simplified subset: no real/shortreal, no unpacked arrays, no
  user-defined enum ranges beyond a plain type tag.")

(def four-state-types
  "4-state SystemVerilog types: bits can be 0, 1, X (unknown), or
  Z (high-impedance)."
  #{:logic :reg :wire :integer :time})

(def two-state-types
  "2-state SystemVerilog types: bits are only ever 0 or 1."
  #{:bit :byte :shortint :int :longint})

(defn four-state?
  [type-kw]
  (contains? four-state-types type-kw))

(defn two-state?
  [type-kw]
  (contains? two-state-types type-kw))

(defn signal
  "A typed signal declaration, e.g. a `logic [7:0] counter` net.
  `(signal :counter :logic 8)` => `{:name :counter :type :logic
  :width 8 :signed? false}`."
  ([name type width] (signal name type width false))
  ([name type width signed?]
   {:name name :type type :width width :signed? signed?}))

(defn packed-agg
  "A packed struct/union field-list model. `kind` is `:struct` or
  `:union`; `fields` is a seq of `{:name :type :width}` maps."
  [kind fields]
  {:kind kind :packed? true :fields (vec fields)})

(defn- field-width
  [{:keys [width]}]
  (or width 1))

(defn packed-width
  "Total bit width of a packed struct/union. A packed *struct* lays
  its fields out contiguously, so the total is the sum of member
  widths. A packed *union* overlays every member on the same bits, so
  the total is the widest member (SystemVerilog semantics, IEEE 1800
  clause 7.3)."
  [{:keys [kind fields]}]
  (let [widths (map field-width fields)]
    (case kind
      :union (if (seq widths) (apply max widths) 0)
      (reduce + 0 widths))))
