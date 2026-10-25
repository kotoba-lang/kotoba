(ns i18n-cid.pin
  "Piece 3: pin content-addressed i18n catalogs to an IPFS Pinning Service.

  `i18n-cid.core` encodes and addresses catalog bytes; it has never pinned
  them (its honesty boundary says pin/announce/authorize are the caller's).
  This namespace fills the pin seam against
  `kotoba-lang/kotobase-protocol-pinning`'s `/pins` PSA surface — an IPFS
  Pinning Service API contract (`POST /pins {cid, name?, origins?}`) that
  kotobase exposes over the shared block space (ADR-2608051000).

  Like the rest of i18n-cid, this is transport-agnostic: the caller injects a
  `post-fn` (HTTP POST by CID) so the logic stays pure — request-body
  construction and response-status interpretation are unit-testable without a
  socket. A real HTTP caller (clj-http / node fetch / a kotobase client)
  supplies the transport, exactly as `i18n-cid.core` asks callers to bring
  their own `put!`/`get-fn`.")

;; ---------------------------------------------------------------------------
;; Pure request shaping
;; ---------------------------------------------------------------------------

(defn pin-request
  "Build the PSA `POST /pins` request body for `cid`. Returns
  `{:path \"/pins\" :body {:cid ..}}` — `name` (the IPNS name to publish the
  pin under) and `origins` (seed peer to fetch from, if any) are optional and
  only included when supplied.

  The response of a pin request is the pin's request-id, which the caller
  later uses for `DELETE /pins/{requestid}`."
  [cid {:keys [name origins]}]
  (let [body (cond-> {:cid cid}
               name    (assoc :name name)
               origins (assoc :origins (if (string? origins) [origins] origins)))]
    {:path "/pins"
     :body body}))

(defn request-id-of
  "Interpret a `POST /pins` response into the pin's request-id. The PSA
  contract returns either `{\"id\" ..}` or `{\"requestid\" ..}` depending on
  the deployment; we accept both. Throws when neither is present so a caller
  can never mistake a non-pin response for a pinned catalog."
  [resp]
  (let [id (or (get resp "id") (get resp "requestid")
               (get resp :id) (get resp :requestid))]
    (when-not id
      (throw (ex-info "pin response carried no request-id"
                      {:response resp})))
    (str id)))

;; ---------------------------------------------------------------------------
;; Transport seam
;; ---------------------------------------------------------------------------

(defn pin!
  "Pin the catalog block at `cid` through an injected `post-fn`.

  `post-fn` is `(fn [path body] -> resp)`, where `resp` is the parsed JSON
  object of the PSA response. `post-fn` performs the actual HTTP (kotobase
  `/pins`), and is free to add auth (CACAO capability, ADR-2608159100) around
  the call — that is the transport's concern, not this library's.

  Returns `{:cid .. :request-id .. :pinned? true}` on success."
  [post-fn cid opts]
  (let [{:keys [path body]} (pin-request cid opts)
        resp (post-fn path body)
        rid  (request-id-of resp)]
    {:cid cid
     :request-id rid
     :pinned? true}))

(defn status
  "Fetch a pin request's status via an injected `get-fn` (HTTP GET by
  request-id). Returns the PSA status response unchanged. The status moves
  through `queued → pinning → pinned` (or `failed`) while a remote node
  fetches + pins the CID — see kotobase-protocol-pinning."
  [get-fn request-id]
  (get-fn (str "/pins/" request-id)))

(defn unpin!
  "Remove a pin request (not the block) via an injected `delete-fn`
  (`DELETE /pins/{requestid}`). Block bytes stay in the shared block space;
  only the pin holding them is released."
  [delete-fn request-id]
  (delete-fn (str "/pins/" request-id)))