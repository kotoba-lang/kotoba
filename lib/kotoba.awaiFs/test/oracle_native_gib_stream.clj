;; One-off Otehon oracle for Native-produced 64-Pack 1 GiB fixture.
(require '[otehon.storage :as store] '[otehon.pack-store :as pack] '[awai.fs.car :as car])
(import '[java.nio.file Files Paths] '[java.security MessageDigest] '[java.util Arrays HexFormat])
(let [base (or (first *command-line-args*) (throw (ex-info "new output required" {})))
      manifest (Files/readAllBytes (Paths/get (str base "/manifest") (make-array String 0)))
      sha (mapv #(bit-and 255 %) (.digest (MessageDigest/getInstance "SHA-256") manifest))
      cid (car/cid-str (car/cid-bytes car/codec-dag-cbor sha)) paths (mapv #(str base "/pack-" %) (range 64)) dir (str base "/otehon-store")]
 (store/init! dir)
 (pack/import-logical-forest-files! dir "native" paths manifest cid {:file-backed? true})
 (let [h (pack/recover dir) refs (get-in (pack/summary h) [:groups "native" :packs]) md (MessageDigest/getInstance "SHA-256") expected (byte-array 1048576)]
  (assert (= 64 (count refs)))
  (dotimes [i 1024]
   (let [actual (pack/read-group-range h "native" (* i 1048576) 1048576)]
    (aset-byte expected 0 (unchecked-byte (mod i 256))) (aset-byte expected 1 (unchecked-byte (quot i 256)))
    (assert (Arrays/equals expected actual)) (.update md ^bytes actual)))
  (prn {:manifest-cid cid :manifest-bytes (alength manifest) :packs (count refs) :bytes (* 1024 1048576)
        :full-sha (.formatHex (HexFormat/of) (.digest md)) :sizes (mapv :stored-size refs) :pass true})))
