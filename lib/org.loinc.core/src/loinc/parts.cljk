(ns loinc.parts
  "LOINC's six-axis part model — a data *shape*, not data. Every LOINC
  term is fully specified by six independent axes (this decomposition,
  and the colon-delimited \"Fully-Specified Name\" convention that
  concatenates them, is LOINC's published structural model — see LOINC's
  freely-available Users' Guide chapter on the six-part naming
  convention — not the licensed code-to-name table itself):

  | axis | question it answers | example axis *value* (illustrative only, not a real term) |
  |---|---|---|
  | Component | what is measured/observed | `Sodium` |
  | Property  | the kind of property (e.g. mass concentration) | `SCnc` |
  | Time      | single point vs. time interval | `Pt` |
  | System    | the specimen/system observed | `Ser/Plas` |
  | Scale     | how the result is expressed (quantitative/ordinal/nominal/narrative) | `Qn` |
  | Method    | how the observation was made, when relevant | (often empty) |

  This namespace provides the *shape* (a plain map with these six keys),
  a validator that the shape has all six keys present (possibly blank —
  `Method` legitimately is, for many terms), and the Fully-Specified Name
  concatenation/parsing convention. It does not ship, and has no way to
  look up, any actual axis values for any actual LOINC code — a licensee
  supplies those from their own copy of the release file (see
  `loinc.release-csv`)."
  (:require [kotoba.lang.text :as str]))

(def axes
  "The six axis keys, in the canonical Fully-Specified-Name order."
  [:component :property :time :system :scale :method])

(defn part
  "Construct a six-axis part map. Missing axes default to `\"\"`
  (LOINC's own convention: `Method` is blank for the large majority of
  terms, and is the only axis regularly left empty)."
  [m]
  (into {} (map (fn [k] [k (get m k "")]) axes)))

(defn valid-part?
  "True when `m` has all six axis keys (each mapped to a string — an
  absent/blank string is a legitimate value, a missing *key* or a
  non-string value is not)."
  [m]
  (and (map? m)
       (every? #(contains? m %) axes)
       (every? #(string? (get m %)) axes)))

(defn fully-specified-name
  "The six axis values joined `:`-delimited, in canonical order — LOINC's
  published Fully-Specified Name (FSN) convention, e.g.
  `\"Component:Property:Time:System:Scale:Method\"`. Returns
  `[:error :loinc/invalid-part]` if `m` is missing an axis."
  [m]
  (if (valid-part? m)
    [:ok (str/join ":" (map #(get m %) axes))]
    [:error :loinc/invalid-part]))

(defn parse-fully-specified-name
  "Inverse of `fully-specified-name`: split a colon-delimited FSN string
  into a six-axis part map. Returns `[:error :loinc/wrong-axis-count]`
  if `s` doesn't split into exactly 6 colon-delimited fields — this
  library does not attempt to disambiguate an FSN whose Component text
  itself happens to contain a literal colon (rare, and LOINC's own
  release format avoids it by using the FSN only as a display
  convention, never as the parseable source of truth — the release CSV's
  separate per-axis columns are)."
  [s]
  (let [fields (str/split s #":" -1)]
    (if (not= (count axes) (count fields))
      [:error :loinc/wrong-axis-count]
      [:ok (part (zipmap axes fields))])))
