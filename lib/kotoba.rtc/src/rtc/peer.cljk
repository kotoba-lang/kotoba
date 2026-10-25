(ns rtc.peer
  "Peer connection state machine: connecting -> connected ->
  disconnected. Each peer has media tracks and a spatial position.
  Restored from kami-rtc's `peer` module (deleted PR #82)."
  (:require [rtc.media :as media]))

(def peer-states #{:connecting :connected :disconnected})

(defn peer
  "A new peer in `:connecting` state."
  [id display-name]
  {:id id :display-name display-name :state :connecting
   :position [0.0 0.0 0.0] :tracks [] :spatial-audio true})

(defn position-vec3 [p] (:position p))

(defn set-position [p pos] (assoc p :position pos))

(defn add-track
  [p id kind]
  (update p :tracks conj {:id id :kind kind :state :active}))

(defn remove-track
  "Remove the track with `id` from `p`. Returns `[p' removed-track-or-nil]`."
  [p id]
  (let [removed (some #(when (= (:id %) id) %) (:tracks p))]
    [(update p :tracks (fn [ts] (vec (remove #(= (:id %) id) ts)))) removed]))

(defn set-track-state
  [p id state]
  (update p :tracks (fn [ts] (mapv (fn [t] (if (= (:id t) id) (assoc t :state state) t)) ts))))

(defn has-audio? [p] (boolean (some #(and (= (:kind %) :audio) (= (:state %) :active)) (:tracks p))))
(defn has-video? [p] (boolean (some #(and (= (:kind %) :video) (= (:state %) :active)) (:tracks p))))
