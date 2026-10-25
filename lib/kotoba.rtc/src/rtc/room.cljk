(ns rtc.room
  "Room management: create, join, leave, peer lifecycle. A room is a
  named session containing multiple peers; signaling is routed through
  a KNP ReliableOrdered channel and media exchanged via WebRTC peer
  connections (mesh topology). Restored from kami-rtc's `room` module
  (deleted PR #82)."
  (:require [kotoba.lang.edn :as edn]
            [rtc.media :as media]
            [rtc.peer :as peer]
            [rtc.signal :as signal]
            [rtc.spatial :as spatial]))

(def topologies #{:mesh :sfu})

(defn room-config
  ([] (room-config {}))
  ([{:keys [name max-participants spatial-audio topology media-constraints data-channel]
     :or {name "" max-participants 16 spatial-audio true topology :mesh
          media-constraints (media/media-constraints) data-channel true}}]
   {:name name :max-participants max-participants :spatial-audio spatial-audio
    :topology topology :media-constraints media-constraints :data-channel data-channel}))

(defn room
  "A new room state machine."
  [id local-peer-id config]
  {:id id :config config :local-peer-id local-peer-id
   :peers {} :signal-seq 0 :spatial-mixer (spatial/spatial-mixer)})

(defn- next-seq
  "Returns `[seq room']` — the next sequence number and the room with
  its counter advanced."
  [room]
  [(:signal-seq room) (update room :signal-seq inc)])

(defn join
  "Generate a join signal for `room`. Returns `[msg room']`."
  [room display-name]
  (let [[seq room] (next-seq room)]
    [(signal/join (:local-peer-id room) (:id room) display-name seq) room]))

(defn leave
  "Generate a leave signal for `room`. Returns `[msg room']`."
  [room]
  (let [[seq room] (next-seq room)]
    [(signal/leave (:local-peer-id room) (:id room) seq) room]))

(defn process-signal
  "Process an incoming signaling `msg` against `room`. Returns `[events
  room']`."
  [room msg]
  (if (not= (:room-id msg) (:id room))
    [[] room]
    (case (:signal-type msg)
      :join
      (let [p (peer/peer (:from msg) (:payload msg))
            room (assoc-in room [:peers (:from msg)] p)]
        [[{:type :peer-joined :peer-id (:from msg) :display-name (:payload msg)}] room])

      :leave
      (let [room (update room :peers dissoc (:from msg))]
        [[{:type :peer-left :peer-id (:from msg)}] room])

      :offer
      (let [room (update-in room [:peers (:from msg)] (fn [p] (when p (assoc p :state :connecting))))]
        [[{:type :offer-received :from (:from msg) :sdp (:payload msg)}] room])

      :answer
      (let [has-peer (contains? (:peers room) (:from msg))
            room (update-in room [:peers (:from msg)] (fn [p] (when p (assoc p :state :connected))))
            events (cond-> []
                     has-peer (conj {:type :peer-state-changed :peer-id (:from msg) :state :connected})
                     true (conj {:type :answer-received :from (:from msg) :sdp (:payload msg)}))]
        [events room])

      :ice-candidate
      [[{:type :ice-candidate-received :from (:from msg) :candidate (:payload msg)}] room]

      :position
      (let [pos (try (edn/read-string (:payload msg)) (catch #?(:clj Exception :cljs js/Error) _ nil))]
        (if pos
          (let [room (update-in room [:peers (:from msg)] (fn [p] (when p (peer/set-position p pos))))]
            [[{:type :position-updated :peer-id (:from msg) :position pos}] room])
          [[] room]))

      :data
      [[{:type :data-received :from (:from msg) :data (:payload msg)}] room])))

(defn create-offer
  "Returns `[msg room']`."
  [room to sdp]
  (let [[seq room] (next-seq room)]
    [(signal/offer (:local-peer-id room) to (:id room) sdp seq) room]))

(defn create-answer
  "Returns `[msg room']`."
  [room to sdp]
  (let [[seq room] (next-seq room)]
    [(signal/answer (:local-peer-id room) to (:id room) sdp seq) room]))

(defn create-ice-candidate
  "Returns `[msg room']`."
  [room to candidate]
  (let [[seq room] (next-seq room)]
    [(signal/ice-candidate (:local-peer-id room) to (:id room) candidate seq) room]))

(defn update-position
  "Broadcast local position for spatial audio. Returns `[msg room']`."
  [room pos]
  (let [[seq room] (next-seq room)]
    [(signal/position (:local-peer-id room) (:id room) pos seq) room]))

(defn send-data
  "Returns `[msg room']`."
  [room data-str]
  (let [[seq room] (next-seq room)]
    [(signal/data (:local-peer-id room) (:id room) data-str seq) room]))

(defn get-peer [room id] (get (:peers room) id))

(defn all-peers [room] (vals (:peers room)))

(defn peer-count [room] (count (:peers room)))

(defn connected-peer-ids
  [room]
  (vec (map :id (filter #(= (:state %) :connected) (vals (:peers room))))))

(defn spatialize
  "Run spatial audio spatialization for all peers in `room`. Returns
  `[[peer-id left right pan] ...]`."
  [room]
  (if-not (:spatial-audio (:config room))
    []
    (vec (for [[id r] (spatial/spatialize-peers (:spatial-mixer room) (vals (:peers room)))]
           [id (:left r) (:right r) (:pan r)]))))

(defn update-spatial-mixer
  "Apply `f` to the room's spatial mixer. `f` takes and returns a
  mixer."
  [room f]
  (update room :spatial-mixer f))

(defn summary
  "Room summary as an EDN map (for a /_app/meta or health endpoint)."
  [room]
  {:room-id (:id room) :name (:name (:config room)) :peer-count (peer-count room)
   :topology (:topology (:config room)) :spatial-audio (:spatial-audio (:config room))
   :local-peer (:local-peer-id room)})
