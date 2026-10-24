(ns vhdl.entity
  "Entity declaration model (IEEE 1076 §3.2): a named list of ports, each
  with a mode (:in/:out/:inout/:buffer) and a VHDL type string.

  {:name \"and_gate\"
   :ports [{:name \"a\" :mode :in :type \"std_logic\"}
           {:name \"y\" :mode :out :type \"std_logic\"}]}")

(defn- parse-int
  [s]
  #?(:clj (Long/parseLong s)
     :cljs (js/parseInt s 10)))

(defn port-by-mode
  "Return the ports of `entity` whose :mode equals `mode`."
  [entity mode]
  (filterv #(= mode (:mode %)) (:ports entity)))

(defn bus-width
  "Parse a VHDL type string into its numeric width.

  Vector types carry an explicit range, e.g. \"std_logic_vector(7 downto 0)\"
  -> 8, \"std_logic_vector(0 to 7)\" -> 8. Scalar types (std_logic, integer,
  boolean, ...) have no range and are treated as width 1."
  [type-str]
  (if-let [[_ hi _dir lo] (re-find #"\((\d+)\s+(downto|to)\s+(\d+)\)" type-str)]
    (let [hi (parse-int hi)
          lo (parse-int lo)]
      (inc (- (max hi lo) (min hi lo))))
    1))
