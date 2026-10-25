(ns pades.core
  "PAdES (ETSI EN 319 142) baseline signatures — a **writer**, by incremental
  update. Portable `.cljc`.

  ## Why a writer, when the evidence record is already better

  `cloud.itonami.app.esign` produces an evidence record that is more precise
  than a signed PDF: exhaustive outline, frozen status list, DID-named signers.
  A counterparty will not run its verifier. They will open a PDF in Acrobat and
  look for the blue bar.

  So this exists for exactly one job — **hand the outside world something their
  software already checks** — and it does not replace the record. The record
  stays the authority; the PDF is the export.

  ## Incremental update, and the property that makes it a signature at all

  A signed PDF is not rewritten. Everything already in the file stays at the
  byte offset it had, and the signature is **appended**: new objects, a new
  cross-reference section, a new trailer pointing back at the previous one. The
  original bytes are inside the signed range, so a verifier can show that the
  document as-signed is a prefix of the file it is holding.

  Rewriting the file instead — even to produce identical semantics — would mean
  the signature covers bytes the author never saw. This namespace therefore
  never reorders, renumbers or re-serializes an existing object.

  ## /ByteRange and the gap, which is where implementations go wrong

      /ByteRange [0 a b c]

  covers `[0,a)` and `[b,b+c)`. The gap between them is the `/Contents
  <…hex…>` string **including its angle brackets**, because that is the one
  thing that cannot be inside its own digest.

  Two failures follow from getting this wrong and both are silent:

  1. **A gap that does not exactly cover the placeholder** leaves signature
     bytes inside the signed range, or document bytes outside it. Acrobat
     reports the first as invalid and — worse — the second as *valid*, over a
     region an attacker can edit.
  2. **Numbers that change width when filled in** move every following byte.
     So the placeholders are written zero-padded to a fixed width and patched in
     place, never re-rendered. `sign` asserts the length is unchanged after
     patching rather than trusting that it is.

  ## What this is and is not

  **B-B** (basic): the CMS signature and the fields a viewer needs. NOT B-T
  (`signature-timestamp` embeds one, but placing it in the unsigned attributes
  of the CMS is the caller's step), and NOT B-LT/B-LTA, which need a DSS and
  document timestamps. `profile` reports which one a produced file is, so that
  nothing downstream claims a level it did not build."
  (:require [asn1.core :as asn1]
            [kotoba.lang.text :as str]
            [pdf.core :as pdf]))

(defn fail! [code message data]
  (throw (ex-info message (assoc data :type code))))

(def default-signature-bytes
  "How many bytes to reserve for the CMS blob.

  16 KiB. A P-256 signature with two certificates is around 2 KiB and an RSA-4096
  chain with a timestamp can pass 10 KiB, so this is generous on purpose: running
  out means re-signing, and the reservation costs disk rather than correctness.
  `sign` refuses rather than truncating if the CMS does not fit — a truncated
  signature is a file that looks signed."
  16384)

;; ── reading enough of the original ───────────────────────────────────────────

(defn- ->text
  "Bytes as Latin-1 text.

  Latin-1 because it is the only encoding where one byte is one character in
  both directions — offsets computed on the text are byte offsets, which is the
  entire requirement here. Decoding as UTF-8 would fold multi-byte sequences and
  silently move every offset after the first non-ASCII byte in a stream."
  [data]
  (let [ints (asn1/->ints data)]
    #?(:clj (String. (byte-array (map unchecked-byte ints)) "ISO-8859-1")
       :cljs (apply str (map js/String.fromCharCode ints)))))

(defn- text->
  "Latin-1 text back to bytes.

  `.charCodeAt` on `:cljs` and not `int`. A String iterates as Characters on the
  JVM and as one-character STRINGS on ClojureScript, where `int` parses them as
  numbers — so `\"%\"` became 0 and `\"4\"` became 4, and every PDF this produced
  on cljs was mostly zeros. The same mistake `pdf.core/write-document` had; found
  in both by running a portable job for the first time."
  [s]
  (mapv (fn [c] (bit-and #?(:clj (int c) :cljs (.charCodeAt c 0)) 0xff)) s))

(defn- last-startxref [text]
  (let [i (str/last-index-of text "startxref")]
    (when-not i
      (fail! :pades/not-a-pdf "startxref がありません — PDF ではないか壊れています" {}))
    (let [tail (subs text i)]
      (or (some-> (re-find #"startxref\s+(\d+)" tail) second parse-long)
          (fail! :pades/no-startxref "startxref の値を読めません" {})))))

(defn document-facts
  "What an incremental update needs from the file it is appending to.

  `:next-object` is derived from the trailer's `/Size` when there is one and
  from the highest `N 0 obj` otherwise. Scanning is the fallback rather than the
  rule: `/Size` is what the spec says an update must respect, and a file whose
  `/Size` is wrong is one this refuses to guess about quietly."
  [data]
  (let [text (->text data)
        ;; First, because it is the "is this a PDF" question. Reading /Root out
        ;; of something with no trailer produces a refusal about the wrong thing.
        startxref (last-startxref text)
        size (some-> (re-find #"/Size\s+(\d+)" (subs text (max 0 (- (count text) 2048))))
                     second parse-long)
        highest (->> (re-seq #"(?m)^(\d+)\s+0\s+obj" text)
                     (map (comp parse-long second))
                     (reduce max 0))
        root (or (second (re-find #"/Root\s+(\d+)\s+0\s+R" text))
                 (fail! :pades/no-root "trailer に /Root がありません" {}))]
    {:length (count text)
     :startxref startxref
     :root-object (parse-long root)
     :next-object (max (inc highest) (or size 1))
     :page-object (some-> (re-find #"(?m)^(\d+)\s+0\s+obj\s*<<[^>]*/Type\s*/Page[^s]" text)
                          second parse-long)}))

;; ── building the appended section ────────────────────────────────────────────

(def ^:private byte-range-width 10)

(defn- pad-number [n]
  (let [s (str n)]
    (str (apply str (repeat (max 0 (- byte-range-width (count s))) "0")) s)))

(defn- object [n body] (str n " 0 obj\n" body "\nendobj\n"))

(defn- signature-dictionary
  [{:keys [name reason location contact-info signing-time-pdf placeholder-hex]}]
  (str "<< /Type /Sig /Filter /Adobe.PPKLite /SubFilter /ETSI.CAdES.detached\n"
       ;; Written with fixed-width zero padding and patched in place. Re-rendering
       ;; the numbers after they are known would change their width and move every
       ;; byte after them — including the ones being signed.
       "/ByteRange [" (pad-number 0) " " (pad-number 0) " "
       (pad-number 0) " " (pad-number 0) "]\n"
       "/Contents <" placeholder-hex ">\n"
       (when name (str "/Name (" (pdf/escape-text name) ")\n"))
       (when reason (str "/Reason (" (pdf/escape-text reason) ")\n"))
       (when location (str "/Location (" (pdf/escape-text location) ")\n"))
       (when contact-info (str "/ContactInfo (" (pdf/escape-text contact-info) ")\n"))
       (when signing-time-pdf (str "/M (" signing-time-pdf ")\n"))
       ">>"))

(defn pdf-date
  "An ISO instant as a PDF date string, `D:YYYYMMDDHHmmSSZ`.

  A conversion and not a clock: the caller supplies the instant, so a signature's
  `/M` is the time the caller chose and can reproduce. `/M` is the signer's
  CLAIM in any case — an RFC 3161 timestamp is the evidence, and
  `kotoba-lang/org-ietf-rfc3161` is where that lives."
  [iso-instant]
  (when iso-instant
    (str "D:" (str/replace (subs iso-instant 0 19) #"[-:T]" "") "Z")))

(defn- appended-section
  "Everything after the original file, with placeholders still in it."
  [facts {:keys [field-name page-object] :as opts}]
  (let [sig-n (:next-object facts)
        field-n (inc sig-n)
        acroform-n (+ 2 sig-n)
        catalog-n (:root-object facts)
        placeholder (apply str (repeat (* 2 (:signature-bytes opts
                                                              default-signature-bytes))
                                       "0"))
        objects
        [[sig-n (signature-dictionary (assoc opts :placeholder-hex placeholder))]
         [field-n (str "<< /Type /Annot /Subtype /Widget /FT /Sig /T ("
                       (pdf/escape-text field-name) ")"
                       ;; A zero-size rectangle: an invisible signature field.
                       ;; A visible one needs an appearance stream, and an empty
                       ;; appearance stream renders as a blank box that reads as
                       ;; a broken signature rather than an absent one.
                       " /Rect [0 0 0 0] /F 132 /V " sig-n " 0 R"
                       (when page-object (str " /P " page-object " 0 R"))
                       " >>")]
         [acroform-n (str "<< /Fields [" field-n " 0 R] /SigFlags 3 >>")]
         ;; The catalog is REPLACED, not edited in place — that is what an
         ;; incremental update is. The original object keeps its bytes and its
         ;; offset; the new xref points readers at this one instead.
         [catalog-n (str "<< /Type /Catalog /Pages " (:pages-object facts 2)
                         " 0 R /AcroForm " acroform-n " 0 R >>")]]]
    {:objects objects
     :signature-object sig-n
     :placeholder-length (count placeholder)}))

(defn- xref-section
  "A classic cross-reference section for the appended objects, plus a trailer
  whose `/Prev` points at the previous one."
  [offsets facts next-size]
  (let [entries (sort-by first offsets)
        ;; One subsection per contiguous run of object numbers. A single
        ;; subsection spanning a gap would claim offsets for objects this update
        ;; did not write.
        runs (reduce (fn [acc [n off]]
                       (if (and (seq acc) (= (inc (first (last (last acc)))) n))
                         (conj (vec (butlast acc)) (conj (last acc) [n off]))
                         (conj acc [[n off]])))
                     [] entries)]
    (str "xref\n"
         (str/join
          (for [run runs]
            (str (ffirst run) " " (count run) "\n"
                 (str/join (for [[_ off] run]
                             (str (subs (str "0000000000" off)
                                        (- (count (str "0000000000" off)) 10))
                                  " 00000 n \n"))))))
         "trailer\n<< /Size " next-size " /Root " (:root-object facts)
         " 0 R /Prev " (:startxref facts) " >>\n")))

;; ── signing ──────────────────────────────────────────────────────────────────

(defn prepare
  "The file with the signature scaffolding appended and `/Contents` still a
  placeholder, plus the byte ranges to sign.

  Separated from `sign` because it is the half that has to be exactly right and
  is testable without a key: `:byte-range` either covers the whole file except
  the placeholder or it does not, and that is an arithmetic property."
  [data opts]
  (let [facts (document-facts data)
        original (->text data)
        {:keys [objects signature-object placeholder-length]}
        (appended-section facts (merge {:field-name "Signature1"
                                        :page-object (:page-object facts)}
                                       opts))
        ;; Offsets are absolute in the whole file, so the original's length is
        ;; the base for every appended object.
        [rendered offsets]
        (reduce (fn [[text offs] [n body]]
                  [(str text (object n body))
                   (conj offs [n (+ (count original) (count text))])])
                ["" []] objects)
        next-size (inc (reduce max (map first offsets)))
        xref-offset (+ (count original) (count rendered))
        tail (str (xref-section offsets facts next-size)
                  "startxref\n" xref-offset "\n%%EOF\n")
        whole (str original rendered tail)
        ;; The gap is the placeholder INCLUDING its angle brackets — the one
        ;; thing that cannot be inside its own digest.
        contents-start (str/index-of whole (str "/Contents <"))
        gap-start (+ contents-start (count "/Contents "))
        gap-end (+ gap-start placeholder-length 2)]
    (when-not contents-start
      (fail! :pades/no-contents "placeholder が見つかりません" {}))
    (let [byte-range [0 gap-start gap-end (- (count whole) gap-end)]
          patched (str/replace-first
                   whole
                   (re-pattern (str "/ByteRange \\[" (apply str (repeat 4 "\\d{10} ?"))
                                    "?\\]"))
                   (str "/ByteRange [" (str/join " " (map pad-number byte-range)) "]"))]
      ;; If patching changed the length, every offset after it moved and the
      ;; byte range now describes a file that does not exist. Asserted rather
      ;; than assumed: this is the failure that produces a plausible-looking
      ;; signed PDF nobody can verify.
      (when-not (= (count whole) (count patched))
        (fail! :pades/byte-range-width-changed
               "ByteRange の埋め込みで長さが変わりました（固定幅が壊れています）"
               {:before (count whole) :after (count patched)}))
      {:pades/prepared (text-> patched)
       :pades/byte-range byte-range
       :pades/gap [gap-start gap-end]
       :pades/signature-object signature-object
       :pades/placeholder-length placeholder-length})))

(defn signed-bytes
  "The bytes `/ByteRange` selects — what the CMS signature is over."
  [prepared]
  (let [ints (asn1/->ints (:pades/prepared prepared))
        [a b c d] (:pades/byte-range prepared)]
    (into (subvec ints a (+ a b)) (subvec ints c (+ c d)))))

(defn embed
  "Put `cms-der` into the reserved `/Contents`, padded with zeros.

  Refuses a CMS blob that does not fit rather than truncating. A truncated
  signature produces a file that looks signed and verifies nowhere, which is
  strictly worse than a failure at signing time."
  [prepared cms-der]
  (let [hex (asn1/hex cms-der)
        room (:pades/placeholder-length prepared)]
    (when (> (count hex) room)
      (fail! :pades/signature-too-large
             (str "CMS が予約領域を超えました: " (quot (count hex) 2) " > "
                  (quot room 2) " bytes。:signature-bytes を増やしてください。")
             {:needed (quot (count hex) 2) :reserved (quot room 2)}))
    (let [padded (str hex (apply str (repeat (- room (count hex)) "0")))
          ints (vec (asn1/->ints (:pades/prepared prepared)))
          [gap-start] (:pades/gap prepared)
          ;; +1 to step over the '<'.
          start (inc gap-start)]
      (assoc prepared
             :pades/signed (into (into (subvec ints 0 start) (text-> padded))
                                 (subvec ints (+ start room)))))))

(defn sign
  "A signed PDF, as an int vector.

    :sign-cms  (fn [signed-bytes] -> CMS SignedData DER)

  The CMS is built by the caller — `kotoba-lang/org-ietf-cms`'s
  `build-signed-data` with `:detached? true` and
  `:content-type (oid/dotted :data)` — because the private key belongs on the
  caller's side of this boundary, as everywhere else in this stack."
  [data {:keys [sign-cms] :as opts}]
  (let [prepared (prepare data opts)
        cms (sign-cms (signed-bytes prepared))
        embedded (embed prepared cms)]
    (when-not (= (count (:pades/prepared prepared)) (count (:pades/signed embedded)))
      (fail! :pades/length-changed
             "署名の埋め込みでファイル長が変わりました" {}))
    (:pades/signed embedded)))

(defn profile
  "Which PAdES baseline level a produced file actually reaches.

  Reported rather than asserted, because the higher levels need things this
  namespace does not build: B-T needs a signature timestamp in the CMS unsigned
  attributes, B-LT needs a DSS with certificates and revocation data, B-LTA
  needs a document timestamp on top. A file that says B-B is one nobody will
  mistake for archival."
  [{:keys [signature-timestamp? dss? document-timestamp?]}]
  (cond
    (and dss? document-timestamp?) :b-lta
    dss? :b-lt
    signature-timestamp? :b-t
    :else :b-b))
