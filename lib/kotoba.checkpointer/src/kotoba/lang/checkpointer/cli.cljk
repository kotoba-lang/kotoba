(ns kotoba.lang.checkpointer.cli
  "CLI entrypoint -- env var resolution + JVM shutdown-hook signal handling,
  mirroring checkpointer-bin.ts + checkpointer.ts's `runFromEnv`.

  `.clj`, genuinely JVM-only (not a compliance gap): `cfg-from-env`/`-main`
  are `System/getenv`/`Runtime/getRuntime`/JVM-shutdown-hook/blocking-main-
  thread process bootstrapping -- a process entrypoint, not portable core
  logic. `resolve-did-list` (the one piece with a real claim to being a
  'pure indexKey/resolveDidList-style helper', per this port's design doc)
  is NOT fully pure either: its `@/abs/path` branch does a real `slurp` file
  read, so it isn't split out into a separate `.cljc` namespace here -- doing
  so would need its own injected file-read capability, a module-boundary
  change beyond this compliance pass's rename+reader-conditional scope."
  (:require [kotoba.lang.text :as str]
            [kotoba.lang.checkpointer.sidecar :as sidecar]))

(defn resolve-did-list
  "Mirrors checkpointer.ts's `resolveDidList`: `raw` may be a comma/
  whitespace-separated value, an `@/abs/path` file reference (sidesteps the
  OS ARG_MAX when ALLOWED_DIDS/ENCRYPT_CELLS together must cover a very
  large DID list), or the sentinel `*` (only meaningful for ENCRYPT_CELLS,
  paired with `fallback-allowed` = 'every allowed cell')."
  ([raw] (resolve-did-list raw nil))
  ([raw fallback-allowed]
   (cond
     (str/blank? raw) []
     (and (= raw "*") fallback-allowed) (vec fallback-allowed)
     :else
     (let [body (if (str/starts-with? raw "@") (slurp (subs raw 1)) raw)]
       (->> (str/split body #"[,\s]+")
            (map str/trim)
            (remove str/blank?)
            vec)))))

(defn cfg-from-env
  "Reads env vars into a `sidecar/start!` cfg map. Throws if
  ETZ_CHECKPOINTER_ALLOWED_DIDS is unset/empty, or if ENCRYPT_CELLS lists a
  DID not in ALLOWED_DIDS -- both match checkpointer.ts's `runFromEnv`."
  []
  (let [allowed (resolve-did-list (System/getenv "ETZ_CHECKPOINTER_ALLOWED_DIDS"))]
    (when (empty? allowed)
      (throw (ex-info (str "ETZ_CHECKPOINTER_ALLOWED_DIDS must list at least one DID "
                            "(comma-separated, @/abs/path, or *)")
                       {})))
    (let [allowed-set (set allowed)
          encrypt-cells (set (resolve-did-list (System/getenv "ETZ_CHECKPOINTER_ENCRYPT_CELLS") allowed-set))]
      (doseq [did encrypt-cells]
        (when-not (contains? allowed-set did)
          (throw (ex-info (str "ETZ_CHECKPOINTER_ENCRYPT_CELLS lists " did
                                " not in ETZ_CHECKPOINTER_ALLOWED_DIDS")
                           {:did did}))))
      {:socket-path (or (System/getenv "ETZ_CHECKPOINTER_SOCKET") "/run/etzhayyim/checkpointer.sock")
       :state-dir (or (System/getenv "ETZ_CHECKPOINTER_STATE_DIR")
                       (str (System/getProperty "user.home") "/.etzhayyim/checkpointer"))
       :allowed-dids allowed-set
       :ipfs-api-url (System/getenv "ETZ_IPFS_API_URL")
       :anchor-chain-id (if-let [v (System/getenv "ETZ_ANCHOR_CHAIN_ID")] (Long/parseLong v) 8453)
       :encrypt-cells encrypt-cells})))

(defn run-from-env!
  "Resolves env-based config and starts the sidecar. Returns the running
  Sidecar."
  []
  (sidecar/start! (cfg-from-env)))

(defn -main [& _args]
  (let [sc (run-from-env!)]
    (.addShutdownHook (Runtime/getRuntime)
                       (Thread. ^Runnable
                                (fn []
                                  (binding [*out* *err*] (println "[checkpointer] received shutdown signal, stopping..."))
                                  (sidecar/stop! sc))))
    (binding [*out* *err*] (println "[checkpointer] sidecar listening"))
    ;; the accept-loop thread is a daemon thread; block the main thread
    ;; forever so the JVM stays up until a shutdown hook fires.
    @(promise)))
