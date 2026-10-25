(ns dicom.file-meta
  "The Part 10 file header — PS3.10 §7.1: a 128-byte preamble, the 4-byte
  magic `\"DICM\"`, and the File Meta Information group (tag group
  `0002`).

  Two things about this header are fixed regardless of what the rest of
  the file negotiates:

  1. **The preamble's 128 bytes are application-defined and this library
     does not interpret them** — historically used for a bootable/
     dual-format hint, PS3.10 says only that they \"may be used\" and
     defines no content. `decode-header` returns them uninspected so a
     caller who cares can look; `encode-header` writes 128 zero bytes if
     the caller doesn't supply their own.
  2. **Group `0002` is always Explicit VR Little Endian, no matter what
     Transfer Syntax UID (`0002,0010`) the file meta group itself is
     about to declare for the *main* dataset that follows it** (PS3.10
     §7.1). A decoder that reads the file meta group using whatever
     transfer syntax the *previous* file happened to use, or that
     bootstraps by guessing, will misparse the very element that would
     have told it the right answer. This is the sort of self-referential
     trap that only shows up once you've read the actual normative text:
     the fixed point has to be fixed by fiat, and PS3.10 fiats it here."
  (:require [dicom.bytes :as b]
            [dicom.tag :as tag]
            [dicom.dataset :as ds]))

(def preamble-length 128)
(def magic [0x44 0x49 0x43 0x4D]) ; "DICM"

(def file-meta-syntax
  "Group 0002 is always read/written in this fixed syntax — see the
  namespace docstring."
  {:vr-mode :explicit :endian :little})

(defn decode-header
  "Decode the preamble + magic + File Meta Information group from `bs`
  starting at `offset` (normally 0). Returns
  `[:ok {:preamble <128 bytes> :elements [...] } next-offset]` or
  `[:error reason]`.

  Group length comes from `(0002,0000)` File Meta Information Group
  Length — a `UL` giving the exact byte count of every group-0002
  element *after* this one. A file with that value wrong, or missing,
  cannot be safely bounded (reading until \"the next group changes\"
  requires already parsing lookahead this library won't do silently) and
  is refused rather than guessed at."
  [bs offset]
  (if (< (- (count bs) offset) (+ preamble-length (count magic)))
    [:error :dicom/truncated-file]
    (let [preamble (b/slice bs offset preamble-length)
          magic-off (+ offset preamble-length)
          magic-bytes (b/slice bs magic-off (count magic))]
      (if (not= magic-bytes magic)
        [:error :dicom/bad-magic]
        (let [ds-off (+ magic-off (count magic))
              gl-result (ds/decode-element bs ds-off file-meta-syntax)]
          (if (= (first gl-result) :error)
            gl-result
            (let [[gl-element voff] gl-result]
              (if (not= (:tag gl-element) tag/file-meta-information-group-length)
                [:error :dicom/missing-group-length]
                (let [group-length (first (:value gl-element))
                      end (+ voff group-length)
                      rest-result (ds/decode-dataset-bounded bs voff end file-meta-syntax)]
                  (if (= (first rest-result) :error)
                    rest-result
                    (let [[elements off2] rest-result]
                      [:ok {:preamble preamble
                            :elements (into [gl-element] elements)}
                       off2])))))))))))

(defn find-element
  "The first element in a decoded file-meta `:elements` list matching
  `tag`, or `nil`."
  [elements tag]
  (first (filter #(= (:tag %) tag) elements)))

(defn transfer-syntax-uid
  "The `(0002,0010)` value out of a decoded file-meta map, as a plain
  UID string, or `nil`. `UI` is a VR that generally permits VM > 1 (so
  `dicom.element/decode-text` returns a vector for it), but this
  specific data element is defined with VM = 1 (PS3.10 §7.1) — this
  function is the place that VM=1-ness is asserted, by taking the first
  (only) component."
  [{:keys [elements]}]
  (when-let [el (find-element elements tag/transfer-syntax-uid)]
    (first (:value el))))

(defn encode-header
  "Encode `{:preamble <optional 128 bytes> :elements [...]}` (the
  `:elements` list must include a correct `(0002,0000)` Group Length —
  see `with-group-length`) back to Part 10 file-meta bytes: preamble +
  magic + the group-0002 elements. Returns a byte vector or
  `[:error reason]`."
  [{:keys [preamble elements]}]
  (let [preamble (or preamble (vec (repeat preamble-length 0)))]
    (if (not= (count preamble) preamble-length)
      [:error :dicom/bad-preamble-length]
      (let [body (ds/encode-dataset elements file-meta-syntax)]
        (if (and (vector? body) (= (first body) :error))
          body
          (into (into preamble magic) body))))))

(defn with-group-length
  "Given the group-0002 elements *other than* `(0002,0000)` itself,
  compute and prepend a correct Group Length element. This is the
  encode-side counterpart of the self-referential rule in the namespace
  docstring: Group Length must be **the encoded byte length of every
  element that follows it**, which can only be known after those
  elements are themselves encoded once."
  [elements]
  (let [body (ds/encode-dataset elements file-meta-syntax)]
    (if (and (vector? body) (= (first body) :error))
      body
      (into [{:tag tag/file-meta-information-group-length
              :vr :UL
              :value [(count body)]}]
            elements))))
