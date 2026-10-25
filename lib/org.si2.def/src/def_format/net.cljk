(ns def-format.net
  "DEF NETS section: net connectivity (instance/pin pairs) and simplified
  routed-wire geometry for a placed-and-routed design (Si2 DEF, si2.org).")

(defn net
  [name connections routed]
  {:name name :connections connections :routed (or routed [])})

(defn connection [instance pin] {:instance instance :pin pin})

(defn routed-wire [layer points] {:layer layer :points points})

(defn net-fanout
  "Number of instance/pin connections on a net, i.e. how many component
  pins this net fans out to."
  [n]
  (count (:connections n)))
