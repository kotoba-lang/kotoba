(ns comfyui.real-diffusers-unet-verify
  "Execute a real small Diffusers Stable Diffusion UNet safetensors graph."
  (:require [json.data-json :as json]
            [comfyui.nodes.diffusion-runtime :as runtime]
            [comfyui.safetensors :as safe]
            [num.array :as arr]
            [num.cpu :as cpu])
  (:import [java.io FileReader]))

(defn -main [& [checkpoint-path config-path]]
  (when-not (and checkpoint-path config-path)
    (throw (ex-info "usage: real-diffusers-unet-verify unet.safetensors config.json" {})))
  (let [config (with-open [reader (FileReader. config-path)]
                 (json/read reader))
        backend (cpu/cpu-backend)
          loader (first (filter #(= "CheckpointLoaderSimple" (:type %))
                                (runtime/pack {:backend backend
                                               :resolve-checkpoint (constantly checkpoint-path)
                                               :diffusers-config config})))
          [model _clip _vae] ((:fn loader) {:ckpt_name checkpoint-path})
          spec (:comfyui/model-spec model)
        denoise (:comfyui/denoise model)]
    (try
      (let [checkpoint (:comfyui/checkpoint model)
          sample (arr/from-vec backend
                               (map #(- (* 0.001 %) 0.1) (range (* 4 8 8)))
                               [1 4 8 8])
          conditioning {:tensor (arr/from-vec backend (repeat (* 4 32) 0.01)
                                              [1 4 32])}
          started (System/nanoTime)
          output (denoise sample 10 conditioning)
          values (arr/->vec output)
          reference-first16
          [-0.29191914200782776 -0.33132222294807434 -0.40973877906799316
           0.05906502157449722 -0.0688026174902916 0.0985460877418518
           -0.11644833534955978 0.0016031544655561447 -0.07609662413597107
           0.08188310265541077 -0.08149494230747223 0.5356400012969971
           0.06697320193052292 -0.18308958411216736 -0.3919602930545807
           0.2770814299583435]
          reference-max-error (apply max (map #(Math/abs (- %1 %2))
                                               (take 16 values) reference-first16))
          reference-sum-error (Math/abs (- (reduce + values) -5.931081771850586))
          report {:architecture (:architecture spec) :layers (count (:layers spec))
                  :checkpoint-tensors (count (safe/tensor-names checkpoint))
                  :loaded-tensors (count @(-> denoise meta :comfyui/tensor-cache))
                  :shape (:shape output)
                  :finite (every? #(Double/isFinite (double %)) values)
                  :sum (reduce + values)
                  :range [(apply min values) (apply max values)]
                  :first16 (vec (take 16 values))
                  :reference-max-error reference-max-error
                  :reference-sum-error reference-sum-error
                  :seconds (/ (- (System/nanoTime) started) 1.0e9)}]
      (println (pr-str report))
      (when-not (and spec (= [1 4 8 8] (:shape output)) (:finite report)
                     (pos? (:loaded-tensors report))
                     (< reference-max-error 1.0e-4)
                     (< reference-sum-error 1.0e-3))
          (throw (ex-info "real Diffusers UNet verification failed" report))))
      (finally
        (safe/close! (:comfyui/checkpoint model))))))
