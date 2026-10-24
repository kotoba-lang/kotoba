(ns ical.model
  "iCalendar-as-EDN: a plain-data representation of an iCalendar object (VCALENDAR),
  its events (VEVENT) and todos (VTODO), plus recurrence rules (RRULE). No I/O, no
  third-party deps — portable .cljc (JVM, ClojureScript, SCI).

  A calendar is a map keyed by namespaced `:ical/*` keys:

    {:ical/prodid  \"-//com-junkawasaki//ical-clj//EN\"
     :ical/version \"2.0\"
     :ical/events
     [{:ical/uid     \"evt-001@host\"
       :ical/summary \"Weekly Standup\"
       :ical/dtstart {:y 2026 :m 7 :d 1 :hh 10 :mm 0}
       :ical/dtend   {:y 2026 :m 7 :d 1 :hh 11 :mm 0}
       :ical/rrule   {:ical/freq     :weekly
                      :ical/interval 1
                      :ical/count    5
                      :ical/byday    [:mo :we]}}]
     :ical/todos
     [{:ical/uid     \"todo-001@host\"
       :ical/summary \"Review PR\"
       :ical/dtstart {:y 2026 :m 7 :d 1 :hh 9 :mm 0}
       :ical/due     {:y 2026 :m 7 :d 15 :hh 9 :mm 0}
       :ical/status  :needs-action}]}

  Date-time values are plain maps {:y int :m int :d int :hh int :mm int}. There is
  intentionally no java.time / java.util.Date dependency — calendar arithmetic is
  handled by ical.execute using the Howard Hinnant proleptic-Gregorian day-number
  algorithm.")

;; --- valid taxonomy sets ---

(def freqs
  "Valid RRULE FREQ values."
  #{:daily :weekly :monthly :yearly})

(def weekdays
  "Valid BYDAY day-of-week tokens."
  #{:mo :tu :we :th :fr :sa :su})

;; --- builder helpers (threadable) ---

(defn calendar
  "A fresh, empty calendar map. opts: {:prodid :version}."
  ([] (calendar nil))
  ([opts]
   (cond-> {:ical/events [] :ical/todos []}
     (:prodid opts)  (assoc :ical/prodid  (:prodid opts))
     (:version opts) (assoc :ical/version (:version opts)))))

(defn event
  "A bare VEVENT map. opts: {:summary :dtstart :dtend :rrule :location :description}."
  ([uid] (event uid nil))
  ([uid opts]
   (cond-> {:ical/uid uid}
     (:summary     opts) (assoc :ical/summary     (:summary opts))
     (:dtstart     opts) (assoc :ical/dtstart     (:dtstart opts))
     (:dtend       opts) (assoc :ical/dtend       (:dtend opts))
     (:rrule       opts) (assoc :ical/rrule       (:rrule opts))
     (:location    opts) (assoc :ical/location    (:location opts))
     (:description opts) (assoc :ical/description (:description opts)))))

(defn todo
  "A bare VTODO map. opts: {:summary :dtstart :due :status :description}."
  ([uid] (todo uid nil))
  ([uid opts]
   (cond-> {:ical/uid uid}
     (:summary     opts) (assoc :ical/summary     (:summary opts))
     (:dtstart     opts) (assoc :ical/dtstart     (:dtstart opts))
     (:due         opts) (assoc :ical/due         (:due opts))
     (:status      opts) (assoc :ical/status      (:status opts))
     (:description opts) (assoc :ical/description (:description opts)))))

(defn rrule
  "Build an RRULE map. opts: {:freq :interval :count :until :byday}.
  :freq must be one of `freqs`; :byday a seq of `weekdays` keywords."
  [opts]
  (cond-> {:ical/freq (get opts :freq :weekly)}
    (:interval opts) (assoc :ical/interval (:interval opts))
    (:count    opts) (assoc :ical/count    (:count opts))
    (:until    opts) (assoc :ical/until    (:until opts))
    (:byday    opts) (assoc :ical/byday    (vec (:byday opts)))))

(defn add-event
  "Append `evt-map` (built via `event`) to `cal`."
  [cal evt-map]
  (update cal :ical/events conj evt-map))

(defn add-todo
  "Append `todo-map` (built via `todo`) to `cal`."
  [cal todo-map]
  (update cal :ical/todos conj todo-map))

;; --- date-time constructors ---

(defn dt
  "Construct a date-time map. hh and mm default to 0."
  ([y m d] (dt y m d 0 0))
  ([y m d hh mm] {:y y :m m :d d :hh hh :mm mm}))
