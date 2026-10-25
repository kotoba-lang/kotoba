(ns comfyui.real-diffusers-pipeline-verify
  "Run real split Diffusers UNet, CLIP, scheduler, and VAE files to a PNG."
  (:require [json.data-json :as json]
            [comfyui.clip.tokenizer :as tokenizer]
            [comfyui.exec :as exec]
            [comfyui.diffusion.scheduler :as scheduler]
            [comfyui.node :as node]
            [comfyui.nodes.diffusion-runtime :as runtime]
            [comfyui.safetensors :as safe]
            [num.array :as arr]
            [num.cpu :as cpu])
  (:import [java.nio.file Files Path]
           [java.nio.file.attribute FileAttribute]))

(defn- read-json [path]
  (json/read-str (Files/readString (Path/of path (make-array String 0)))))

(defn -main
  [& [unet-path unet-config-path text-path text-config-path vae-path
      vae-config-path scheduler-config-path vocab-path merges-path]]
  (when-not merges-path
    (throw (ex-info
            (str "usage: real-diffusers-pipeline-verify UNET UNET_CONFIG TEXT "
                 "TEXT_CONFIG VAE VAE_CONFIG SCHEDULER_CONFIG VOCAB MERGES") {})))
  (let [backend (cpu/cpu-backend)
        output-dir (Files/createTempDirectory "comfyui-diffusers-output-"
                                              (make-array FileAttribute 0))
        clip-tokenizer (tokenizer/load-tokenizer
                        vocab-path merges-path {:pad-token "<|endoftext|>"})
        pipeline {:unet unet-path :unet-config (read-json unet-config-path)
                  :text-encoder text-path :text-config (read-json text-config-path)
                  :vae vae-path :vae-config (read-json vae-config-path)
                  :scheduler-config (read-json scheduler-config-path)}
        definitions (runtime/pack
                     {:backend backend :clip-tokenizer clip-tokenizer
                      :output-directory output-dir
                      :resolve-diffusers-pipeline (constantly pipeline)})
        registry (node/registry definitions)
        workflow
        {"load" {:class_type "DiffusersPipelineLoader"
                  :inputs {:pipeline_name "tiny-stable-diffusion"}}
         "positive" {:class_type "CLIPTextEncode"
                     :inputs {:clip ["load" 1] :text "a tiny red robot"}}
         "negative" {:class_type "CLIPTextEncode"
                     :inputs {:clip ["load" 1] :text "blurry"}}
         "latent" {:class_type "EmptyLatentImage"
                   :inputs {:width 64 :height 64 :batch_size 1}}
         "sample" {:class_type "KSampler"
                   :inputs {:model ["load" 0] :positive ["positive" 0]
                            :negative ["negative" 0] :latent_image ["latent" 0]
                            :seed 260713 :steps 1 :cfg 2.0
                            :sampler_name "ddim" :scheduler "normal" :denoise 1.0}}
         "decode" {:class_type "VAEDecode"
                   :inputs {:samples ["sample" 0] :vae ["load" 2]}}
         "save" {:class_type "SaveImage"
                 :inputs {:images ["decode" 0] :filename_prefix "diffusers-real"}}}
        started (System/nanoTime)
        result (exec/execute {:registry registry} workflow)
        model (get-in result [:results "load" 0])
        clip (get-in result [:results "load" 1])
        vae (get-in result [:results "load" 2])]
    (try
      (let [image (get-in result [:results "decode" 0])
            positive (get-in result [:results "positive" 0])
            negative (get-in result [:results "negative" 0])
            clip-values (vec (arr/->vec (:tensor positive)))
            reference-clip-first8 [-0.8407002091407776 -0.3963874876499176
                                   -0.6832109093666077 0.021882688626646996
                                   -0.6473066210746765 0.13609130680561066
                                   -1.265396237373352 0.06672965735197067]
            clip-reference-max-error
            (apply max (map #(Math/abs (- %1 %2))
                            (take 8 clip-values) reference-clip-first8))
            fixed-noise (arr/from-vec backend (map #(* 0.5 (Math/sin %))
                                                   (range (* 4 8 8))) [1 4 8 8])
            alphas (:comfyui/alphas-cumprod model)
            fixed-events (atom [])
            fixed-sample (scheduler/ddim-sample
                          {:sample fixed-noise :alphas alphas :timesteps [501 1]
                           :denoise-fn (:comfyui/denoise model)
                           :positive positive :negative negative :cfg 2.0
                           :final-alpha (first alphas)
                           :retain-step-tensors? true
                           :on-step #(swap! fixed-events conj %)})
            fixed-latent (:sample fixed-sample)
            vae-decode (first (filter #(= "VAEDecode" (:type %)) definitions))
            [fixed-image] ((:fn vae-decode) {:samples fixed-latent :vae vae})
            fixed-values (vec (arr/->vec fixed-image))
            reference-image-first16
            [0.49303802847862244 0.47796139121055603 0.525601327419281
             0.4234960377216339 0.4761624038219452 0.4867897033691406
             0.3834155797958374 0.40941333770751953 0.40316879749298096
             0.44823935627937317 0.39917871356010437 0.2875598669052124
             0.43192023038864136 0.3542705476284027 0.2174679934978485
             0.6154196262359619]
            epsilon-sums (mapv #(reduce + (arr/->vec (:epsilon %))) @fixed-events)
            epsilon-reference-max-error
            (apply max (map #(Math/abs (- %1 %2)) epsilon-sums
                            [-8.784357070922852 -8.41365909576416]))
            image-reference-max-error
            (apply max (map #(Math/abs (- %1 %2))
                            (take 16 fixed-values) reference-image-first16))
            image-reference-sum-error
            (Math/abs (- (reduce + fixed-values) 391.7310791015625))
            latent-reference-sum-error
            (Math/abs (- (reduce + (arr/->vec fixed-latent)) 15.379568099975586))
            saved (get-in result [:results "save" 0 :images 0])
            path (Path/of (:path saved) (make-array String 0))
            report {:image-shape (:shape image)
                    :png-bytes (Files/size path)
                    :model-tensors (count @(-> (:comfyui/denoise model)
                                               meta :comfyui/tensor-cache))
                    :clip-tensors (count @(-> (:comfyui/encode clip)
                                              meta :comfyui/tensor-cache))
                    :clip-input-ids (vec (take 12 (:input-ids positive)))
                    :clip-sum (reduce + clip-values)
                    :clip-first8 (vec (take 8 clip-values))
                    :clip-reference-max-error clip-reference-max-error
                    :two-step-timesteps [501 1]
                    :two-step-epsilon-sums
                    epsilon-sums
                    :two-step-epsilon-reference-max-error epsilon-reference-max-error
                    :two-step-latent-sums
                    (mapv #(reduce + (arr/->vec (:sample %))) @fixed-events)
                    :two-step-latent-sum (reduce + (arr/->vec fixed-latent))
                    :two-step-image-sum (reduce + fixed-values)
                    :two-step-image-first16 (vec (take 16 fixed-values))
                    :two-step-latent-reference-sum-error latent-reference-sum-error
                    :two-step-image-reference-max-error image-reference-max-error
                    :two-step-image-reference-sum-error image-reference-sum-error
                    :vae-tensors (count @(-> (:comfyui/decode vae)
                                             meta :comfyui/tensor-cache))
                    :seconds (/ (- (System/nanoTime) started) 1.0e9)}]
        (println (pr-str report))
        (when-not (and (= [1 16 16 3] (:image-shape report))
                       (> (:png-bytes report) 100)
                       (= [0 197 85 358 211 83 362 385 67 879 1 1]
                          (:clip-input-ids report))
                       (< clip-reference-max-error 1.0e-5)
                       (< epsilon-reference-max-error 1.0e-4)
                       (< latent-reference-sum-error 1.0e-3)
                       (< image-reference-max-error 1.0e-4)
                       (< image-reference-sum-error 1.0e-2)
                       (every? pos? ((juxt :model-tensors :clip-tensors :vae-tensors)
                                     report)))
          (throw (ex-info "real Diffusers pipeline verification failed" report))))
      (finally
        (doseq [checkpoint (map :comfyui/checkpoint [model clip vae])]
          (safe/close! checkpoint))))))
