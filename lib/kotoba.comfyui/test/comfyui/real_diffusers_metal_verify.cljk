(ns comfyui.real-diffusers-metal-verify
  "Execute public split Diffusers safetensors directly on Apple Metal."
  (:require [cljs.reader :as reader]
            [comfyui.clip.encoder :as clip]
            [comfyui.diffusion.model :as model]
            [comfyui.diffusion.scheduler :as scheduler]
            [comfyui.png-deno :as png]
            [comfyui.safetensors-deno :as safe]
            [num.array :as arr]
            [num.deno-gpu :as dg]
            [num.tensor :as t]))

(defn- close? [expected actual tolerance]
  (and (= (count expected) (count actual))
       (every? true? (map #(< (Math/abs (- %1 %2)) tolerance) expected actual))))

(defn- f16-checkpoint? [checkpoint]
  (let [floating #{"F16" "BF16" "F32" "F64"}
        dtypes (keep #(get % "dtype") (vals (:tensors checkpoint)))]
    (and (some floating dtypes)
         (every? #(or (not (floating %)) (= "F16" %)) dtypes))))

(defn -main [& [spec-path unet-path text-path vae-path output-path]]
  (when-not vae-path
    (throw (ex-info "usage: SPEC UNET TEXT_ENCODER VAE" {})))
  (let [{:keys [unet clip vae alphas positive negative]}
        (reader/read-string (js/Deno.readTextFileSync spec-path))
        unet-file (safe/open-file unet-path)
        text-file (safe/open-file text-path)
        vae-file (safe/open-file vae-path)
        f16? (every? f16-checkpoint? [unet-file text-file vae-file])
        output-path (or output-path "/tmp/comfyui-real-diffusers-metal.png")]
    (-> (dg/request-device)
        (.then
         (fn [request]
           (let [backend (dg/backend request)
                 baseline (dg/backend-stats backend)
                 unet-component (safe/component unet-file)
                 clip-component (safe/component text-file)
                 vae-component (safe/component vae-file)
                 denoise (model/compile-denoiser unet-component backend unet)
                 encode (clip/compile-encoder clip-component backend clip)
                 decode (model/compile-decoder vae-component backend vae)
                 positive-result (do (println "Metal stage: CLIP positive")
                                     (encode positive))
                 negative-result (do (println "Metal stage: CLIP negative")
                                     (encode negative))
                 fixed-noise (arr/from-vec backend
                                           (mapv #(* 0.5 (Math/sin %))
                                                 (range (* 4 8 8))) [1 4 8 8])
                 events (atom [])
                 sampled (do
                           (println "Metal stage: 2-step UNet")
                           (scheduler/ddim-sample
                          {:sample fixed-noise :alphas alphas :timesteps [501 1]
                           :denoise-fn denoise :positive positive-result
                           :negative negative-result :cfg 2.0
                           :final-alpha (first alphas) :retain-step-tensors? true
                           :on-step #(swap! events conj %)}))
                 latent (:sample sampled)
                 decoded (do (println "Metal stage: VAE decode") (decode latent))
                 image (t/nchw-to-rgb-image decoded)
                 clip-promise (arr/->vec (:tensor positive-result))
                 epsilon-promises (mapv #(arr/->vec (:epsilon %)) @events)
                 latent-promise (arr/->vec latent)
                 image-promise (arr/->vec image)
                 promises (js/Promise.all
                           (into-array
                            [clip-promise (js/Promise.all (into-array epsilon-promises))
                             latent-promise image-promise]))
                 caches [(-> denoise meta :comfyui/tensor-cache)
                         (-> encode meta :comfyui/tensor-cache)
                         (-> decode meta :comfyui/tensor-cache)]
                 direct-upload? (boolean (resolve 'num.deno-gpu/upload-byte-view))
                 owned (concat [fixed-noise decoded image
                                (:tensor positive-result) (:pooled positive-result)
                                (:tensor negative-result) (:pooled negative-result)]
                               (mapcat vals (map deref caches))
                               (mapcat #(vals (select-keys % [:epsilon :sample
                                                              :predicted-original-sample]))
                                       @events))]
             (arr/release-all! (concat owned [latent]))
             (doseq [cache caches] (reset! cache {}))
             (.then
              promises
              (fn [results]
                (let [clip-values (aget results 0)
                      epsilon-values (vec (js/Array.from (aget results 1)))
                      latent-values (aget results 2)
                      image-values (aget results 3)
                      epsilon-sums (mapv #(reduce + %) epsilon-values)
                      stats (dg/backend-stats backend)
                      reader-stats (mapv safe/reader-stats
                                         [unet-file text-file vae-file])
                      reference-clip (if f16?
                                       [-0.8401386314601924 -0.39627744368989104
                                        -0.6829871882367291 0.02191159227272704
                                        -0.6475881348045954 0.13595497578593466
                                        -1.2650584114823653 0.06671595517928518]
                                       [-0.8407002091407776 -0.3963874876499176
                                        -0.6832109093666077 0.021882688626646996
                                        -0.6473066210746765 0.13609130680561066
                                        -1.265396237373352 0.06672965735197067])
                      reference-epsilon (if f16?
                                          [-8.781381938205236 -8.408713143250834]
                                          [-8.784357070922852 -8.41365909576416])
                      reference-latent (if f16? 15.374797308671601
                                           15.379568099975586)
                      reference-image (if f16?
                                        [0.4929879523647378 0.4779479154820478
                                         0.525698217349902 0.4235678746113127
                                         0.47616785497202296 0.48686916416119913
                                         0.3833928842590487 0.40951022731100106]
                                        [0.49303802847862244 0.47796139121055603
                                         0.525601327419281 0.4234960377216339
                                         0.4761624038219452 0.4867897033691406
                                         0.3834155797958374 0.40941333770751953])
                      reference-image-sum (if f16? 391.73747777734826
                                                391.7310791015625)]
                  (when-not
                      (and (close? reference-clip (take 8 clip-values) 1.0e-5)
                           (close? reference-epsilon epsilon-sums 1.0e-4)
                           (< (Math/abs (- (reduce + latent-values)
                                           reference-latent)) 1.0e-3)
                           (close? reference-image (take 8 image-values) 1.0e-4)
                           (< (Math/abs (- (reduce + image-values)
                                           reference-image-sum)) 1.0e-2)
                           (= (:live-buffers baseline) (:live-buffers stats))
                           (= (:live-bytes baseline) (:live-bytes stats))
                           (or (not direct-upload?)
                               (every? pos? (map :direct-uploads reader-stats)))
                           (every? true?
                                   (map #(< (:peak-window-bytes %)
                                            (:file-size %2))
                                        reader-stats
                                        [unet-file text-file vae-file])))
                    (throw (ex-info "real Diffusers Metal verification failed"
                                    {:clip-first8 (vec (take 8 clip-values))
                                     :epsilon-sums epsilon-sums
                                     :latent-sum (reduce + latent-values)
                                     :image-sum (reduce + image-values)
                                     :image-first8 (vec (take 8 image-values))
                                     :baseline baseline :stats stats
                                     :reader-stats reader-stats})))
                  (.then
                   (png/encode-rgb image-values 16 16)
                   (fn [png-bytes]
                     (js/Deno.writeFileSync output-path png-bytes)
                     (when-not (and (= [16 16] (png/dimensions png-bytes))
                                    (> (.-byteLength png-bytes) 500))
                       (throw (ex-info "encoded PNG verification failed"
                                       {:path output-path
                                        :bytes (.-byteLength png-bytes)})))
                     (println "OK real Diffusers CLIP→2-step UNet→VAE matches"
                              (if f16? "JVM CPU oracle on" "PyTorch on")
                              (dg/adapter-description request) "peak-bytes"
                              (:peak-live-bytes stats) "direct-checkpoint-bytes"
                              (reduce + (map :direct-bytes reader-stats))
                              "largest-host-window"
                              (apply max (map :peak-window-bytes reader-stats))
                              "checkpoint-dtype" (if f16? "F16" "F32")
                              "png-bytes" (.-byteLength png-bytes)
                              "output" output-path)))))))))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (when-let [data (ex-data error)]
                    (println "DATA:" (pr-str data)))
                  (js/Deno.exit 1)))
        (.finally #(doseq [checkpoint [unet-file text-file vae-file]]
                     (safe/close-file! checkpoint))))))

(set! *main-cli-fn* -main)
