(ns importer.coverage
  "What the corpus can and cannot answer for, attached to every answer it
  gives.

  This is the namespace the whole design is for.

  A bot asks `did the customer reply?` and gets back an empty list. That empty
  list has two readings -- `there is no reply` and `we never imported this
  mailbox` -- and the bot will act on them identically. One of those actions is
  wrong, the mistake is invisible in every log, and no amount of care in the
  bot's prompt can recover a distinction the data never carried.

  So a result is not a list. A result is a list plus the coverage that produced
  it, and `answer` is the only constructor. Absence of rows is only evidence of
  absence where coverage says the stream was read.

  It is the same rule `concept-lookup` follows when it prints how many
  repositories are unindexed, and the same one ADR-2608136000 generalised: an
  index that cannot say what it missed reports `not found` for both."
  (:require [importer.cursor :as cur]))

(def states
  "  :covered        read, and the last run reached the provider and finished
  :backfilling    being read now; older records may not be in yet
  :stale          the last run did not sync, or the cursor is known to have lapsed
  :never-imported no cursor has ever advanced for this stream

  **There is deliberately no `:unknown` here, and there was, for a day.**

  `state` used to answer `:unknown` whenever `cursor/expired?` could not
  decide -- which is whenever the stream declares `:unknown` retention. That
  reads as caution and is the opposite. Microsoft Graph does not publish a
  deltaLink expiry, and neither does Drive or Calendar, so **every stream on
  those providers would have been permanently `:unknown`**, every answer
  permanently incomplete, and a reader who is told `incomplete` about
  everything learns to stop reading it. A caveat that fires always carries no
  information.

  The two questions had been collapsed. `state` answers *can I trust this
  empty result*, which is settled by what the last run actually did.
  *Will the next run still work* is a different question, and it is carried
  separately as `:importer.coverage/expiry-unknown?` on the row -- present
  when the provider publishes no window, absent when it does."
  #{:covered :backfilling :stale :never-imported})

(def coverage {})

(defn record
  "Fold one cursor and the outcome of its last run into the coverage map."
  [cov c outcome now]
  (assoc cov (cur/stream-key c)
         {:importer.coverage/cursor c
          :importer.coverage/outcome outcome
          :importer.coverage/at now}))

(defn state
  "The three-plus-two valued verdict for one stream key."
  [cov stream-key now]
  (if-let [{:keys [importer.coverage/cursor importer.coverage/outcome]} (get cov stream-key)]
    (cond
      (not (cur/started? cursor)) :never-imported
      ;; What the last run did comes first: it is measured. A window we cannot
      ;; compute must not overrule a success we watched happen.
      (not= :synced outcome) :stale
      (= true (cur/expired? cursor now)) :stale
      (= :backfill (cur/phase cursor)) :backfilling
      :else :covered)
    :never-imported))

(defn through
  "The watermark this stream is read through, or nil."
  [cov stream-key]
  (some-> (get cov stream-key) :importer.coverage/cursor cur/watermark))

(defn expiry-unknown?
  "The provider publishes no validity window for this cursor, so nothing here
  can say whether the next run will still be able to resume.

  Separate from `state` on purpose -- see the note there. A caller that wants
  to resync preemptively reads this; a caller deciding whether an empty result
  means `no` reads `state`."
  [cov stream-key now]
  (boolean
   (when-let [c (:importer.coverage/cursor (get cov stream-key))]
     (nil? (cur/expired? c now)))))

(defn answer
  "The only way to build a corpus result.

  Rows alone are not a result; there is deliberately no arity that takes them.
  `stream-keys` are the streams the query drew from -- naming them is what lets
  a caller see that its question ranged over a mailbox nobody has imported."
  [rows cov stream-keys now]
  (let [per (into {}
                  (map (fn [k]
                         [k (cond-> {:importer.coverage/state (state cov k now)
                                     :importer.coverage/through (through cov k)}
                              (expiry-unknown? cov k now)
                              (assoc :importer.coverage/expiry-unknown? true))]))
                  stream-keys)]
    {:importer/rows (vec rows)
     :importer/coverage per
     :importer/complete? (every? #(= :covered (:importer.coverage/state %)) (vals per))
     :importer/at now}))

(defn complete? [a] (boolean (:importer/complete? a)))

(defn gaps
  "The stream keys whose state is anything but :covered, with their state. What
  a caller prints next to an empty list so a reader is not left to assume."
  [a]
  (->> (:importer/coverage a)
       (remove #(= :covered (:importer.coverage/state (val %))))
       (map (fn [[k v]] [k (:importer.coverage/state v)]))
       (sort-by (comp str first))
       vec))

(defn empty-and-incomplete?
  "No rows, and at least one stream was not fully read.

  The single condition under which an answer must not be read as `no`. Worth a
  predicate rather than a comment, because it is the one a caller forgets."
  [a]
  (and (empty? (:importer/rows a)) (not (complete? a))))
