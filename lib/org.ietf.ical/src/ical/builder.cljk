(ns ical.builder
  "Small builder API for iCalendar content lines."
  (:require [kotoba.lang.text :as str]))

(def ^:private text-props #{:summary :description :location :comment :categories :name :contact})

(defn- esc-text [s]
  (-> (str s)
      (str/replace "\\" "\\\\")
      (str/replace ";" "\\;")
      (str/replace "," "\\,")
      (str/replace "\n" "\\n")))

(defn- prop [k v]
  (str (str/upper (name k)) ":" (if (text-props k) (esc-text v) (str v))))

(defn- fold [line]
  (if (<= (count line) 75)
    line
    (apply str (subs line 0 75)
           (for [i (range 75 (count line) 74)]
             (str "\r\n " (subs line i (min (count line) (+ i 74))))))))

(defn- lines [cname props children]
  (concat [(str "BEGIN:" (str/upper (name cname)))]
          (for [[k v] props] (prop k v))
          (apply concat children)
          [(str "END:" (str/upper (name cname)))]))

(defn vevent "A VEVENT component as content lines." [props] (lines :vevent props nil))
(defn vtodo "A VTODO component as content lines." [props] (lines :vtodo props nil))
(defn valarm "A VALARM component as content lines." [props] (lines :valarm props nil))
(defn vjournal "A VJOURNAL component as content lines." [props] (lines :vjournal props nil))

(defn vcalendar
  "Compile a VCALENDAR document to an .ics string with CRLF line endings."
  [opts & components]
  (str/join "\r\n"
            (map fold
                 (lines :vcalendar
                        (into [[:version (or (:version opts) "2.0")]
                               [:prodid (or (:prodid opts) "-//kotoba//ical//EN")]]
                              (for [[k v] (dissoc opts :version :prodid)] [k v]))
                        components))))
