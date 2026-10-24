(ns kotoba.lang.ipfs
  "Kubo (IPFS) HTTP API pin/fetch/node-info helpers — PURE core over an
  injected IHttp transport.

  This namespace models the Kubo protocol — endpoint URLs, the multipart
  upload envelope, and the NDJSON/JSON response shapes — as pure functions,
  and drives an actual transfer through a host-supplied IHttp impl. The
  library performs ZERO network I/O and carries ZERO vendor/SDK deps: the
  host (JVM java.net / babashka.http-client, cljs fetch, WASM host) supplies
  IHttp. This is the kotoba-lang layer contract — a pure technical layer that
  models records/protocol/data only (ADR-2606302300 §Step-1).

  JVM: synchronous, returns plain values. CLJS: async, returns js/Promise
  (mirroring the original TS, which was async throughout).

  IHttp returns {:status Int :body bytes}; bytes are decoded to string for
  JSON parsing via reader conditionals (JVM String./UTF-8, cljs TextDecoder).

  Public API:
    (pin-blob   http api-url content)   => {:cid String :size Int}        | js/Promise
    (fetch-blob http gateway-url cid)   => bytes                          | js/Promise
    (node-info  http api-url)           => {:id String :version String}   | js/Promise
  where `http` satisfies IHttp."
  (:require #?(:clj [json.data-json :as json])
            [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; Capability seam — host-injected transport. Core never touches the network.
;; ---------------------------------------------------------------------------

(defprotocol IHttp
  "Host-injected HTTP transport. Core builds every URL, request body, and
  parses every response; the host only moves bytes over the wire. Each method
  returns {:status Int :body bytes} (CLJS impls may resolve a js/Promise to it)."
  (-get       [this url]          "GET `url`.                => {:status :body bytes}.")
  (-post      [this url]          "POST `url`, empty body.   => {:status :body bytes}.")
  (-post-file [this url content]  "POST multipart/form-data with a single \"file\"
                                  field whose content is `content` (String or bytes).
                                  The host builds the envelope natively (FormData /
                                  babashka http-client multipart). => {:status :body bytes}."))

;; ---------------------------------------------------------------------------
;; Pure: endpoint URLs
;; ---------------------------------------------------------------------------

(defn- strip-trailing-slashes [s] (str/replace s #"/+$" ""))

(defn add-url
  "Kubo `/api/v0/add` (pin=true, cid-version=1) URL for `api-url`."
  [api-url]
  (str (strip-trailing-slashes api-url) "/api/v0/add?pin=true&cid-version=1"))

(defn gateway-url
  "Kubo gateway `/ipfs/<cid>` URL for `gateway-url` + `cid`."
  [gateway-url cid]
  (str (strip-trailing-slashes gateway-url) "/ipfs/" cid))

(defn version-url
  "Kubo `/api/v0/version` URL for `api-url`."
  [api-url]
  (str (strip-trailing-slashes api-url) "/api/v0/version"))

(defn id-url
  "Kubo `/api/v0/id` URL for `api-url`."
  [api-url]
  (str (strip-trailing-slashes api-url) "/api/v0/id"))

;; ---------------------------------------------------------------------------
;; Pure: bytes<->string + JSON (platform shims behind reader conditionals)
;; ---------------------------------------------------------------------------

(defn- bytes->string
  "UTF-8 decode. `b` is bytes (JVM) / js/Uint8Array (CLJS)."
  [b]
  #?(:clj  (String. ^bytes b "UTF-8")
     :cljs (.decode (js/TextDecoder. "utf-8") b)))

(defn- read-json
  "Parse a JSON object string to a map with STRING keys (uniform clj/cljs)."
  [s]
  #?(:clj  (json/read-str s)                          ; string keys by default
     :cljs (js->clj (js/JSON.parse s))))                 ; string keys by default

(defn- parse-size [v]
  #?(:clj  (Long/parseLong (str v))
     :cljs (js/Number v)))

(defn parse-add-response
  "Kubo `/api/v0/add` returns NDJSON (one object per file; the last is the
  root). Pure: response-body-string => {:cid String :size Int}."
  [body-str]
  {:pre [(string? body-str)]}
  (let [last-line (->> (str/split-lines (str/trim body-str))
                       (remove str/blank?)
                       last)
        obj (read-json last-line)]
    {:cid  (get obj "Hash")
     :size (parse-size (get obj "Size"))}))

;; ---------------------------------------------------------------------------
;; Orchestration (JVM synchronous / CLJS async). Pure helpers above are shared.
;; ---------------------------------------------------------------------------

(defn- ok? [status] (<= 200 status 299))

#?(:clj
   (defn pin-blob
     "Pin `content` (String or bytes) to Kubo at `api-url` via `http`.
     => {:cid String :size Int}. Throws ex-info on non-2xx."
     [http api-url content]
     (let [resp (-post-file http (add-url api-url) content)]
       (when-not (ok? (:status resp))
         (throw (ex-info "[kotoba.lang.ipfs] pin failed"
                         {:status (:status resp) :body (bytes->string (:body resp))})))
       (parse-add-response (bytes->string (:body resp))))))

#?(:cljs
   (defn pin-blob
     "Pin `content` (String, js/Uint8Array, or js/Blob) to Kubo at `api-url`
     via `http`. => js/Promise of {:cid String :size Int}."
     [http api-url content]
     (-> (-post-file http (add-url api-url) content)
         (.then (fn [resp]
                  (if-not (ok? (:status resp))
                    (throw (js/Error. (str "[kotoba.lang.ipfs] pin failed: "
                                           (:status resp) " "
                                           (bytes->string (:body resp)))))
                    (parse-add-response (bytes->string (:body resp)))))))))

#?(:clj
   (defn fetch-blob
     "Fetch `cid` from Kubo gateway `gateway-url` via `http`. => bytes."
     [http gateway cid]
     (let [resp (-get http (gateway-url gateway cid))]
       (when-not (ok? (:status resp))
         (throw (ex-info "[kotoba.lang.ipfs] fetch failed"
                         {:status (:status resp)})))
       (:body resp))))

#?(:cljs
   (defn fetch-blob
     "Fetch `cid` from Kubo gateway `gateway-url` via `http`.
     => js/Promise of js/Uint8Array."
     [http gateway cid]
     (-> (-get http (gateway-url gateway cid))
         (.then (fn [resp]
                  (if-not (ok? (:status resp))
                    (throw (js/Error. (str "[kotoba.lang.ipfs] fetch failed: "
                                           (:status resp))))
                    (:body resp)))))))

#?(:clj
   (defn node-info
     "Check the Kubo node at `api-url` is reachable via `http`.
     => {:id String :version String}."
     [http api-url]
     (let [v-resp (-post http (version-url api-url))]
       (when-not (ok? (:status v-resp))
         (throw (ex-info "[kotoba.lang.ipfs] node unreachable"
                         {:status (:status v-resp)})))
       (let [v-obj  (read-json (bytes->string (:body v-resp)))
             id-resp (-post http (id-url api-url))
             id-obj  (read-json (bytes->string (:body id-resp)))]
         {:id      (get id-obj "ID")
          :version (get v-obj "Version")}))))

#?(:cljs
   (defn node-info
     "Check the Kubo node at `api-url` is reachable via `http`.
     => js/Promise of {:id String :version String}."
     [http api-url]
     (-> (-post http (version-url api-url))
         (.then (fn [v-resp]
                  (when-not (ok? (:status v-resp))
                    (throw (js/Error. (str "[kotoba.lang.ipfs] node unreachable: "
                                           (:status v-resp)))))
                  (read-json (bytes->string (:body v-resp)))))
         (.then (fn [v-obj]
                  (-> (-post http (id-url api-url))
                      (.then (fn [id-resp]
                               (read-json (bytes->string (:body id-resp)))))
                      (.then (fn [id-obj]
                               {:id      (get id-obj "ID")
                                :version (get v-obj "Version")}))))))))
