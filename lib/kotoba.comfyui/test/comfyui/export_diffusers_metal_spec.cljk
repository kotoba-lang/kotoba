(ns comfyui.export-diffusers-metal-spec
  "Export inferred graph data and deterministic tokens for the Deno Metal host."
  (:require [json.data-json :as json]
            [comfyui.clip.tokenizer :as tokenizer]
            [comfyui.diffusion.architecture :as architecture]
            [comfyui.diffusion.scheduler :as scheduler]
            [comfyui.safetensors :as safe])
  (:import [java.nio.file Files Path]))

(defn- read-json [path]
  (json/read-str (Files/readString (Path/of path (make-array String 0)))))

(defn -main
  [& [output unet unet-config text text-config vae vae-config scheduler-config
      vocab merges]]
  (when-not merges
    (throw (ex-info "usage: export OUTPUT UNET UNET_CONFIG TEXT TEXT_CONFIG VAE VAE_CONFIG SCHEDULER VOCAB MERGES" {})))
  (with-open [unet-file (safe/open-file unet)
              text-file (safe/open-file text)
              vae-file (safe/open-file vae)]
    (let [unet-config (read-json unet-config)
          text-config (read-json text-config)
          vae-config (read-json vae-config)
          scheduler-config (read-json scheduler-config)
          getc #(or (get scheduler-config %) (get scheduler-config (keyword %)))
          betas ((case (getc "beta_schedule")
                   "scaled_linear" scheduler/scaled-linear-betas
                   "linear" scheduler/linear-betas)
                 (long (getc "num_train_timesteps"))
                 (double (getc "beta_start")) (double (getc "beta_end")))
          tokenize (tokenizer/load-tokenizer vocab merges {:pad-token "<|endoftext|>"})
          exported {:unet (architecture/infer-diffusers-unet-spec unet-file unet-config)
                    :clip (architecture/infer-diffusers-clip-spec text-file text-config)
                    :vae (architecture/infer-diffusers-vae-spec vae-file vae-config)
                    :alphas (scheduler/alphas-cumprod betas)
                    :positive (tokenize "a tiny red robot")
                    :negative (tokenize "blurry")}]
      (when-not (every? exported [:unet :clip :vae])
        (throw (ex-info "incomplete exported pipeline" {})))
      (spit output (pr-str exported))
      (println output))))
