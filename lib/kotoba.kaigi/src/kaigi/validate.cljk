(ns kaigi.validate
  "Structural defects in a `kaigi.model` meeting value.

  `problems` returns a vector of `{:kaigi/severity :kaigi/code ...}` maps and
  `valid?` is false on any `:error`. The same shape `kaisha.validate` uses,
  for the same reason: a host that persists meetings wants one call it can
  put in front of every write, and a UI wants something it can show.

  The checks here are the invariants `kaigi.model`'s functions maintain. They
  exist because a meeting value can also arrive from storage, from another
  node, or from a caller that built it by hand — and a value that reaches
  `assoc-in` directly bypasses every guard in the model namespace."
  (:require [kaigi.model :as m]
            [kotoba.webrtc.room :as room]))

(defn- problem
  ([severity code msg] {:kaigi/severity severity :kaigi/code code :kaigi/message msg})
  ([severity code msg extra] (merge (problem severity code msg) extra)))

(defn problems
  "Return every structural defect in meeting `mtg`.

  Errors (the value is not usable):
    :meeting/no-host              — `:kaigi/host` names nobody in `:kaigi/participants`
    :meeting/host-not-admitted    — the host is not `:admitted`
    :meeting/host-role-wrong      — the host's role is not `:host`
    :meeting/unknown-state        — `:kaigi/state` is not one of `model/states`
    :meeting/unknown-lobby        — `:kaigi/lobby` is not a known policy
    :participant/unknown-role     — a participant's role is not in `model/roles`
    :participant/unknown-admission— a participant's admission is not known
    :participant/blank-id         — a participant is keyed by \"\" or a non-string
    :participant/key-id-mismatch  — the map key and the record's own id disagree
    :room/participant-not-admitted— someone is in the media room without being admitted
    :room/id-mismatch             — the embedded room's id is not the meeting's id
    :share/multiple-sharers       — more than one participant has `:sharing?`
    :recording/without-consent    — recording is `:on` without unanimous consent
    :recording/consent-not-admitted— a consent is held by a non-admitted id

  Warnings (usable, but a symptom):
    :meeting/ended-with-room-members — an ended meeting still lists room members
    :share/sharer-not-in-room        — the sharer is not in the media room
    :recording/asset-ref-while-on    — an asset ref is set while still recording"
  [mtg]
  (let [ps        (:kaigi/participants mtg)
        host-id   (:kaigi/host mtg)
        host      (get ps host-id)
        rm        (:kaigi/room mtg)
        room-ids  (room/participant-ids rm)
        admitted  (m/admitted-ids mtg)
        consents  (get-in mtg [:kaigi/recording :kaigi.recording/consents])
        sharers   (->> ps (filter (fn [[_ p]] (:kaigi.participant/sharing? p))) (mapv key))]
    (into
     []
     (concat
      (when-not host
        [(problem :error :meeting/no-host
                  (str "host " (pr-str host-id) " is not a participant")
                  {:kaigi/host host-id})])
      (when (and host (not= :admitted (:kaigi.participant/admission host)))
        [(problem :error :meeting/host-not-admitted
                  (str "host " (pr-str host-id) " is "
                       (pr-str (:kaigi.participant/admission host)) ", not :admitted"))])
      (when (and host (not= :host (:kaigi.participant/role host)))
        [(problem :error :meeting/host-role-wrong
                  (str "host " (pr-str host-id) " carries role "
                       (pr-str (:kaigi.participant/role host))))])
      (when-not (contains? m/states (:kaigi/state mtg))
        [(problem :error :meeting/unknown-state
                  (str "unknown state " (pr-str (:kaigi/state mtg))))])
      (when-not (contains? m/lobby-policies (:kaigi/lobby mtg))
        [(problem :error :meeting/unknown-lobby
                  (str "unknown lobby policy " (pr-str (:kaigi/lobby mtg))))])

      ;; Added after an end-to-end run found one: a host-less room is built
      ;; with a blank host id, which yields a participant keyed by the empty
      ;; string, and nothing here noticed the placeholder surviving into the
      ;; roster. A blank id is never a real participant.
      (for [[id _] ps
            :when (or (not (string? id)) (empty? id))]
        (problem :error :participant/blank-id
                 (str "participant key " (pr-str id) " is not a usable id")
                 {:kaigi.participant/id id}))
      (for [[id p] ps
            :when (and (not= id (:kaigi.participant/id p))
                       (string? id) (seq id))]
        (problem :error :participant/key-id-mismatch
                 (str "participant is keyed " (pr-str id) " but carries id "
                      (pr-str (:kaigi.participant/id p)))
                 {:kaigi.participant/id id}))

      (for [[id p] ps
            :when (not (contains? m/roles (:kaigi.participant/role p)))]
        (problem :error :participant/unknown-role
                 (str (pr-str id) " carries unknown role "
                      (pr-str (:kaigi.participant/role p)))
                 {:kaigi.participant/id id}))
      (for [[id p] ps
            :when (not (contains? m/admissions (:kaigi.participant/admission p)))]
        (problem :error :participant/unknown-admission
                 (str (pr-str id) " carries unknown admission "
                      (pr-str (:kaigi.participant/admission p)))
                 {:kaigi.participant/id id}))

      (for [id room-ids
            :when (not (contains? admitted id))]
        (problem :error :room/participant-not-admitted
                 (str (pr-str id) " is in the media room but not admitted")
                 {:kaigi.participant/id id}))
      (when (not= (:webrtc.room/room-id rm) (:kaigi/id mtg))
        [(problem :error :room/id-mismatch
                  (str "room id " (pr-str (:webrtc.room/room-id rm))
                       " does not match meeting id " (pr-str (:kaigi/id mtg))))])

      (when (> (count sharers) 1)
        [(problem :error :share/multiple-sharers
                  (str (count sharers) " participants are sharing at once: "
                       (pr-str (vec (sort-by str sharers))))
                  {:kaigi/sharers (vec (sort-by str sharers))})])

      (when (and (m/recording-on? mtg) (not (m/recording-allowed? mtg)))
        [(problem :error :recording/without-consent
                  (str "recording is on but these admitted participants have not consented: "
                       (pr-str (vec (sort-by str (m/missing-recording-consents mtg)))))
                  {:kaigi/missing (vec (sort-by str (m/missing-recording-consents mtg)))})])
      (for [id consents
            :when (not (contains? admitted id))]
        (problem :error :recording/consent-not-admitted
                 (str "consent held by " (pr-str id) " who is not admitted")
                 {:kaigi.participant/id id}))

      ;; warnings
      (when (and (m/ended? mtg) (seq room-ids))
        [(problem :warning :meeting/ended-with-room-members
                  (str "meeting is ended but the room still lists "
                       (count room-ids) " member(s)"))])
      (for [id sharers
            :when (not (contains? room-ids id))]
        (problem :warning :share/sharer-not-in-room
                 (str (pr-str id) " is sharing but is not in the media room")
                 {:kaigi.participant/id id}))
      (when (and (m/recording-on? mtg)
                 (get-in mtg [:kaigi/recording :kaigi.recording/asset-ref]))
        [(problem :warning :recording/asset-ref-while-on
                  "an asset ref is attached while recording is still on")])))))

(defn errors
  "Only the `:error` problems."
  [mtg]
  (filterv #(= :error (:kaigi/severity %)) (problems mtg)))

(defn valid?
  "False when `mtg` has any `:error` problem."
  [mtg]
  (empty? (errors mtg)))
