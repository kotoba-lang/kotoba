(ns apn.fixture
  "Small reference topologies shared across apn.* tests. Test-only, not
  part of the public API."
  (:require [apn.model :as m]
            [apn.grid :as grid]))

(defn- full-grid [] (set (grid/channels)))

(defn linear-topology
  "a -- b -- c, two links (100km / 200km), full DWDM grid on each."
  []
  (-> (m/system)
      (m/add-node (m/node "a" {}))
      (m/add-node (m/node "b" {}))
      (m/add-node (m/node "c" {}))
      (m/add-link (m/link "ab" "a" "b" {:apn/distance-km 100.0 :apn/channels (full-grid)}))
      (m/add-link (m/link "bc" "b" "c" {:apn/distance-km 200.0 :apn/channels (full-grid)}))))

(defn triangle-topology
  "linear-topology plus a direct a -- c link (250km), for alternate-route
  and cost-preference testing (a-b-c costs 300km vs. the 250km direct hop)."
  []
  (-> (linear-topology)
      (m/add-link (m/link "ac" "a" "c" {:apn/distance-km 250.0 :apn/channels (full-grid)}))))
