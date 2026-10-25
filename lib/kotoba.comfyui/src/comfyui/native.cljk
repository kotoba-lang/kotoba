(ns comfyui.native
  "Pure SDXL txt2img node graphs for ComfyUI's **native** protocol.

  `comfyui.gateway` speaks the OpenAI-images shape and therefore needs a
  translating bridge in front of a real ComfyUI. That bridge is a middle layer
  that can be down while ComfyUI itself is up — observed 2026-07-31 on the
  murakumo fleet head node. This namespace removes it: the graph goes to
  /prompt as ComfyUI's own format.

  Pure: a request map in, a graph out. No HTTP, no env, so a graph can be
  asserted in a test without a GPU. `comfyui.native-client` moves the bytes.

  Node input names and defaults were read from a live server's /object_info
  (KSampler, EmptyLatentImage, SaveImage), not guessed."

  (:require [kotoba.lang.text :as str]))

(def default-config
  "Defaults a caller may override wholesale. A consumer that cares about style
  should state its own config rather than inherit these — the checkpoint in
  particular is a craft decision, not a technical one.

  A caller must NOT pass a model name that came out of its own data without
  checking it against the server: one caller's records carried
  `:sdxlModel \"gpt-4o-mini\"`, the LLM that wrote the prompt rather than an
  image model, which fails at the server with a confusing enum error."
  {:checkpoint "Illustrious-XL-v2.0.safetensors"
   :width 832
   :height 1216           ; portrait default; callers override
   :steps 28
   :cfg 5.0
   :sampler "euler_ancestral"
   :scheduler "karras"
   :denoise 1.0})

(def default-negative
  ["low quality" "worst quality" "blurry"])

(defn- text-of
  "A prompt field that may be a tag vector or an already-joined string."
  [v fallback]
  (cond
    (sequential? v) (str/join ", " v)
    (str/blank? (str v)) (str/join ", " fallback)
    :else (str v)))

(defn seed
  "A deterministic seed from a stable key, so re-running the same unit
  reproduces the same image. Derived rather than random: `Math/random` would
  make every retry a different picture and make a retry indistinguishable from
  a change."
  [k]
  ;; `(int c)` is NOT portable here: under ClojureScript a seq'd string yields
  ;; single-character STRINGS and `(int \"k\")` is 0, so the hash ignored the key
  ;; entirely and depended only on its length. Every unit whose key was the same
  ;; length got the same seed. It looked fine because differing prompts still
  ;; produce differing images — the seed was simply doing nothing.
  (let [code #?(:clj (fn [c] (int c))
                :cljs (fn [c] (.charCodeAt c 0)))]
    ;; `(bit-or 0 x)` truncates to a signed 32-bit int in JavaScript but is a
    ;; NO-OP on the JVM, where `bit-or` is a long operation. So `h` grew without
    ;; bound under :clj and `(* 31 h)` threw `ArithmeticException: long overflow`
    ;; once the key was long enough — while :cljs silently kept wrapping. The two
    ;; platforms were computing different seeds before that, and the JVM stopped
    ;; computing one at all. `unchecked-multiply` + `unchecked-int` is the same
    ;; `|0` truncation on both.
    (Math/abs (reduce (fn [h c] (unchecked-int (+ (unchecked-multiply 31 h) (code c)))) 7 (str k)))))

(defn graph
  "Request + config -> the ComfyUI node graph, keyed by node id.

  Request:
    :prompt    tag vector or string (required)
    :negative  tag vector or string (optional)
    :key       stable identity for the seed and the filename (optional)

  Node ids are strings because /prompt takes an object keyed by id; a vector
  [id slot] is how one node references another's output."
  ([req] (graph req nil))
  ([{:keys [prompt negative key]} cfg]
   ;; Read every value off the MERGED map. Destructuring with
   ;; `:or {x (:y cfg)}` reads the *argument*, not the merge, which is how an
   ;; earlier version produced `:cfg nil` for `(graph req {})` and had ComfyUI
   ;; reject the prompt while the no-config path worked.
   (let [{:keys [checkpoint width height steps cfg sampler scheduler denoise]}
         (merge default-config cfg)
         pos (text-of prompt nil)]
     {"1" {:class_type "CheckpointLoaderSimple"
           :inputs {:ckpt_name checkpoint}}
      "2" {:class_type "CLIPTextEncode"
           :inputs {:clip ["1" 1] :text pos}}
      "3" {:class_type "CLIPTextEncode"
           :inputs {:clip ["1" 1] :text (text-of negative default-negative)}}
      "4" {:class_type "EmptyLatentImage"
           :inputs {:width width :height height :batch_size 1}}
      "5" {:class_type "KSampler"
           :inputs {:model ["1" 0]
                    :positive ["2" 0]
                    :negative ["3" 0]
                    :latent_image ["4" 0]
                    :seed (seed (or key pos))
                    :steps steps
                    :cfg cfg
                    :sampler_name sampler
                    :scheduler scheduler
                    :denoise denoise}}
      "6" {:class_type "VAEDecode"
           :inputs {:samples ["5" 0] :vae ["1" 2]}}
      "7" {:class_type "SaveImage"
           :inputs {:images ["6" 0]
                    :filename_prefix (str (or key "comfyui-native"))}}})))
