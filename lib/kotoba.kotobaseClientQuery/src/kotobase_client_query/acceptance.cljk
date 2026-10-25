(ns kotobase-client-query.acceptance
  "Does the query actually run in the client, with the server holding only
  bytes? This asks the question in the only way that can answer it: by
  recording every HTTP request the run makes and looking at what they are.

  ## The claim, and what would falsify it

  The engine (`kotobase-engine`) is portable `.cljc`/`.cljs`. Point its
  storage at a block transport that speaks `GET /ipld/<cid>` and it should
  build the database value, walk the index and evaluate the pattern in this
  process. If any part of that were still happening on the server, this run
  would have to POST something — a query, a `datoms` index read, an
  `xrpc/…` method. So the acceptance is not \"did we get the right answer\";
  it is:

      every request this process made was `GET /ipld/<cid>`

  A single POST, or a single URL outside that shape, fails the run.

  ## Two phases, and why the second one is cold

  Phase A writes a small graph. That already exercises the client side —
  encoding, block splitting and CID derivation all happen here — but it is
  not evidence about reads, because the engine still holds everything it
  just built.

  Phase B therefore constructs a *new* engine over a *new* transport with an
  empty ref store, pins it to phase A's commit CID with `at-cid`, and
  queries. Nothing is carried over but the 59-character address. Every block
  the query needs has to come back over the wire, which is what makes the
  request log meaningful.

  ## What this does NOT claim

  This is not a benchmark. It counts round trips, not milliseconds — the
  workstation it runs on has dozens of concurrent agents and a load average
  in the tens, so wall clock here measures the workstation
  (`kotobase-peer`'s dag-shape bench established that discipline, root
  ADR-2608021000). And the graph is small: the GET count it prints is a
  property of this graph, not a scaling result."
  (:require ["@noble/curves/ed25519.js" :refer [ed25519]]
            [clojure.string :as str]
            [kotobase.blocks :as blocks]
            [kotobase.cacao :as cacao]
            [kotobase.engine :as k]
            [kotobase.storage.core :as storage]
            [kotobase.storage.ipfs :as ipfs]
            [kotobase.storage.memory :as memory]))

(def ^:private endpoint "https://kotobase.net")
(def ^:private operator-did "did:web:kotobase.net")

(def ^:private facts
  [["alice" "works-at" "acme"]
   ["bob" "works-at" "globex"]
   ["acme" "located-in" "kyoto"]
   ["globex" "located-in" "osaka"]
   ["alice" "role" "admin"]])

;; ── request log ─────────────────────────────────────────────────────────────

(defn- recording-fetch
  "Wrap the global fetch so every request is recorded. This is the
   instrument: the whole acceptance rests on being able to say what was
   asked of the server, so it must be impossible for a request to bypass
   it — which is why the engine is only ever handed a transport built on
   this function and never touches `js/fetch` itself."
  [log]
  (fn [url opts]
    (swap! log conj {:url url :method (or (some-> opts .-method) "GET")})
    (js/fetch url opts)))

(defn- summarize [log]
  (let [entries @log
        by (frequencies (map :method entries))
        block-reads (filter #(and (= "GET" (:method %))
                                  (str/starts-with? (:url %) (str endpoint "/ipld/")))
                            entries)
        others (remove (set block-reads) entries)]
    {:total (count entries) :by-method by
     :block-reads (count block-reads) :others others}))

;; ── engine wiring ───────────────────────────────────────────────────────────

(defn- open-database
  "An engine whose entire contact with the outside world is `fetch-fn`.

   The controls are plaintext pass-throughs, stated explicitly because the
   engine refuses to open without them (fail-closed) and because this graph
   really is public bytes.

   They must return PROMISES, not values. `kotobase-peer`'s `put-tx-block!`
   is `#?(:clj (encrypt-fn …) :cljs (-> (encrypt-fn …) (.then …)))`, so the
   `identity` that its JVM tests pass produces `identity(...).then is not a
   function` here — a failure two libraries away from the line that chose
   it."
  [fetch-fn authorization]
  (k/open {:storage (storage/compose
                     {:blocks (ipfs/open
                               {:client (blocks/client {:endpoint endpoint
                                                        :fetch-fn fetch-fn
                                                        :authorization authorization})})
                      :refs (memory/memory-store)})
           :ref-name "acceptance"
           :encrypt-fn #(js/Promise.resolve %)
           :decrypt-fn #(js/Promise.resolve %)
           :blind-fn pr-str
           :visible? (constantly true)}))

(defn- fail! [message]
  (js/console.error (str "FAIL: " message))
  (set! (.-exitCode js/process) 1))

(defn- run []
  (let [secret (.randomPrivateKey (.-utils ed25519))
        mint (fn [] (str "CACAO "
                         (:cacao-b64
                          (cacao/mint-cacao {:secret-key secret
                                             :aud operator-did
                                             :capability "kotobase:pin"
                                             :graph "kotobase/client-query-acceptance"
                                             :statement "client-side query acceptance"
                                             :ttl-sec 300}))))
        write-log (atom [])
        read-log (atom [])
        writer (open-database (recording-fetch write-log) mint)]
    (js/console.log (str "phase A — writing " (count facts) " facts through the client engine"))
    (-> (k/transact! writer facts)
        (.then
         (fn [commit-cid]
           (when-not (string? commit-cid)
             (throw (js/Error. (str "transact! did not return a commit CID: " (pr-str commit-cid)))))
           (js/console.log (str "  commit " commit-cid))
           (js/console.log (str "  " (:total (summarize write-log)) " requests to write"))
           commit-cid))
        (.then
         (fn [commit-cid]
           ;; Phase B. A new engine, a new transport, an empty ref store: the
           ;; only thing that crosses from phase A is this string.
           (js/console.log "phase B — cold read: new engine, empty ref store, only the CID carried over")
           (let [reader (open-database (recording-fetch read-log) mint)
                 pinned (k/at-cid reader commit-cid)]
             (-> (js/Promise.resolve pinned)
                 (.then (fn [db] (k/q db ["alice" "works-at" nil])))
                 (.then
                  (fn [result]
                    (let [got (set (map (juxt :s :p :o) result))]
                      (if (= #{["alice" "works-at" "acme"]} got)
                        (js/console.log "  ok   query answered from blocks fetched in this process:"
                                        (pr-str got))
                        (throw (js/Error. (str "wrong answer: " (pr-str got))))))
                    (summarize read-log)))))))
        (.then
         (fn [{:keys [total by-method block-reads others]}]
           (js/console.log (str "  " total " requests to read, " block-reads " of them GET /ipld/<cid>"))
           (cond
             (zero? total)
             (fail! "the cold read made no requests at all — it cannot have read anything, so this run measured nothing")

             (seq others)
             (do (fail! (str (count others) " request(s) were not a block read — the server did more than store bytes"))
                 (doseq [o (take 5 others)]
                   (js/console.error (str "    " (:method o) " " (:url o)))))

             :else
             (js/console.log
              (str "PASS: every one of the " total
                   " requests was GET /ipld/<cid>. "
                   "The query, the index walk and the materialisation ran here.")))))
        (.catch
         (fn [error]
           (fail! (str error))
           (when-let [st (some-> error .-stack)] (js/console.error st))
           (js/console.error (str "  requests so far — write " (count @write-log)
                                  ", read " (count @read-log))))))))

(defn main []
  (if-not (= "1" (.. js/process -env -KOTOBASE_LIVE_BLOCKS))
    (js/console.log "SKIP: set KOTOBASE_LIVE_BLOCKS=1 to run against the real plane")
    (run)))
