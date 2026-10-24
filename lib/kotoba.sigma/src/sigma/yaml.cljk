(ns sigma.yaml
  "Convert between an already-parsed Sigma YAML map (string keys, as a YAML library
  would produce) and the sigma EDN model (namespaced :sigma/* keys).

  Does NOT parse YAML text — the host must parse YAML first (e.g. clj-yaml on the
  JVM, js-yaml on ClojureScript). This namespace is intentionally pure data
  transformation with zero I/O.

  Round-trip guarantee (for well-formed data):
    (= (to-data (from-data data)) data)"
  (:require [sigma.model :as m]))

(defn- logsource->edn
  "Convert a string-keyed logsource map to :sigma/* namespaced keywords."
  [ls]
  (reduce-kv (fn [acc k v]
               (assoc acc (keyword "sigma" k) v))
             {}
             ls))

(defn- edn->logsource
  "Convert a :sigma/* namespaced logsource map back to string keys."
  [ls]
  (reduce-kv (fn [acc k v]
               (assoc acc (name k) v))
             {}
             ls))

(defn from-data
  "Convert an already-parsed Sigma YAML map (string keys) to a :sigma/* rule map.

  Expected `data` shape:
    {\"title\"       \"Brute Force Login\"
     \"id\"          \"uuid-or-custom\"
     \"level\"       \"high\"
     \"status\"      \"stable\"
     \"description\" \"...\"
     \"tags\"        [\"attack.t1110\"]
     \"logsource\"   {\"product\" \"windows\" \"service\" \"security\"}
     \"detection\"   {\"sel\"  {\"EventID\" [4625] \"TargetUserName|contains\" [\"adm\"]}
                     \"filt\" {\"IpAddress\" [\"127.0.0.1\"]}
                     \"condition\" \"sel and not filt\"}}

  The `condition` key inside `detection` becomes :sigma/condition; all other
  keys inside `detection` become named selections in :sigma/selections."
  [data]
  (let [det      (get data "detection" {})
        cond-str (get det "condition" "")
        sels     (dissoc det "condition")]
    (cond-> {:sigma/detection {:sigma/selections sels
                               :sigma/condition  cond-str}}
      (get data "title")       (assoc :sigma/title       (get data "title"))
      (get data "id")          (assoc :sigma/id          (get data "id"))
      (get data "level")       (assoc :sigma/level       (keyword (get data "level")))
      (get data "logsource")   (assoc :sigma/logsource   (logsource->edn (get data "logsource")))
      (get data "status")      (assoc :sigma/status      (get data "status"))
      (get data "description") (assoc :sigma/description (get data "description"))
      (get data "tags")        (assoc :sigma/tags        (get data "tags")))))

(defn to-data
  "Convert a :sigma/* rule map back to a string-keyed map (YAML-compatible shape)."
  [rule]
  (let [det-edn  (:sigma/detection rule)
        sels     (get det-edn :sigma/selections {})
        cond-str (get det-edn :sigma/condition "")
        det-out  (assoc sels "condition" cond-str)]
    (cond-> {"detection" det-out}
      (:sigma/title       rule) (assoc "title"       (:sigma/title rule))
      (:sigma/id          rule) (assoc "id"          (:sigma/id rule))
      (:sigma/level       rule) (assoc "level"       (name (:sigma/level rule)))
      (:sigma/logsource   rule) (assoc "logsource"   (edn->logsource (:sigma/logsource rule)))
      (:sigma/status      rule) (assoc "status"      (:sigma/status rule))
      (:sigma/description rule) (assoc "description" (:sigma/description rule))
      (:sigma/tags        rule) (assoc "tags"        (:sigma/tags rule)))))
