(ns kaigi.signal
  "Signaling for a meeting: relay routing gated on admission.

  `kotoba.rt.core` already decides where an opaque `:signal` frame goes given
  a room-membership value, and this namespace does not reimplement that. What
  it adds is the meeting's own precondition — **only admitted participants
  are on the media plane** — and the distinction between the two ways a
  sender can fail to be there.

  ## Why `:not-admitted` is not `:sender-not-in-room`

  `kotoba.rt.core` knows one kind of absence. A meeting has two, and they
  need different answers in the UI:

    :kaigi.signal/not-admitted   — you are in this meeting's roster, waiting
                                   for (or refused by) the host. \"Waiting to
                                   be let in.\"
    :kaigi.signal/not-a-participant — you are not in this meeting at all.
                                   \"Wrong link.\"

  Collapsing them produces the worst version of this screen: a participant
  patiently waiting in a lobby that the host cannot see, being told the room
  does not exist.

  ## Control messages do not go through the relay

  Admitting, denying, muting and ending are decisions about the meeting, not
  payloads to forward. `classify` separates them so a host cannot be tricked
  into relaying a frame that a client cosmetically labelled as control, and
  `may?` says whether the sender is allowed to make that decision at all."
  (:require [kaigi.model :as m]
            [kotoba.rt.core :as rt]
            [kotoba.webrtc.room :as room]))

(def control-types
  "Message types that mutate the meeting rather than being forwarded."
  #{:admit :deny :remove :promote :demote
    :mute :camera-off :start-share :stop-share
    :request-recording :consent-recording :revoke-consent
    :start-recording :stop-recording :start :end})

(def moderator-only-types
  "Control types that require `:host` or `:cohost`."
  #{:admit :deny :remove :request-recording :start-recording :stop-recording})

(def host-only-types
  "Control types that require `:host` specifically."
  #{:promote :demote :end})

(defn classify
  "`:control` for a meeting decision, `:signal` for a frame to relay, or
  `:unknown`."
  [{:keys [type]}]
  (cond
    (contains? control-types type) :control
    (= :signal type)               :signal
    :else                          :unknown))

(defn- err
  [code msg]
  {:kaigi.signal/error code :kaigi.signal/message msg})

(defn may?
  "Whether `actor-id` is permitted to issue control message `type` in `mtg`.

  Self-directed media actions (`:mute`, `:camera-off`, `:start-share`,
  `:stop-share`) and consent actions are allowed for any admitted
  participant; `kaigi.model` applies the finer rule that a moderator may mute
  someone else but not unmute them."
  [mtg actor-id type]
  (cond
    (not (m/admitted? mtg actor-id))        false
    (contains? host-only-types type)        (= :host (m/role-of mtg actor-id))
    (contains? moderator-only-types type)   (m/moderator? mtg actor-id)
    (contains? control-types type)          true
    :else                                   false))

(defn rooms-of
  "The `kotoba.rt.core` room-membership value implied by `mtg`: one room,
  keyed by meeting id, whose members are the admitted participants currently
  in the media room.

  Derived on each call rather than kept alongside the meeting. Two values
  that must agree about who is in the room is a bug waiting for the moment
  they disagree; here the meeting is the only writer and this is a view of
  it."
  [mtg]
  {(:kaigi/id mtg)
   (into #{}
         (filter #(m/admitted? mtg %))
         (room/participant-ids (:kaigi/room mtg)))})

(defn route
  "Route one `:signal` frame within `mtg`.

  Returns either a vector of `{:to id :payload payload}` deliveries — the
  same shape `kotoba.rt.core/route-message` produces — or an error map.
  Broadcast (no `:to`) reaches every other admitted in-room participant;
  unicast reaches exactly the named one.

  A frame whose sender is not admitted is refused before it reaches the
  relay, which is what keeps a participant in the lobby from sending SDP to
  people who have not agreed to let them in."
  [mtg {:keys [from to] :as msg}]
  (cond
    (not (m/participant-by-id mtg from))
    (err :kaigi.signal/not-a-participant
         (str (pr-str from) " is not a participant of " (pr-str (:kaigi/id mtg))))

    (not (m/admitted? mtg from))
    (err :kaigi.signal/not-admitted
         (str (pr-str from) " is " (pr-str (m/admission-of mtg from))
              ", not admitted"))

    (and (some? to) (not (m/admitted? mtg to)))
    (err :kaigi.signal/recipient-not-admitted
         (str (pr-str to) " is not admitted"))

    (m/ended? mtg)
    (err :kaigi.signal/meeting-ended
         (str (pr-str (:kaigi/id mtg)) " has ended"))

    :else
    (let [result (rt/route-message (rooms-of mtg) (assoc msg :type :signal
                                                             :room-id (:kaigi/id mtg)))]
      (if (:error result)
        ;; rt.core's vocabulary, kept verbatim so the relay's own errors stay
        ;; distinguishable from this layer's admission errors.
        {:kaigi.signal/error (keyword "kaigi.signal.relay" (name (:error result)))
         :kaigi.signal/message (:message result)}
        result))))

(defn error?
  [result]
  (contains? result :kaigi.signal/error))

(defn apply-control
  "Apply a control message to `mtg`, returning `{:kaigi.signal/meeting …}` or
  an error map.

  Authorization is checked here, once, rather than in each `kaigi.model`
  function — the model functions are also no-ops when the actor lacks
  permission, but a silent no-op gives the client no way to tell 'refused'
  from 'applied'. This returns the refusal."
  [mtg {:keys [type from target payload]}]
  (cond
    (not (contains? control-types type))
    (err :kaigi.signal/unknown-control (str "not a control type: " (pr-str type)))

    (not (may? mtg from type))
    (err :kaigi.signal/forbidden
         (str (pr-str from) " (" (pr-str (m/role-of mtg from)) ", "
              (pr-str (m/admission-of mtg from)) ") may not " (name type)))

    :else
    {:kaigi.signal/meeting
     (case type
       :admit             (m/admit mtg from target)
       :deny              (m/deny mtg from target)
       :remove            (m/remove-participant mtg from target)
       :promote           (m/promote mtg from target)
       :demote            (m/demote mtg from target)
       :mute              (m/set-muted mtg from (or target from) (boolean payload))
       :camera-off        (m/set-camera-off mtg from (or target from) (boolean payload))
       :start-share       (m/start-share mtg from)
       :stop-share        (m/stop-share mtg from)
       :request-recording (m/request-recording mtg from)
       :consent-recording (m/grant-recording-consent mtg from)
       :revoke-consent    (m/revoke-recording-consent mtg from)
       :start-recording   (m/start-recording mtg from)
       :stop-recording    (m/stop-recording mtg from payload)
       :start             (m/start mtg)
       :end               (m/end mtg))}))
