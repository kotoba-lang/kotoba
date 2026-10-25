(ns num.deno-arrow-simd-benchmark
  (:require [arrow.source :as arrow]
            [arrow.write :as aw]
            [columnar.bytes :as bytes]
            [columnar.vector :as cvec]
            [num.arrow-gpu :as arrow-buffer]
            ["os" :as os]))

(def element-count 262147) ; 1 MiB plus a three-element scalar tail
(def iterations 64)
(def warmups 5)
(def sample-count 11)
(def scale 1.000001)

(defn- fail! [message data]
  (throw (ex-info message data)))

(defn- median [xs]
  (let [ordered (vec (sort xs))]
    (nth ordered (quot (count ordered) 2))))

(defn- elapsed-ms [kernel ptr length]
  (let [started (.now js/performance)]
    (dotimes [_ iterations]
      (kernel ptr length scale))
    (- (.now js/performance) started)))

(defn- check-result! [view original]
  (let [factor (Math/pow scale iterations)
        indexes [0 1 1023 131071 (dec element-count)]]
    (doseq [i indexes]
      (let [expected (* (aget original i) factor)
            actual (aget view i)
            tolerance (* 2.0e-5 (max 1.0 (Math/abs expected)))]
        (when (> (Math/abs (- expected actual)) tolerance)
          (fail! "benchmark kernel failed scalar oracle"
                 {:index i :expected expected :actual actual}))))))

(defn- hex [buffer]
  (apply str (map #(.padStart (.toString % 16) 2 "0")
                  (js/Uint8Array. buffer))))

(defn- benchmark! [wasm-bytes]
  (-> (js/WebAssembly.instantiate wasm-bytes #js {})
      (.then
       (fn [result]
         (let [instance (.-instance result)
               exports (.-exports instance)
               memory (.-memory exports)
               simd (.-scale_f32x4 exports)
               scalar (.-scale_f32_scalar exports)
               load1 (aget (.loadavg os) 0)
               logical-cpus (.-length (.cpus os))
               values (mapv (fn [i] (- (/ (mod i 1024) 32.0) 16.0))
                            (range element-count))
               encoded (aw/file
                        {:fields [{:name "value" :type :float :nullable? false}]
                         :batches [[(cvec/column :float values)]]})
               encoded-bytes (js/Uint8Array.from (clj->js encoded))
               _ (when (> (.-byteLength encoded-bytes)
                          (.-byteLength (.-buffer memory)))
                   (.grow memory
                          (Math/ceil
                           (/ (- (.-byteLength encoded-bytes)
                                 (.-byteLength (.-buffer memory)))
                              65536))))
               file-bytes (js/Uint8Array. (.-buffer memory)
                                          0 (.-byteLength encoded-bytes))
               _ (.set file-bytes encoded-bytes)
               source (arrow/open (bytes/of-view file-bytes))
               column (arrow/column-buffer-views source 0 "value")
               view (arrow-buffer/borrow-f32-column column)
               ptr (.-byteOffset view)
               original (js/Float32Array.from view)
               reset! #(.set view original)
               run! (fn [kernel]
                      (reset!)
                      (let [ms (elapsed-ms kernel ptr element-count)]
                        (check-result! view original)
                        ms))]
           (when-not (identical? (.-buffer memory) (.-buffer view))
             (fail! "benchmark lost Arrow/Wasm backing identity" {}))
           (dotimes [_ warmups]
             (run! simd)
             (run! scalar))
           (let [pairs (mapv (fn [i]
                               ;; Alternate order to reduce systematic thermal
                               ;; and frequency bias between the two kernels.
                               (if (even? i)
                                 {:simd (run! simd) :scalar (run! scalar)}
                                 (let [s (run! scalar) v (run! simd)]
                                   {:simd v :scalar s})))
                             (range sample-count))
                 simd-ms (mapv :simd pairs)
                 scalar-ms (mapv :scalar pairs)
                 simd-median (median simd-ms)
                 scalar-median (median scalar-ms)]
             (-> (js/crypto.subtle.digest "SHA-256" wasm-bytes)
                 (.then
                  (fn [digest]
                    (println
                     (js/JSON.stringify
                      (clj->js
                       {:schema "num.arrow-wasm-simd-benchmark/v1"
                        :host "Apple M4"
                        :arch "arm64"
                        :runtime (str "Deno " js/Deno.version.deno)
                        :wasm-sha256 (hex digest)
                        :elements element-count
                        :bytes (* 4 element-count)
                        :iterations iterations
                        :warmups warmups
                        :samples sample-count
                        :timed-region "kernel calls only; reset excluded"
                        :host-load {:load1 load1
                                    :logical-cpus logical-cpus
                                    :qualified? (<= load1 logical-cpus)}
                        :simd-ms simd-ms
                        :scalar-ms scalar-ms
                        :simd-median-ms simd-median
                        :scalar-median-ms scalar-median
                        :scalar-over-simd (/ scalar-median simd-median)
                        :publishable? (<= load1 logical-cpus)})
                      nil 2)))))))))))

(defn -main [& _]
  (-> (js/Deno.readFile "target/arrow-f32-simd.wasm")
      (.then benchmark!)
      (.catch (fn [error]
                (println "ERROR:" (or (.-stack error) (str error)))
                (js/Deno.exit 1)))))

(set! *main-cli-fn* -main)
