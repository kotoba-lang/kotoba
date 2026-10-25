(ns comfyui.standard-vae-metal-verify
  "Exercise production tiled VAE decode with a real four-block standard SD VAE."
  (:require [cljs.reader :as reader]
            [comfyui.diffusion.model :as model]
            [comfyui.exec :as exec]
            [comfyui.node :as node]
            [comfyui.nodes.diffusion-runtime-deno :as runtime]
            [comfyui.png-deno :as png]
            [comfyui.safetensors-deno :as safe]
            [num.array :as arr]
            [num.deno-gpu :as dg]))

(def latent-size 64)
(def output-size 512)

(defn- tile-count [size tile overlap]
  (let [stride (- tile overlap)
        origins (fn [length]
                  (let [last-origin (- length tile)]
                    (conj (vec (range 0 last-origin stride)) last-origin)))]
    (* (count (origins size)) (count (origins size)))))

(defn -main [& [spec-path checkpoint-path output-directory tile-size-arg overlap-arg]]
  (when-not checkpoint-path
    (throw (ex-info "usage: SPEC CHECKPOINT [OUTPUT] [TILE_SIZE] [OVERLAP]" {})))
  (let [spec (reader/read-string (js/Deno.readTextFileSync spec-path))
        checkpoint (safe/open-file checkpoint-path)
        floating #{#{"F16"} #{"F32"}}
        checkpoint-dtypes (set (keep #(get % "dtype")
                                     (vals (:tensors checkpoint))))
        _ (when-not (contains? floating checkpoint-dtypes)
            (throw (ex-info "standard VAE gate requires uniform F32 or F16 tensors"
                            {:dtypes checkpoint-dtypes})))
        checkpoint-dtype (first checkpoint-dtypes)
        direct? (boolean (resolve 'num.deno-gpu/upload-byte-view))
        output-directory (or output-directory "/tmp/comfyui-standard-vae-metal")
        tile-size (if tile-size-arg (js/parseInt tile-size-arg 10) 8)
        overlap (if overlap-arg (js/parseInt overlap-arg 10) 2)
        tiles (tile-count latent-size tile-size overlap)]
    (-> (dg/request-device)
        (.then
         (fn [request]
           (let [backend (dg/backend request)
                 baseline (dg/backend-stats backend)
                 typed? (= "F16" checkpoint-dtype)
                 component (safe/component checkpoint {:preserve-f16? typed?})
                 decode (model/compile-decoder component backend spec)
                 cache (-> decode meta :comfyui/tensor-cache)
                 vae (assoc component
                            :comfyui/component :vae :comfyui/decode decode)
                 latent (arr/from-vec
                         backend
                         (mapv #(* 0.25 (Math/sin (* 0.01 %)))
                               (range (* 4 latent-size latent-size)))
                         [1 4 latent-size latent-size])
                 registry (node/registry
                           (runtime/pack {:backend backend
                                          :output-directory output-directory}))
                 workflow {"decode" {:class_type "VAEDecodeTiled"
                                     :inputs {:samples {:samples latent} :vae vae
                                              :tile_size tile-size :overlap overlap}}
                           "save" {:class_type "SaveImage"
                                   :inputs {:images ["decode" 0]
                                            :filename_prefix "standard_vae"}}}
                 started (.now js/performance)]
             (-> (exec/execute-async {:registry registry} workflow)
                 (.then
                  (fn [execution]
                    (let [image (get-in execution [:results "decode" 0])
                          ui (get-in execution [:results "save" 0])
                          path (get-in ui [:images 0 :path])]
                    (when-not (and (= ["decode" "save"] (:executed execution))
                                   (= [1 output-size output-size 3] (:shape image)))
                      (throw (ex-info "standard VAE image shape mismatch"
                                      {:shape (:shape image)
                                       :executed (:executed execution)})))
                    (-> (arr/->vec image)
                        (.then (fn [values]
                                 {:image image :values values :path path}))))))
                 (.then
                  (fn [{:keys [image values path]}]
                    (let [bytes (js/Deno.readFileSync path)]
                           (when-not (every? #(js/Number.isFinite %) values)
                             (throw (ex-info "standard VAE produced non-finite pixels" {})))
                           (let [weights-loaded (count @cache)
                                 reader-stats (safe/reader-stats checkpoint)
                                 image-sum (reduce + values)]
                             (arr/release-all! [latent image])
                             (arr/release-all! (vals @cache))
                             (reset! cache {})
                             (safe/close-file! checkpoint)
                             (let [stats (dg/backend-stats backend)
                                   elapsed (- (.now js/performance) started)]
                               (when-not (and (= [output-size output-size]
                                                  (png/dimensions bytes))
                                              (> (.-byteLength bytes) 10000)
                                              (or (not direct?)
                                                  (and (pos? (:direct-uploads reader-stats))
                                                       (= (:direct-uploads reader-stats)
                                                          (:window-reads reader-stats))))
                                              (= (:live-buffers baseline)
                                                 (:live-buffers stats))
                                              (= (:live-bytes baseline)
                                                 (:live-bytes stats)))
                                 (throw (ex-info "standard VAE Metal lifecycle failed"
                                                 {:bytes (.-byteLength bytes)
                                                  :stats stats})))
                               (println "OK production VAEDecodeTiled standard SD VAE → 512x512 Metal PNG on"
                                        (dg/adapter-description request)
                                        "tiles" tiles
                                        "tile-size" tile-size
                                        "overlap" overlap
                                        "png-bytes" (.-byteLength bytes)
                                        "checkpoint-dtype" checkpoint-dtype
                                        "weights" weights-loaded
                                        "checkpoint-bytes" (:window-bytes reader-stats)
                                        "image-sum" (.toFixed image-sum 6)
                                        "peak-bytes" (:peak-live-bytes stats)
                                        "elapsed-ms" (.toFixed elapsed 3)
                                        "output" path))))))))))
        (.catch (fn [error]
                  (safe/close-file! checkpoint)
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (when-let [data (ex-data error)] (println "DATA:" (pr-str data)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
