(ns cloudflare.stream
  "Cloudflare Stream Live -- live inputs and their RTMP live outputs.

  A live input is one ingest endpoint that accepts WHIP/WebRTC, RTMPS or
  SRT and hands Cloudflare the media. Live *outputs* attached to that input
  are what make it useful beyond Cloudflare's own player: Cloudflare
  re-broadcasts the same stream to arbitrary RTMP destinations -- YouTube
  Live, Twitch, anything else that speaks RTMP -- so a browser that can
  only speak WebRTC reaches those platforms without anyone running an
  RTMP encoder.

  Unlike the rest of this library, everything here is split in two:

    `*-request` fns are PURE .cljc -- args -> {:method :path :url :body}.
      They work anywhere, including ClojureScript and nbb, where the
      JVM-only `cloudflare.client/rest!` cannot follow.
    `*!` fns are the :clj convenience layer over `client/rest!`, matching
      cloudflare.pages / cloudflare.workers.

  That split is not decoration. Provisioning a live output means handling a
  destination stream key, which is a broadcast credential -- whoever holds
  it can publish as that channel. Keeping the request shaping pure lets the
  script that actually touches the key run wherever the key already lives,
  instead of forcing a JVM into that path."
  (:require [kotoba.lang.text :as str]
            [cloudflare.client :as client]
            [cloudflare.kotoba.oracle :as oracle]))

(def ^:private oid :stream)

(defn- o
  "Call a pure export. Requires the shipped oracle on every platform (T6.4)."
  [export args]
  (oracle/require-ready! oid)
  (oracle/call oid export args))

(defn- o-record
  "T5.2: structural host map → call-record (requires shipped oracle)."
  [export host-map field-specs]
  (oracle/require-ready! oid)
  (oracle/call-record oid export host-map field-specs))

;; ---------------------------------------------------------------------------
;; Known RTMP destinations
;;
;; Ingest hostnames, not stream keys. These are the published, stable ingest
;; endpoints for each platform; the per-channel key is always supplied by
;; the caller and never appears in this file or in any log line it produces.
;; ---------------------------------------------------------------------------

(def destinations
  "Ingest URLs for the platforms this library knows by name. `:rtmps` is
  preferred wherever a platform offers it -- an RTMP live output carries
  the stream key in the clear on the wire, and Cloudflare is speaking to
  the platform across the public internet."
  {:youtube {:rtmps "rtmps://a.rtmps.youtube.com/live2"
             :rtmp "rtmp://a.rtmp.youtube.com/live2"
             :rtmp-backup "rtmp://b.rtmp.youtube.com/live2?backup=1"}
   :twitch {:rtmps "rtmps://live.twitch.tv/app"
            :rtmp "rtmp://live.twitch.tv/app"}})

(defn destination-url
  "Ingest URL for `platform` (:youtube / :twitch). `variant` defaults to
  :rtmps. Returns nil for an unknown platform or variant -- callers pass
  their own URL in that case.
   JVM: kotoba `destination-url` (empty ≡ unknown)."
  ([platform] (destination-url platform :rtmps))
  ([platform variant]
   (let [u (o-record 'destination-url
                     {:in (oracle/record
                           [:record :stream/dest [[:platform :string] [:variant :string]]]
                           {:platform (name (keyword platform))
                            :variant (name (keyword variant))})}
                     [[:in :raw]])]
     (when-not (str/blank? u) u))))

(defn redact-key
  "A stream key rendered safe to print: first 4 characters, then the length.
  Provisioning is the one moment a human needs to confirm *which* key was
  used, and echoing it whole is how a broadcast credential ends up in a
  terminal scrollback, a CI log, or a screenshot.
   JVM: kotoba `redact-key`."
  [stream-key]
  (o-record 'redact-key {:stream-key stream-key} [[:stream-key :string]]))

;; ---------------------------------------------------------------------------
;; Validation
;; ---------------------------------------------------------------------------

(defn validate-output
  "Check a live output before it is sent. Returns a vector of problem
  keywords -- empty means valid.

    :missing-url          no destination URL
    :bad-scheme           not rtmp:// or rtmps:// (Cloudflare pushes RTMP
                          only; an https:// URL here is accepted by no one
                          and produces an output that never connects)
    :missing-stream-key   no key
    :whitespace-in-key    the key contains a space, tab or newline. Nearly
                          always a copy-paste artifact, and the single most
                          common reason a correctly-configured live output
                          silently never appears on the platform: the RTMP
                          handshake carries the key verbatim, trailing
                          newline and all.
    :key-embedded-in-url  the URL already ends with the stream key. Pasting
                          `<ingest-url>/<key>` into the URL field and the
                          key into the key field sends it twice.

   JVM: kotoba `validate-flags` bitset decoded to keywords."
  [{:keys [url stream-key]}]
  (let [flags (oracle/i64->host
                  (o-record 'validate-flags
                        {:in (oracle/record
                              [:record :stream/flags [[:url :string] [:stream-key :string]]]
                              {:url (or url "") :stream-key (or stream-key "")})}
                        [[:in :raw]]))]
       (into []
             (keep (fn [[bit kw]]
                     (when (pos? (bit-and flags bit)) kw)))
             [[1 :missing-url]
              [2 :bad-scheme]
              [4 :missing-stream-key]
              [8 :whitespace-in-key]
              [16 :key-embedded-in-url]])))

;; ---------------------------------------------------------------------------
;; Pure request builders
;; ---------------------------------------------------------------------------

(defn- path->request [method path body]
  (cond-> {:method method :path path :url (str client/api-base path)}
    (some? body) (assoc :body body)))

(defn inputs-path
  "REST path for live inputs collection. JVM: kotoba `inputs-path`."
  [account-id]
  (o-record 'inputs-path {:account-id account-id} [[:account-id :string]]))

(defn live-input-path
  "REST path for one live input. JVM: kotoba `live-input-path`."
  [account-id input-uid]
  (o-record 'live-input-path
            {:in (oracle/record
                  [:record :stream/account-uid [[:account-id :string] [:input-uid :string]]]
                  {:account-id account-id :input-uid input-uid})}
            [[:in :raw]]))

(defn outputs-path
  "REST path for live outputs under an input. JVM: kotoba `outputs-path`."
  [account-id input-uid]
  (o-record 'outputs-path
            {:in (oracle/record
                  [:record :stream/account-uid [[:account-id :string] [:input-uid :string]]]
                  {:account-id account-id :input-uid input-uid})}
            [[:in :raw]]))

(defn create-live-input-request
  "POST a new live input.

  opts:
    :name              human label, stored in Cloudflare's :meta
    :recording-mode    \"off\" (default) or \"automatic\". Recording turns
                       every broadcast into stored minutes that keep
                       billing after the stream ends, so it is off unless
                       asked for.
    :timeout-seconds   how long Cloudflare keeps the live stream open after
                       the publisher disconnects (0 = end immediately)
    :require-signed-urls / :allowed-origins  playback restrictions
    :delete-recording-after-days"
  [account-id {:keys [name recording-mode timeout-seconds require-signed-urls
                      allowed-origins delete-recording-after-days]
               :or {recording-mode "off"}}]
  (path->request
   :post (inputs-path account-id)
   (cond-> {:meta {:name (or name "live-input")}
            :recording (cond-> {:mode recording-mode}
                         (some? timeout-seconds) (assoc :timeoutSeconds timeout-seconds)
                         (some? require-signed-urls) (assoc :requireSignedURLs require-signed-urls)
                         (seq allowed-origins) (assoc :allowedOrigins (vec allowed-origins)))}
     (some? delete-recording-after-days)
     (assoc :deleteRecordingAfterDays delete-recording-after-days))))

(defn list-live-inputs-request [account-id]
  (path->request :get (inputs-path account-id) nil))

(defn live-input-request [account-id input-uid]
  (path->request :get (live-input-path account-id input-uid) nil))

(defn delete-live-input-request
  "DELETE a live input. This also removes its outputs -- Cloudflare keeps
  no orphan output once the input is gone."
  [account-id input-uid]
  (path->request :delete (live-input-path account-id input-uid) nil))

(defn create-live-output-request
  "POST an RTMP live output onto `input-uid`: Cloudflare re-broadcasts the
  input to `:url` using `:stream-key`.

  Either pass `:url` directly, or `:platform` (:youtube / :twitch) and let
  `destination-url` resolve it. Throws on an invalid output rather than
  letting Cloudflare accept a destination that can never connect --
  `validate-output` is the same check without the throw."
  [account-id input-uid {:keys [url platform variant stream-key enabled]
                         :or {enabled true variant :rtmps}}]
  (let [url (or url (destination-url platform variant))
        problems (validate-output {:url url :stream-key stream-key})]
    (when (seq problems)
      (throw (ex-info "Invalid Cloudflare Stream live output"
                      {:problems problems
                       :url url
                       :stream-key (redact-key stream-key)})))
    (path->request :post (outputs-path account-id input-uid)
                   {:url url :streamKey stream-key :enabled enabled})))

(defn list-live-outputs-request [account-id input-uid]
  (path->request :get (outputs-path account-id input-uid) nil))

(defn delete-live-output-request [account-id input-uid output-uid]
  (path->request :delete (str (outputs-path account-id input-uid) "/" output-uid) nil))

;; ---------------------------------------------------------------------------
;; Pure response readers
;; ---------------------------------------------------------------------------

(defn parse-live-input
  "Normalize one live-input result into the handful of fields a caller
  actually publishes with. Cloudflare nests each protocol's endpoint under
  its own key with its own casing (`webRTC`, `rtmps`, `srt`); this flattens
  them and keeps the raw map under :raw for anything not modelled here.

  :whip-url is the endpoint a WHIP client POSTs its SDP offer to (see
  kotoba-lang/webrtc's kotoba.webrtc.whip); :whep-url is the matching
  WebRTC playback endpoint."
  [result]
  (when (map? result)
    {:uid (:uid result)
     :whip-url (get-in result [:webRTC :url])
     :whep-url (get-in result [:webRTCPlayback :url])
     :rtmps-url (get-in result [:rtmps :url])
     :rtmps-stream-key (get-in result [:rtmps :streamKey])
     :srt-url (get-in result [:srt :url])
     :name (get-in result [:meta :name])
     :status (:status result)
     :created (:created result)
     :raw result}))

(defn parse-live-output [result]
  (when (map? result)
    {:uid (:uid result)
     :url (:url result)
     :enabled (:enabled result)
     :raw result}))

(defn live-input-summary
  "A one-line, credential-free description of a live input, safe to log or
  print during provisioning. The RTMPS stream key Cloudflare hands back is
  itself a publish credential for this input -- it is redacted here for the
  same reason the destination key is.
   JVM: kotoba `live-input-summary`."
  [{:keys [uid name whip-url rtmps-url rtmps-stream-key]}]
  ;; Guest defaults: missing whip/rtmps render as "-" (parity with stream_core).
  (o-record 'live-input-summary
            {:in (oracle/record
                  [:record :stream/summary
                   [[:uid :string] [:name :string]
                    [:whip-disp :string] [:rtmps-disp :string]
                    [:rtmps-stream-key :string]]]
                  {:uid (or uid "")
                   :name (or name "")
                   :whip-disp (or whip-url "-")
                   :rtmps-disp (or rtmps-url "-")
                   :rtmps-stream-key (or rtmps-stream-key "")})}
            [[:in :raw]]))

;; ---------------------------------------------------------------------------
;; :clj convenience layer
;; ---------------------------------------------------------------------------

#?(:clj
   (defn- call! [{:keys [method path body]} http-opts]
     (client/rest! path (cond-> (assoc http-opts :method method)
                          (some? body) (assoc :body body)))))

#?(:clj
   (defn create-live-input!
     ([account-id opts] (create-live-input! account-id opts {}))
     ([account-id opts http-opts]
      (parse-live-input (call! (create-live-input-request account-id opts) http-opts)))))

#?(:clj
   (defn live-inputs
     ([account-id] (live-inputs account-id {}))
     ([account-id http-opts]
      (mapv parse-live-input (call! (list-live-inputs-request account-id) http-opts)))))

#?(:clj
   (defn live-input
     ([account-id input-uid] (live-input account-id input-uid {}))
     ([account-id input-uid http-opts]
      (parse-live-input (call! (live-input-request account-id input-uid) http-opts)))))

#?(:clj
   (defn delete-live-input!
     ([account-id input-uid] (delete-live-input! account-id input-uid {}))
     ([account-id input-uid http-opts]
      (call! (delete-live-input-request account-id input-uid) http-opts)
      true)))

#?(:clj
   (defn create-live-output!
     ([account-id input-uid opts] (create-live-output! account-id input-uid opts {}))
     ([account-id input-uid opts http-opts]
      (parse-live-output (call! (create-live-output-request account-id input-uid opts) http-opts)))))

#?(:clj
   (defn live-outputs
     ([account-id input-uid] (live-outputs account-id input-uid {}))
     ([account-id input-uid http-opts]
      (mapv parse-live-output (call! (list-live-outputs-request account-id input-uid) http-opts)))))

#?(:clj
   (defn delete-live-output!
     ([account-id input-uid output-uid] (delete-live-output! account-id input-uid output-uid {}))
     ([account-id input-uid output-uid http-opts]
      (call! (delete-live-output-request account-id input-uid output-uid) http-opts)
      true)))
