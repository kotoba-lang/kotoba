(ns kaigi.sfu
  "Cloudflare Realtime SFU binding — request shaping and response parsing as
  pure functions. No HTTP client, no `fetch`, no secrets.

  ## Why this is a data layer and not a client

  The SFU protocol is the part of a meeting that is hardest to test and
  easiest to get subtly wrong: a misspelled `trackName`, a `location` of
  `\"remote\"` where `\"local\"` belongs, a missing `sessionId` on a pull. All
  of those are decisions, and decisions belong in portable code with tests.
  Sending bytes is mechanism, and it stays in the host (`kaigi.worker.room`).

  Every function here returns a request descriptor:

      {:kaigi.sfu/method :post | :put | :get
       :kaigi.sfu/url    \"https://rtc.live.cloudflare.com/v1/apps/…\"
       :kaigi.sfu/body   {…}}   ; absent for GET

  Body maps use keyword keys spelled EXACTLY as the wire field names
  (`:sessionDescription`, `:trackName`, `:requiresImmediateRenegotiation`),
  because the JSON is camelCase and a translation table between two spellings
  is one more thing to drift. A ClojureScript host serializes with
  `clj->js` + `JSON.stringify` and gets the right document; a JVM host with
  any keyword-to-string JSON writer does too.

  ## The token is not in the request

  `request` descriptors deliberately carry no `Authorization` header, so a
  descriptor can be logged, diffed and asserted on without leaking the app
  secret. `authorize` is the single function that attaches it, called by the
  host immediately before the send.

  ## Field names are from the published spec, not from memory

  Shapes follow Cloudflare's OpenAPI document `realtime-api-2024-05-21.yaml`
  (`servers: https://rtc.live.cloudflare.com/v1`, bearer auth). The endpoints
  used here are `POST /apps/{appId}/sessions/new`,
  `POST /apps/{appId}/sessions/{sessionId}/tracks/new`,
  `PUT  /apps/{appId}/sessions/{sessionId}/renegotiate`,
  `PUT  /apps/{appId}/sessions/{sessionId}/tracks/close` and
  `GET  /apps/{appId}/sessions/{sessionId}`."
  (:require [kotoba.lang.text :as str]))

(def base-url
  "The SFU API root, including the version segment."
  "https://rtc.live.cloudflare.com/v1")

(def track-locations
  "`local` publishes a track to the SFU; `remote` subscribes to someone
  else's. These are wire strings, not keywords, because they go out as-is."
  #{"local" "remote"})

(defn- app-path
  [app-id & segments]
  (str base-url "/apps/" app-id (when (seq segments) (str "/" (str/join "/" segments)))))

(defn- session-desc
  "A `SessionDescription` object. `kind` is `:offer` or `:answer`."
  [kind sdp]
  {:type (name kind) :sdp sdp})

;; ---------------------------------------------------------------------------
;; requests
;; ---------------------------------------------------------------------------

(defn new-session-request
  "Create a PeerConnection on the SFU.

  Called with `sdp` the local offer is sent and the SFU answers. Called
  without one, the session is created empty and the first `tracks/new` does
  the negotiation — which is what the pull-first flow in `kaigi.plan` uses,
  since a participant who is only watching has nothing to offer yet."
  ([app-id] {:kaigi.sfu/method :post
             :kaigi.sfu/url    (app-path app-id "sessions" "new")
             :kaigi.sfu/body   {}})
  ([app-id sdp] {:kaigi.sfu/method :post
                 :kaigi.sfu/url    (app-path app-id "sessions" "new")
                 :kaigi.sfu/body   {:sessionDescription (session-desc :offer sdp)}}))

(defn push-tracks-request
  "Publish local tracks. `tracks` is a seq of `{:mid :track-name}` — the
  transceiver mid from the local PeerConnection and the name other
  participants will pull by.

  `sdp` is the local offer that created those transceivers. The SFU replies
  with an answer to apply."
  [app-id session-id sdp tracks]
  {:kaigi.sfu/method :post
   :kaigi.sfu/url    (app-path app-id "sessions" session-id "tracks" "new")
   :kaigi.sfu/body   {:sessionDescription (session-desc :offer sdp)
                      :tracks (mapv (fn [{:keys [mid track-name kind bidirectional?]}]
                                      (cond-> {:location "local"
                                               :mid mid
                                               :trackName track-name}
                                        kind           (assoc :kind (name kind))
                                        bidirectional? (assoc :bidirectionalMediaStream true)))
                                    tracks)}})

(defn pull-tracks-request
  "Subscribe to remote tracks. `tracks` is a seq of
  `{:session-id :track-name}` naming the publisher's SFU session and track.

  No `sessionDescription` is sent: pulling is the one direction where the SFU
  generates the offer, and the response's `requiresImmediateRenegotiation`
  tells the caller to apply it. Sending an offer here is the mistake this
  arity shape exists to prevent."
  [app-id session-id tracks]
  {:kaigi.sfu/method :post
   :kaigi.sfu/url    (app-path app-id "sessions" session-id "tracks" "new")
   :kaigi.sfu/body   {:tracks (mapv (fn [{:keys [session-id track-name]}]
                                      {:location "remote"
                                       :sessionId session-id
                                       :trackName track-name})
                                    tracks)}})

(defn renegotiate-request
  "Answer an SFU-generated offer. `kind` is `:answer` in the normal flow."
  ([app-id session-id sdp] (renegotiate-request app-id session-id sdp :answer))
  ([app-id session-id sdp kind]
   {:kaigi.sfu/method :put
    :kaigi.sfu/url    (app-path app-id "sessions" session-id "renegotiate")
    :kaigi.sfu/body   {:sessionDescription (session-desc kind sdp)}}))

(defn close-tracks-request
  "Close tracks by transceiver mid. `force?` stops the data flow without a
  WebRTC renegotiation — the right choice when the peer is already gone and
  there is nobody left to renegotiate with."
  [app-id session-id mids & [{:keys [force?]}]]
  {:kaigi.sfu/method :put
   :kaigi.sfu/url    (app-path app-id "sessions" session-id "tracks" "close")
   :kaigi.sfu/body   (cond-> {:tracks (mapv (fn [mid] {:mid mid}) mids)}
                       force? (assoc :force true))})

(defn session-state-request
  "Read the SFU's view of a session — every track and its `active` /
  `inactive` / `waiting` status. Used to reconcile after a reconnect rather
  than trusting local bookkeeping that may have missed events."
  [app-id session-id]
  {:kaigi.sfu/method :get
   :kaigi.sfu/url    (app-path app-id "sessions" session-id)})

(defn authorize
  "Attach the app secret. The only function that touches it; call it
  immediately before sending and do not retain the result."
  [request app-token]
  (assoc request :kaigi.sfu/headers
         {"Authorization" (str "Bearer " app-token)
          "Content-Type"  "application/json"}))

;; ---------------------------------------------------------------------------
;; responses
;; ---------------------------------------------------------------------------

(defn- track-error
  [t]
  (when (:errorCode t)
    {:kaigi.sfu/error-code (:errorCode t)
     :kaigi.sfu/error-description (:errorDescription t)
     :kaigi.sfu/track-name (:trackName t)
     :kaigi.sfu/mid (:mid t)}))

(defn parse-response
  "Normalize any SFU response body into one shape:

      {:kaigi.sfu/ok?       true|false
       :kaigi.sfu/session-id       \"…\"            ; sessions/new only
       :kaigi.sfu/sdp              \"…\"            ; when one came back
       :kaigi.sfu/sdp-type         :answer|:offer
       :kaigi.sfu/renegotiate?     true|false
       :kaigi.sfu/tracks           [{…} …]
       :kaigi.sfu/errors           [{…} …]}

  `body` is expected already parsed from JSON with keyword keys.

  A per-track `errorCode` makes the whole response not-ok even when the HTTP
  status was 200. The SFU reports partial failures inside a successful
  response — a caller that only checks the status will happily record a
  subscription that was refused, and the participant sees a black tile with
  no error anywhere."
  [body]
  (let [tracks     (:tracks body)
        top-error  (when (:errorCode body)
                     {:kaigi.sfu/error-code (:errorCode body)
                      :kaigi.sfu/error-description (:errorDescription body)})
        track-errs (into [] (keep track-error) tracks)
        errs       (into (if top-error [top-error] []) track-errs)
        sdp        (get-in body [:sessionDescription :sdp])
        sdp-type   (get-in body [:sessionDescription :type])]
    (cond-> {:kaigi.sfu/ok? (empty? errs)
             :kaigi.sfu/renegotiate? (boolean (:requiresImmediateRenegotiation body))}
      (:sessionId body) (assoc :kaigi.sfu/session-id (:sessionId body))
      sdp               (assoc :kaigi.sfu/sdp sdp)
      sdp-type          (assoc :kaigi.sfu/sdp-type (keyword sdp-type))
      (seq tracks)      (assoc :kaigi.sfu/tracks (vec tracks))
      (seq errs)        (assoc :kaigi.sfu/errors errs))))

(defn ok?
  [parsed]
  (true? (:kaigi.sfu/ok? parsed)))

(defn needs-renegotiation?
  [parsed]
  (true? (:kaigi.sfu/renegotiate? parsed)))

;; ---------------------------------------------------------------------------
;; configuration
;; ---------------------------------------------------------------------------

(defn configured?
  "True when `config` carries both an app id and an app token.

  `kaigi.plan/transport` uses this to choose between the SFU and the mesh
  fallback. It is a function rather than an inline `and` so the one place
  that decides 'do we have an SFU' is named and testable."
  [{:keys [app-id app-token]}]
  (boolean (and (string? app-id) (seq app-id)
                (string? app-token) (seq app-token))))
