(ns num.deno-quantized-verify
  "Real Metal parity for packed Q4_K matmul without dense weight upload."
  (:require [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as dg]
            [num.dtype :as dtype]
            [num.quantized :as q]))

(def scales [1 2 3 4 49 34 19 60])
(def mins [9 10 11 12 45 30 51 20])
(def packed-scales [193 130 67 196, 137 74 203 76, 209 226 51 76])

(defn half-bytes [value]
  (let [bits (bit-and 0xffff (dtype/f32->f16-bits value))]
    [(bit-and bits 0xff) (bit-and (bit-shift-right bits 8) 0xff)]))

(defn block [d dmin]
  (vec (concat (half-bytes d) (half-bytes dmin) packed-scales
               (repeat 128 0x21))))

(def packed-bytes (vec (concat (block 0.5 0.25) (block -0.125 0.5))))
(def inputs (mapv #(- (* 0.01 (mod % 17)) 0.08) (range (* 5 256))))

(defn run-q4 [backend]
  (q/matmul (arr/from-vec backend inputs [5 256])
            (q/matrix backend packed-bytes [2 256] :q4-k)))

(defn q6-block [d]
  (vec (concat (repeat (+ 128 64) 0)
               (map #(bit-and % 0xff) (range -8 8))
               (half-bytes d))))

(def q6-bytes (vec (concat (q6-block 0.25) (q6-block -0.125))))

(defn run-q6 [backend]
  (q/matmul (arr/from-vec backend inputs [5 256])
            (q/matrix backend q6-bytes [2 256] :q6-k)))

(defn q8-block [d]
  (vec (concat (half-bytes d) (map #(bit-and % 0xff) (range -16 16)))))

(def q8-bytes (vec (concat (q8-block 0.25) (q8-block -0.5))))

(defn run-q8 [backend]
  (q/matmul (arr/from-vec backend (take (* 5 32) inputs) [5 32])
            (q/matrix backend q8-bytes [2 32] :q8-0)))

(defn q5-block [d]
  (vec (concat (half-bytes d) [1 0 0 128] (repeat 16 0xf0))))

(def q5-bytes (q5-block 0.5))

(defn run-q5 [backend]
  (q/matmul (arr/from-vec backend (take (* 5 16) inputs) [5 16])
            (q/matrix backend q5-bytes [2 16] :q5-0)))

(defn run-embedding [backend bytes shape quant-type]
  (q/embedding (arr/from-vec backend [1 0 1] [3])
               (q/table backend bytes shape quant-type)))

(defn close? [left right]
  (every? #(< (js/Math.abs %) 2.0e-3) (map - left right)))

(defn -main [& _]
  (let [cpu (cpu/cpu-backend)
        q5-expected (arr/->vec (run-q5 cpu))
        q4-expected (arr/->vec (run-q4 cpu))
        q6-expected (arr/->vec (run-q6 cpu))
        q8-expected (arr/->vec (run-q8 cpu))
        embedding-expected
        [(arr/->vec (run-embedding cpu q5-bytes [2 16] :q5-0))
         (arr/->vec (run-embedding cpu packed-bytes [2 256] :q4-k))
         (arr/->vec (run-embedding cpu q6-bytes [2 256] :q6-k))
         (arr/->vec (run-embedding cpu q8-bytes [2 32] :q8-0))]]
    (-> (dg/request-device)
        (.then (fn [request]
                 (println "Packed Q4_K matmul on" (dg/adapter-description request))
                 (let [gpu (dg/backend request)]
                   (js/Promise.all
                    #js [(arr/->vec (run-q5 gpu))
                         (arr/->vec (run-q4 gpu))
                         (arr/->vec (run-q6 gpu))
                         (arr/->vec (run-q8 gpu))
                         (arr/->vec (run-embedding gpu q5-bytes [2 16] :q5-0))
                         (arr/->vec (run-embedding gpu packed-bytes [2 256] :q4-k))
                         (arr/->vec (run-embedding gpu q6-bytes [2 256] :q6-k))
                         (arr/->vec (run-embedding gpu q8-bytes [2 32] :q8-0))]))))
        (.then (fn [actual]
                 (let [q5-ok? (close? (aget actual 0) q5-expected)
                       q4-ok? (close? (aget actual 1) q4-expected)
                       q6-ok? (close? (aget actual 2) q6-expected)
                       q8-ok? (close? (aget actual 3) q8-expected)
                       embedding-ok? (every? true?
                                             (map-indexed
                                              (fn [index expected]
                                                (close? (aget actual (+ index 4)) expected))
                                              embedding-expected))
                       ok? (and q5-ok? q4-ok? q6-ok? q8-ok? embedding-ok?)]
                   (println (str "Q5_0 CPU/Metal parity: "
                                 (if q5-ok? "passed" "failed")))
                   (println (str "Q4_K CPU/Metal parity: "
                                 (if q4-ok? "passed" "failed")))
                   (println (str "Q6_K CPU/Metal parity: "
                                 (if q6-ok? "passed" "failed")))
                   (println (str "Q8_0 CPU/Metal parity: "
                                 (if q8-ok? "passed" "failed")))
                   (println (str "packed embedding CPU/Metal parity: "
                                 (if embedding-ok? "passed" "failed")))
                   (when-not ok?
                     (println "q5 expected=" q5-expected "actual=" (aget actual 0))
                     (println "q4 expected=" q4-expected "actual=" (aget actual 1))
                     (println "q6 expected=" q6-expected "actual=" (aget actual 2))
                     (println "q8 expected=" q8-expected "actual=" (aget actual 3)))
                   (js/Deno.exit (if ok? 0 1)))))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
