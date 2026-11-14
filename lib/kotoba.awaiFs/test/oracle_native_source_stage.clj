(require '[otehon.storage :as store] '[otehon.pack-store :as pack] '[awai.fs.car :as car])
(import '[java.nio.file Files Paths] '[java.security MessageDigest] '[java.util Arrays HexFormat])
(let [base (first *command-line-args*) input (Files/readAllBytes (Paths/get (str base "/input") (make-array String 0)))]
 (doseq [[label n packs] [["one" 1 1] ["partial" 1048579 1] ["multipack" 16777219 2]]]
  (let [dir (str base "/" label) m (Files/readAllBytes (Paths/get (str dir "/manifest") (make-array String 0)))
        sha (mapv #(bit-and 255 %) (.digest (MessageDigest/getInstance "SHA-256") m))
        cid (car/cid-str (car/cid-bytes car/codec-dag-cbor sha))
        paths (mapv #(str dir "/pack-" %) (range packs)) dest (str dir "/store")]
   (store/init! dest)
   (pack/import-logical-forest-files! dest "file" paths m cid {:file-backed? true})
   (let [h (pack/recover dest)]
    (loop [at 0] (when (< at n)
      (let [end (min n (+ at 1048576)) result (pack/read-group-range h "file" at (- end at))]
       (assert (Arrays/equals (Arrays/copyOfRange input at end) result)) (recur end))))
    (prn {:case label :bytes n :packs packs :cid cid :pass true})))))
