(ns kami.gen.hybrid.workflow
  "Prompt -> `comfyui-clj` workflow EDN. ADR-2607051130: 'a template-based
  EDN builder that fills in the prompt string and resolution into a fixed
  graph shape is genuinely fine [for v0] ... inject the graph-builder as a
  function so a smarter one can be swapped in later.'

  `costume-prompt->workflow` is exactly that: a pure, deterministic
  template — no LLM call, no network, no randomness beyond the caller's own
  `:seed`. A later iteration can swap in an LLM-authored graph builder (one
  that varies node COUNT/shape — extra ControlNet/LoRA nodes, a different
  sampler — not just these fixed slots) behind the same
  `(fn [costume-prompt opts] -> workflow-edn)` signature; `kami.gen.hybrid/
  generate` takes it as an injected `:graph-builder` option for exactly
  that reason, same DI seam convention as this org's other /loop-maturity
  agent repos (propose/critique-shaped, e.g. sibling `kami-gen-sdf-agent`).")

(def channels [:albedo :normal :roughness])

(def default-negative-prompt
  "low quality, blurry, distorted, extra limbs, watermark, text")

(defn- chan-name [c] (name c))

(defn costume-prompt->workflow
  "Builds a `comfyui-clj` API-format workflow EDN: one shared
  `CheckpointLoaderSimple` + positive/negative `CLIPTextEncode` +
  `EmptyLatentImage`, feeding 3 parallel `KSampler -> VAEDecode ->
  SaveTextureImage` chains, one per texture channel (`:albedo :normal
  :roughness`) targeting the body's UV-unwrapped texture-slot resolution.

  `opts`: `{:width :height :seed :negative-prompt :steps :cfg
  :sampler-name :scheduler :denoise :ckpt-name :filename-prefix}` (all but
  `:width`/`:height` have defaults). Per-channel seeds are
  `seed + channel-offset` (0/1/2) — a real graph-authoring LLM would instead
  vary graph STRUCTURE per channel (e.g. a normal-map-specialized
  ControlNet pass); documented v0 simplification, not hidden.

  Returns `{:workflow <EDN> :targets [<SaveTextureImage node-ids>]}`."
  [costume-prompt
   {:keys [width height seed negative-prompt steps cfg sampler-name scheduler denoise
           ckpt-name filename-prefix]
    :or {seed 0
         negative-prompt default-negative-prompt
         steps 20 cfg 7.0 sampler-name "euler" scheduler "normal" denoise 1.0
         ckpt-name "sdxl-base-placeholder"
         filename-prefix "kami_gen_hybrid"}}]
  (when-not (and (pos-int? width) (pos-int? height))
    (throw (ex-info "costume-prompt->workflow: :width/:height must be positive ints"
                     {:width width :height height})))
  (let [base
        {"ckpt" {:class_type "CheckpointLoaderSimple" :inputs {:ckpt_name ckpt-name}}
         "clip_pos" {:class_type "CLIPTextEncode"
                     :inputs {:text (str costume-prompt) :clip ["ckpt" 1]}}
         "clip_neg" {:class_type "CLIPTextEncode"
                     :inputs {:text negative-prompt :clip ["ckpt" 1]}}
         "latent" {:class_type "EmptyLatentImage"
                   :inputs {:width width :height height :batch_size 1}}}
        per-channel-flat
        (into {}
              (mapcat
               (fn [i c]
                 (let [cn (chan-name c)
                       sampler-id (str "sampler_" cn)
                       decode-id (str "decode_" cn)
                       save-id (str "save_" cn)]
                   [[sampler-id
                     {:class_type "KSampler"
                      :inputs {:model ["ckpt" 0] :positive ["clip_pos" 0] :negative ["clip_neg" 0]
                               :latent_image ["latent" 0] :seed (+ seed i)
                               :steps steps :cfg cfg :sampler_name sampler-name
                               :scheduler scheduler :denoise denoise :channel cn}}]
                    [decode-id
                     {:class_type "VAEDecode" :inputs {:samples [sampler-id 0] :vae ["ckpt" 2]}}]
                    [save-id
                     {:class_type "SaveTextureImage"
                      :inputs {:images [decode-id 0] :filename_prefix filename-prefix :channel cn}}]]))
               (range) channels))
        workflow (merge base per-channel-flat)
        targets (mapv (fn [c] (str "save_" (chan-name c))) channels)]
    {:workflow workflow :targets targets}))
