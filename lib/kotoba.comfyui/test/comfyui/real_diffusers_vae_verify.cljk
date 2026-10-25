(ns comfyui.real-diffusers-vae-verify
  "Decode a latent through a real Diffusers AutoencoderKL safetensors file."
  (:require [json.data-json :as json]
            [kotoba.lang.text :as str]
            [comfyui.nodes.diffusion-runtime :as runtime]
            [comfyui.safetensors :as safe]
            [num.array :as arr]
            [num.cpu :as cpu])
  (:import [java.io FileReader]))

(defn -main [& [checkpoint-path config-path]]
  (when-not (and checkpoint-path config-path)
    (throw (ex-info "usage: real-diffusers-vae-verify vae.safetensors config.json" {})))
  (let [config (with-open [reader (FileReader. config-path)]
                 (json/read reader))
        backend (cpu/cpu-backend)
        definitions (runtime/pack
                     {:backend backend
                      :resolve-checkpoint (constantly checkpoint-path)
                      :diffusers-vae-config config})
        loader (first (filter #(= "CheckpointLoaderSimple" (:type %)) definitions))
        vae-decode (first (filter #(= "VAEDecode" (:type %)) definitions))
        vae-encode (first (filter #(= "VAEEncode" (:type %)) definitions))
        [_model _clip vae] ((:fn loader) {:ckpt_name checkpoint-path})]
    (try
      (let [latent (arr/from-vec
                    backend (map #(- (* 0.002 %) 0.25) (range (* 4 8 8)))
                    [1 4 8 8])
            started (System/nanoTime)
            [image] ((:fn vae-decode) {:samples latent :vae vae})
            [roundtrip-latent] ((:fn vae-encode) {:pixels image :vae vae})
            values (arr/->vec image)
            latent-values (arr/->vec roundtrip-latent)
            reference-first8 [0.4374271631240845 0.3919304311275482
                              0.4134933352470398 0.42122697830200195
                              0.47406381368637085 0.499450147151947
                              0.5006544589996338 0.45798537135124207]
            reference-max-error (apply max (map #(Math/abs (- %1 %2))
                                                 (take 8 values) reference-first8))
            reference-sum-error (Math/abs (- (reduce + values)
                                             392.2850646972656))
            decoder-cache @(-> (:comfyui/decode vae) meta :comfyui/tensor-cache)
            encoder-cache @(-> (:comfyui/encode vae) meta :comfyui/tensor-cache)
            report {:architecture (get-in vae [:comfyui/model-spec :architecture])
                    :checkpoint-tensors (count (safe/tensor-names
                                                (:comfyui/checkpoint vae)))
                    :loaded-tensors (+ (count decoder-cache) (count encoder-cache))
                    :encoder-tensors-loaded
                    (count (filter #(str/starts-with? % "encoder.")
                                   (keys encoder-cache)))
                    :encoded-shape (:shape roundtrip-latent)
                    :encoded-finite (every? #(Double/isFinite (double %)) latent-values)
                    :shape (:shape image)
                    :finite (every? #(Double/isFinite (double %)) values)
                    :range [(apply min values) (apply max values)]
                    :sum (reduce + values)
                    :first8 (vec (take 8 values))
                    :reference-max-error reference-max-error
                    :reference-sum-error reference-sum-error
                    :seconds (/ (- (System/nanoTime) started) 1.0e9)}]
        (println (pr-str report))
        (when-not (and (= :diffusers-autoencoder-kl (:architecture report))
                       (= [1 16 16 3] (:shape report)) (:finite report)
                       (= [1 4 8 8] (:encoded-shape report)) (:encoded-finite report)
                       (every? #(<= 0.0 % 1.0) values)
                       (pos? (:loaded-tensors report))
                       (pos? (:encoder-tensors-loaded report))
                       (< reference-max-error 1.0e-4)
                       (< reference-sum-error 1.0e-2))
          (throw (ex-info "real Diffusers VAE verification failed" report))))
      (finally
        (safe/close! (:comfyui/checkpoint vae))))))
