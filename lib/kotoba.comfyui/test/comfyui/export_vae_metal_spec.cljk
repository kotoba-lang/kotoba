(ns comfyui.export-vae-metal-spec
  "Export an inferred Diffusers AutoencoderKL graph for the Deno Metal gate."
  (:require [json.data-json :as json]
            [comfyui.diffusion.architecture :as architecture]
            [comfyui.safetensors :as safe])
  (:import [java.nio.file Files Path]))

(defn -main [& [output checkpoint-path config-path]]
  (when-not config-path
    (throw (ex-info "usage: OUTPUT CHECKPOINT CONFIG" {})))
  (with-open [checkpoint (safe/open-file checkpoint-path)]
    (let [config (json/read-str
                  (Files/readString (Path/of config-path (make-array String 0))))
          spec (architecture/infer-diffusers-vae-spec checkpoint config)]
      (when-not spec
        (throw (ex-info "unable to infer Diffusers VAE" {})))
      (spit output (pr-str spec))
      (println output))))
