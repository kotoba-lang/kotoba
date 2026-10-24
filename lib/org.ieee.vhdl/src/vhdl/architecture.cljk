(ns vhdl.architecture
  "Architecture body model (IEEE 1076 §3.3): a named body of an entity,
  carrying signal declarations and process statements.

  {:name \"rtl\"
   :entity-name \"and_gate\"
   :signals [{:name \"tmp\" :type \"std_logic\"}]
   :processes [{:name \"p0\" :sensitivity-list [\"a\" \"b\"] :statement-count 1}]}"
  (:refer-clojure :exclude [sequential?]))

(def ^:private clock-like-re
  "Heuristic for a clock-like signal name in a sensitivity list."
  #"(?i)clk|clock")

(defn combinational?
  "A process is treated as combinational when none of the signal names in
  its sensitivity list look clock-like (heuristic: no name matching
  #\"(?i)clk|clock\"). Clocked (sequential) processes are expected to be
  sensitive to a clock signal, so their absence is the signal we key on."
  [process]
  (not-any? #(re-find clock-like-re %) (:sensitivity-list process)))

(defn sequential?
  [process]
  (not (combinational? process)))

(defn processes-by-kind
  "Return the :combinational or :sequential processes of `architecture`."
  [architecture kind]
  (let [pred (case kind
               :combinational combinational?
               :sequential sequential?)]
    (filterv pred (:processes architecture))))

(defn signal-names
  [architecture]
  (mapv :name (:signals architecture)))
