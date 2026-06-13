(ns kotoba.ipns
  "IPNS head resolution for the kotoba browser node — gateway-untrusted.

   The mutable head of a graph is a member-signed `IpnsRecord`
   (crates/kotoba-ipns-record): `{name, value, sequence, valid_until,
   public_key_multibase, signature_multibase}`, where `value` is the head/commit
   CID (multibase). The consumer verifies the Ed25519 signature IN-WASM via
   `KotobaNode.verifyIpnsRecord`, so whichever server/gateway served the record is
   NOT trusted (no-server-key): a malicious holder can withhold a newer head but
   cannot forge one.

   See docs/ADR-browser-cid-query-vs-p2p.md §1. Query is content-addressed; this
   is the only step where trust is not already carried by a CID, so it is the only
   step that needs a signature check.")

(defn verify-record
  "Verify a canonical `IpnsRecord` JSON string against its embedded Ed25519
   signature, in-wasm. `node-class` is the `KotobaNode` wasm class export (it
   exposes the static `verifyIpnsRecord`). Returns a boolean — true iff a
   signature + public key are present and verify over the canonical CBOR payload."
  [^js node-class ^string record-json]
  (boolean (.verifyIpnsRecord node-class record-json)))

(defn- parse-record [record-json]
  (js->clj (js/JSON.parse record-json) :keywordize-keys true))

(defn resolve-head
  "Resolve and verify the signed head record for `graph` from `remote`.

   opts:
     :node-class          the KotobaNode wasm class — REQUIRED for verification
     :remote              base URL of a kotoba-server / gateway — REQUIRED
     :require-signature?  default true — reject unsigned / invalid records
     :fetch-fn            override fetch (testing); (fn [url] -> Promise<Response>)

   Returns Promise resolving to a JS object:
     {head: <commit/root CID multibase>,
      sequence: <int>, validUntil: <string>,
      verified: <bool>, record: <parsed object>, raw: <json string>}

   With :require-signature? true the returned head is gateway-untrusted.

   Backed by `GET /xrpc/com.etzhayyim.apps.kotoba.ipns.head?graph=<cid>`
   (xrpc::ipns_head) — UNAUTHENTICATED, returns the member-signed IpnsRecord.
   Callers that only need today's (server-asserted) head can instead use
   `kotoba.node/hydrate-and-query!`, which goes through `datomic.sync`."
  [graph {:keys [node-class remote require-signature? fetch-fn]
          :or   {require-signature? true fetch-fn js/fetch}}]
  (when (nil? node-class)
    (throw (js/Error. "resolve-head: :node-class (KotobaNode) is required for signature verification")))
  (-> (fetch-fn (str remote
                     "/xrpc/com.etzhayyim.apps.kotoba.ipns.head?graph="
                     (js/encodeURIComponent graph)))
      (.then (fn [^js r]
               (if (.-ok r)
                 (.text r)
                 (throw (js/Error. (str "ipns.head " graph " → HTTP " (.-status r)))))))
      (.then (fn [json]
               (let [verified (verify-record node-class json)]
                 (when (and require-signature? (not verified))
                   (throw (js/Error.
                           (str "ipns.head " graph
                                " → signature INVALID/absent — refusing untrusted head"))))
                 (let [rec (parse-record json)]
                   #js {:head       (:value rec)
                        :sequence   (:sequence rec)
                        :validUntil (:valid_until rec)
                        :verified   verified
                        :record     (clj->js rec)
                        :raw        json}))))))
