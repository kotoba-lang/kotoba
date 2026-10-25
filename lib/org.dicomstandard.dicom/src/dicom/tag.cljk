(ns dicom.tag
  "Data element tags — a `(group,element)` pair of unsigned 16-bit ints,
  each read in the transfer syntax's byte order (PS3.5 §7.1). On the wire
  the group comes first, then the element, each as its own 2-byte field —
  they are *two separate u16 reads*, not one u32 read, which matters for
  big-endian transfer syntaxes: reading the 4 bytes as one big-endian u32
  and splitting it in half happens to give the same answer as two
  big-endian u16 reads, but doing the equivalent for *little*-endian would
  swap group and element. Keeping them as two explicit `read-u16` calls
  makes that non-issue instead of a latent bug waiting for someone to
  \"simplify\" the big-endian path."
  (:require [dicom.bytes :as b]))

(defn read-tag
  "Read a tag from `bs` at `offset` in byte-`order`. Returns
  `[{:group g :element e} next-offset]`."
  [bs offset order]
  (let [[group off] (b/read-u16 bs offset order)
        [element off] (b/read-u16 bs off order)]
    [{:group group :element element} off]))

(defn write-tag
  "4-byte wire encoding of `{:group :element}` in byte-`order`."
  [{:keys [group element]} order]
  (into (b/write-u16 group order) (b/write-u16 element order)))

(defn ->hex
  "`(0008,0016)`-style display form, the way PS3.6 and every DICOM tool
  prints a tag."
  [{:keys [group element]}]
  #?(:clj (format "(%04X,%04X)" group element)
     :cljs (str "(" (-> (.toString group 16) (.toUpperCase) (#(.padStart % 4 "0")))
                "," (-> (.toString element 16) (.toUpperCase) (#(.padStart % 4 "0")))
                ")")))

;; Pseudo-element tags used to delimit undefined-length sequences and
;; encapsulated pixel-data fragments (PS3.5 §7.5). These are not real data
;; elements — they carry no VR on the wire (Implicit-VR-shaped: tag +
;; length32, always, in *both* Explicit and Implicit VR transfer syntaxes,
;; because the committee didn't want a VR field on a structural marker).
(def item {:group 0xFFFE :element 0xE000})
(def item-delimitation {:group 0xFFFE :element 0xE00D})
(def sequence-delimitation {:group 0xFFFE :element 0xE0DD})

(defn item-group?
  "True for any of the three FFFE-group structural pseudo-elements."
  [tag] (= (:group tag) 0xFFFE))

;; A handful of well-known tags this library's own file-meta and dataset
;; logic needs to recognise by name. Not a data dictionary (see
;; `dicom.dictionary`) — just the identifiers this code itself branches on.
(def file-meta-information-group-length {:group 0x0002 :element 0x0000})
(def transfer-syntax-uid {:group 0x0002 :element 0x0010})
(def media-storage-sop-class-uid {:group 0x0002 :element 0x0002})
(def media-storage-sop-instance-uid {:group 0x0002 :element 0x0003})
(def pixel-data {:group 0x7FE0 :element 0x0010})

(defn private?
  "Odd group numbers are reserved for private (implementation-specific)
  data elements (PS3.5 §7.8.1); even groups are the standard dictionary."
  [{:keys [group]}]
  (odd? group))
