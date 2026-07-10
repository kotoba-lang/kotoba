#!/usr/bin/env clojure
;; Generate golden AOT digests for safe Kotoba → WASM.
;; Run from repo root: clojure -M:dev -i scripts/gen-wasm-goldens.clj
(require '[kotoba.runtime :as r]
         '[kotoba.wasm.bytes :as b]
         '[clojure.java.io :as io])

(def targets
  [["demo" "src/demo.kotoba"]
   ["demo_call" "src/demo_call.kotoba"]
   ["fact" "../kototama/test/kototama/fixtures/kotoba-compiled-fact.kotoba"]])

(doseq [[label path] targets]
  (when (.exists (io/file path))
    (let [forms (r/read-file path :kotoba)
          w (r/wasm-binary forms)
          sha (b/hex-sha256 (:kotoba.wasm/bytes w))
          dir "test/kotoba/wasm/goldens"]
      (.mkdirs (io/file dir))
      (spit (str dir "/" label ".sha256") (str sha "\n"))
      (spit (str dir "/" label ".bytes.edn") (pr-str (:kotoba.wasm/bytes w)))
      (println label (:kotoba.wasm/byte-count w) sha))))
