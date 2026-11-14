(require '[otehon.storage :as store] '[otehon.pack-store :as pack] '[awai.fs.car :as car])
(import '[java.nio.file Files Paths] '[java.security MessageDigest] '[java.util Arrays HexFormat])
(let [base (or (first *command-line-args*) (throw (ex-info "new input directory required" {}))) manifest (Files/readAllBytes (Paths/get (str base "/manifest") (make-array String 0)))
      v (mapv #(bit-and 255 %) manifest) sha (mapv #(bit-and 255 %) (.digest (MessageDigest/getInstance "SHA-256") manifest))
      cid (car/cid-str (car/cid-bytes car/codec-dag-cbor sha)) paths (mapv #(str base "/pack-" %) (range 17)) dir (str base "/otehon-store")]
 (store/init! dir)
 (pack/import-logical-forest-files! dir "native" paths manifest cid {:file-backed? true})
 (let [h (pack/recover dir) refs (get-in (pack/summary h) [:groups "native" :packs]) md (MessageDigest/getInstance "SHA-256")]
  (assert (= 17 (count refs)))
  (dotimes [j 17]
   (let [actual (pack/read-group-range h "native" (* j 1048576) 1048576) expected (byte-array 1048576)]
    (dotimes [i 1048576] (let [p (+ (* j 1048576) i)] (aset-byte expected i (unchecked-byte (mod (+ (* p 19) (quot p 8191)) 256)))))
    (assert (Arrays/equals expected actual)) (.update md ^bytes actual)))
  (prn {:manifest-cid cid :manifest-bytes (alength manifest) :packs (count refs) :bytes (* 17 1048576) :full-sha (.formatHex (HexFormat/of) (.digest md)) :sizes (mapv :stored-size refs) :pass true})))
