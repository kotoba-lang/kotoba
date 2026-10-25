(ns dicom.file
  "Top-level Part 10 file decode/encode: preamble + magic + file meta
  group (always Explicit VR Little Endian) + main dataset (in whichever
  transfer syntax the file meta group's `(0002,0010)` names).

  This is the one function most callers want, and it exists to make the
  two-phase nature of a DICOM file impossible to skip by accident: you
  cannot know how to read the main dataset until you have already read
  the file meta group *in a different, fixed syntax* to find out
  (`dicom.file-meta`'s docstring covers why this isn't circular — the
  meta group's own syntax is nailed down by the standard, not
  negotiated)."
  (:require [dicom.file-meta :as fm]
            [dicom.dataset :as ds]
            [dicom.transfer-syntax :as ts]
            [dicom.tag :as tag]))

(defn decode
  "Decode a full Part 10 file. Returns `[:ok {:preamble :file-meta
  :transfer-syntax-uid :dataset} ]` or `[:error reason]`."
  [bs]
  (let [meta-result (fm/decode-header bs 0)]
    (if (= (first meta-result) :error)
      meta-result
      (let [[_ok file-meta ds-offset] meta-result
            uid (fm/transfer-syntax-uid file-meta)]
        (if (nil? uid)
          [:error :dicom/missing-transfer-syntax]
          (let [syntax-result (ts/syntax-for uid)]
            (if (= (first syntax-result) :error)
              syntax-result
              (let [[_ok syntax] syntax-result
                    dataset-result (ds/decode-dataset bs ds-offset syntax)]
                (if (= (first dataset-result) :error)
                  dataset-result
                  (let [[elements _off] dataset-result]
                    [:ok {:preamble (:preamble file-meta)
                          :file-meta (:elements file-meta)
                          :transfer-syntax-uid uid
                          :dataset elements}]))))))))))

(defn encode
  "Encode `{:preamble <opt> :file-meta [...without group length...]
  :transfer-syntax-uid \"...\" :dataset [...]}` back to Part 10 bytes.
  `:file-meta` must include `(0002,0010)` Transfer Syntax UID matching
  `:transfer-syntax-uid`, but need not include `(0002,0000)` Group
  Length — `dicom.file-meta/with-group-length` computes it. Returns a
  byte vector or `[:error reason]`."
  [{:keys [preamble file-meta transfer-syntax-uid dataset]}]
  (let [syntax-result (ts/syntax-for transfer-syntax-uid)]
    (if (= (first syntax-result) :error)
      syntax-result
      (let [[_ok syntax] syntax-result
            file-meta-result (if (some #(= (:tag %) tag/file-meta-information-group-length) file-meta)
                                file-meta
                                (fm/with-group-length file-meta))]
        (if (and (vector? file-meta-result) (keyword? (first file-meta-result))
                 (= (first file-meta-result) :error))
          file-meta-result
          (let [header-result (fm/encode-header {:preamble preamble :elements file-meta-result})]
            (if (and (vector? header-result) (keyword? (first header-result))
                     (= (first header-result) :error))
              header-result
              (let [dataset-bytes (ds/encode-dataset dataset syntax)]
                (if (and (vector? dataset-bytes) (keyword? (first dataset-bytes))
                         (= (first dataset-bytes) :error))
                  dataset-bytes
                  (into header-result dataset-bytes))))))))))
