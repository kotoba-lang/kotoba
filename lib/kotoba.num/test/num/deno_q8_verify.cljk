(ns num.deno-q8-verify
  "Live Apple Metal verification of fused GGML Q8_0 GEMV."
  (:require [num.wgsl :as wgsl]))

(def usage (.-GPUBufferUsage js/globalThis))
(def map-mode (.-GPUMapMode js/globalThis))

(defn- gpu-buffer [device typed-array flags]
  (let [buffer (.createBuffer device #js {:size (.-byteLength typed-array)
                                           :usage flags :mappedAtCreation true})
        constructor (.-constructor typed-array)
        mapped (new constructor (.getMappedRange buffer))]
    (.set mapped typed-array) (.unmap buffer) buffer))

(defn- approx? [expected actual]
  (every? true? (map #(< (Math/abs (- %1 %2)) 1.0e-4) expected actual)))

(defn -main [& _]
  (-> (.requestAdapter (.-gpu js/navigator))
      (.then (fn [adapter]
               (when-not adapter (throw (js/Error. "no WebGPU adapter")))
               (.then (.requestDevice adapter)
                      (fn [device]
                        (let [rows 2 cols 64 blocks 2
                              signed (vec (take (* rows cols) (cycle (range -16 16))))
                              packed (js/Uint8Array. (clj->js (map #(bit-and % 255) signed)))
                              packed-u32 (js/Uint32Array. (.-buffer packed))
                              scales (js/Float32Array. #js [0.5 1.0 1.5 0.25])
                              xv (js/Float32Array. (clj->js (map #(- (* 0.02 %) 0.4)
                                                                    (range cols))))
                              expected (mapv
                                        (fn [row]
                                          (reduce + (for [column (range cols)]
                                                      (* (aget scales (+ (* row blocks)
                                                                         (quot column 32)))
                                                         (nth signed (+ (* row cols) column))
                                                         (aget xv column)))))
                                        (range rows))
                              storage (bit-or (.-STORAGE usage) (.-COPY_DST usage))
                              qbuf (gpu-buffer device packed-u32 storage)
                              sbuf (gpu-buffer device scales storage)
                              xbuf (gpu-buffer device xv storage)
                              ybuf (.createBuffer device #js {:size (* rows 4)
                                                               :usage (bit-or (.-STORAGE usage)
                                                                              (.-COPY_SRC usage))})
                              params (gpu-buffer device (js/Uint32Array. #js [rows cols blocks 0])
                                                 (bit-or (.-UNIFORM usage) (.-COPY_DST usage)))
                              module (.createShaderModule device #js {:code wgsl/q8-0-gemv-wgsl})
                              pipeline (.createComputePipeline device
                                                               #js {:layout "auto"
                                                                    :compute #js {:module module
                                                                                  :entryPoint "main"}})
                              bind (.createBindGroup device
                                                     #js {:layout (.getBindGroupLayout pipeline 0)
                                                          :entries #js [#js {:binding 0 :resource #js {:buffer qbuf}}
                                                                        #js {:binding 1 :resource #js {:buffer sbuf}}
                                                                        #js {:binding 2 :resource #js {:buffer xbuf}}
                                                                        #js {:binding 3 :resource #js {:buffer ybuf}}
                                                                        #js {:binding 4 :resource #js {:buffer params}}]})
                              read (.createBuffer device #js {:size (* rows 4)
                                                              :usage (bit-or (.-COPY_DST usage)
                                                                             (.-MAP_READ usage))})
                              encoder (.createCommandEncoder device)
                              pass (.beginComputePass encoder)]
                          (.setPipeline pass pipeline) (.setBindGroup pass 0 bind)
                          (.dispatchWorkgroups pass 1) (.end pass)
                          (.copyBufferToBuffer encoder ybuf 0 read 0 (* rows 4))
                          (.submit (.-queue device) #js [(.finish encoder)])
                          (-> (.mapAsync read (.-READ map-mode))
                              (.then (fn []
                                       (let [actual (vec (js/Float32Array. (.getMappedRange read)))]
                                         (println "adapter:" (or (.-description (.-info adapter)) "Apple Metal"))
                                         (println "Q8_0 expected:" expected "actual:" actual)
                                         (when-not (approx? expected actual) (.exit js/Deno 1)))))))))))
      (.catch (fn [error] (js/console.error error) (.exit js/Deno 1)))))

(set! *main-cli-fn* -main)
