(ns kotodama.inference.ports
  "Host ports for model runtimes. The .cljc kernel never imports JS packages,
  opens GPU devices, or reads model files by itself. Browser, terminal, and
  kotoba-runtime hosts inject implementations of these protocols.")

(defprotocol IModelRuntime
  (probe! [this]
    "Return a data map describing available backends and limits.")
  (load! [this runtime-spec]
    "Load a model/runtime spec. Returns a session data map.")
  (generate! [this session prompt-or-token-ids generation]
    "Generate text or token ids from a loaded session.")
  (forward! [this session token-ids options]
    "Run a raw forward pass. Returns logits or host-defined tensor data.")
  (dispose! [this session]
    "Release host resources for a session. Returns a data map."))

(def no-runtime
  (reify IModelRuntime
    (probe! [_] {:kotodama/backends []})
    (load! [_ runtime-spec]
      (throw (ex-info "no kotodama IModelRuntime bound"
                      {:kotodama/runtime-spec runtime-spec})))
    (generate! [_ session input generation]
      (throw (ex-info "no kotodama IModelRuntime bound"
                      {:kotodama/session session
                       :kotodama/input input
                       :kotodama/generation generation})))
    (forward! [_ session token-ids options]
      (throw (ex-info "no kotodama IModelRuntime bound"
                      {:kotodama/session session
                       :kotodama/input-ids token-ids
                       :kotodama/options options})))
    (dispose! [_ session]
      {:kotodama/disposed? false
       :kotodama/session session})))

(defn fn-runtime
  "Build an `IModelRuntime` from functions. Useful for tests, SCI, and thin
  adapters around browser WebGPU, terminal wasm, or Rust kotodama inference."
  [{:keys [probe load generate forward dispose]}]
  (reify IModelRuntime
    (probe! [_] (if probe (probe) {:kotodama/backends []}))
    (load! [_ runtime-spec] (load runtime-spec))
    (generate! [_ session input generation] (generate session input generation))
    (forward! [_ session token-ids options] (forward session token-ids options))
    (dispose! [_ session] (if dispose (dispose session) {:kotodama/disposed? true}))))
