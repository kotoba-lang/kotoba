(ns upf.parser
  "Simplified TCL-style command parser for the UPF command subset modeled in
  `upf.domain` / `upf.supply` / `upf.power-state` / `upf.strategy`:
  tokenizes a UPF script (respecting `{...}` grouped tokens as TCL does),
  dispatches on command name, and parses `-flag value` pairs into a map to
  build the model structures from `create_power_domain` /
  `create_supply_port` / `create_supply_net` / `connect_supply_net` /
  `add_power_state` / `set_isolation` / `set_level_shifter` script lines."
  (:require [kotoba.lang.text :as str]
            [upf.domain :as domain]
            [upf.supply :as supply]
            [upf.power-state :as power-state]
            [upf.strategy :as strategy]))

(defn- ws? [c] (or (= c \space) (= c \tab)))

(defn tokenize
  "Tokenize one command line into a vector of string tokens. A `{...}`
  group is collapsed into a single token with the braces stripped (its
  contents, including internal whitespace, preserved for the caller to
  split further as a list value)."
  [line]
  (loop [chars (seq line) tokens [] current nil in-brace false]
    (cond
      (empty? chars) (vec (cond-> tokens current (conj current)))
      (and in-brace (= (first chars) \})) (recur (rest chars) tokens current false)
      (and (not in-brace) (= (first chars) \{)) (recur (rest chars) tokens (or current "") true)
      (and (not in-brace) (ws? (first chars)))
      (recur (rest chars) (cond-> tokens current (conj current)) nil false)
      :else (recur (rest chars) tokens (str (or current "") (first chars)) in-brace))))

(defn- strip-comment [line]
  (let [idx (str/index-of line "#")]
    (if idx (subs line 0 idx) line)))

(defn- code-lines [script]
  (->> (str/split-lines script)
       (map strip-comment)
       (map str/trim)
       (remove str/blank?)))

(defn- parse-flags
  "Parse a token seq of the form `-flag1 value1 -flag2 value2 ...` into a
  map of keyword -> raw string value."
  [tokens]
  (loop [tokens tokens flags {}]
    (if (empty? tokens)
      flags
      (let [t (first tokens)]
        (if (str/starts-with? t "-")
          (recur (drop 2 tokens) (assoc flags (keyword (subs t 1)) (second tokens)))
          (recur (rest tokens) flags))))))

(defn- split-list [s]
  (if (str/blank? s) [] (str/split (str/trim s) #"\s+")))

(defn- parse-int [s]
  (when s #?(:clj (Integer/parseInt s) :cljs (js/parseInt s 10))))

(defn- parse-voltage-or-off
  "`\"off\"` (any case) -> `:off`; otherwise the string parsed as a
  floating-point voltage, falling back to the raw string if unparseable."
  [s]
  (if (= "off" (str/lower s))
    :off
    #?(:clj (try (Double/parseDouble s) (catch Exception _ s))
       :cljs (let [n (js/parseFloat s)] (if (js/isNaN n) s n)))))

(defn- parse-supply-assignments [group-str]
  (into {}
        (map (fn [pair]
               (let [[net v] (str/split pair #"=" 2)]
                 [net (parse-voltage-or-off v)])))
        (split-list group-str)))

(defn parse-line
  "Parse one UPF command line into a `[kind value]` pair — `kind` is one of
  `:power-domain :supply-port :supply-net :connections :power-state
  :isolation :level-shifter`, or nil for a blank/unrecognized command.
  `value` for `:connections` is a vector (one `connect_supply_net` call can
  fan out to multiple ports); every other kind produces a single map."
  [line]
  (let [tokens (tokenize line)
        cmd (first tokens)
        name (second tokens)
        flags (parse-flags (drop 2 tokens))]
    (case cmd
      "create_power_domain"
      [:power-domain (domain/create-power-domain name (split-list (:elements flags)))]

      "create_supply_port"
      [:supply-port (supply/create-supply-port name (keyword (:direction flags)))]

      "create_supply_net"
      [:supply-net (supply/create-supply-net name (:domain flags))]

      "connect_supply_net"
      [:connections (mapv #(supply/connect-supply-net name %) (split-list (:ports flags)))]

      "add_power_state"
      [:power-state (power-state/add-power-state
                     name (:state flags) (parse-supply-assignments (:supplies flags)))]

      "set_isolation"
      [:isolation (strategy/set-isolation
                   name (:domain flags) (:isolation_condition flags)
                   (parse-int (:clamp_value flags)) (keyword (:location flags)))]

      "set_level_shifter"
      [:level-shifter (strategy/set-level-shifter name (:domain flags) (keyword (:location flags)))]

      nil)))

(defn parse-script
  "Parse a multi-line UPF script string into the aggregate model:
  `{:domains [...] :ports [...] :nets [...] :connections [...]
    :power-states [...] :strategies [...]}`. `:strategies` holds both
  isolation and level-shifter maps (disambiguated by `:kind`, see
  `upf.strategy`)."
  [script]
  (reduce
   (fn [acc line]
     (if-let [[kind value] (parse-line line)]
       (case kind
         :power-domain (update acc :domains conj value)
         :supply-port (update acc :ports conj value)
         :supply-net (update acc :nets conj value)
         :connections (update acc :connections into value)
         :power-state (update acc :power-states conj value)
         (:isolation :level-shifter) (update acc :strategies conj value))
       acc))
   {:domains [] :ports [] :nets [] :connections [] :power-states [] :strategies []}
   (code-lines script)))
