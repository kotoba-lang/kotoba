(ns ayatori.remote
  "Verified, range-pruned queries over a remote persistent arrangement.

  This namespace is the wiring between Ayatori's three existing planes:

  1. `discover-fn` resolves a block CID to IPNI provider records;
  2. `fetch-fn` asks those providers for the IPLD block bytes;
  3. every returned block is rehashed against the requested CID;
  4. `arrangement.source/cursor` follows only the persisted index ranges a
     query names; and
  5. `ayatori.query/q` evaluates Datalog directly over that cursor.

  Discovery is not retrieval, and retrieval is not verification.  The
  separate injected functions keep those effects visible and make provider
  fallback testable without a network.  A verified block is memoised by CID
  for the lifetime of an opened snapshot; unverified bytes are never cached.

  The persistent index is produced by `arrangement.core/commit!` (or its
  incremental variants).  Ayatori reads that IPLD snapshot; it does not copy
  it into a throwaway in-memory database."
  (:require [arrangement.source :as arrangement-source]
            #?(:cljs [arrangement.datalog :as arrangement-datalog])
            [ayatori.discovery :as discovery]
            [ayatori.query :as query]
            [kotoba.lang.text :as str]
            [ipld.core :as ipld]
            [multiformats.core :as mf]
            [multiformats.multiaddr :as multiaddr]))

(defn- message [e]
  #?(:clj (.getMessage ^Throwable e)
     :cljs (or (.-message e) (str e))))

(defn- byte-count [bytes]
  #?(:clj (count bytes)
     :cljs (or (.-byteLength bytes) (.-length bytes) (count bytes))))

(defn- validate-cid! [cid]
  (when-not (and (string? cid) (some? (ipld/cid-codec cid)))
    (throw (ex-info "ayatori: expected a parseable CID"
                    {:type :ayatori/invalid-cid :value cid})))
  cid)

(defn- verify-block! [expected-cid bytes]
  (let [{:keys [codec multihash error]} (mf/cid->parts expected-cid)
        mh (when multihash (vec multihash))]
    (when error
      (throw (ex-info "ayatori: expected a CIDv1 block identity"
                      {:type :ayatori/invalid-cid :cid expected-cid
                       :reason error})))
    (when-not (and (= 0x12 (first mh)) (= 32 (second mh)))
      (throw (ex-info "ayatori: unsupported CID multihash"
                      {:type :ayatori/unsupported-multihash
                       :cid expected-cid :code (first mh)
                       :length (second mh)})))
    (let [actual (mf/cidv1 codec (mf/multihash-sha256 bytes))]
      (when-not (= expected-cid actual)
        (throw (ex-info "ayatori: block CID mismatch"
                        {:type :ipld/cid-mismatch
                         :expected-cid expected-cid :actual-cid actual})))
      bytes)))

(def ^:private empty-stats
  {:discoveries 0 :fetch-attempts 0 :provider-failures 0
   :verified-blocks 0 :memo-hits 0 :in-flight-hits 0 :verified-bytes 0
   :source-attempts 0 :source-hits 0 :source-failures 0})

(defn- promise-like?
  "Thenable, in the JS sense. Always false on the JVM."
  [x]
  #?(:cljs (and (some? x) (fn? (unchecked-get x "then")))
     :clj  false))

(defn- refuse-async-crypto!
  "The synchronous snapshot API cannot await a Promise, and does not notice
  one: a Promise-returning `blind-fn` produces a blinded key that matches
  nothing, so every scan comes back EMPTY -- indistinguishable from a query
  that ran and matched nothing.

  Measured 2026-09-04 under nbb: the same snapshot answered `#{[\"s1\"]}` with
  a synchronous blind-fn and `#{}` with a Promise-returning one, with no
  error in between. And `arrangement.core/commit!` REQUIRES Promise-returning
  blind/encrypt on cljs, so following its contract and then opening the
  snapshot synchronously is the natural way to reach this.

  Probing costs one call with a sentinel. A blind-fn that throws on the
  sentinel tells us nothing, so that case is allowed through rather than
  refused on a guess."
  [label f]
  (let [probed (try {:ok (f ::ayatori-probe)}
                    (catch #?(:clj Exception :cljs :default) _ nil))]
    (when (and probed (promise-like? (:ok probed)))
      (throw (ex-info (str "ayatori: " label " returned a Promise, and the "
                           "synchronous snapshot API cannot await it -- every "
                           "scan would come back empty rather than fail. Use "
                           "open-snapshot-async, or pass a synchronous "
                           label ".")
                      {:type :ayatori/async-crypto-in-sync-api
                       :fn label})))))

(defn- stats-atom [stats]
  (let [stats (or stats (atom {}))]
    (swap! stats #(merge empty-stats %))
    stats))

(defn- failure [provider reason detail]
  (cond-> {:peer (:peer provider) :reason reason}
    detail (assoc :detail detail)))

(defn- validate-discovery! [cid result]
  (when-not (map? result)
    (throw (ex-info "ayatori: discovery did not return a result map"
                    {:type :ayatori/invalid-discovery-result :cid cid})))
  (when-not (:ok? result)
    (throw (ex-info "ayatori: provider discovery failed"
                    {:type :ayatori/discovery-failed
                     :cid cid
                     :reason (:reason result)
                     :answered (:answered result)
                     :quorum (:quorum result)})))
  (when-not (= cid (:cid result))
    (throw (ex-info "ayatori: discovery changed the requested CID"
                    {:type :ayatori/discovery-cid-mismatch
                     :expected-cid cid :actual-cid (:cid result)})))
  (when (true? (:mutates-cid? result))
    (throw (ex-info "ayatori: discovery reported that it mutates CIDs"
                    {:type :ayatori/discovery-mutates-cid :cid cid})))
  (let [providers (vec (:providers result))]
    (doseq [provider providers]
      (when-not (map? provider)
        (throw (ex-info "ayatori: discovery returned a non-map provider"
                        {:type :ayatori/invalid-provider :cid cid})))
      (when (and (contains? provider :cid) (not= cid (:cid provider)))
        (throw (ex-info "ayatori: provider record names a different CID"
                        {:type :ayatori/provider-cid-mismatch
                         :expected-cid cid :actual-cid (:cid provider)
                         :peer (:peer provider)})))
      (when (true? (:mutates-cid? provider))
        (throw (ex-info "ayatori: provider record mutates the content CID"
                        {:type :ayatori/provider-mutates-cid
                         :cid cid :peer (:peer provider)}))))
    (when (empty? providers)
      (throw (ex-info "ayatori: no provider advertises the requested CID"
                      {:type :ayatori/no-providers :cid cid})))
    providers))

(defn gateway-url
  "Turn one HTTP-gateway multiaddr into its raw-block URL.

  Supported address shape is a DNS/IP host, optional TCP port, and `/https`
  (or `/http` only when `:allow-http? true`). The default path is the IPFS
  trustless-gateway block namespace `/ipfs/{cid}`; a provider with another
  stable block route may supply `:path-prefix`.

  Returns nil for a well-formed address that is not an HTTP gateway. Parsing
  errors propagate to the gateway fetcher, which records the bad address and
  continues to the provider's next address."
  ([addr cid] (gateway-url addr cid {}))
  ([addr cid {:keys [allow-http? path-prefix]
              :or {allow-http? false path-prefix "/ipfs/"}}]
   (validate-cid! cid)
   (let [components (multiaddr/components (multiaddr/parse addr))
         values (into {} components)
         protocols (set (map first components))
         scheme (cond (protocols "https") "https"
                      (and allow-http? (protocols "http")) "http"
                      :else nil)
         host (or (get values "dns4") (get values "dns6")
                  (get values "dns") (get values "ip4")
                  (get values "ip6"))
         port (get values "tcp")]
     (when (and scheme host)
       (let [host (if (and (get values "ip6")
                           (not (and (str/starts-with? host "[")
                                     (str/ends-with? host "]"))))
                    (str "[" host "]") host)
             default-port? (or (and (= scheme "https") (= port "443"))
                               (and (= scheme "http") (= port "80")))]
         (str scheme "://" host
              (when (and port (not default-port?)) (str ":" port))
              path-prefix cid))))))

(defn gateway-fetcher
  "Build a `fetch-fn` for `provider-block-getter` from an injected HTTP port.

  `http-fn` receives `{:method :get :url ... :headers ...}` and returns
  `{:status :body}`. Every usable provider address is tried in order with
  `Accept: application/vnd.ipld.raw`. Only a 200 body is returned; CID
  verification still happens outside this function, before the bytes can be
  cached or queried.

  Options are forwarded to `gateway-url`: `:allow-http?` (false by default)
  and `:path-prefix` (`/ipfs/` by default)."
  ([http-fn] (gateway-fetcher http-fn {}))
  ([http-fn opts]
   (when-not (fn? http-fn)
     (throw (ex-info "ayatori: gateway http-fn is required"
                     {:type :ayatori/missing-gateway-http-fn})))
   (fn fetch-provider [provider cid]
     (loop [addrs (:addrs provider) attempts []]
       (if-let [addr (first addrs)]
         (let [url-result (try
                            {:url (gateway-url addr cid opts)}
                            (catch #?(:clj Exception :cljs :default) e
                              {:error (message e)}))
               url (:url url-result)]
           (if (:error url-result)
             (recur (next addrs)
                    (conj attempts {:addr addr :reason :invalid-multiaddr
                                    :detail (:error url-result)}))
             (if-not url
             (recur (next addrs) (conj attempts {:addr addr :reason :unsupported}))
             (let [response (try
                              (http-fn {:method :get :url url
                                        :headers {"Accept" "application/vnd.ipld.raw"}})
                              (catch #?(:clj Exception :cljs :default) e
                                {:transport-error (message e)}))]
               (if (and (= 200 (:status response)) (some? (:body response)))
                 (:body response)
                 (recur (next addrs)
                        (conj attempts
                              (if-let [detail (:transport-error response)]
                                {:addr addr :reason :transport-error :detail detail}
                                {:addr addr :reason :http-error
                                 :status (:status response)}))))))))
         (throw (ex-info "ayatori: provider has no successful HTTP gateway"
                         {:type :ayatori/no-gateway-route
                          :peer (:peer provider) :attempts attempts})))))))

#?(:cljs
   (defn gateway-fetcher-async
     "Worker-native Promise counterpart to `gateway-fetcher`.

     `http-fn` may be global `fetch` adapted to return a Promise of
     `{:status :body}`. Provider addresses are attempted in order; malformed,
     unsupported, rejected, and non-200 routes fall through without hiding a
     Promise behind the synchronous cursor contract."
     ([http-fn] (gateway-fetcher-async http-fn {}))
     ([http-fn opts]
      (fn fetch-provider [provider cid]
        (letfn [(attempt [addrs failures]
                  (if-let [addr (first addrs)]
                    (let [url-result (try
                                       {:url (gateway-url addr cid opts)}
                                       (catch :default e
                                         {:error (message e)}))
                          url (:url url-result)]
                      (cond
                        (:error url-result)
                        (attempt (next addrs)
                                 (conj failures {:addr addr
                                                 :reason :invalid-multiaddr
                                                 :detail (:error url-result)}))

                        (nil? url)
                        (attempt (next addrs)
                                 (conj failures {:addr addr :reason :unsupported}))

                        :else
                        (-> (js/Promise.resolve
                             (http-fn {:method :get :url url
                                       :headers {"Accept" "application/vnd.ipld.raw"}}))
                            (.then (fn [response]
                                     (if (and (= 200 (:status response))
                                              (some? (:body response)))
                                       (:body response)
                                       (attempt (next addrs)
                                                (conj failures
                                                      {:addr addr
                                                       :reason :http-error
                                                       :status (:status response)})))))
                            (.catch (fn [e]
                                      (attempt (next addrs)
                                               (conj failures
                                                     {:addr addr
                                                      :reason :transport-error
                                                      :detail (message e)})))))))
                    (js/Promise.reject
                     (ex-info "ayatori: provider has no successful HTTP gateway"
                              {:type :ayatori/no-gateway-route
                               :peer (:peer provider) :attempts failures}))))]
          (attempt (:addrs provider) []))))))

(defn provider-block-getter
  "Build a synchronous `(fn [cid] -> verified-bytes)` block getter.

  Options:

  - `:discover-fn` — `(fn [cid] -> {:ok? :cid :providers ...})`;
  - `:fetch-fn` — `(fn [provider cid] -> bytes-or-nil)`;
  - `:stats` — optional caller-owned atom;
  - `:block-memo` — optional caller-owned atom keyed by CID.

  Providers are tried in discovery order. A missing, throwing, or
  CID-mismatching provider is skipped; success is possible only when some
  provider returns bytes that hash to the requested CID. If every provider
  fails, the function throws with bounded metadata and never exposes or
  caches the unverified bytes.

  The transport is synchronous because `arrangement.source/cursor` is
  synchronous. A Worker-native async cursor is a separate API rather than a
  Promise hidden inside this one."
  [{:keys [discover-fn fetch-fn stats block-memo block-source]}]
  (when-not (fn? discover-fn)
    (throw (ex-info "ayatori: discover-fn is required"
                    {:type :ayatori/missing-discover-fn})))
  (when (and (some? block-source) (not (fn? block-source)))
    (throw (ex-info "ayatori: block-source must be a function of one CID"
                    {:type :ayatori/invalid-block-source})))
  (when-not (fn? fetch-fn)
    (throw (ex-info "ayatori: fetch-fn is required"
                    {:type :ayatori/missing-fetch-fn})))
  (let [stats (stats-atom stats)
        block-memo (or block-memo (atom {}))]
    (fn get-verified [cid]
      ;; Reject malformed identities before discovery or provider I/O. A CID
      ;; that cannot be parsed is not a cache miss and must not become a URL.
      (validate-cid! cid)
      (if-let [cached (get @block-memo cid)]
        (do (swap! stats update :memo-hits inc) cached)
        (if-let [local (when block-source
                         (swap! stats update :source-attempts inc)
                         ;; Verified on the same path as a provider's bytes:
                         ;; being local is not being trusted. A source that
                         ;; answers with the wrong bytes, or throws, is SKIPPED
                         ;; the way a mismatching provider is -- but counted, so
                         ;; a corrupt pack shows up as :source-failures rather
                         ;; than as a lookup that merely got slower.
                         (try
                           (when-let [bytes (block-source cid)]
                             (let [verified (verify-block! cid bytes)]
                               (swap! block-memo assoc cid verified)
                               (swap! stats #(-> %
                                                 (update :source-hits inc)
                                                 (update :verified-blocks inc)
                                                 (update :verified-bytes + (byte-count verified))))
                               verified))
                           (catch #?(:clj Exception :cljs :default) _
                             (swap! stats update :source-failures inc)
                             nil)))]
          local
          (let [result (try
                       (swap! stats update :discoveries inc)
                       (discover-fn cid)
                       (catch #?(:clj Exception :cljs :default) e
                         (throw (ex-info "ayatori: provider discovery threw"
                                         {:type :ayatori/discovery-failed
                                          :cid cid :detail (message e)} e))))
              providers (validate-discovery! cid result)]
          (loop [remaining providers failures []]
            (if-let [provider (first remaining)]
              (let [attempt
                    (try
                      (swap! stats update :fetch-attempts inc)
                      (if-let [bytes (fetch-fn provider cid)]
                        (try
                          {:verified (verify-block! cid bytes)}
                          (catch #?(:clj Exception :cljs :default) e
                            {:failure (failure provider
                                               (or (:type (ex-data e)) :verification-failed)
                                               (message e))}))
                        {:failure (failure provider :missing nil)})
                      (catch #?(:clj Exception :cljs :default) e
                        {:failure (failure provider :transport-error (message e))}))]
                (if-let [verified (:verified attempt)]
                  (do
                    (swap! block-memo assoc cid verified)
                    (swap! stats (fn [s]
                                   (-> s
                                       (update :verified-blocks inc)
                                       (update :verified-bytes + (byte-count verified)))))
                    verified)
                  (do
                    (swap! stats update :provider-failures inc)
                    (recur (next remaining) (conj failures (:failure attempt))))))
              (throw (ex-info "ayatori: no provider returned a verified block"
                              {:type :ayatori/all-providers-failed
                               :cid cid :attempts failures}))))))))))

#?(:cljs
   (defn- attempt-providers-async
     "Try `providers` in order under `:fetch-fn`, verifying every candidate.
     Returns a Promise of verified bytes or rejects with
     :ayatori/all-providers-failed. Extracted so the block-source fall-through
     and the plain discovery path share ONE provider loop (iteration 02)."
     [{:keys [cid providers fetch-fn stats block-memo]}]
     (let [attempt
           (fn attempt [remaining failures]
             (if-let [provider (first remaining)]
               (do
                 (swap! stats update :fetch-attempts inc)
                 (-> (js/Promise.resolve (fetch-fn provider cid))
                     (.then (fn [bytes]
                              (if-not bytes
                                (throw (ex-info "missing block" {:type :missing}))
                                (verify-block! cid bytes))))
                     (.then (fn [verified]
                              (swap! block-memo assoc cid verified)
                              (swap! stats
                                     (fn [s]
                                       (-> s
                                           (update :verified-blocks inc)
                                           (update :verified-bytes +
                                                   (byte-count verified)))))
                              verified))
                     (.catch (fn [e]
                               (swap! stats update :provider-failures inc)
                               (attempt (next remaining)
                                        (conj failures
                                              (failure provider
                                                       (or (:type (ex-data e))
                                                           :transport-error)
                                                       (message e))))))))
               (js/Promise.reject
                (ex-info "ayatori: no provider returned a verified block"
                         {:type :ayatori/all-providers-failed
                          :cid cid :attempts failures}))))]
       (attempt providers []))))

#?(:cljs
   (defn- discover-then-attempt-async
     "Discovery, then the provider loop: the one path a block-source miss
     falls through to, and the whole of the path when there is no source.

     Extracted because there were three copies of it, and having three is how
     one of them lost its place in the `if-not` below: a stray paren closed
     the branch early, so the nil case ran discovery for effect, threw the
     resulting Promise away, and then ran it AGAIN through `verify-block!`
     rejecting on nil. A source that simply did not carry the block cost two
     discoveries and two fetches -- more round trips than passing no source
     at all. One copy cannot drift from itself."
     [{:keys [cid discover-fn fetch-fn stats block-memo]}]
     (-> (do (swap! stats update :discoveries inc)
             (js/Promise.resolve (discover-fn cid)))
         (.then (fn [result]
                  (let [providers (validate-discovery! cid result)]
                    (attempt-providers-async
                     {:cid cid :providers providers
                      :fetch-fn fetch-fn :stats stats
                      :block-memo block-memo})))))))

#?(:cljs
   (defn provider-block-getter-async
     "Worker-native `(fn [cid] -> Promise<verified-bytes>)` getter.

     Discovery and provider retrieval may reject or return Promises. Providers
     are tried in discovery order; only bytes whose SHA-256 multihash matches
     the requested CID are memoised. The memo stores resolved verified bytes,
     never a rejected Promise or an unverified response.

     `:block-source` is optional: `(fn [cid] -> bytes-or-nil-or-Promise)`,
     tried BEFORE discovery and awaited if it returns a Promise. Its bytes are
     verified on the same path as a provider's -- being local is not being
     trusted. A source that answers with the wrong bytes, rejects, or throws
     is SKIPPED the way a mismatching provider is, and counted as
     :source-failures so a corrupt pack is visible rather than merely slow.

     A source that resolves NIL is skipped and NOT counted: it has not failed
     at anything, it simply does not carry that block. Counting a miss makes
     a pack that legitimately holds half the blocks read exactly like a
     corrupt one, which is the distinction :source-failures exists to draw.
     This matches `provider-block-getter`, whose miss is likewise uncounted.

     Whatever the source does, a miss costs exactly ONE discovery -- the same
     as passing no source at all. The two stages below are ordered so that a
     fall-through which itself fails cannot re-enter the source's error
     handler and buy a second one.

     The source call participates in the same `:in-flight` coalescing as a
     provider miss: concurrent callers for one CID share one source attempt.
     Absent `:block-source`, behaviour is unchanged."
     [{:keys [discover-fn fetch-fn stats block-memo in-flight block-source]}]
     (when (and (some? block-source) (not (fn? block-source)))
       (throw (ex-info "ayatori: block-source must be a function of one CID"
                       {:type :ayatori/invalid-block-source})))
     (let [stats (stats-atom stats)
           block-memo (or block-memo (atom {}))
           in-flight (or in-flight (atom {}))]
       (fn get-verified-async [cid]
         (try
           (validate-cid! cid)
           (if-let [cached (get @block-memo cid)]
             (do (swap! stats update :memo-hits inc)
                 (js/Promise.resolve cached))
             (if-let [pending (get @in-flight cid)]
               (do (swap! stats update :in-flight-hits inc) pending)
               (let [fall-through
                     (fn []
                       (discover-then-attempt-async
                        {:cid cid :discover-fn discover-fn :fetch-fn fetch-fn
                         :stats stats :block-memo block-memo}))
                     request
                     (if block-source
                       ;; Two stages, and the order of the handlers is the
                       ;; point. Stage one resolves the source to verified
                       ;; bytes or to ::miss, and its `.catch` is attached
                       ;; HERE -- before discovery is spliced in -- so a
                       ;; fall-through that itself fails cannot re-enter this
                       ;; handler and buy a second round of discovery.
                       (-> (try (swap! stats update :source-attempts inc)
                                ;; A source that throws synchronously must be
                                ;; skipped like one that rejects; without this
                                ;; the throw escapes the whole getter and the
                                ;; read fails where the sync getter would have
                                ;; fallen through.
                                (js/Promise.resolve (block-source cid))
                                (catch :default e (js/Promise.reject e)))
                           (.then (fn [bytes]
                                    (if-not bytes
                                      ;; Not in hand. The sync getter does not
                                      ;; count this, and neither does this one:
                                      ;; a source that does not carry the block
                                      ;; has not failed at anything. Counting it
                                      ;; makes a pack that legitimately holds
                                      ;; half the blocks indistinguishable from
                                      ;; a corrupt one.
                                      ::miss
                                      (let [verified (verify-block! cid bytes)]
                                        (swap! block-memo assoc cid verified)
                                        (swap! stats
                                               (fn [s]
                                                 (-> s
                                                     (update :source-hits inc)
                                                     (update :verified-blocks inc)
                                                     (update :verified-bytes + (byte-count verified)))))
                                        verified))))
                           (.catch (fn [_]
                                     ;; Threw, rejected, or answered with bytes
                                     ;; that do not hash to the CID: counted,
                                     ;; then skipped the way a mismatching
                                     ;; provider is.
                                     (swap! stats update :source-failures inc)
                                     ::miss))
                           (.then (fn [result]
                                    (if (= ::miss result) (fall-through) result))))
                       (fall-through))
                     settled (-> request
                                 (.then (fn [verified]
                                          (swap! in-flight dissoc cid)
                                          verified))
                                 (.catch (fn [e]
                                           (swap! in-flight dissoc cid)
                                           (throw e))))]
                 ;; JavaScript runs this miss path synchronously until here, so
                 ;; the next caller for the same CID observes the shared Promise.
                 (swap! in-flight assoc cid settled)
                 settled)))
           (catch :default e (js/Promise.reject e)))))))

(defn open-snapshot
  "Open a persistent arrangement snapshot through IPNI-backed block reads.

  Required options are `:snapshot-cid`, `:fetch-fn`, `:blind-fn`, and
  `:decrypt-fn`, plus either:

  - `:discover-fn`, or
  - `:http-fn` and optional `:discovery-opts`, which are composed through
    `ayatori.discovery/find-providers`.

  `:block-source` is optional: `(fn [cid] -> bytes-or-nil)`, tried BEFORE
  discovery and verified on the same path as a provider's bytes. A source
  that answers serves the read without an IPNI lookup; one that returns nil
  falls through. `ayatori.pack/read-block` has exactly this shape, which is
  the point -- a packed read does not need to be told where the block is.

  `:partitions` is the same declared range-partition vector used when the
  snapshot was committed. The return value is an opened session containing
  `:source`, `:get-block`, and caller-observable `:stats`. Opening verifies
  the snapshot block immediately; index blocks remain lazy and are fetched
  only when a query reaches their ranges."
  [{:keys [snapshot-cid discover-fn http-fn discovery-opts fetch-fn
           blind-fn decrypt-fn partitions stats block-memo block-source]}]
  (when-not (string? snapshot-cid)
    (throw (ex-info "ayatori: snapshot-cid must be a CID string"
                    {:type :ayatori/invalid-snapshot-cid :value snapshot-cid})))
  (when-not (fn? blind-fn)
    (throw (ex-info "ayatori: blind-fn is required"
                    {:type :ayatori/missing-blind-fn})))
  (when-not (fn? decrypt-fn)
    (throw (ex-info "ayatori: decrypt-fn is required"
                    {:type :ayatori/missing-decrypt-fn})))
  (refuse-async-crypto! "blind-fn" blind-fn)
  (refuse-async-crypto! "decrypt-fn" decrypt-fn)
  (let [discover-fn (or discover-fn
                        (when (fn? http-fn)
                          (fn [cid]
                            (discovery/find-providers http-fn cid
                                                      (or discovery-opts {})))))
        stats (stats-atom stats)
        block-memo (or block-memo (atom {}))
        get-block (provider-block-getter {:discover-fn discover-fn
                                          :fetch-fn fetch-fn
                                          :block-source block-source
                                          :stats stats
                                          :block-memo block-memo})
        source (arrangement-source/cursor get-block snapshot-cid blind-fn
                                          decrypt-fn partitions)]
    {:snapshot-cid snapshot-cid
     :source source
     :get-block get-block
     :stats stats
     :block-memo block-memo}))

#?(:cljs
   (defn open-snapshot-async
     "Open a Worker-native persistent snapshot without a synchronous network
     trampoline. Returns a Promise of the same session shape as
     `open-snapshot`, but `:source` is an arrangement `AsyncCursorSource` and
     `:get-block` returns Promises.

     Required effects are Promise-capable `:fetch-fn`, `:blind-fn`, and
     `:decrypt-fn`, plus either Promise-capable `:discover-fn` or `:http-fn`
     (composed through `ayatori.discovery/find-providers-async`).

     `:block-source` is optional and has the same contract as in
     `open-snapshot`: `(fn [cid] -> bytes-or-nil-or-Promise)`, tried before
     discovery, awaited, verified like a provider's bytes, and coalesced
     through `:in-flight`. A Worker serving a pack therefore pays zero
     discoveries for blocks the pack holds."
     [{:keys [snapshot-cid discover-fn http-fn discovery-opts fetch-fn
              blind-fn decrypt-fn partitions stats block-memo in-flight
              block-source]}]
     (try
       (validate-cid! snapshot-cid)
       (when-not (fn? blind-fn)
         (throw (ex-info "ayatori: blind-fn is required"
                         {:type :ayatori/missing-blind-fn})))
       (when-not (fn? decrypt-fn)
         (throw (ex-info "ayatori: decrypt-fn is required"
                         {:type :ayatori/missing-decrypt-fn})))
       (let [discover-fn (or discover-fn
                             (when (fn? http-fn)
                               (fn [cid]
                                 (discovery/find-providers-async
                                  http-fn cid (or discovery-opts {})))))
             stats (stats-atom stats)
             block-memo (or block-memo (atom {}))
             in-flight (or in-flight (atom {}))
             get-block (provider-block-getter-async
                        {:discover-fn discover-fn :fetch-fn fetch-fn
                         :stats stats :block-memo block-memo
                         :in-flight in-flight
                         :block-source block-source})]
         (-> (arrangement-source/cursor-async get-block snapshot-cid
                                               blind-fn decrypt-fn partitions)
             (.then (fn [source]
                      {:snapshot-cid snapshot-cid :source source
                       :get-block get-block :stats stats
                       :block-memo block-memo :in-flight in-flight}))))
       (catch :default e (js/Promise.reject e)))))

(defn q
  "Run Datalog directly over an opened persistent snapshot.

  No in-memory database is materialized. The arrangement cursor asks for the
  index prefix/range needed by each Datalog clause, and every block crossing
  the provider boundary is CID-verified by the opened session."
  ([opened query-form visible?]
   (query/q (:source opened) query-form visible?))
  ([opened query-form visible? inputs]
   (query/q (:source opened) query-form visible? inputs)))

#?(:cljs
   (defn q-async
     "Run the full Datalog language over an opened Worker-native persistent
     snapshot and return a Promise of the result.

     Every triple/range scan awaits the async Arrangement cursor, so joins,
     negation, rules, aggregates, ordering, and limits remain on the same
     CID-verified lazy block path as `scan-async`; the snapshot is never
     hydrated into an in-memory db."
     ([opened query-form visible?]
      (arrangement-datalog/q-async
       (:source opened) query-form visible?))
     ([opened query-form visible? inputs]
      (arrangement-datalog/q-async
       (:source opened) query-form visible? inputs))))

(defn scan-range-report
  "Read one declared value range and report whether persisted range buckets
  actually pruned the read, including their disclosure budget."
  ([opened attr lo hi]
   (scan-range-report opened attr lo hi {}))
  ([opened attr lo hi opts]
   (arrangement-source/scan-range-report (:source opened) attr lo hi opts)))

#?(:cljs
   (defn scan-async
     "Worker-native Promise scan for one `[s p o]` pattern over an opened
     async snapshot. Use `q-async` when clauses must bind and join."
     [opened pattern]
     (arrangement-source/scan-async (:source opened) pattern)))

#?(:cljs
   (defn scan-range-report-async
     "Worker-native Promise range scan with persisted pruning evidence."
     ([opened attr lo hi]
      (scan-range-report-async opened attr lo hi {}))
     ([opened attr lo hi opts]
      (arrangement-source/scan-range-report-async
       (:source opened) attr lo hi opts))))

(defn stats
  "Current verified retrieval counters for `opened`. These are block/byte
  counts, not wall-clock latency and not proof of an external deployment."
  [opened]
  @(:stats opened))
