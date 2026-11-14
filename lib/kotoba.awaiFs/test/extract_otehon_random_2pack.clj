(require '[otehon.pack-store :as pack] '[awai.fs.car :as car])
(import '[java.nio.file Files Paths CopyOption OpenOption])
(let [[root out] *command-line-args* h (pack/recover root) g (get-in h [:groups "file"]) refs (:packs g)]
 (assert (= 2 (count refs)))
 (Files/createDirectory (Paths/get out (make-array String 0)) (make-array java.nio.file.attribute.FileAttribute 0))
 (Files/write (Paths/get (str out "/gib-manifest") (make-array String 0)) (byte-array (map unchecked-byte (car/hex-decode (:manifest-hex g)))) (make-array OpenOption 0))
 (doseq [[i p] (map-indexed vector refs)] (Files/copy (Paths/get (str root "/" (:stored-sha p) ".forest") (make-array String 0)) (Paths/get (str out "/pack-" i) (make-array String 0)) (make-array CopyOption 0)))
 (prn {:manifest (:manifest-cid g) :packs (mapv #(select-keys % [:stored-sha :stored-size]) refs)}))
