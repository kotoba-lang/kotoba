(ns num.deno-arrow-simd-verify
  (:require [arrow.source :as arrow]
            [arrow.write :as aw]
            [columnar.bytes :as bytes]
            [columnar.vector :as cvec]
            [num.arrow-simd :as arrow-simd]))

(def values [1.25 -2.5 3.75 0.125 8.0 -0.5 2.25])

(defn- fail! [message data]
  (throw (ex-info message data)))

(defn- close? [expected actual]
  (< (Math/abs (- expected actual)) 1.0e-6))

(defn- expect-refused! [f]
  (try
    (f)
    (fail! "Arrow SIMD integration admitted foreign memory" {})
    (catch :default error
      (when-not (= :num/arrow-simd-refused (:type (ex-data error)))
        (throw error)))))

(defn- verify! [wasm-bytes]
  (-> (js/WebAssembly.instantiate wasm-bytes #js {})
      (.then
       (fn [result]
         (let [instance (.-instance result)
               memory (.. instance -exports -memory)
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
               ;; The sole copy is the named ingress write into owned Wasm
               ;; memory. Arrow and SIMD borrow this backing from here onward.
               file-bytes (js/Uint8Array. (.-buffer memory)
                                          0 (.-byteLength encoded-bytes))
               _ (.set file-bytes encoded-bytes)
               source (arrow/open (bytes/of-view file-bytes))
               column-view (arrow/column-buffer-views source 0 "value")
               _ (expect-refused!
                  #(arrow-simd/scale-f32x4!
                    instance
                    (arrow/column-buffer-views
                     (arrow/open
                      (bytes/of-view
                       (js/Uint8Array.from (clj->js encoded))))
                     0 "value")
                    2.0))
               scaled (arrow-simd/scale-f32x4! instance column-view 2.0)
               actual (vec (js/Array.from scaled))
               expected (mapv #(* 2.0 %) values)]
           (when-not (and (identical? (.-buffer file-bytes)
                                      (.-buffer scaled))
                          (= (count expected) (count actual))
                          (every? true? (map close? expected actual)))
             (fail! "Arrow-to-SIMD backing or scalar-oracle check failed"
                    {:expected expected :actual actual}))
           (println "OK one ingress write -> Arrow borrowed values ->"
                    "Wasm v128 f32x4 scale, zero intermediate copies;"
                    "vector lanes plus scalar tail:" (count actual)))))))

(defn -main [& _]
  (-> (js/Deno.readFile "target/arrow-f32-simd.wasm")
      (.then verify!)
      (.catch (fn [error]
                (println "ERROR:" (or (.-stack error) (str error)))
                (js/Deno.exit 1)))))

(set! *main-cli-fn* -main)
