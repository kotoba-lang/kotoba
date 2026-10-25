(ns comfyui.safetensors-deno-metal-verify
  (:require [comfyui.safetensors-deno :as safe]
            [num.array :as arr]
            [num.deno-gpu :as dg]))

(defn- fixture-bytes []
  (let [json (.stringify js/JSON
                         #js {:half #js {:dtype "F16" :shape #js [3]
                                         :data_offsets #js [0 6]}
                              :bfloat #js {:dtype "BF16" :shape #js [3]
                                           :data_offsets #js [6 12]}})
        padding (mod (- 8 (mod (count json) 8)) 8)
        header (.encode (js/TextEncoder.) (str json (apply str (repeat padding " "))))
        output (js/Uint8Array. (+ 8 (.-byteLength header) 12))
        view (js/DataView. (.-buffer output))]
    (.setBigUint64 view 0 (js/BigInt (.-byteLength header)) true)
    (.set output header 8)
    (let [payload (+ 8 (.-byteLength header))]
      (.setUint16 view payload 0x3c00 true)
      (.setUint16 view (+ payload 2) 0xc000 true)
      (.setUint16 view (+ payload 4) 0x4200 true)
      (.setUint16 view (+ payload 6) 0x3f80 true)
      (.setUint16 view (+ payload 8) 0xc000 true)
      (.setUint16 view (+ payload 10) 0x4040 true))
    output))

(defn -main [& _]
  (let [path (js/Deno.makeTempFileSync #js {:suffix ".safetensors"})]
    (js/Deno.writeFileSync path (fixture-bytes))
    (-> (dg/request-device)
        (.then
         (fn [request]
           (let [backend (dg/backend request)
                 baseline (dg/backend-stats backend)
                 direct? (boolean
                          (and (resolve 'num.deno-gpu/upload-f16-as-f32-byte-view)
                               (resolve 'num.deno-gpu/upload-bf16-as-f32-byte-view)))
                 checkpoint (safe/open-file path)
                 half (safe/read-tensor checkpoint backend "half")
                 bfloat (safe/read-tensor checkpoint backend "bfloat")]
             (.then (js/Promise.all #js [(arr/->vec half) (arr/->vec bfloat)])
                    (fn [values]
                      (arr/release-all! [half bfloat])
                      (safe/close-file! checkpoint)
                      (let [closed-rejected?
                            (try (safe/read-tensor checkpoint backend "half") false
                                 (catch :default _ true))
                            reader (safe/reader-stats checkpoint)
                            stats (dg/backend-stats backend)]
                        (when-not (and (= [1.0 -2.0 3.0] (aget values 0))
                                       (= [1.0 -2.0 3.0] (aget values 1))
                                       (if direct?
                                         (and (= {"F16" 1 "BF16" 1}
                                                 (:direct-dtypes reader))
                                              (= 12 (:direct-bytes reader)))
                                         (and (= 2 (:decoded-uploads reader))
                                              (= 6 (:decoded-elements reader))))
                                       (= (:live-buffers baseline) (:live-buffers stats))
                                       (= (:live-bytes baseline) (:live-bytes stats))
                                       closed-rejected?)
                          (throw (ex-info "F16 safetensors Metal verification failed"
                                          {:values values :reader reader
                                           :baseline baseline :stats stats})))
                        (println "OK F16/BF16 safetensors Metal reader"
                                 (if direct? "used device expansion"
                                     "used compatible host fallback"))))))))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1)))
        (.finally #(js/Deno.removeSync path)))))

(set! *main-cli-fn* -main)
