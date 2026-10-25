(ns dicom.pixel-data
  "Encapsulated Pixel Data framing — PS3.5 Annex A.4.

  When Pixel Data (`7FE0,0010`) holds *compressed* pixels (JPEG, JPEG
  2000, RLE, ...) rather than a flat native array, it is not one value —
  it is written with **undefined length** and VR `OB`, and its \"value\"
  is a sequence of Item pseudo-elements exactly like an undefined-length
  `SQ`'s items, except an item here holds **raw fragment bytes**, not a
  nested dataset:

  ```
  (7FE0,0010) OB, length = 0xFFFFFFFF        <- the Pixel Data element itself
    (FFFE,E000) length = N0    <- Item 0: the Basic Offset Table (may be 0 bytes)
    (FFFE,E000) length = N1    <- Item 1: fragment
    (FFFE,E000) length = N2    <- Item 2: fragment (a frame may span > 1 item)
    ...
    (FFFE,E0DD) length = 0     <- Sequence Delimitation Item, ends the value
  ```

  This is deliberately **not** built on `dicom.dataset`'s item decoder —
  that decoder's items contain nested *elements*; these items contain
  opaque bytes (a JPEG/RLE fragment), and decoding them as if they held
  DICOM elements would either fail outright or, worse, occasionally
  \"succeed\" by coincidentally matching a valid-looking tag inside
  compressed image data. Two structurally identical framings (item +
  length + delimiter) with two different payload interpretations is
  exactly the kind of thing that gets collapsed into one code path by
  someone reusing \"the sequence parser\" — this module exists so that
  reuse doesn't happen.

  The **Basic Offset Table** (the first item) holds, for a multi-frame
  encapsulated image, the byte offset of each frame's first fragment
  relative to the start of the first fragment's item — `[]`/zero-length
  is legal and means \"offset table not provided\"."
  (:require [dicom.bytes :as b]
            [dicom.tag :as tag]
            [dicom.vr :as vr]))

(defn read-fragment-item
  "One `tag + length32 + raw-bytes` item. Returns `[{:length :bytes}
  next-offset]` or `[:error :dicom/expected-item-tag]`."
  [bs offset order]
  (let [[t off] (tag/read-tag bs offset order)]
    (if (not= t tag/item)
      [:error :dicom/expected-item-tag]
      (let [[length off] (b/read-u32 bs off order)
            data (b/slice bs off length)]
        [{:length length :bytes data} (+ off length)]))))

(defn decode-encapsulated
  "Decode the undefined-length value of an encapsulated Pixel Data
  element, starting right after its `length = 0xFFFFFFFF` field. Returns
  `[:ok {:offset-table <bytes> :fragments [<bytes> ...]} next-offset]` or
  `[:error reason]`. The first item is always the Basic Offset Table
  (possibly zero-length); every item after it, up to the Sequence
  Delimitation Item, is a fragment."
  [bs offset order]
  (let [ot-result (read-fragment-item bs offset order)]
    (if (= (first ot-result) :error)
      ot-result
      (let [[{:keys [bytes]} off] ot-result]
        (loop [off off fragments []]
          (let [[t toff] (tag/read-tag bs off order)]
            (if (= t tag/sequence-delimitation)
              (let [[_len off2] (b/read-u32 bs toff order)]
                [:ok {:offset-table bytes :fragments fragments} off2])
              (let [frag-result (read-fragment-item bs off order)]
                (if (= (first frag-result) :error)
                  frag-result
                  (let [[{:keys [bytes]} off2] frag-result]
                    (recur off2 (conj fragments bytes))))))))))))

(defn encode-encapsulated
  "Encode `{:offset-table <bytes> :fragments [<bytes> ...]}` back to the
  undefined-length item-framed wire form, *not including* the leading
  `(7FE0,0010) OB reserved length=0xFFFFFFFF` header — callers combine
  this with that header themselves (see `dicom.dataset`'s element
  encoder, which this module intentionally does not depend on, to avoid
  a namespace cycle: `dataset` -> `pixel-data` would be fine but
  `pixel-data` -> `dataset` would not, since `dataset` already needs to
  special-case this tag)."
  [{:keys [offset-table fragments]} order]
  (let [item (fn [bs] (into (into (tag/write-tag tag/item order)
                                   (b/write-u32 (count bs) order))
                             bs))
        delim (into (tag/write-tag tag/sequence-delimitation order)
                     (b/write-u32 0 order))]
    (vec (concat (item (or offset-table []))
                 (mapcat item fragments)
                 delim))))

(defn encapsulated?
  "True when `element` (a decoded Pixel Data header, before its value is
  read) is written in encapsulated form: `OB`/`OW` with undefined
  length."
  [{:keys [tag vr length]}]
  (and (= tag tag/pixel-data)
       (contains? #{:OB :OW} vr)
       (= length vr/undefined-length)))
