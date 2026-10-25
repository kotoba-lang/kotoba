(ns torch.edge-runtime
  "Host-runtime plan for one resident OpenAI-compatible llama.cpp edge replica.

  num owns byte admission; torch owns the executable/model resource contract."
  (:require [num.residency :as residency]))

(defn replica-plan
  [{:keys [model-id model-path mmproj-path port context parallel
           memory-bytes os-reserve-bytes headroom-bytes
           runtime-bytes speculative-bytes context-bytes api-key-file llama-server
           mtp? draft-token-count batch ubatch]
    :or {parallel 1 mtp? false draft-token-count 3 speculative-bytes 0}}]
  (when-not (and (string? model-id) (seq model-id)
                 (string? model-path) (seq model-path)
                 (string? llama-server) (seq llama-server)
                 (pos-int? port) (pos-int? context) (pos-int? parallel)
                 (boolean? mtp?)
                 (or (not mtp?)
                     (and (pos-int? draft-token-count)
                          (<= draft-token-count 8)))
                 ;; Batch sizing is optional, but a half-specified pair is not
                 ;; a smaller batch -- it is llama.cpp's default silently
                 ;; overriding the one value that was measured, on a node that
                 ;; was given that value because the default did not fit.
                 (or (and (nil? batch) (nil? ubatch))
                     (and (pos-int? batch) (pos-int? ubatch) (<= ubatch batch))))
    (throw (ex-info "invalid edge replica plan" {:model model-id :port port})))
  (let [capacity (residency/admission
                  {:memory-bytes memory-bytes
                   :os-reserve-bytes os-reserve-bytes
                   :headroom-bytes headroom-bytes
                   :runtime-bytes runtime-bytes
                   :speculative-bytes speculative-bytes
                   :context-bytes context-bytes})]
    (assoc capacity
           :model-id model-id
           :mtp-enabled? mtp?
           :draft-token-count (when mtp? draft-token-count)
           :argv (cond-> [llama-server
                          "--model" model-path
                          "--alias" model-id
                          "--host" "127.0.0.1"
                          "--port" (str port)
                          "--ctx-size" (str context)
                          "--parallel" (str parallel)
                          "--flash-attn" "on"
                          "--cache-type-k" "q8_0"
                          "--cache-type-v" "q8_0"
                          "--jinja"
                          "--no-webui"]
                   ;; Physical and micro batch. Absent, llama.cpp uses 2048/512,
                   ;; which is the right default for a model with room to spare
                   ;; and the wrong one for a model that fills the machine: the
                   ;; compute buffer for a batch is charged on top of weights
                   ;; and KV, so on a node admitted with single-digit-percent
                   ;; free memory the batch is what pushes it into swap.
                   batch (into ["--batch-size" (str batch)
                                "--ubatch-size" (str ubatch)])
                   mtp? (into ["--n-gpu-layers" "99"
                               "-fit" "off"
                               "--spec-type" "draft-mtp"
                               "--spec-draft-n-max" (str draft-token-count)])
                   (seq mmproj-path) (into ["--mmproj" mmproj-path])
                   (seq api-key-file) (into ["--api-key-file" api-key-file])))))
