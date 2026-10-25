(ns kotoba.lang.checkpointer.pin
  "Fire-and-forget IPFS pin via kotoba.lang.ipfs/pin-blob, mirroring
  checkpointer.ts's #pinSoon. `http` is an injected kotoba.lang.ipfs/IHttp
  (production wiring: kotoba.lang.checkpointer.http-jdk; tests inject a
  fake/mock -- the same IHttp seam kotoba-lang/ipfs already established, per
  this port's 'pure core + injected I/O' convention).

  `.clj`, genuinely JVM-only (not a compliance gap): `future` is JVM-thread-
  pool concurrency with no direct cljs equivalent (cljs has no threads;
  fire-and-forget there would be a Promise/core.async channel, a different
  concurrency model, not a reader-conditional swap-in). `kotoba.lang.ipfs`
  itself (the `IHttp`/`pin-blob` it calls) is already portable `.cljc`."
  (:require [kotoba.lang.ipfs :as ipfs]))

(defn pin-soon!
  "Runs on a separate thread so #put's response is never blocked on the pin.
  `on-result` is called with {:cid ... :size ...} on success, or nil on
  failure (errors are logged + swallowed -- 'will retry [via
  anchor_pending]', matching the TS catch clause's comment) -- kept as an
  explicit callback (rather than this fn mutating shared state itself) so
  the caller decides how/whether to update its index, keeping this fn
  independently testable with a fake `on-result`."
  [http ipfs-api-url ^bytes car-bytes on-result]
  (when ipfs-api-url
    (future
      (try
        (on-result (ipfs/pin-blob http ipfs-api-url car-bytes))
        (catch Exception e
          (binding [*out* *err*]
            (println "[checkpointer] pin failed (will retry):" (.getMessage e)))
          (on-result nil))))))
