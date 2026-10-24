(ns coap.code
  "The CoAP Code field (RFC 7252 §3, §5.9, §12.1).

  Written down in the spec text as `c.dd` — a 3-bit class and a 5-bit
  detail, separated by a dot purely for human reading — and packed on the
  wire as one byte: `(class << 5) | detail`. `0.xx` is a request method,
  `2.xx` success, `4.xx` client error, `5.xx` server error, and `0.00`
  (`:empty`) is the empty message used for CoAP's own ACK/RST/ping
  machinery rather than carrying a request or response at all.

  RFC 7252 §12.1 Table 1/2/3, the full sets this workspace has occasion to
  use: `0.01`=0x01 GET through `0.04`=0x04 DELETE; `2.01`=0x41 Created
  through `2.05`=0x45 Content; the `4.xx`/`5.xx` client/server error codes.
  Every `class.detail -> byte` pair below is the arithmetic, not a copied
  table — `(bit-or (bit-shift-left class 5) detail)` for each — which is
  what the round-trip test over the whole table actually checks.")

(def code-names
  "`[class detail] -> keyword`. RFC 7252 §12.1."
  {[0 0] :empty
   [0 1] :get [0 2] :post [0 3] :put [0 4] :delete
   [2 1] :created [2 2] :deleted [2 3] :valid [2 4] :changed [2 5] :content
   [4 0] :bad-request [4 1] :unauthorized [4 2] :bad-option
   [4 3] :forbidden [4 4] :not-found [4 5] :method-not-allowed
   [4 6] :not-acceptable [4 12] :precondition-failed
   [4 13] :request-entity-too-large [4 15] :unsupported-content-format
   [5 0] :internal-server-error [5 1] :not-implemented [5 2] :bad-gateway
   [5 3] :service-unavailable [5 4] :gateway-timeout
   [5 5] :proxying-not-supported})

(def name->code (into {} (map (fn [[k v]] [v k])) code-names))

(defn class-detail [byte]
  [(bit-and (unsigned-bit-shift-right byte 5) 0x07) (bit-and byte 0x1F)])

(defn ->byte [[class detail]]
  (bit-or (bit-shift-left (bit-and class 0x07) 5) (bit-and detail 0x1F)))

(defn encode
  "A code keyword (from `code-names`) -> its wire byte."
  [kw]
  (if-let [cd (name->code kw)]
    {:status :ok :byte (->byte cd)}
    {:status :error :reason :unknown-code-name :name kw}))

(defn decode
  "A wire byte -> `{:status :ok :name kw :class c :detail d}`. An unknown
  `class.detail` combination is not an error — RFC 7252 §5.9 explicitly
  reserves room for codes it does not name yet, and a proxy or generic
  logger has to be able to pass one through — so `:name` is `nil` rather
  than the whole decode failing; only `class`/`detail` are guaranteed."
  [byte]
  (let [[c d] (class-detail byte)]
    {:status :ok :class c :detail d :name (code-names [c d])}))
