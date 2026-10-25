(ns comfyui.nodes.diffusion-runtime-deno
  "Executable ComfyUI diffusion node pack for Deno WebGPU/Metal hosts."
  (:require [kotoba.lang.text :as str]
            [comfyui.clip.encoder :as clip]
            [comfyui.diffusion.model :as model]
            [comfyui.diffusion.scheduler :as scheduler]
            [comfyui.diffusion.tiled-vae-deno :as tiled-vae]
            [comfyui.png-deno :as png]
            [comfyui.safetensors-deno :as safe]
            [num.array :as arr]
            [num.core :as nm]
            [num.tensor :as t]))

(defn- component [checkpoint kind]
  {:comfyui/component kind
   :comfyui/checkpoint checkpoint
   :comfyui/read-tensor (fn [backend name]
                          (safe/read-tensor checkpoint backend name))})

(defn release-components! [components]
  (let [components (vec (remove nil? components))
        caches (->> components (mapcat vals) (filter fn?)
                    (keep #(-> % meta :comfyui/tensor-cache)) distinct vec)
        checkpoints (->> components (keep :comfyui/checkpoint) distinct vec)]
    (arr/release-all! (mapcat #(vals @%) caches))
    (doseq [cache caches] (reset! cache {}))
    (doseq [checkpoint checkpoints] (safe/close-file! checkpoint))
    nil))

(defn release-execution!
  "Release every distinct public NDArray and model component retained by an
  executor result. Nodes borrow their inputs, so the result graph remains valid
  until this explicit lifecycle boundary."
  [execution]
  (let [values (tree-seq coll? seq (:results execution))
        arrays (filter #(and (map? %) (:backend %) (:handle %)) values)
        components (->> values
                        (filter #(and (map? %) (:comfyui/component %)))
                        distinct
                        vec)]
    (arr/release-all! arrays)
    (release-components! components)))

(defn- safe-prefix [value]
  (let [value (str/replace (or value "ComfyUI") #"[^A-Za-z0-9._-]" "_")]
    (if (seq value) value "ComfyUI")))

(defonce ^:private output-counters (atom {}))

(defn- existing-next-counter [directory prefix]
  (if-not (try (.-isDirectory (js/Deno.statSync directory))
               (catch :default _ false))
    0
    (inc (reduce
          max -1
          (keep (fn [entry]
                  (let [name (.-name entry)
                        start (str prefix "_")]
                    (when (and (.-isFile entry) (str/starts-with? name start)
                               (str/ends-with? name ".png"))
                      (let [number (subs name (count start) (- (count name) 4))]
                        (when (re-matches #"[0-9]{5}" number)
                          (js/parseInt number 10))))))
                (js/Array.from (js/Deno.readDirSync directory)))))))

(defn- reserve-counters! [directory prefix count]
  (let [key [directory prefix]
        existing (existing-next-counter directory prefix)
        result (swap! output-counters
                      (fn [state]
                        (let [start (max existing (get state key 0))]
                          (assoc state key (+ start count)))))]
    (- (get result key) count)))

(defn- save-png-batch! [images output-directory filename-prefix]
  (let [[batch height width channels :as shape] (:shape images)]
    (when-not (and (= 4 (count shape)) (pos-int? batch) (= 3 channels))
      (throw (ex-info "Deno SaveImage requires batched NHWC RGB images"
                      {:shape shape})))
    (when-not (seq output-directory)
      (throw (ex-info "Deno SaveImage requires output-directory" {})))
    (js/Deno.mkdirSync output-directory #js {:recursive true})
    (let [prefix (safe-prefix filename-prefix)
          start (reserve-counters! output-directory prefix batch)
          image-size (* height width channels)]
      (-> (arr/->vec images)
          (.then
           (fn [values]
             (js/Promise.all
              (into-array
               (mapv
                (fn [batch-index]
                  (let [counter (+ start batch-index)
                        filename (str prefix "_" (.padStart (str counter) 5 "0") ".png")
                        path (str output-directory "/" filename)
                        pixels (subvec (vec values) (* batch-index image-size)
                                       (* (inc batch-index) image-size))]
                    (-> (png/encode-rgb pixels width height)
                        (.then (fn [bytes]
                                 (js/Deno.writeFileSync path bytes)
                                 {:filename filename :subfolder "" :type "output"
                                  :path path :bytes (.-byteLength bytes)})))))
                (range batch))))))
          (.then #(vector {:images (vec (js->clj % :keywordize-keys true))}))))))

(defn- load-png [backend input-directory filename]
  (when-not (and (seq input-directory) (string? filename) (not (str/blank? filename)))
    (throw (ex-info "Deno LoadImage requires input-directory and filename" {})))
  (let [directory (js/Deno.realPathSync input-directory)
        candidate (js/Deno.realPathSync (str input-directory "/" filename))
        _ (when-not (and (str/starts-with? candidate (str directory "/"))
                         (.-isFile (js/Deno.statSync candidate)))
            (throw (ex-info "LoadImage path escapes input directory"
                            {:filename filename})))
        bytes (js/Deno.readFileSync candidate)]
    (-> (png/decode-rgb bytes)
        (.then (fn [{:keys [width height values mask]}]
                 [(arr/from-vec backend values [1 height width 3])
                  (arr/from-vec backend mask [1 height width])])))))

(defn pack
  "Build real Deno nodes. `pipeline` contains paths plus inferred specs/alphas;
  `tokenize` and `noise-fn` are explicit host capabilities."
  [{:keys [backend pipeline tokenize noise-fn input-directory output-directory
           timesteps-fn]
    :or {timesteps-fn (fn [alphas steps]
                        (scheduler/select-timesteps (count alphas) steps))}}]
  [{:type "DiffusersPipelineLoader"
    :category "loaders"
    :inputs {:pipeline_name {:type "STRING"}}
    :outputs [{:name "MODEL" :type "MODEL"}
              {:name "CLIP" :type "CLIP"}
              {:name "VAE" :type "VAE"}]
    :fn
    (fn [_]
      (let [{:keys [unet text-encoder vae unet-spec clip-spec vae-spec alphas]}
            pipeline
            opened (atom [])
            open! (fn [path]
                    (let [checkpoint (safe/open-file path)]
                      (swap! opened conj checkpoint)
                      checkpoint))]
        (when-not (and backend unet-spec clip-spec vae-spec (seq alphas))
          (throw (ex-info "incomplete Deno Diffusers pipeline"
                          {:backend? (boolean backend) :unet? (boolean unet-spec)
                           :clip? (boolean clip-spec) :vae? (boolean vae-spec)
                           :alphas? (boolean (seq alphas))})))
        (try
          (let [unet-file (open! unet)
                text-file (open! text-encoder)
                vae-file (open! vae)
                model-component (component unet-file :model)
                clip-component (component text-file :clip)
                vae-component (component vae-file :vae)]
            [(assoc model-component :comfyui/model-spec unet-spec
                    :comfyui/alphas-cumprod alphas
                    :comfyui/denoise
                    (model/compile-denoiser model-component backend unet-spec))
             (assoc clip-component :comfyui/clip-spec clip-spec
                    :comfyui/encode
                    (clip/compile-encoder clip-component backend clip-spec))
             (cond-> (assoc vae-component :comfyui/model-spec vae-spec
                            :comfyui/decode
                            (model/compile-decoder vae-component backend vae-spec))
               (:encoder-layers vae-spec)
               (assoc :comfyui/encode
                      (model/compile-encoder vae-component backend vae-spec)))])
          (catch :default error
            (doseq [checkpoint @opened] (safe/close-file! checkpoint))
            (throw error)))))}
   {:type "LoadImage"
    :category "image"
    :inputs {:image {:type "STRING"}}
    :outputs [{:name "IMAGE" :type "IMAGE"} {:name "MASK" :type "MASK"}]
    :fn (fn [{:keys [image]}] (load-png backend input-directory image))}
   {:type "CLIPTextEncode"
    :category "conditioning"
    :inputs {:clip {:type "CLIP"} :text {:type "STRING"}}
    :outputs [{:name "CONDITIONING" :type "CONDITIONING"}]
    :fn (fn [{:keys [clip text]}]
          (when-not (and (fn? tokenize) (fn? (:comfyui/encode clip)))
            (throw (ex-info "Deno CLIPTextEncode requires tokenizer and encoder" {})))
          [((:comfyui/encode clip) (assoc (tokenize text) :text text))])}
   {:type "EmptyLatentImage"
    :category "latent"
    :inputs {:width {:type "INT" :default 512}
             :height {:type "INT" :default 512}
             :batch_size {:type "INT" :default 1}}
    :outputs [{:name "LATENT" :type "LATENT"}]
    :fn (fn [{:keys [width height batch_size]}]
          (when-not (and (pos-int? width) (pos-int? height)
                         (zero? (mod width 8)) (zero? (mod height 8))
                         (pos-int? batch_size))
            (throw (ex-info "invalid latent dimensions"
                            {:width width :height height :batch batch_size})))
          [{:samples (arr/zeros backend
                                [batch_size 4 (quot height 8) (quot width 8)])}])}
   {:type "KSampler"
    :category "sampling"
    :inputs {:model {:type "MODEL"} :positive {:type "CONDITIONING"}
             :negative {:type "CONDITIONING"} :latent_image {:type "LATENT"}
             :seed {:type "INT" :default 0} :steps {:type "INT" :default 20}
             :cfg {:type "FLOAT" :default 7.0}
             :sampler_name {:type "STRING" :default "ddim"}
             :scheduler {:type "STRING" :default "normal"}
             :denoise {:type "FLOAT" :default 1.0}}
    :outputs [{:name "LATENT" :type "LATENT"}]
    :fn
    (fn [{:keys [model positive negative latent_image seed steps cfg
                 sampler_name scheduler denoise]}]
      (when-not (and (contains? #{"ddim" "euler" "euler_ancestral" "dpmpp_2m"
                                  "dpmpp_2s_ancestral"}
                                sampler_name)
                     (contains? #{"normal" "karras" "exponential"
                                  "polyexponential"} scheduler)
                     (not (and (= "ddim" sampler_name)
                               (not= "normal" scheduler)))
                     (< 0.0 (double denoise) 1.0000000001)
                     (fn? noise-fn))
        (throw (ex-info "unsupported Deno sampler/scheduler/denoise combination"
                        {:sampler sampler_name :scheduler scheduler :denoise denoise})))
      (let [empty (if (and (map? latent_image) (contains? latent_image :samples))
                    (:samples latent_image) latent_image)
            alphas (:comfyui/alphas-cumprod model)
            denoise-fn (:comfyui/denoise model)
            denoise (double denoise)
            total-steps (if (= 1.0 denoise)
                          steps (max steps (long (/ steps denoise))))
            continuous-sigma? (not= "normal" scheduler)
            explicit-sigmas (when continuous-sigma?
                              (vec (take-last
                                    (inc steps)
                                    (scheduler/sigma-schedule
                                     scheduler total-steps
                                     (scheduler/alpha->sigma (double (first alphas)))
                                     (scheduler/alpha->sigma (double (last alphas)))))))
            timesteps (if continuous-sigma?
                        (mapv #(scheduler/sigma->timestep alphas %)
                              (butlast explicit-sigmas))
                        (vec (take-last steps (timesteps-fn alphas total-steps))))
            initial-timestep (first timesteps)
            sample-noise (fn [shape timestep]
                           (noise-fn shape (+ (long seed) (long timestep)) backend))
            initial-noise (sample-noise (:shape empty) initial-timestep)
            initial-sample
            (case sampler_name
              "ddim" (if (= 1.0 denoise)
                       (t/add empty initial-noise)
                       (scheduler/add-noise
                        empty initial-noise (double (nth alphas initial-timestep))))
              (let [sigma (if explicit-sigmas
                            (first explicit-sigmas)
                            (scheduler/alpha->sigma
                             (double (nth alphas initial-timestep))))]
                (t/add empty (nm/scal! sigma initial-noise))))
            args {:sample initial-sample :alphas alphas :timesteps timesteps
                  :sigmas explicit-sigmas :denoise-fn denoise-fn
                  :positive positive :negative negative :cfg cfg
                  :final-alpha (first alphas) :eta 0.0 :noise-fn sample-noise}
            sampled (case sampler_name
                      "ddim" (scheduler/ddim-sample args)
                      "euler" (scheduler/euler-sample args)
                      "euler_ancestral"
                      (scheduler/euler-ancestral-sample (assoc args :eta 1.0))
                      "dpmpp_2s_ancestral"
                      (scheduler/dpmpp-2s-ancestral-sample (assoc args :eta 1.0))
                      "dpmpp_2m" (scheduler/dpmpp-2m-sample args))]
        ;; `empty` is an upstream executor result and is borrowed by this node.
        ;; Its owner releases it at the execution lifecycle boundary.
        (arr/release-all! [initial-noise initial-sample])
        [{:samples (:sample sampled) :history (:history sampled)}]))}
   {:type "VAEDecode"
    :category "latent"
    :inputs {:samples {:type "LATENT"} :vae {:type "VAE"}}
    :outputs [{:name "IMAGE" :type "IMAGE"}]
    :fn (fn [{:keys [samples vae]}]
          (let [decoded ((:comfyui/decode vae) (:samples samples))
                image (t/nchw-to-rgb-image decoded)]
            (arr/release! decoded)
            [image]))}
   {:type "VAEDecodeTiled"
    :category "latent"
    :inputs {:samples {:type "LATENT"} :vae {:type "VAE"}
             :tile_size {:type "INT" :default 8}
             :overlap {:type "INT" :default 2}}
    :outputs [{:name "IMAGE" :type "IMAGE"}]
    :fn (fn [{:keys [samples vae tile_size overlap]}]
          (let [latent (if (:samples samples) (:samples samples) samples)
                decode (:comfyui/decode vae)]
            (-> (tiled-vae/decode-tiled
                 decode latent {:tile-size (or tile_size 8)
                                :overlap (or overlap 2)})
                (.then (fn [image] [image])))))}
   {:type "VAEEncode"
    :category "latent"
    :inputs {:pixels {:type "IMAGE"} :vae {:type "VAE"}}
    :outputs [{:name "LATENT" :type "LATENT"}]
    :fn (fn [{:keys [pixels vae]}]
          (let [encode (:comfyui/encode vae)
                [batch _height _width channels :as shape] (:shape pixels)]
            (when-not (and (fn? encode) (= 4 (count shape)) (= 3 channels))
              (throw (ex-info "Deno VAEEncode requires executable VAE and NHWC RGB"
                              {:shape shape})))
            (let [nchw (t/rgb-image-to-nchw pixels)
                  latent (encode nchw)]
              (arr/release! nchw)
              (when-not (and (= 4 (count (:shape latent)))
                             (= batch (first (:shape latent))))
                (arr/release! latent)
                (throw (ex-info "Deno VAE encoder returned invalid latent"
                                {:pixels shape :latent (:shape latent)})))
              [latent])))}
   {:type "SaveImage"
    :category "image" :output-node? true
    :inputs {:images {:type "IMAGE"}
             :filename_prefix {:type "STRING" :default "ComfyUI"}}
    :outputs [{:name "UI" :type "UI"}]
    :fn (fn [{:keys [images filename_prefix]}]
          (save-png-batch! images output-directory filename_prefix))}])
