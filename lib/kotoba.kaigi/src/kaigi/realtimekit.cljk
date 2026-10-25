(ns kaigi.realtimekit
  "Cloudflare RealtimeKit binding — request shaping and response parsing as
  pure functions. No HTTP client, no secrets.

  ## RealtimeKit is the media plane, not the meeting

  RealtimeKit has its own notion of a meeting and a participant, and adopting
  it wholesale would put two authorities in the same system: its presets would
  decide who may speak while `kaigi.model` decides who is admitted, and the two
  would disagree the first time a host denied someone.

  So the split is explicit. `kaigi.model` stays the authority for admission,
  roles and recording consent; RealtimeKit carries audio and video. The seam is
  `participant-request`, which the room may only call for a participant
  `kaigi.model` says is `:admitted` — see `token-refusal`. RealtimeKit never
  learns about the lobby, and it does not need to: someone who is not admitted
  simply never receives a token, and a meeting they cannot get a token for is
  one they cannot join.

  ## This is a different product from the SFU, with different credentials

  `kaigi.sfu` talks to `rtc.live.cloudflare.com/v1/apps/{appId}/…` with an app
  secret. This talks to the Cloudflare API at
  `/accounts/{account}/realtime/kit/{app}/…` with a **Cloudflare API token**.
  An SFU app id is not a RealtimeKit app id — measured 2026-07-31, a
  RealtimeKit app id returns exactly the same `not_found` from the SFU API as
  an all-zeros UUID does. `kaigi.sfu` is kept rather than deleted (the SFU
  remains the lower-level option, and the binding is written and tested), but
  the two are never configured at once; see `kaigi.plan/transport`.

  Portable `.cljc`: no clock, no I/O. Ids and tokens are supplied by the
  caller."
  (:require [kotoba.lang.text :as str]
            [kaigi.model :as m]))

(def base-url
  "The Cloudflare API root. RealtimeKit lives under the account, unlike the
  SFU which has its own host."
  "https://api.cloudflare.com/client/v4")

(defn- app-path
  [{:keys [account-id app-id]} & segments]
  (str base-url "/accounts/" account-id "/realtime/kit/" app-id
       (when (seq segments) (str "/" (str/join "/" segments)))))

;; ---------------------------------------------------------------------------
;; requests
;; ---------------------------------------------------------------------------

(defn create-meeting-request
  "Create the RealtimeKit meeting that carries a kaigi meeting's media.

  `record-on-start` is deliberately NOT set here even though the API offers
  it. Recording in kaigi requires unanimous explicit consent
  (`kaigi.model/recording-allowed?`), and a meeting that starts recording
  because a flag was set at creation would begin before anyone had agreed —
  the exact inversion the consent rule exists to prevent."
  [config {:keys [title]}]
  {:kaigi.rk/method :post
   :kaigi.rk/url (app-path config "meetings")
   :kaigi.rk/body (cond-> {:record_on_start false
                           :persist_chat false}
                    (seq (str title)) (assoc :title title))})

(defn participant-request
  "Mint a client token for one participant.

  `custom_participant_id` is kaigi's own participant id, so the two systems
  agree on identity without a mapping table — a table is a thing that can be
  stale, and a stale identity mapping puts someone else's video under your
  name."
  [config meeting-id {:keys [participant-id display-name preset]}]
  {:kaigi.rk/method :post
   :kaigi.rk/url (app-path config "meetings" meeting-id "participants")
   :kaigi.rk/body (cond-> {:custom_participant_id (str participant-id)
                           :preset_name (str preset)}
                    (seq (str display-name)) (assoc :name display-name))})

(defn authorize
  "Attach the Cloudflare API token. The only function that touches it; call it
  immediately before the send and do not retain the result.

  Same discipline as `kaigi.sfu/authorize` and for the same reason: a request
  descriptor with no credential in it can be logged, diffed and asserted on."
  [request token]
  (assoc request :kaigi.rk/headers
         {"Authorization" (str "Bearer " token)
          "Content-Type" "application/json"}))

;; ---------------------------------------------------------------------------
;; responses
;; ---------------------------------------------------------------------------

(defn parse-response
  "Normalize a Cloudflare API response body.

  Returns `{:kaigi.rk/ok? … :kaigi.rk/data … :kaigi.rk/errors [...]}`.

  `success` is checked rather than assumed from the HTTP status: the
  Cloudflare API returns `{\"success\": false, \"errors\": [...]}` with a 200 in
  some cases, and a caller that trusts the status records a meeting that was
  never created."
  [body]
  (let [ok? (true? (:success body))
        errors (vec (:errors body))]
    (cond-> {:kaigi.rk/ok? (and ok? (empty? errors))}
      (:result body) (assoc :kaigi.rk/data (:result body))
      (:data body)   (assoc :kaigi.rk/data (:data body))
      (seq errors)   (assoc :kaigi.rk/errors
                            (mapv (fn [e] {:kaigi.rk/code (:code e)
                                           :kaigi.rk/message (:message e)})
                                  errors)))))

(defn meeting-id
  "The RealtimeKit meeting id from a parsed create response, or nil."
  [parsed]
  (get-in parsed [:kaigi.rk/data :id]))

(defn participant-token
  "The participant's client token from a parsed add-participant response.

  Nil rather than a partial result when the call failed: a caller that sent a
  nil token to a browser would produce a join that fails inside the SDK, far
  from the request that actually went wrong."
  [parsed]
  (when (:kaigi.rk/ok? parsed)
    (get-in parsed [:kaigi.rk/data :token])))

;; ---------------------------------------------------------------------------
;; the gate
;; ---------------------------------------------------------------------------

(defn token-refusal
  "Why `participant-id` must NOT be given a RealtimeKit token, or nil.

  This is the seam between the two systems. RealtimeKit authorizes by preset
  and knows nothing about kaigi's lobby, so the admission decision has to be
  enforced at the moment a token is minted — there is no second chance, because
  a token already issued is a join already possible.

  Refusals mirror `kaigi.signal`'s vocabulary so a client sees one set of
  reasons regardless of which layer refused it."
  [mtg participant-id]
  (cond
    (nil? (m/participant-by-id mtg participant-id))
    {:kaigi.rk/reason :kaigi.signal/not-a-participant
     :kaigi.rk/message "not a participant of this meeting"}

    (not (m/admitted? mtg participant-id))
    {:kaigi.rk/reason :kaigi.signal/not-admitted
     :kaigi.rk/message (str "admission is " (pr-str (m/admission-of mtg participant-id)))}

    (m/ended? mtg)
    {:kaigi.rk/reason :kaigi.signal/meeting-ended
     :kaigi.rk/message "this meeting has ended"}

    :else nil))

(defn may-mint-token?
  [mtg participant-id]
  (nil? (token-refusal mtg participant-id)))

;; ---------------------------------------------------------------------------
;; configuration
;; ---------------------------------------------------------------------------

(defn configured?
  "True when every part needed to reach RealtimeKit is present.

  All four are required. A partial configuration is worse than none: with an
  app id but no token the transport would report itself available and every
  join would fail at the moment someone tried to speak, which is the point at
  which it is hardest to diagnose."
  [{:keys [account-id app-id api-token preset]}]
  (boolean (and (string? account-id) (seq account-id)
                (string? app-id) (seq app-id)
                (string? api-token) (seq api-token)
                (string? preset) (seq preset))))

(defn config-from-env
  "Read RealtimeKit configuration from a Worker `env`-shaped lookup.

  Takes a getter rather than the env object so this stays `.cljc` and
  testable."
  [get-env]
  {:account-id (some-> (get-env "REALTIMEKIT_ACCOUNT_ID") str)
   :app-id     (some-> (get-env "REALTIMEKIT_APP_ID") str)
   :api-token  (some-> (get-env "REALTIMEKIT_API_TOKEN") str)
   :preset     (or (some-> (get-env "REALTIMEKIT_PRESET") str) "")})
