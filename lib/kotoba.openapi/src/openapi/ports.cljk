(ns openapi.ports
  "Host-injected port for executing OpenAPI requests. openapi-clj defines the protocol;
  the host supplies a concrete implementation (clj-http, hato, js/fetch, …). The request
  builder in `openapi.execute` is pure — it builds the request map and delegates I/O
  entirely to this protocol.

  req-map shape: {:method method-kw :url url-str :query query-map :body body-map :headers headers-map}")

(defprotocol IHttp
  "Thin HTTP port. `request` receives a request map and returns a response map.
  The caller decides the shape of the response map; openapi-clj makes no assumptions
  beyond what the host chooses to return."
  (request [this req-map]
    "Send `req-map` and return a response map. Pure implementations may return fixture data."))

(def default-ports
  "A fixture IHttp that echoes the request without performing any I/O.
  Returns {:status 0 :echo req-map}. Useful for unit-testing request construction."
  (reify IHttp
    (request [_ req-map]
      {:status 0 :echo req-map})))
