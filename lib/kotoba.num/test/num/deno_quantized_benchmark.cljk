(ns num.deno-quantized-benchmark
  "Forced-materialization Metal benchmark for decode-token quantized GEMM."
  (:require [num.array :as arr]
            [num.core :as nm]
            [num.deno-gpu :as dg]
            [num.dtype :as dtype]
            [num.quantized :as q]))

(def k 1024)
(def n 1024)
(def scales [1 2 3 4 49 34 19 60])
(def mins [9 10 11 12 45 30 51 20])
(def packed-scales [193 130 67 196, 137 74 203 76, 209 226 51 76])

(defn half-bytes [value]
  (let [bits (bit-and 0xffff (dtype/f32->f16-bits value))]
    [(bit-and bits 0xff) (bit-and (bit-shift-right bits 8) 0xff)]))

(def block (vec (concat (half-bytes 0.005) (half-bytes 0.0025)
                        packed-scales (repeat 128 0x21))))
(def packed-bytes (vec (mapcat (fn [_] block) (range (* n (quot k 256))))))
(def dense-row
  (vec (mapcat (fn [index]
                 (let [quant (if (even? index) 1 2)]
                   (repeat 32 (- (* 0.005 (nth scales index) quant)
                                 (* 0.0025 (nth mins index))))))
               (range 8))))
(defn input-values [m]
  (mapv #(- (* 0.001 (mod % 97)) 0.048) (range (* m k))))

(defn now [] (.now js/performance))

(defn repeated-run [operation count]
  (let [start (now)]
    (letfn [(step [remaining]
              (if (zero? remaining)
                (js/Promise.resolve (- (now) start))
                (.then (arr/->vec (operation)) (fn [_] (step (dec remaining))))))]
      (step count))))

(defn -main [& args]
  (let [m (if (= "prefill" (first args)) 64 1)
        iterations (if (= m 64) 3 5)]
   (-> (dg/request-device)
      (.then
       (fn [request]
         (let [gpu (dg/backend request)
               input (arr/from-vec gpu (input-values m) [m k])
               packed (q/matrix gpu packed-bytes [n k] :q4-k)
               ;; All output rows share this deterministic fixture, so transpose
               ;; into the dense `[k,n]` layout by repeating each K value N times.
               dense (arr/from-vec gpu
                                   (vec (mapcat #(repeat n %) (apply concat
                                                                     (repeat (quot k 256)
                                                                             dense-row))))
                                   [k n])
               quant-op #(q/matmul input packed)
               dense-op #(nm/matmul input dense)
               cold (atom {})
               quant-cold-start (now)]
           (println "Quantized benchmark on" (dg/adapter-description request))
           (println (if (= m 1) "decode shape:" "prefill shape:") [m k] "x" [k n])
           (-> (arr/->vec (quant-op))
               (.then (fn [quant-values]
                        (swap! cold assoc :quant (- (now) quant-cold-start))
                        (let [dense-cold-start (now)]
                          (.then (arr/->vec (dense-op))
                                 (fn [dense-values]
                                   (swap! cold assoc :dense (- (now) dense-cold-start))
                                   (let [error (reduce max 0.0
                                                       (map #(js/Math.abs (- %1 %2))
                                                            quant-values dense-values))]
                                     (when (> error 2.0e-3)
                                       (throw (js/Error. (str "benchmark parity error " error))))))))))
               (.then (fn [_]
                        (.then (repeated-run quant-op iterations)
                               (fn [quant-ms]
                                 (.then (repeated-run dense-op iterations)
                                        (fn [dense-ms]
                                          (println "Q4_K bytes:" (count packed-bytes))
                                          (println "dense f32 bytes:" (* 4 k n))
                                          (println "memory ratio:"
                                                   (.toFixed (/ (* 4 k n)
                                                                (count packed-bytes)) 2) "x")
                                          (println "Q4_K cold ms:"
                                                   (.toFixed (:quant @cold) 3))
                                          (println "dense cold ms:"
                                                   (.toFixed (:dense @cold) 3))
                                          (println "Q4_K warm ms/op:"
                                                   (.toFixed (/ quant-ms iterations) 3))
                                          (println "dense warm ms/op:"
                                                   (.toFixed (/ dense-ms iterations) 3))))))))))))
      (.catch (fn [error]
                (println "ERROR:" (or (.-stack error) (str error)))
                (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
