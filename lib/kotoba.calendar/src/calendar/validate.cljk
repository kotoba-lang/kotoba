(ns calendar.validate
  (:require [calendar.kotoba-oracle :as oracle]))

(defn problem [severity code id msg]
  {:calendar/severity severity :calendar/code code :calendar/id id :calendar/msg msg})

(def ^:private placeholder-id
  "`:calendar/event` carries an `:id` that `event-valid?` never reads, and the
  guest requires the field to be present and a `:keyword`. This library's ids
  are strings, so passing the real one would mean converting data for a field
  nobody looks at."
  :e)

(defn occupies-time?
  "Does `ev` occupy any time at all — is its start strictly before its end?

  The rule is `validate.kotoba/event-valid?`, executed from
  `resources/calendar/oracle/validate.kir.edn`; this function does not compute
  it. What is left here is what is not a decision: reading the two keys and
  ranking the two instants into the `:i64` the guest speaks.

  Callers must have established that both instants are present. Absence is not
  a shorter event, it is an event that has not said when it happens, and the
  guest cannot express it — `:i64` has no `nil`. `event-problems` reports that
  separately and it is deliberately not folded in here, because the two
  produce different problems.

  This is the same rule `model.kotoba/overlaps?` applies to each of its two
  events before comparing them. Until 7b98dbc they were two rules: the
  `.kotoba` required an event to occupy time and `model.cljc/overlaps?` did
  not, so an event this namespace called `:event/non-positive-duration` was
  still reported as a conflict. They agree now because there is one of them."
  [ev]
  (let [[start* end*] (oracle/instant-ranks [(:calendar/start ev) (:calendar/end ev)])]
    (oracle/call :validate 'event-valid?
                 [(oracle/record oracle/event-type [placeholder-id start* end*])])))

(defn event-problems [ev]
  (let [start (:calendar/start ev)
        end (:calendar/end ev)]
    (cond-> []
      (or (nil? start) (nil? end))
      (conj (problem :error :event/missing-time (:calendar/id ev) "event requires start and end"))

      (and start end (not (occupies-time? ev)))
      (conj (problem :error :event/non-positive-duration (:calendar/id ev) "event start must be before end")))))

(defn problems [cal]
  (vec (mapcat event-problems (vals (:calendar/events cal)))))

(defn valid?
  "Is every event in `cal` free of errors?

  Not `validate.kotoba/valid?`, which answers a narrower question: that export
  holds the events map inside the guest and reports `false` for any calendar
  over eight events by construction, while this one reports on every event of
  an open-schema calendar. See `kotoba-oracle/host-answered`."
  [cal]
  (not-any? #(= :error (:calendar/severity %)) (problems cal)))
