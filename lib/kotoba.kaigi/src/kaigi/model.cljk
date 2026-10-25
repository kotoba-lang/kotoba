(ns kaigi.model
  "会議 — the meeting layer above a WebRTC room. Pure EDN data + pure functions.

  This namespace owns the concepts a *meeting* has and a *room* does not:
  who is allowed in (admission), who may act on whom (roles), what the
  participants' media state is, and whether recording is permitted. The
  transport-level facts — which tracks exist and who subscribes to whom —
  stay in `kotoba.webrtc.room`, which this namespace embeds under
  `:kaigi/room` rather than reimplementing.

  ## Why admission is a first-class state and not a boolean

  A participant is not `in` or `out`; they move through
  `:requested -> :admitted | :denied` and possibly on to `:removed`. Keeping
  the whole path lets the host answer two different questions that a boolean
  collapses: \"may this person send signaling traffic?\" (only `:admitted`)
  and \"is there someone waiting for the host?\" (any `:requested`). A
  removed participant is retained with `:removed` rather than dissoc'd so a
  re-join attempt is distinguishable from a first knock — a host who ejected
  someone should not silently re-admit them because the record vanished.

  ## Recording consent is unanimous and explicit

  `recording-allowed?` is true only when EVERY admitted participant has an
  explicit consent record. Silence is not consent, and a majority is not
  consent. This is the same ground rule `kotoba-lang/gijiroku` charters as
  G3, and it is enforced here rather than left to the host because the host
  is exactly the layer under pressure to skip it.

  Portable `.cljc`: no I/O, no clock, no randomness. Timestamps and ids are
  supplied by the caller so the same input always produces the same value."
  (:require [kotoba.webrtc.room :as room]))

;; ---------------------------------------------------------------------------
;; vocabulary
;; ---------------------------------------------------------------------------

(def states
  "Lifecycle states of a meeting."
  #{:scheduled :live :ended})

(def roles
  "Participant roles. `:host` may admit/deny/remove and end the meeting;
  `:cohost` may admit/deny/remove but not end it; `:participant` may do
  neither."
  #{:host :cohost :participant})

(def admissions
  "Admission states. See the namespace docstring for why `:removed` is kept
  rather than deleted."
  #{:requested :admitted :denied :removed})

(def lobby-policies
  "`:open` admits every knock automatically; `:approval-required` holds each
  knock at `:requested` until a host or cohost acts on it."
  #{:open :approval-required})

(def moderator-roles
  "Roles permitted to admit, deny and remove."
  #{:host :cohost})

;; ---------------------------------------------------------------------------
;; constructors
;; ---------------------------------------------------------------------------

(defn participant
  "Construct a participant record. `opts` may carry `:did` (CACAO
  `did:key`), `:name`, and `:role` (defaults to `:participant`).

  A new participant starts at `:requested` regardless of the meeting's lobby
  policy — `request-admission` is what consults the policy. Constructing a
  participant is not joining."
  [id & [{:keys [did name role]}]]
  {:kaigi.participant/id          id
   :kaigi.participant/did         did
   :kaigi.participant/name        name
   :kaigi.participant/role        (if (contains? roles role) role :participant)
   :kaigi.participant/admission   :requested
   :kaigi.participant/muted?      false
   :kaigi.participant/camera-off? false
   :kaigi.participant/sharing?    false})

(defn meeting
  "Construct a meeting. `opts` may carry `:title`, `:lobby` (defaults to
  `:approval-required`), `:scheduled-at` and `:created-at` (ISO-8601
  strings supplied by the caller), and `:channel` — the
  `kotoba-lang/kaisha` channel id this meeting belongs to, so a meeting and
  the chat it was called from can be joined without a second index.

  The host is added directly at `:admitted`: a host who had to wait for
  approval could never be approved, since only a moderator can approve."
  [id host-id & [{:keys [title lobby scheduled-at created-at channel]}]]
  (let [host (-> (participant host-id {:role :host})
                 (assoc :kaigi.participant/admission :admitted))]
    {:kaigi/id           id
     :kaigi/title        title
     :kaigi/host         host-id
     :kaigi/channel      channel
     :kaigi/state        :scheduled
     :kaigi/lobby        (if (contains? lobby-policies lobby) lobby :approval-required)
     :kaigi/scheduled-at scheduled-at
     :kaigi/created-at   created-at
     :kaigi/participants {host-id host}
     :kaigi/room         (room/create-room id)
     :kaigi/recording    {:kaigi.recording/state     :off
                          :kaigi.recording/consents  #{}
                          :kaigi.recording/asset-ref nil}}))

;; ---------------------------------------------------------------------------
;; reading
;; ---------------------------------------------------------------------------

(defn participant-by-id
  [m id]
  (get-in m [:kaigi/participants id]))

(defn role-of
  [m id]
  (:kaigi.participant/role (participant-by-id m id)))

(defn moderator?
  "True when `id` is a host or cohost of `m`."
  [m id]
  (contains? moderator-roles (role-of m id)))

(defn admission-of
  [m id]
  (:kaigi.participant/admission (participant-by-id m id)))

(defn admitted?
  "True when `id` is currently admitted. This is the gate the signaling
  layer consults; see `kaigi.signal`."
  [m id]
  (= :admitted (admission-of m id)))

(defn ids-with-admission
  "The set of participant ids whose admission state is `state`."
  [m state]
  (->> (:kaigi/participants m)
       (filter (fn [[_ p]] (= state (:kaigi.participant/admission p))))
       (map key)
       set))

(defn admitted-ids
  "The set of currently admitted participant ids."
  [m]
  (ids-with-admission m :admitted))

(defn waiting-ids
  "The set of participant ids knocking and not yet acted upon — what a host
  sees as the lobby queue."
  [m]
  (ids-with-admission m :requested))

(defn sharing-id
  "The participant id currently sharing their screen, or nil. At most one by
  construction; see `start-share`."
  [m]
  (->> (:kaigi/participants m)
       (filter (fn [[_ p]] (:kaigi.participant/sharing? p)))
       (map key)
       first))

(defn live?
  [m]
  (= :live (:kaigi/state m)))

(defn ended?
  [m]
  (= :ended (:kaigi/state m)))

;; ---------------------------------------------------------------------------
;; lifecycle
;; ---------------------------------------------------------------------------

(defn start
  "Move a `:scheduled` meeting to `:live`. No-op otherwise, so a duplicate
  start from a retried request cannot resurrect an ended meeting."
  [m]
  (if (= :scheduled (:kaigi/state m)) (assoc m :kaigi/state :live) m))

(defn end
  "End the meeting: state `:ended`, every participant removed from the room,
  screen share cleared, and recording stopped.

  Admission records are left as they are — after the fact, 'who was in this
  meeting' is a question the record still has to answer."
  [m]
  (-> m
      (assoc :kaigi/state :ended)
      (assoc :kaigi/room (room/create-room (:kaigi/id m)))
      (update :kaigi/participants
              (fn [ps] (into {} (map (fn [[id p]] [id (assoc p :kaigi.participant/sharing? false)])) ps)))
      (assoc-in [:kaigi/recording :kaigi.recording/state] :off)))

;; ---------------------------------------------------------------------------
;; admission
;; ---------------------------------------------------------------------------

(defn request-admission
  "Record `p`'s knock. Under an `:open` lobby the knock is admitted
  immediately; under `:approval-required` it stays `:requested`.

  A knock on an ended meeting is refused (the participant lands at
  `:denied`) rather than left pending forever. A participant previously
  `:removed` re-enters at `:requested` even under an `:open` lobby — an
  ejection has to survive a reconnect, otherwise ejecting someone
  accomplishes nothing."
  [m p]
  (let [id      (:kaigi.participant/id p)
        prior   (admission-of m id)
        state   (cond
                  (ended? m)            :denied
                  (= :removed prior)    :requested
                  (= :admitted prior)   :admitted
                  (= :open (:kaigi/lobby m)) :admitted
                  :else                 :requested)
        ;; keep the established role (and the host's) rather than letting a
        ;; re-knock demote or promote anyone.
        role    (or (role-of m id) (:kaigi.participant/role p))]
    (assoc-in m [:kaigi/participants id]
              (assoc p :kaigi.participant/admission state
                       :kaigi.participant/role role))))

(defn admit
  "Admit `target-id`, if `actor-id` is a moderator and the target is not
  already `:removed`. Returns `m` unchanged when not permitted, so callers
  can treat this as idempotent."
  [m actor-id target-id]
  (if (and (moderator? m actor-id)
           (participant-by-id m target-id)
           (not= :removed (admission-of m target-id)))
    (assoc-in m [:kaigi/participants target-id :kaigi.participant/admission] :admitted)
    m))

(defn deny
  "Deny `target-id`'s knock. Moderators only. Denying the host is refused —
  a meeting whose host is locked out cannot be moderated at all."
  [m actor-id target-id]
  (if (and (moderator? m actor-id)
           (participant-by-id m target-id)
           (not= target-id (:kaigi/host m)))
    (assoc-in m [:kaigi/participants target-id :kaigi.participant/admission] :denied)
    m))

(defn remove-participant
  "Eject `target-id`: admission `:removed`, dropped from the room, share
  cleared, and their recording consent withdrawn — consent from someone no
  longer present must not keep a recording legal.

  Moderators only, and never the host."
  [m actor-id target-id]
  (if (and (moderator? m actor-id)
           (participant-by-id m target-id)
           (not= target-id (:kaigi/host m)))
    (-> m
        (assoc-in [:kaigi/participants target-id :kaigi.participant/admission] :removed)
        (assoc-in [:kaigi/participants target-id :kaigi.participant/sharing?] false)
        (update :kaigi/room room/leave target-id)
        (update-in [:kaigi/recording :kaigi.recording/consents] disj target-id))
    m))

(defn promote
  "Make `target-id` a cohost. Host only — a cohost cannot mint more
  cohosts, which keeps the moderator set traceable to one decision."
  [m actor-id target-id]
  (if (and (= :host (role-of m actor-id))
           (participant-by-id m target-id)
           (not= target-id (:kaigi/host m)))
    (assoc-in m [:kaigi/participants target-id :kaigi.participant/role] :cohost)
    m))

(defn demote
  "Return `target-id` to `:participant`. Host only, and never the host."
  [m actor-id target-id]
  (if (and (= :host (role-of m actor-id))
           (participant-by-id m target-id)
           (not= target-id (:kaigi/host m)))
    (assoc-in m [:kaigi/participants target-id :kaigi.participant/role] :participant)
    m))

;; ---------------------------------------------------------------------------
;; presence in the room
;; ---------------------------------------------------------------------------

(defn join
  "Put an admitted participant into the media room. Refused for anyone not
  `:admitted`, and for an ended meeting — this is the single choke point
  that keeps un-approved participants out of the media plane."
  [m id]
  (if (and (admitted? m id) (not (ended? m)))
    (update m :kaigi/room room/join id)
    m))

(defn leave
  "Take `id` out of the media room without changing their admission — a
  dropped connection is not an ejection, and they may come back."
  [m id]
  (-> m
      (update :kaigi/room room/leave id)
      (assoc-in [:kaigi/participants id :kaigi.participant/sharing?] false)))

(defn in-room?
  [m id]
  (contains? (room/participant-ids (:kaigi/room m)) id))

(defn publish-track
  "Register a published track for `id`. Admitted participants who are in the
  room only."
  [m id track-name]
  (if (and (admitted? m id) (in-room? m id))
    (update m :kaigi/room room/publish-track id track-name)
    m))

(defn unpublish-track
  [m id track-name]
  (update m :kaigi/room room/unpublish-track id track-name))

(defn tracks-of
  [m id]
  (room/tracks-of (:kaigi/room m) id))

;; ---------------------------------------------------------------------------
;; media state
;; ---------------------------------------------------------------------------

(defn set-muted
  "Set `target-id`'s mute flag. A participant may mute/unmute themselves; a
  moderator may mute anyone but may NOT unmute someone else — unmuting a
  remote microphone is opening a live mic in someone's room, and that has to
  be their own action."
  [m actor-id target-id muted?]
  (let [self? (= actor-id target-id)
        mod?  (moderator? m actor-id)]
    (if (and (participant-by-id m target-id)
             (or self? (and mod? muted?)))
      (assoc-in m [:kaigi/participants target-id :kaigi.participant/muted?] (boolean muted?))
      m)))

(defn set-camera-off
  "Set `target-id`'s camera flag. Same asymmetry as `set-muted`: a moderator
  can turn a camera off, only its owner can turn it back on."
  [m actor-id target-id off?]
  (let [self? (= actor-id target-id)
        mod?  (moderator? m actor-id)]
    (if (and (participant-by-id m target-id)
             (or self? (and mod? off?)))
      (assoc-in m [:kaigi/participants target-id :kaigi.participant/camera-off?] (boolean off?))
      m)))

(defn start-share
  "Give `id` the screen share, taking it from whoever held it.

  Exclusive by construction rather than by convention: the previous sharer's
  flag is cleared in the same update, so no state exists in which two
  participants are sharing and the grid has to guess which to show."
  [m id]
  (if (and (admitted? m id) (in-room? m id) (not (ended? m)))
    (update m :kaigi/participants
            (fn [ps] (into {} (map (fn [[pid p]]
                                     [pid (assoc p :kaigi.participant/sharing? (= pid id))]))
                           ps)))
    m))

(defn stop-share
  [m id]
  (assoc-in m [:kaigi/participants id :kaigi.participant/sharing?] false))

;; ---------------------------------------------------------------------------
;; recording consent
;; ---------------------------------------------------------------------------

(defn request-recording
  "Move recording to `:requested`. Moderators only. This does not start
  anything; it only makes the ask visible so participants can answer it."
  [m actor-id]
  (if (and (moderator? m actor-id) (not (ended? m)))
    (assoc-in m [:kaigi/recording :kaigi.recording/state] :requested)
    m))

(defn grant-recording-consent
  "Record `id`'s explicit consent. Only an admitted participant's consent
  counts."
  [m id]
  (if (admitted? m id)
    (update-in m [:kaigi/recording :kaigi.recording/consents] conj id)
    m))

(defn revoke-recording-consent
  "Withdraw `id`'s consent, and stop an in-progress recording if that
  withdrawal breaks unanimity. Consent is revocable at any time; a recording
  that continues after someone objects is the failure this guards."
  [m id]
  (let [m' (update-in m [:kaigi/recording :kaigi.recording/consents] disj id)]
    (if (and (= :on (get-in m' [:kaigi/recording :kaigi.recording/state]))
             (not (every? (get-in m' [:kaigi/recording :kaigi.recording/consents])
                          (admitted-ids m'))))
      (assoc-in m' [:kaigi/recording :kaigi.recording/state] :off)
      m')))

(defn recording-allowed?
  "True only when every admitted participant has explicitly consented.

  An empty meeting is not consent either: with no admitted participants this
  returns false, so a recording cannot be armed before anyone arrives and
  then inherit their attendance as agreement."
  [m]
  (let [admitted (admitted-ids m)
        consents (get-in m [:kaigi/recording :kaigi.recording/consents])]
    (and (seq admitted) (every? consents admitted))))

(defn missing-recording-consents
  "The admitted participants who have not consented — what the UI shows
  instead of a disabled button with no explanation."
  [m]
  (let [consents (get-in m [:kaigi/recording :kaigi.recording/consents])]
    (into #{} (remove consents) (admitted-ids m))))

(defn start-recording
  "Arm recording. Moderators only, and only when consent is unanimous.
  Refused otherwise — this is the enforcement point for the rule stated in
  the namespace docstring."
  [m actor-id]
  (if (and (moderator? m actor-id) (live? m) (recording-allowed? m))
    (assoc-in m [:kaigi/recording :kaigi.recording/state] :on)
    m))

(defn stop-recording
  "Stop recording and attach `asset-ref` — an object-storage key or platform
  URL. Only the reference is stored: raw audio and video never enter this
  value, matching `gijiroku`'s G4."
  [m actor-id asset-ref]
  (if (moderator? m actor-id)
    (-> m
        (assoc-in [:kaigi/recording :kaigi.recording/state] :off)
        (assoc-in [:kaigi/recording :kaigi.recording/asset-ref] asset-ref))
    m))

(defn recording-on?
  [m]
  (= :on (get-in m [:kaigi/recording :kaigi.recording/state])))
