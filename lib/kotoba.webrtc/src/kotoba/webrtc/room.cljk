(ns kotoba.webrtc.room
  "Multi-party WebRTC room membership — pure data contracts.

  Models an SFU-style multi-party call as an EDN room record: participants,
  their published tracks, and track-subscription requests between
  participants. No network, no media routing — the host runtime's SFU (or
  mesh) is the one actually forwarding media; this library only tracks who
  is in the room and who is subscribed to what.

  Portable (.cljc) across JVM / ClojureScript / SCI / GraalVM.")

(defn create-room
  "Construct an empty room record for room-id."
  [room-id]
  {:webrtc.room/room-id      room-id
   :webrtc.room/participants {}})

(defn join
  "Add participant-id to room with an empty track set. No-op when already
  present."
  [room participant-id]
  (update room :webrtc.room/participants
          (fn [ps] (if (contains? ps participant-id)
                     ps
                     (assoc ps participant-id {:webrtc.room/tracks #{}
                                                :webrtc.room/subscriptions #{}})))))

(defn leave
  "Remove participant-id from room, and drop it from every other
  participant's subscriptions."
  [room participant-id]
  (-> room
      (update :webrtc.room/participants dissoc participant-id)
      (update :webrtc.room/participants
              (fn [ps] (into {} (map (fn [[pid p]]
                                       [pid (update p :webrtc.room/subscriptions
                                                    disj participant-id)]))
                             ps)))))

(defn publish-track
  "Add track-id to participant-id's published track set. No-op when the
  participant is not in the room."
  [room participant-id track-id]
  (if (contains? (:webrtc.room/participants room) participant-id)
    (update-in room [:webrtc.room/participants participant-id :webrtc.room/tracks]
               conj track-id)
    room))

(defn unpublish-track
  "Remove track-id from participant-id's published track set."
  [room participant-id track-id]
  (if (contains? (:webrtc.room/participants room) participant-id)
    (update-in room [:webrtc.room/participants participant-id :webrtc.room/tracks]
               disj track-id)
    room))

(defn subscribe
  "Record that subscriber-id wants target-id's tracks. No-op when either
  participant is not in the room, or subscriber-id == target-id."
  [room subscriber-id target-id]
  (let [ps (:webrtc.room/participants room)]
    (if (and (not= subscriber-id target-id)
             (contains? ps subscriber-id)
             (contains? ps target-id))
      (update-in room [:webrtc.room/participants subscriber-id :webrtc.room/subscriptions]
                 conj target-id)
      room)))

(defn unsubscribe
  "Remove target-id from subscriber-id's subscriptions."
  [room subscriber-id target-id]
  (if (contains? (:webrtc.room/participants room) subscriber-id)
    (update-in room [:webrtc.room/participants subscriber-id :webrtc.room/subscriptions]
               disj target-id)
    room))

(defn participant-ids
  "Return the set of participant ids currently in room."
  [room]
  (set (keys (:webrtc.room/participants room))))

(defn tracks-of
  "Return the set of track ids published by participant-id, or nil when not
  in the room."
  [room participant-id]
  (get-in room [:webrtc.room/participants participant-id :webrtc.room/tracks]))

(defn subscribers-of
  "Return the set of participant ids currently subscribed to target-id's
  tracks."
  [room target-id]
  (->> (:webrtc.room/participants room)
       (filter (fn [[_ p]] (contains? (:webrtc.room/subscriptions p) target-id)))
       (map key)
       (set)))
