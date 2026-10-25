(ns num.deno-raw-upload-verify
  (:require [num.array :as arr]
            [num.deno-gpu :as dg]))

(defn- approx? [expected actual tolerance]
  (every? true? (map #(< (Math/abs (- %1 %2)) tolerance) expected actual)))

(defn -main [& _]
  (-> (dg/request-device)
      (.then
       (fn [request]
         (let [backend (dg/backend request)
               baseline (dg/backend-stats backend)
               f32-source (js/Float32Array. #js [1.25 -2.5 3.75 0.125])
               f16-bits (js/Uint16Array. #js [0x3c00 0xc000 0x4200])
               bf16-bits (js/Uint16Array. #js [0x3f80 0xc000 0x4040])
               f32 (dg/upload-byte-view backend
                                        (js/Uint8Array. (.-buffer f32-source)) [2 2] :f32)
               f16 (dg/upload-byte-view backend
                                        (js/Uint8Array. (.-buffer f16-bits)) [3] :f16)
               expanded (dg/upload-f16-as-f32-byte-view
                         backend (js/Uint8Array. (.-buffer f16-bits)) [3])
               bf16-expanded (dg/upload-bf16-as-f32-byte-view
                              backend (js/Uint8Array. (.-buffer bf16-bits)) [3])]
           (-> (js/Promise.all #js [(arr/->vec f32) (arr/->vec f16)
                                    (arr/->vec expanded) (arr/->vec bf16-expanded)])
               (.then
                (fn [values]
                  (arr/release-all! [f32 f16 expanded bf16-expanded])
                  (let [stats (dg/backend-stats backend)]
                    (when-not (and (approx? [1.25 -2.5 3.75 0.125]
                                             (aget values 0) 1.0e-7)
                                   (approx? [1.0 -2.0 3.0] (aget values 1) 1.0e-3)
                                   (approx? [1.0 -2.0 3.0] (aget values 2) 1.0e-7)
                                   (approx? [1.0 -2.0 3.0] (aget values 3) 1.0e-7)
                                   (= (:live-buffers baseline) (:live-buffers stats))
                                   (= (:live-bytes baseline) (:live-bytes stats)))
                      (throw (ex-info "raw GPU upload verification failed"
                                      {:values values :baseline baseline :stats stats})))
                    (println "OK raw f32/f16 byte views upload directly on"
                             (dg/adapter-description request)))))))))
      (.catch (fn [error]
                (println "ERROR:" (or (.-stack error) (str error)))
                (js/Deno.exit 1)))))

(set! *main-cli-fn* -main)
