(ns kotodama.verify.qwen4exp-b70-runtime-compatibility
  "Verify that unsupported B70 runtime checks remain N/A instead of becoming a
  fabricated zero-throughput ranking."
  (:require [json.data-json :as json]))

(defn -main [& _]
  (let [evidence (json/read-str
                  (slurp "verify/evidence/qwen4exp-b70-runtime-compatibility-20260829.json"))
        target (get evidence "target")
        node (get evidence "node")
        capacity (get evidence "capacity_gates")
        runtimes (get evidence "runtimes")
        comparison (get evidence "comparison")
        control (get evidence "control")
        resident (get evidence "final_resident_state")
        post-record (get evidence "post_record_live_check")]
    (when-not (and (= "qwen4_exp" (get target "model_type"))
                   (= "Intel(R) Arc(TM) Pro B70 Graphics" (get node "gpu"))
                   (= 32656 (get node "gpu_memory_mib"))
                   (< (get node "system_memory_gib")
                      (get capacity "official_vllm_ngram_offload_minimum_host_gb"))
                   (every? (fn [[_ runtime]]
                             (and (false? (get runtime "valid_tok_s"))
                                  (nil? (get runtime "tok_s"))
                                  (false? (get runtime "generation_started"))))
                           runtimes)
                   (empty? (get-in runtimes ["vllm" "qwen4exp_registered_architectures"]))
                   (false? (get-in runtimes ["ktransformers" "intel_xpu_serving_supported"]))
                   (false? (get comparison "numeric_ranking_qualified"))
                   (false? (get comparison "unsupported_is_zero_throughput"))
                   (false? (get control "ranking_member"))
                   (pos? (get control "generation_tok_s"))
                   (= "comparison-end" (get resident "snapshot_kind"))
                   (true? (get resident "not_current_state_claim"))
                   (true? (get resident "flash_next_service_active"))
                   (true? (get resident "join_service_active"))
                   (= 200 (get resident "health_http_status"))
                   (= 32768 (get resident "reported_context_tokens"))
                   (false? (get post-record "flash_next_service_active"))
                   (false? (get post-record "flash_next_service_enabled"))
                   (true? (get post-record "llama_27b_service_active"))
                   (true? (get post-record "llama_27b_service_enabled"))
                   (true? (get post-record "join_service_active"))
                   (= 200 (get post-record "health_http_status"))
                   (= "qwen3.8-27b-throughput-b70"
                      (get post-record "model_alias")))
      (throw (ex-info "B70 runtime evidence crossed its qualification boundary"
                      comparison)))
    (prn {:target (get target "model_type")
          :runtime-statuses (into {}
                                  (map (fn [[runtime result]]
                                         [runtime (get result "status")]))
                                  runtimes)
          :numeric-ranking-qualified false})))
