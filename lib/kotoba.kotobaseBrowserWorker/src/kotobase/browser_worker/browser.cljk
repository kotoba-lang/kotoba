(ns kotobase.browser-worker.browser
  "Browser shell (sibling to kotobase.cljc-worker.worker, which is the
  Cloudflare/R2 shell) -- ADR-2607051700 (app-aozora): wires the SAME pure
  XRPC handler (kotobase.cljc-worker.handler) and the SAME block-miss
  trampoline (kotobase.cljc-worker.r2/with-blocks, reused verbatim -- it
  never depended on R2 specifics) to IndexedDB instead of R2.

  Phase 1 scope: local-same-page use only, no CACAO/HTTP layer. A caller in
  the SAME browser tab already holds the local signing key (or is a test
  harness standing in for one), so the remote-caller auth gate the R2
  worker's fetch-handler enforces doesn't apply to a purely local read/
  write. Wiring this to a real actor identity, and a fetch-handler for
  OTHER pages/peers to call over the network, is a follow-up -- proving the
  storage/engine claim (kotobase-peer runs, unmodified, entirely inside a
  browser tab) does not require it."
  (:require [kotobase.cljc-worker.handler :as h]
            [kotobase.cljc-worker.r2 :as r2]
            [kotobase.browser-worker.idb :as idb]))

(defn run-read
  "Reads (datoms/q/pull): trampoline the sync handler through IndexedDB
  blocks. Same shape as kotobase.cljc-worker.worker/run-read."
  [db method body]
  (-> (idb/get-head db (:graph body))
      (.then (fn [{:keys [chain]}]
               (r2/with-blocks
                 (fn [cid] (idb/get-bytes db cid))
                 (fn [sync-get]
                   (h/handle {:get-fn sync-get :head-get (constantly chain)}
                             method body nil)))))))

(defn- flush-and-cas!
  "After a successful pure write (transact OR fold): flush the buffered
  blocks (always safe even on an eventual CAS loss -- content-addressed, a
  retry's blocks are identical or simply orphaned, never corrupting), then
  attempt the conditional head write. Same shape as
  kotobase.cljc-worker.worker/flush-blocks-and-cas-head!."
  [db graph etag resp buffer]
  (if (nil? (:commit resp))
    (js/Promise.resolve {:resp resp :cas-ok? true})
    (-> (js/Promise.all
         (clj->js (map (fn [[cid bytes]] (idb/put-bytes! db cid bytes)) @buffer)))
        (.then (fn [_] (idb/put-head-if-match! db graph (:commit resp) etag)))
        (.then (fn [cas-ok?] {:resp resp :cas-ok? cas-ok?})))))

(defn- run-write-attempt
  "One CAS round for a head-mutating method (transact or fold). Same shape
  as kotobase.cljc-worker.worker/run-write-attempt, with one correction:
  :get-fn is a read-your-own-writes merge of `buffer` (this call's own
  not-yet-flushed :put!s) over the with-blocks trampoline, not the
  trampoline alone.

  Without the merge, do-transact's OWN novelty_size re-read of the
  chain-cid it just committed misses the buffered (unflushed) commit
  block: with-blocks' sync-get throws missing-block (nothing cached yet),
  the trampoline fetches that cid from DURABLE storage (a genuine miss --
  the block only exists in `buffer`), caches the miss AS nil, and retries
  -- so the second attempt's sync-get returns nil WITHOUT throwing this
  time (nil is a cached hit), and ipld/decode nil crashes with `Cannot
  read properties of null (reading 'length')`. handler.cljc's own
  try/catch has no :block-miss on THIS exception (a plain TypeError, not
  a missing-block ex-info), so it's swallowed into a normal-looking `{:ok
  false :error \"InternalError\" ...}` response instead of a rejection --
  every do-transact call silently fails this way against any genuinely
  async store (confirmed here AND in a pure-Node repro against kotoba-
  lang/kotobase-cljc-worker's own handler+r2, independent of IndexedDB).
  This is INCIDENT 2607032800 (\"worker commit! null.length\",
  app-aozora/40-engine/cljs/pds/wrangler.jsonc) — the reason
  FOLD_CRON_ENABLED was left at 0: do-fold hits the identical pattern
  reading back its own fold!-written blocks."
  [db method body auth-did]
  (let [buffer (atom {})
        graph  (:graph body)]
    (-> (idb/get-head db graph)
        (.then (fn [{:keys [chain etag]}]
                 (-> (r2/with-blocks
                      (fn [cid] (idb/get-bytes db cid))
                      (fn [sync-get]
                        (h/handle {:get-fn (fn [cid] (if (contains? @buffer cid)
                                                        (get @buffer cid)
                                                        (sync-get cid)))
                                   :put! (fn [cid bytes] (swap! buffer assoc cid bytes))
                                   :head-get (constantly chain)
                                   :head-put! (fn [_ _] nil)} ; head CAS'd below
                                  method body auth-did)))
                     (.then (fn [resp] (flush-and-cas! db graph etag resp buffer)))))))))

(def ^:private max-cas-attempts 8)

(defn- delay-ms [ms] (js/Promise. (fn [resolve _] (js/setTimeout resolve ms))))

(defn run-write
  "transact/fold: CAS-guarded head advance with retry on a lost race, same
  protocol as kotobase.cljc-worker.worker/run-write."
  ([db method body auth-did] (run-write db method body auth-did 1))
  ([db method body auth-did attempt]
   (-> (run-write-attempt db method body auth-did)
       (.then (fn [{:keys [resp cas-ok?]}]
                (cond
                  cas-ok? resp

                  (>= attempt max-cas-attempts)
                  {:ok false :error "ConcurrentWriteConflict"
                   :message (str "head CAS lost the race " attempt " times")}

                  :else
                  (-> (delay-ms (min 800 (* 50 attempt)))
                      (.then (fn [_] (run-write db method body auth-did (inc attempt)))))))))))
