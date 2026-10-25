(ns kotobase.server.runtime
  "Platform-neutral ports for a secured Kotobase network runtime.

  Product repositories implement these ports for R2, B2, KMS, service
  bindings, and receipt replication. The common server/security pipeline
  consumes them and must not inspect a Cloudflare env object directly.")

(defprotocol BlockStore
  (-get-block [store tenant graph cid]
    "Return bytes or an async completion containing bytes. Consumers verify CID.")
  (-put-block [store tenant graph cid bytes]
    "Persist immutable bytes under CID; never updates a graph head."))

(defprotocol HeadStore
  (-read-head [store tenant graph]
    "Return {:head cid-or-nil :version opaque-version}.")
  (-compare-and-set-head [store tenant graph expected-version new-head]
    "Atomically create/update the head. Returns true only for the winner."))

(defprotocol ClaimStore
  (-claim-once [store tenant namespace key digest]
    "Atomically create a digest claim or return the existing claim.")
  (-read-claim [store tenant namespace key]
    "Read an idempotency, replay, or lease record."))

(defprotocol AuthorityRegistry
  (-authority-snapshot [registry tenant]
    "Return a versioned trusted-root and revocation snapshot."))

(defprotocol KeyUnwrapper
  (-unwrap-keyring [unwrapper tenant wrapped-envelope]
    "Return an unwrapped keyring without logging or persisting it."))

(defprotocol AuditSink
  (-put-receipt [sink tenant receipt-cid encrypted-bytes]
    "Persist/replicate a signed encrypted receipt by CID."))

(def required-services
  #{:block-store :head-store :claim-store :authority-registry
    :key-unwrapper :audit-sink})

(defn validate-services
  "Fail closed at startup when a private/sealed runtime is missing a mandatory
  port. Legacy/public local runtimes may omit authority/key/audit services but
  still require block and head stores. Returns SERVICES unchanged."
  [security-mode services]
  (let [required (if (contains? #{:private :sealed} security-mode)
                   required-services
                   #{:block-store :head-store})
        missing (->> required (remove #(some? (get services %))) sort vec)]
    (when (seq missing)
      (throw (ex-info "Kotobase runtime services missing"
                      {:type :runtime/missing-services
                       :security-mode security-mode
                       :missing missing})))
    services))

(defn deployment-values?
  "Guard used by architecture tests: common runtime configuration must not
  carry product routes, hostnames, bucket names, or raw platform env objects."
  [m]
  (boolean
   (some #(contains? m %)
         [:hostname :route :bucket-name :cloudflare-env :wrangler-vars
          :billing-plan :product-tenant])))
