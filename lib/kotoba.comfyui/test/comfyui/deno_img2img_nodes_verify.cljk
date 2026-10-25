(ns comfyui.deno-img2img-nodes-verify
  "Verify Deno LoadImage → VAEEncode graph execution on real Metal."
  (:require [comfyui.diffusion.model :as model]
            [comfyui.exec :as exec]
            [comfyui.node :as node]
            [comfyui.nodes.diffusion-runtime-deno :as runtime]
            [comfyui.png-deno :as png]
            [num.array :as arr]
            [num.cpu :as cpu]
            [num.deno-gpu :as dg]
            [num.tensor :as t]))

(def spec {:layers []
           :encoder-layers [{:op :take-channels :channels 2}
                            {:op :scale :factor 0.5}]})

(def component
  {:comfyui/read-tensor
   (fn [_ name] (throw (ex-info "unexpected tensor read" {:name name})))})

(defn- encoder [backend]
  (model/compile-encoder component backend spec))

(defn- close-vectors? [expected actual]
  (and (= (count expected) (count actual))
       (every? #(< (js/Math.abs %) 1.0e-5) (map - expected actual))))

(defn- verify-execution [request backend baseline expected quantized execution]
  (let [image (get-in execution [:results "load" 0])
        mask (get-in execution [:results "load" 1])
        latent (get-in execution [:results "encode" 0])]
    (-> (js/Promise.all
         #js [(arr/->vec image) (arr/->vec mask) (arr/->vec latent)])
        (.then
         (fn [values]
           (let [actual-image (aget values 0)
                 actual-mask (aget values 1)
                 actual-latent (aget values 2)]
             (arr/release-all! [image mask latent])
             (let [stats (dg/backend-stats backend)
                   baseline? (and (= (:live-buffers baseline) (:live-buffers stats))
                                  (= (:live-bytes baseline) (:live-bytes stats)))
                   ok? (and (= ["load" "encode"] (:executed execution))
                            (= [1 3 4 3] (:shape image))
                            (= [1 3 4] (:shape mask))
                            (= [1 2 3 4] (:shape latent))
                            (close-vectors? quantized actual-image)
                            (every? zero? actual-mask)
                            (close-vectors? expected actual-latent)
                            baseline?)]
               (println "Deno PNG LoadImage → VAEEncode on"
                        (dg/adapter-description request)
                        (if ok? "passed" "failed"))
               (println "GPU baseline restored:"
                        (if baseline? "passed" "failed"))
               (when-not ok?
                 (throw (ex-info "Deno img2img nodes failed"
                                 {:image actual-image :mask actual-mask
                                 :latent actual-latent :stats stats}))))))))))

(defn- run-batch-save [request backend directory]
  (doseq [entry (js/Array.from (js/Deno.readDirSync directory))
          :when (and (.-isFile entry) (.startsWith (.-name entry) "batch_"))]
    (js/Deno.removeSync (str directory "/" (.-name entry))))
  (let [baseline (dg/backend-stats backend)
        images (arr/from-vec backend
                             [1.0 0.0 0.0, 0.0 1.0 0.0,
                              0.0 0.0 1.0, 1.0 1.0 1.0]
                             [2 1 2 3])
        save-node (first (filter #(= "SaveImage" (:type %))
                                 (runtime/pack {:backend backend
                                                :output-directory directory})))
        save! #((:fn save-node) {:images images :filename_prefix "batch"})]
    (-> (save!)
        (.then (fn [first-result]
                 (-> (save!) (.then #(vector first-result %)))))
        (.then
         (fn [[first-result second-result]]
           (let [rows (concat (:images (first first-result))
                              (:images (first second-result)))
                 names (mapv :filename rows)
                 dimensions (mapv #(png/dimensions
                                    (js/Deno.readFileSync (:path %))) rows)]
             (arr/release! images)
             (let [stats (dg/backend-stats backend)
                   ok? (and (= ["batch_00000.png" "batch_00001.png"
                                "batch_00002.png" "batch_00003.png"] names)
                            (= [[2 1] [2 1] [2 1] [2 1]] dimensions)
                            (= (:live-buffers baseline) (:live-buffers stats))
                            (= (:live-bytes baseline) (:live-bytes stats)))]
               (println "Deno batch SaveImage counter reservation on"
                        (dg/adapter-description request) (if ok? "passed" "failed"))
               (when-not ok?
                 (throw (ex-info "Deno batch SaveImage failed"
                                 {:names names :dimensions dimensions
                                  :stats stats}))))))))))

(defn- run-metal [directory filename expected quantized request]
  (let [backend (dg/backend request)
        baseline (dg/backend-stats backend)
        vae {:comfyui/component :vae :comfyui/encode (encoder backend)}
        registry (node/registry
                  (runtime/pack {:backend backend :input-directory directory}))
        workflow {"load" {:class_type "LoadImage" :inputs {:image filename}}
                  "encode" {:class_type "VAEEncode"
                            :inputs {:pixels ["load" 0] :vae vae}}}]
    (-> (exec/execute-async {:registry registry :cache nil} workflow)
        (.then #(verify-execution request backend baseline expected quantized %))
        (.then (fn [_] (run-batch-save request backend directory))))))

(defn- rejects? [f]
  (try
    (-> (js/Promise.resolve (f))
        (.then (constantly false))
        (.catch (constantly true)))
    (catch :default _ (js/Promise.resolve true))))

(defn- security-checks [directory bytes]
  (let [outside "/tmp/comfyui-deno-outside.png"
        corrupt (.slice bytes)
        _ (aset corrupt 50 (bit-xor 1 (aget corrupt 50)))
        _ (js/Deno.writeFileSync outside bytes)
        load-node (first (filter #(= "LoadImage" (:type %))
                                 (runtime/pack {:backend (cpu/cpu-backend)
                                                :input-directory directory})))
        escaped? (try ((:fn load-node) {:image "../comfyui-deno-outside.png"})
                      false (catch :default _ true))]
    (-> (rejects? #(png/decode-rgb corrupt))
        (.then (fn [crc?]
                 (println "PNG CRC and path confinement:"
                          (if (and crc? escaped?) "passed" "failed"))
                 (when-not (and crc? escaped?)
                   (throw (ex-info "PNG security checks failed"
                                   {:crc? crc? :escaped? escaped?}))))))))

(defn -main [& _]
  (let [directory "/tmp/comfyui-deno-img2img"
        filename "input.png"
        path (str directory "/" filename)
        source (mapv #(/ (mod (* % 31) 256) 255.0) (range (* 4 3 3)))
        quantized (mapv #(/ (js/Math.round (* 255.0 %)) 255.0) source)
        cpu-backend (cpu/cpu-backend)
        cpu-image (arr/from-vec cpu-backend quantized [1 3 4 3])
        cpu-nchw (t/rgb-image-to-nchw cpu-image)
        expected (arr/->vec ((encoder cpu-backend) cpu-nchw))]
    (js/Deno.mkdirSync directory #js {:recursive true})
    (-> (png/encode-rgb source 4 3)
        (.then (fn [bytes]
                 (js/Deno.writeFileSync path bytes)
                 (security-checks directory bytes)))
        (.then (fn [_] (dg/request-device)))
        (.then #(run-metal directory filename expected quantized %))
        (.then #(js/Deno.exit 0))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
