(ns dicom.transfer-syntax
  "Transfer Syntax UID -> `{:vr-mode :endian}`, PS3.5 Annex A.

  The Transfer Syntax UID (`0002,0010`, recorded in the File Meta group —
  see `dicom.file-meta`) is the single piece of out-of-band information a
  DICOM decoder needs before it can read the *main* dataset at all: it is
  the only place \"is this Explicit or Implicit VR, little or big endian\"
  is written down. Get it wrong and every subsequent read is off by
  however many bytes the VR/length field width differs by — which is
  large and immediate, unlike an off-by-one that limps along for a while.

  This library covers the base uncompressed/native transfer syntaxes,
  which is all it needs to determine wire *framing* — decoding this
  table's compressed entries' pixel payload (JPEG, JPEG 2000, RLE...) is
  explicitly out of scope (see README, \"Not here\"); this library only
  needs to know *that* a UID names an encapsulated-pixel-data syntax
  (all of them, other than the three uncompressed ones below, are), not
  how to inflate the compressed bytes.")

(def uncompressed
  "The three transfer syntaxes with native (non-encapsulated) Pixel Data,
  keyed by UID (PS3.5 Annex A.1)."
  {"1.2.840.10008.1.2"      {:vr-mode :implicit :endian :little :name "Implicit VR Little Endian"}
   "1.2.840.10008.1.2.1"    {:vr-mode :explicit :endian :little :name "Explicit VR Little Endian"}
   "1.2.840.10008.1.2.2"    {:vr-mode :explicit :endian :big    :name "Explicit VR Big Endian (retired)"}})

(def known-encapsulated
  "A representative sample of compressed/encapsulated transfer syntax
  UIDs (PS3.5 Annex A) — all of them are Explicit VR Little Endian
  *framing* (the compression happens inside the encapsulated Pixel Data
  fragments, which `dicom.pixel-data` frames without decompressing).
  Not exhaustive; `syntax-for` treats any UID not found in either map as
  unrecognised rather than guessing."
  {"1.2.840.10008.1.2.4.50" {:vr-mode :explicit :endian :little :name "JPEG Baseline (Process 1)"}
   "1.2.840.10008.1.2.4.70" {:vr-mode :explicit :endian :little :name "JPEG Lossless, Non-Hierarchical, First-Order Prediction"}
   "1.2.840.10008.1.2.4.90" {:vr-mode :explicit :endian :little :name "JPEG 2000 Image Compression (Lossless Only)"}
   "1.2.840.10008.1.2.4.91" {:vr-mode :explicit :endian :little :name "JPEG 2000 Image Compression"}
   "1.2.840.10008.1.2.5"    {:vr-mode :explicit :endian :little :name "RLE Lossless"}})

(def all (merge uncompressed known-encapsulated))

(defn syntax-for
  "`{:vr-mode :endian}` for a Transfer Syntax UID string, or
  `[:error :dicom/unknown-transfer-syntax]`. UIDs are matched exactly as
  given — a caller who has trimmed trailing NULs/padding first (as
  `dicom.file-meta` does) gets a match; one who hasn't will legitimately
  miss, since a stray padding byte makes it a different string."
  [uid]
  (if-let [entry (get all uid)]
    [:ok (select-keys entry [:vr-mode :endian])]
    [:error :dicom/unknown-transfer-syntax]))
