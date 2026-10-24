(ns ical.validate
  "Structural validation of an iCalendar-as-EDN model. Pure: returns a vector of
  problem maps `{:ical/severity :error|:warn :ical/code … :ical/id … :ical/msg …}`
  so a caller decides how to surface them. `valid?` is true iff there are no
  :error-level problems (warnings are advisory)."
  (:require [ical.model :as m]))

(defn- problem [severity code id msg]
  {:ical/severity severity :ical/code code :ical/id id :ical/msg msg})

(defn- validate-rrule [rrule uid ps]
  (when rrule
    (when-not (contains? m/freqs (:ical/freq rrule))
      (conj! ps (problem :error :rrule/unknown-freq uid
                         (str "RRULE FREQ " (:ical/freq rrule)
                              " is not one of " (sort (map name m/freqs))))))
    (when (and (:ical/count rrule) (:ical/until rrule))
      (conj! ps (problem :error :rrule/count-and-until uid
                         "RRULE must not specify both COUNT and UNTIL")))
    (doseq [day (get rrule :ical/byday [])]
      (when-not (contains? m/weekdays day)
        (conj! ps (problem :error :rrule/unknown-byday uid
                           (str "RRULE BYDAY token " day
                                " is not one of " (sort (map name m/weekdays)))))))))

(defn- validate-event [evt ps]
  (let [uid (:ical/uid evt)]
    (when-not uid
      (conj! ps (problem :error :vevent/missing-uid nil
                         "VEVENT is missing required :ical/uid")))
    (when-not (:ical/dtstart evt)
      (conj! ps (problem :error :vevent/missing-dtstart uid
                         (str "VEVENT " uid " is missing required :ical/dtstart"))))
    (validate-rrule (:ical/rrule evt) uid ps)))

(defn- validate-todo [td ps]
  (let [uid (:ical/uid td)]
    (when-not uid
      (conj! ps (problem :warn :vtodo/missing-uid nil
                         "VTODO is missing :ical/uid")))))

(defn problems
  "Return a vector of structural problems with `cal`."
  [cal]
  (let [ps (transient [])]
    (doseq [evt (:ical/events cal)] (validate-event evt ps))
    (doseq [td  (:ical/todos  cal)] (validate-todo  td  ps))
    (persistent! ps)))

(defn errors
  "Return only :error-severity problems."
  [cal]
  (filterv #(= :error (:ical/severity %)) (problems cal)))

(defn valid?
  "True iff `cal` has no :error-level structural problems."
  [cal]
  (empty? (errors cal)))
