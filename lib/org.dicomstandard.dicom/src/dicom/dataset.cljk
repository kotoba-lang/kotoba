(ns dicom.dataset
  "A **dataset** is an ordered list of data elements (PS3.5 §7.2). This
  namespace ties `dicom.element`'s single-element codec into the two
  places DICOM nests one dataset inside another:

  - a **Sequence (`SQ`)** element's value is zero or more **Items**
    (`FFFE,E000`), each of which contains a nested dataset;
  - an item, and a sequence itself, may have either a **defined length**
    (read exactly that many bytes) or an **undefined length**
    (`0xFFFFFFFF`, PS3.5 §7.5) — meaning \"keep reading elements until you
    hit a delimiter pseudo-element\", `FFFE,E00D` (Item Delimitation) for
    an item or `FFFE,E0DD` (Sequence Delimitation) for the sequence
    itself.

  **Item and delimiter pseudo-elements never carry a VR field, in either
  Explicit or Implicit VR** — they are always `tag(4) + length(4)`, flat,
  regardless of which header shape the surrounding dataset uses. A
  decoder that tries to read a 2-byte VR code off an item header will
  read two bytes of the item's own content instead and desynchronise
  from there on. This is the single most common bug in a first DICOM
  parsing attempt, and the reason `read-item-header` below is its own
  function rather than a special case bolted onto
  `dicom.element/read-explicit-header`.

  Encoding here always emits **defined lengths** (this library decodes
  undefined-length constructs but chooses, on encode, to always know and
  write the true length — a strictly more useful output, since anything
  that can parse defined-length DICOM can parse this and the reverse is
  not true) and, for a top-level dataset, always the header shape named
  by `(:vr-mode syntax)`, `:explicit` or `:implicit`."
  (:require [dicom.bytes :as b]
            [dicom.tag :as tag]
            [dicom.vr :as vr]
            [dicom.element :as el]
            [dicom.pixel-data :as pixel]))

(declare decode-element decode-item decode-items-bounded
         decode-items-until-sequence-delim decode-dataset-bounded
         decode-dataset-until-item-delim decode-sq-value
         encode-element-in-syntax encode-item encode-sq-value)

;; --- items ---------------------------------------------------------------

(defn read-item-header
  "`tag(4) + length(4)` — no VR, ever. Returns `[{:tag :length} offset]`."
  [bs offset order]
  (let [[t off] (tag/read-tag bs offset order)
        [length off] (b/read-u32 bs off order)]
    [{:tag t :length length} off]))

(defn decode-item
  "Decode one sequence Item: header, then its nested dataset (bounded by
  the item's own length, or — if undefined — read until an Item
  Delimitation pseudo-element). Returns `[{:tag :length :dataset} offset]`
  or `[:error reason]`."
  [bs offset syntax]
  (let [order (:endian syntax)
        [{:keys [tag length]} voff] (read-item-header bs offset order)]
    (if (not= tag tag/item)
      [:error :dicom/expected-item-tag]
      (if (= length vr/undefined-length)
        (let [result (decode-dataset-until-item-delim bs voff syntax)]
          (if (= (first result) :error)
            result
            (let [[elems off2] result]
              [{:tag tag :length length :dataset elems} off2])))
        (let [end (+ voff length)
              result (decode-dataset-bounded bs voff end syntax)]
          (if (= (first result) :error)
            result
            (let [[elems off2] result]
              [{:tag tag :length length :dataset elems} off2])))))))

(defn decode-items-bounded
  "Decode a run of Items occupying exactly `[offset, end)`."
  [bs offset end syntax]
  (loop [off offset items []]
    (cond
      (= off end) [items off]
      (> off end) [:error :dicom/item-overruns-container]
      :else
      (let [result (decode-item bs off syntax)]
        (if (= (first result) :error)
          result
          (let [[item off2] result]
            (recur off2 (conj items item))))))))

(defn decode-items-until-sequence-delim
  "Decode a run of Items terminated by a Sequence Delimitation
  pseudo-element (undefined-length `SQ`)."
  [bs offset syntax]
  (let [order (:endian syntax)]
    (loop [off offset items []]
      (let [[t toff] (tag/read-tag bs off order)]
        (if (= t tag/sequence-delimitation)
          (let [[_len off2] (b/read-u32 bs toff order)]
            [items off2])
          (let [result (decode-item bs off syntax)]
            (if (= (first result) :error)
              result
              (let [[item off2] result]
                (recur off2 (conj items item))))))))))

(defn decode-sq-value
  "Decode an `SQ` element's item list — bounded by `length`, or (if
  `length` is `dicom.vr/undefined-length`) by a Sequence Delimitation
  pseudo-element."
  [bs offset length syntax]
  (if (= length vr/undefined-length)
    (decode-items-until-sequence-delim bs offset syntax)
    (decode-items-bounded bs offset (+ offset length) syntax)))

;; --- datasets --------------------------------------------------------------

(defn decode-dataset-bounded
  "Decode elements from `offset` up to exclusive byte `end`."
  [bs offset end syntax]
  (loop [off offset elems []]
    (cond
      (= off end) [elems off]
      (> off end) [:error :dicom/element-overruns-container]
      :else
      (let [result (decode-element bs off syntax)]
        (if (= (first result) :error)
          result
          (let [[element off2] result]
            (recur off2 (conj elems element))))))))

(defn decode-dataset-until-item-delim
  "Decode elements from `offset` until an Item Delimitation
  pseudo-element (undefined-length Item)."
  [bs offset syntax]
  (let [order (:endian syntax)]
    (loop [off offset elems []]
      (let [[t toff] (tag/read-tag bs off order)]
        (if (= t tag/item-delimitation)
          (let [[_len off2] (b/read-u32 bs toff order)]
            [elems off2])
          (let [result (decode-element bs off syntax)]
            (if (= (first result) :error)
              result
              (let [[element off2] result]
                (recur off2 (conj elems element))))))))))

;; --- single element, tying value decode to header + SQ recursion --------

(defn decode-element
  "Decode one data element at `offset`, per `syntax`:
  `{:vr-mode :explicit|:implicit :endian :little|:big :dictionary <opt>}`.
  Returns `[element next-offset]` on success, `[:error reason]` on
  failure. `SQ` recurses into `decode-sq-value`. Encapsulated `OB`/`OW`
  Pixel Data with undefined length is a different framing (`dicom.pixel-
  data`, raw fragments rather than nested elements) — this function
  refuses that case explicitly (`:dicom/unexpected-undefined-length`)
  rather than misreading fragment bytes as a plain element value."
  [bs offset syntax]
  (let [order (:endian syntax)
        header-result (if (= (:vr-mode syntax) :explicit)
                         (el/read-explicit-header bs offset order)
                         (el/read-implicit-header bs offset order (:dictionary syntax)))]
    (if (= (first header-result) :error)
      header-result
      (let [[{:keys [tag vr length]} voff] header-result]
        (cond
          (= vr :SQ)
          (let [sq-result (decode-sq-value bs voff length syntax)]
            (if (= (first sq-result) :error)
              sq-result
              (let [[items off2] sq-result]
                [{:tag tag :vr vr :length length :value items} off2])))

          (pixel/encapsulated? {:tag tag :vr vr :length length})
          (let [px-result (pixel/decode-encapsulated bs voff order)]
            (if (= (first px-result) :error)
              px-result
              (let [[_ok value off2] px-result]
                [{:tag tag :vr vr :length length :value value} off2])))

          (= length vr/undefined-length)
          [:error :dicom/unexpected-undefined-length]

          :else
          (let [value-bytes (b/slice bs voff length)
                decoded (el/decode-value value-bytes vr order)]
            (if (= (first decoded) :error)
              decoded
              [{:tag tag :vr vr :length length :value (second decoded)}
               (+ voff length)])))))))

;; --- encode ----------------------------------------------------------------

(defn encode-item
  "Encode one item's nested dataset as `tag + length32(defined) + bytes`.
  Always a defined length on encode."
  [dataset syntax]
  (let [body (reduce (fn [acc element]
                        (if (and (vector? acc) (keyword? (first acc)) (= (first acc) :error))
                          acc
                          (let [r (encode-element-in-syntax element syntax)]
                            (if (and (vector? r) (= (first r) :error))
                              r
                              (into acc r)))))
                      []
                      dataset)]
    (if (and (vector? body) (= (first body) :error))
      body
      (let [order (:endian syntax)]
        (into (into (tag/write-tag tag/item order) (b/write-u32 (count body) order))
              body)))))

(defn encode-sq-value
  "Encode an `SQ` element's item list, each item with a defined length."
  [items syntax]
  (reduce (fn [acc item]
            (if (and (vector? acc) (= (first acc) :error))
              acc
              (let [r (encode-item (:dataset item) syntax)]
                (if (and (vector? r) (= (first r) :error))
                  r
                  (into acc r)))))
          []
          items))

(defn- encapsulated-value?
  [v] (and (map? v) (contains? v :fragments)))

(defn- encode-element-explicit
  "Encode one element in Explicit VR: `tag + VR + length(2|4) + value`."
  [{:keys [tag vr value]} syntax]
  (let [order (:endian syntax)]
    (cond
      (= vr :SQ)
      (let [body (encode-sq-value value syntax)]
        (if (and (vector? body) (= (first body) :error))
          body
          (into (into (into (into (tag/write-tag tag order) (vr/vr->code vr))
                             [0 0])
                       (b/write-u32 (count body) order))
                body)))

      (encapsulated-value? value)
      (let [body (pixel/encode-encapsulated value order)]
        (into (into (into (into (tag/write-tag tag order) (vr/vr->code vr))
                           [0 0])
                     (b/write-u32 vr/undefined-length order))
              body))

      :else
      (let [encoded (el/encode-value value vr order)]
        (if (= (first encoded) :error)
          encoded
          (let [body (second encoded)
                header (into (tag/write-tag tag order) (vr/vr->code vr))
                len-field (if (vr/short-form? vr)
                            (b/write-u16 (count body) order)
                            (into [0 0] (b/write-u32 (count body) order)))]
            (into (into header len-field) body)))))))

(defn- encode-element-implicit
  "Encode one element in Implicit VR: `tag + length32 + value`, no VR
  field."
  [{:keys [tag vr value]} syntax]
  (let [order (:endian syntax)
        encoded (cond
                  (= vr :SQ)
                  (let [body (encode-sq-value value syntax)]
                    (if (and (vector? body) (= (first body) :error))
                      body
                      [:ok body]))

                  (encapsulated-value? value)
                  [:ok (pixel/encode-encapsulated value order) :undefined]

                  :else (el/encode-value value vr order))]
    (if (= (first encoded) :error)
      encoded
      (let [body (second encoded)
            len (if (= (nth encoded 2 nil) :undefined)
                  (b/write-u32 vr/undefined-length order)
                  (b/write-u32 (count body) order))]
        (into (into (tag/write-tag tag order) len) body)))))

(defn encode-element-in-syntax
  "Encode one element per `(:vr-mode syntax)`."
  [element syntax]
  (if (= (:vr-mode syntax) :explicit)
    (encode-element-explicit element syntax)
    (encode-element-implicit element syntax)))

(defn encode-dataset
  "Encode an ordered list of elements in `syntax`. Returns a byte vector,
  or `[:error reason]` from the first element that fails to encode."
  [elements syntax]
  (reduce (fn [acc element]
            (if (and (vector? acc) (= (first acc) :error))
              acc
              (let [r (encode-element-in-syntax element syntax)]
                (if (and (vector? r) (= (first r) :error))
                  r
                  (into acc r)))))
          []
          elements))

(defn decode-dataset
  "Decode all elements in `bs` from `offset` to `(count bs)`, in `syntax`."
  [bs offset syntax]
  (decode-dataset-bounded bs offset (count bs) syntax))
