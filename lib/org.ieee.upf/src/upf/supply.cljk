(ns upf.supply
  "UPF supply-network model — a simplified subset of `create_supply_port` /
  `create_supply_net` / `connect_supply_net`: supply ports, supply nets, and
  net-to-port connections, plus a graph-walk that traces a net back through
  chained connections to its ultimate source port.")

(defn create-supply-port
  "Build a supply port map: `direction` is `:in` or `:out`."
  [name direction]
  {:name name :direction direction})

(defn create-supply-net
  "Build a supply net map, scoped to power `domain`."
  [name domain]
  {:name name :domain domain})

(defn connect-supply-net
  "Build a connection map tying supply `net` to supply `port`. A port name
  may itself be reused as a `:net` in another connection to model a supply
  passed down through hierarchy (net -> port -> net -> port -> ...)."
  [net port]
  {:net net :port port})

(defn net-voltage-path
  "Given `connections` (a collection of `connect-supply-net` maps) and a
  `net-name`, walk the net -> port -> net -> port ... chain (a port name
  that is itself referenced as the `:net` of another connection is followed
  transitively) and return the name of the ultimate source port — the last
  port reached that is not itself connected onward as a net.

  Returns nil when `net-name` has no connection at all. Returns nil (rather
  than looping forever) if the chain cycles back on itself."
  [connections net-name]
  (loop [current net-name
         visited #{}
         advanced? false]
    (if (contains? visited current)
      nil
      (let [conn (some #(when (= (:net %) current) %) connections)]
        (cond
          conn (recur (:port conn) (conj visited current) true)
          advanced? current
          :else nil)))))
