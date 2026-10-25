(ns provider.object-transport
  "Production transport for stream-object-v1 (`provider.object`), backed by a
  host-configured durable object service over fixed-path JSON-on-HTTPS.

  Does NOT define a new capability and does NOT modify `object.cljc`. The
  reference providers already enforce binding allow-lists, non-empty keys,
  and max-pull-bytes before this transport runs. This namespace supplies the
  real synchronous `(fn [request] -> reply)` the host injects as `:transport`.

  ## No ambient object store (kit `:ambient-object-store false`)

  Like `storage-transport` (ADR 0071) and unlike a naive local filesystem
  blob root, this namespace never invents a default backend. The host MUST
  pass `:endpoint` (or `KOTOBA_OBJECT_ENDPOINT`). There is no baked-in
  default destination.

  ## Fixed path, guest data only in the JSON body

  POST to a single host-configured path (default `/object/v1/transact`).
  Binding keywords, keys, digests, and bytes never appear in the URL path
  (avoids path-traversal / percent-encoding hazards on guest-controlled
  strings — same rationale as storage-transport).

  ## Operations

  | request `:operation` | wire success | provider reply |
  |---|---|---|
  | `:get-stream` | `{\"tag\":\"found\",\"bytes_base64\":\"...\"}` | `{:bytes <host :bytes>}` |
  | `:put-block` | `{\"tag\":\"ok\",\"won\":true}` | `true`/`false` |
  | `:compare-and-set-ref` | `{\"tag\":\"ok\",\"won\":true|false}` | `true`/`false` |

  Missing get-stream → throw (redacted by `object.cljc` invoke-transport).
  Non-2xx / malformed wire → throw similarly. Network exceptions propagate
  uncaught for the same redaction path (ADR 0064/0066/0071 pattern).

  ## `:cljs` / nbb (ADR 0129)

  spawnSync Node hop (same pattern as ADR 0117/0119). Required `:endpoint`,
  fixed path, base64 bytes, fail-closed wire parsing match the `:clj` path."
  (:require [kotoba.lang.text :as string]
            [provider.object :as object]
            [kotoba.kir.value :as value]
            #?(:clj [json.data-json :as json]))
  #?(:clj
     (:import (java.net URI)
              (java.net.http HttpClient HttpClient$Version HttpRequest
                             HttpRequest$BodyPublishers HttpResponse
                             HttpResponse$BodyHandlers)
              (java.nio.charset StandardCharsets)
              (java.util Base64)
              (java.time Duration)
              (java.io ByteArrayOutputStream InputStream))))

(def default-path "/object/v1/transact")
(def default-connect-timeout-ms 5000)
(def default-request-timeout-ms 10000)
(def env-endpoint-var "KOTOBA_OBJECT_ENDPOINT")
(def env-api-key-var "KOTOBA_OBJECT_API_KEY")
(def response-byte-limit (+ object/max-pull-bytes 8192))

#?(:clj
   (defn- getenv [name]
     (let [v (System/getenv name)]
       (when (and v (seq (string/trim v))) v))))

#?(:cljs
   (defn- getenv [name]
     (let [v (aget js/process.env name)]
       (when (and v (seq (string/trim v))) v))))

(defn mem-transport
  "In-memory object transport for tests + audit-hook demos (ADR 0271).

  Not durable. Optional `:on-call` receives
  `{:kit :object :operation :binding :key :reply-tag}` after each op
  (same optional audit surface as `production-transport`). Exceptions
  from on-call are swallowed.

  Blocks are keyed by digest string; refs by key → etag string."
  ([] (mem-transport {}))
  ([{:keys [initial-blocks initial-refs on-call]
     :or {initial-blocks {} initial-refs {} on-call (fn [_])}}]
   (let [blocks (atom (into {} initial-blocks))
         refs (atom (into {} initial-refs))
         audit! (fn [e]
                  (try (on-call e)
                       (catch #?(:clj Exception :cljs :default) _ nil)))]
     (fn [{:keys [operation binding key digest bytes expected next] :as _req}]
       (let [reply
             (case operation
               :get-stream
               (if-let [b (or (get @blocks key) (get @blocks digest))]
                 {:bytes b}
                 (throw (ex-info "object mem not found"
                                 {:phase :object-transport})))
               :put-block
               (do (swap! blocks assoc (str digest) bytes)
                   true)
               :compare-and-set-ref
               (let [cur (get @refs key)]
                 (if (= cur expected)
                   (do (swap! refs assoc key next) true)
                   false))
               (throw (ex-info "object mem unknown op"
                               {:phase :object-transport :operation operation})))]
         (audit! {:kit :object
                  :operation operation
                  :binding binding
                  :key key
                  :reply-tag (if (boolean? reply)
                               (if reply :ok :lost)
                               :bytes)})
         reply)))))

(defn resolve-endpoint
  "Resolve host-configured object-store origin: `:endpoint` option, else
  `KOTOBA_OBJECT_ENDPOINT`, else throw. No ambient default."
  [opts]
  (or (:endpoint opts)
      (getenv env-endpoint-var)
      (throw (ex-info
              (str "object-transport requires an :endpoint construction option (or "
                   env-endpoint-var
                   " env var) — no ambient object store")
              {:phase :object-transport}))))

(defn- kw->wire [kw]
  (if-let [ns (namespace kw)]
    (str ns "/" (name kw))
    (name kw)))

#?(:clj
   (defn- bytes->base64 [^bytes b]
     (.encodeToString (Base64/getEncoder) b)))

#?(:cljs
   (defn- bytes->base64 [b]
     (let [u8 (if (instance? js/Uint8Array b) b (js/Uint8Array. b))]
       (.toString (js/Buffer.from u8) "base64"))))

#?(:clj
   (defn- base64->bytes [s]
     (.decode (Base64/getDecoder) (str s))))

#?(:cljs
   (defn- base64->bytes [s]
     (js/Uint8Array. (.from js/Buffer (str s) "base64"))))

(defn- request-body
  [{:keys [operation binding key digest bytes expected next]}]
  (cond-> {"operation" (name operation)
           "binding" (kw->wire binding)}
    (contains? #{:get-stream :compare-and-set-ref} operation)
    (assoc "key" key)
    (= operation :put-block)
    (assoc "digest" digest
           "bytes_base64" (bytes->base64 bytes))
    (= operation :compare-and-set-ref)
    (assoc "expected" expected
           "next" next)))

#?(:clj
   (defn- read-bounded-bytes
     ^bytes [^InputStream in ^long max-bytes]
     (let [out (ByteArrayOutputStream.)
           buf (byte-array (int (min max-bytes 8192)))]
       (loop [total 0]
         (if (>= total max-bytes)
           (.toByteArray out)
           (let [to-read (int (min (alength buf) (- max-bytes total)))
                 n (.read in buf 0 to-read)]
             (if (neg? n)
               (.toByteArray out)
               (do (.write out buf 0 n)
                   (recur (+ total n))))))))))

(defn- truncate-to-byte-limit [s limit]
  (loop [s (str s)]
    (if (<= (value/utf8-byte-count! s) limit)
      s
      (recur (subs s 0 (max 0 (dec (count s))))))))

#?(:clj
   (defn- decode-bounded-body [^bytes raw]
     (truncate-to-byte-limit (String. raw StandardCharsets/UTF_8)
                              response-byte-limit)))

(defn- wire->transport-reply
  "Map upstream JSON to the shape `provider.object` transports expect."
  [operation parsed]
  (let [tag (keyword (str (:tag parsed)))]
    (case tag
      :found
      (let [b64 (:bytes_base64 parsed)]
        (when-not (string? b64)
          (throw (ex-info "object-transport found without bytes_base64"
                          {:phase :object-transport})))
        (let [payload (base64->bytes b64)]
          (when (> (value/bytes-byte-count payload) object/max-pull-bytes)
            (throw (ex-info "object-transport payload exceeds max-pull-bytes"
                            {:phase :object-transport})))
          {:bytes payload}))

      :ok
      (let [won (:won parsed)]
        (when-not (boolean? won)
          (throw (ex-info "object-transport ok without boolean won"
                          {:phase :object-transport})))
        (when-not (contains? #{:put-block :compare-and-set-ref} operation)
          (throw (ex-info "object-transport ok tag for non-write operation"
                          {:phase :object-transport :operation operation})))
        won)

      :missing
      (throw (ex-info "object-transport object missing"
                      {:phase :object-transport :operation operation}))

      :error
      (throw (ex-info "object-transport upstream error"
                      {:phase :object-transport
                       :code (get-in parsed [:error :code])
                       :message (get-in parsed [:error :message])}))

      (throw (ex-info "object-transport unknown wire tag"
                      {:phase :object-transport :tag tag})))))

#?(:clj
   (defn- send-transact-request
     [^HttpClient http-client
      {:keys [endpoint path api-key request-timeout-ms]}
      body-json]
     (let [url (str endpoint path)
           builder (-> (HttpRequest/newBuilder (URI/create url))
                       (.timeout (Duration/ofMillis (long request-timeout-ms)))
                       (.header "content-type" "application/json")
                       (.header "accept" "application/json")
                       (.POST (HttpRequest$BodyPublishers/ofString body-json)))
           builder (if api-key
                     (.header builder "authorization" (str "Bearer " api-key))
                     builder)
           req (.build builder)
           resp (.send http-client req (HttpResponse$BodyHandlers/ofInputStream))
           status (.statusCode resp)
           ^InputStream in (.body resp)
           raw (try (read-bounded-bytes in response-byte-limit)
                    (finally (.close in)))]
       {:status status :body (decode-bounded-body raw)})))

#?(:clj
   (defn production-transport
     "Synchronous production transport for
     `(provider.object/create-providers {:transport (production-transport ...) ...})`.

     Options:
       :endpoint — required (or KOTOBA_OBJECT_ENDPOINT)
       :path — default `/object/v1/transact`
       :api-key — optional bearer (or KOTOBA_OBJECT_API_KEY)
       :connect-timeout-ms / :request-timeout-ms
       :on-call — optional audit hook; exceptions swallowed"
     ([] (production-transport {}))
     ([opts]
      (let [endpoint (resolve-endpoint opts)
            path (:path opts default-path)
            api-key (or (:api-key opts) (getenv env-api-key-var))
            connect-timeout-ms (:connect-timeout-ms opts default-connect-timeout-ms)
            request-timeout-ms (:request-timeout-ms opts default-request-timeout-ms)
            on-call (:on-call opts (fn [_]))
            http-client (-> (HttpClient/newBuilder)
                            (.version HttpClient$Version/HTTP_1_1)
                            (.connectTimeout (Duration/ofMillis (long connect-timeout-ms)))
                            (.build))]
        (fn [{:keys [operation] :as request}]
          (let [started (System/currentTimeMillis)
                safe-audit! (fn [event] (try (on-call event) (catch Exception _ nil)))
                body-json (json/write-str (request-body request))
                {:keys [status body]}
                (send-transact-request http-client
                                       {:endpoint endpoint :path path :api-key api-key
                                        :request-timeout-ms request-timeout-ms}
                                       body-json)
                latency-ms (- (System/currentTimeMillis) started)]
            (when-not (= 200 status)
              (safe-audit! {:operation operation :status :http-error
                            :http-status status :latency-ms latency-ms})
              (throw (ex-info "object-transport HTTP error"
                              {:phase :object-transport
                               :http-status status
                               :body (truncate-to-byte-limit body 400)})))
            (let [parsed (json/read-str body :key-fn keyword)
                  reply (wire->transport-reply operation parsed)]
              (safe-audit! {:operation operation :status :ok
                            :http-status status :latency-ms latency-ms})
              reply)))))))

#?(:cljs
   (def ^:private hop-script
     "Node one-shot POST of JSON body; print {status, body}."
     (str
      "const https=require('https');const http=require('http');const {URL}=require('url');\n"
      "const MAX=65536+8192;\n"
      "let raw='';process.stdin.setEncoding('utf8');\n"
      "process.stdin.on('data',c=>raw+=c);process.stdin.on('end',()=>{\n"
      "  const req=JSON.parse(raw);\n"
      "  const u=new URL(req.url);\n"
      "  const lib=u.protocol==='https:'?https:http;\n"
      "  const headers=Object.assign({'content-type':'application/json','accept':'application/json'},req.headers||{});\n"
      "  const body=Buffer.from(String(req.body||''),'utf8');\n"
      "  headers['content-length']=String(body.length);\n"
      "  const opts={method:'POST',hostname:u.hostname,port:u.port||(u.protocol==='https:'?443:80),"
      "path:u.pathname+u.search,headers,timeout:Number(req.timeoutMs)||10000};\n"
      "  const r=lib.request(opts,res=>{\n"
      "    const chunks=[];let n=0;\n"
      "    res.on('data',c=>{if(n<MAX){const t=c.slice(0,MAX-n);chunks.push(t);n+=t.length;}});\n"
      "    res.on('end',()=>{\n"
      "      process.stdout.write(JSON.stringify({status:res.statusCode,"
      "body:Buffer.concat(chunks).toString('utf8')}));process.exit(0);\n"
      "    });\n"
      "  });\n"
      "  r.on('timeout',()=>{r.destroy();process.stdout.write(JSON.stringify("
      "{error:true,message:'hop timeout'}));process.exit(0);});\n"
      "  r.on('error',e=>{process.stdout.write(JSON.stringify("
      "{error:true,message:String(e&&e.message||e)}));process.exit(0);});\n"
      "  r.write(body);r.end();\n"
      "});\n")))

#?(:cljs
   (defn- send-transact-request
     [{:keys [endpoint path api-key request-timeout-ms]} body-json]
     (let [child (js/require "child_process")
           headers (cond-> {}
                     api-key (assoc "authorization" (str "Bearer " api-key)))
           payload (js/JSON.stringify
                    (clj->js {:url (str endpoint path)
                              :headers headers
                              :body body-json
                              :timeoutMs request-timeout-ms}))
           wall-ms (+ (long request-timeout-ms) 5000)
           result (.spawnSync child js/process.execPath
                              #js ["-e" hop-script]
                              #js {:input payload :encoding "utf8" :timeout wall-ms})]
       (when (.-error result)
         (throw (ex-info "object-transport hop spawn failed"
                         {:phase :object-transport})))
       (let [parsed (js->clj (js/JSON.parse (or (.-stdout result) "{}"))
                             :keywordize-keys true)]
         (when (:error parsed)
           (throw (ex-info "object-transport hop error"
                           {:phase :object-transport
                            :message (:message parsed)})))
         {:status (:status parsed)
          :body (truncate-to-byte-limit (str (:body parsed)) response-byte-limit)}))))

#?(:cljs
   (defn production-transport
     "nbb/cljs production object-store transport (ADR 0129). spawnSync hop."
     ([] (production-transport {}))
     ([opts]
      (let [endpoint (resolve-endpoint opts)
            path (:path opts default-path)
            api-key (or (:api-key opts) (getenv env-api-key-var))
            request-timeout-ms (:request-timeout-ms opts default-request-timeout-ms)
            on-call (:on-call opts (fn [_]))]
        (fn [{:keys [operation] :as request}]
          (let [started (js/Date.now)
                safe-audit! (fn [event] (try (on-call event) (catch :default _ nil)))
                body-json (js/JSON.stringify (clj->js (request-body request)))
                {:keys [status body]}
                (send-transact-request
                 {:endpoint endpoint :path path :api-key api-key
                  :request-timeout-ms request-timeout-ms}
                 body-json)
                latency-ms (- (js/Date.now) started)]
            (when-not (= 200 status)
              (safe-audit! {:operation operation :status :http-error
                            :http-status status :latency-ms latency-ms})
              (throw (ex-info "object-transport HTTP error"
                              {:phase :object-transport
                               :http-status status})))
            (let [parsed (js->clj (js/JSON.parse body) :keywordize-keys true)
                  reply (wire->transport-reply operation parsed)]
              (safe-audit! {:operation operation :status :ok
                            :http-status status :latency-ms latency-ms})
              reply)))))))
