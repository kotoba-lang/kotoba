(ns comfyui.nodes.diffusion
  "Diffusion node-type CONTRACTS for image/video/audio generation — the type
  surface ComfyUI's own diffusion nodes expose, as portable cljc data. Like
  comfyui.std these declare INPUT_TYPES / RETURN_TYPES so comfyui.workflow can
  VALIDATE a real txt2img / img2vid / txt2audio graph; the heavy compute
  (checkpoint load, sampling, VAE) is a host capability injected at exec time
  (`:fn` is host-bound, so these carry none). This is what lets a kotoba host —
  or murakumo's fleet operator — hand ComfyUI-API-format workflows to a portable
  engine without the Python runtime.")

(defn- t [type-name category inputs outputs]
  {:type type-name :category category :inputs inputs :outputs outputs})

;; ── shared latent/conditioning/image/model types ────────────────────────────
;; MODEL CLIP VAE CONDITIONING LATENT IMAGE AUDIO — ComfyUI's core wire types.

(def checkpoint-loader
  (t "CheckpointLoaderSimple" "loaders"
     {:ckpt_name {:type "STRING"}}
     [{:name "MODEL" :type "MODEL"} {:name "CLIP" :type "CLIP"} {:name "VAE" :type "VAE"}]))

(def image-only-checkpoint-loader
  (t "ImageOnlyCheckpointLoader" "loaders"
     {:ckpt_name {:type "STRING"}}
     [{:name "MODEL" :type "MODEL"} {:name "CLIP_VISION" :type "CLIP_VISION"}
      {:name "VAE" :type "VAE"}]))

(def clip-loader
  (t "CLIPLoader" "loaders"
     {:clip_name {:type "STRING"} :type {:type "STRING"}}
     [{:name "CLIP" :type "CLIP"}]))

(def clip-text-encode
  (t "CLIPTextEncode" "conditioning"
     {:clip {:type "CLIP"} :text {:type "STRING"}}
     [{:name "CONDITIONING" :type "CONDITIONING"}]))

(def clip-text-encode-sdxl
  (t "CLIPTextEncodeSDXL" "advanced/conditioning"
     {:clip {:type "CLIP"} :text {:type "STRING"}
      :width {:type "INT"} :height {:type "INT"}
      :crop_w {:type "INT"} :crop_h {:type "INT"}
      :target_width {:type "INT"} :target_height {:type "INT"}}
     [{:name "CONDITIONING" :type "CONDITIONING"}]))

(def empty-latent-image
  (t "EmptyLatentImage" "latent"
     {:width {:type "INT" :default 512} :height {:type "INT" :default 512}
      :batch_size {:type "INT" :default 1}}
     [{:name "LATENT" :type "LATENT"}]))

(def empty-ltxv-latent-video
  (t "EmptyLTXVLatentVideo" "latent/video"
     {:width {:type "INT" :default 704} :height {:type "INT" :default 480}
      :length {:type "INT" :default 97} :batch_size {:type "INT" :default 1}}
     [{:name "LATENT" :type "LATENT"}]))

(def ltxv-conditioning
  (t "LTXVConditioning" "conditioning/video"
     {:positive {:type "CONDITIONING"} :negative {:type "CONDITIONING"}
      :frame_rate {:type "FLOAT" :default 25.0}}
     [{:name "positive" :type "CONDITIONING"} {:name "negative" :type "CONDITIONING"}]))

(def empty-latent-audio
  (t "EmptyLatentAudio" "latent/audio"
     {:seconds {:type "FLOAT" :default 10.0}}
     [{:name "LATENT" :type "LATENT"}]))

(def ksampler
  (t "KSampler" "sampling"
     {:model {:type "MODEL"} :positive {:type "CONDITIONING"}
      :negative {:type "CONDITIONING"} :latent_image {:type "LATENT"}
      :seed {:type "INT" :default 0} :steps {:type "INT" :default 20}
      :cfg {:type "FLOAT" :default 7.0} :sampler_name {:type "STRING"}
      :scheduler {:type "STRING"} :denoise {:type "FLOAT" :default 1.0}}
     [{:name "LATENT" :type "LATENT"}]))

(def svd-conditioning
  (t "SVD_img2vid_Conditioning" "conditioning/video"
     {:clip_vision {:type "CLIP_VISION"} :init_image {:type "IMAGE"}
      :vae {:type "VAE"} :width {:type "INT"} :height {:type "INT"}
      :video_frames {:type "INT"} :motion_bucket_id {:type "INT"}
      :fps {:type "INT"} :augmentation_level {:type "FLOAT"}}
     [{:name "positive" :type "CONDITIONING"} {:name "negative" :type "CONDITIONING"}
      {:name "latent" :type "LATENT"}]))

(def vae-decode
  (t "VAEDecode" "latent"
     {:samples {:type "LATENT"} :vae {:type "VAE"}}
     [{:name "IMAGE" :type "IMAGE"}]))

(def vae-decode-audio
  (t "VAEDecodeAudio" "latent/audio"
     {:samples {:type "LATENT"} :vae {:type "VAE"}}
     [{:name "AUDIO" :type "AUDIO"}]))

(def load-image
  (t "LoadImage" "image"
     {:image {:type "STRING"}}
     [{:name "IMAGE" :type "IMAGE"} {:name "MASK" :type "MASK"}]))

(def save-image
  (t "SaveImage" "image"
     {:images {:type "IMAGE"} :filename_prefix {:type "STRING" :default "ComfyUI"}}
     []))

(def save-animated-webp
  (t "SaveAnimatedWEBP" "image/animation"
     {:images {:type "IMAGE"} :filename_prefix {:type "STRING"} :fps {:type "INT"}
      :lossless {:type "BOOLEAN" :default false} :quality {:type "INT" :default 85}
      :method {:type "STRING" :default "default"}}
     []))

(def save-audio
  (t "SaveAudio" "audio"
     {:audio {:type "AUDIO"} :filename_prefix {:type "STRING" :default "audio"}}
     []))

(def pack
  "The diffusion node pack — register alongside comfyui.std to validate
  image/video/audio workflows."
  [checkpoint-loader image-only-checkpoint-loader clip-loader clip-text-encode
   clip-text-encode-sdxl
   empty-latent-image empty-latent-audio empty-ltxv-latent-video
   ltxv-conditioning ksampler svd-conditioning
   vae-decode vae-decode-audio load-image save-image save-animated-webp
   save-audio])
