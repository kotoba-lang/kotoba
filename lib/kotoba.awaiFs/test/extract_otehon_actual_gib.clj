;; One-off Otehon reference extraction, not a Native runtime or CI gate.
(require '[otehon.pack-store :as pack] '[awai.fs.car :as car])
(import '[java.nio.file Files Paths CopyOption OpenOption])
(let [[root out & more] *command-line-args*]
  (when (or more (nil? root) (nil? out)) (throw (ex-info "usage: <Otehon-store> <new-output>" {})))
  (let [h (pack/recover root) g (get-in h [:groups "gib"]) refs (:packs g)]
    (assert (= 64 (count refs)))
    (assert (= "bafyreidk3dxbsrqaocvdhfr624j4n75v6ddgmyfgkyu24z3lirlg5aj4g4" (:manifest-cid g)))
    (Files/createDirectory (Paths/get out (make-array String 0)) (make-array java.nio.file.attribute.FileAttribute 0))
    (Files/write (Paths/get (str out "/gib-manifest") (make-array String 0))
                 (byte-array (map unchecked-byte (car/hex-decode (:manifest-hex g)))) (make-array OpenOption 0))
    (doseq [[i p] (map-indexed vector refs)]
      (Files/copy (Paths/get (str root "/" (:stored-sha p) ".forest") (make-array String 0))
                  (Paths/get (str out "/pack-" i) (make-array String 0)) (make-array CopyOption 0)))
    (prn {:packs (count refs) :manifest (:manifest-cid g) :pass true})))
