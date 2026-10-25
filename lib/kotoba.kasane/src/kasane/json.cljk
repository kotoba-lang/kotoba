(ns kasane.json
  "Thin adapter over kotoba-lang/json (json.core) — this ns used to be a
   self-contained JSON reader; it's now a wrapper so kasane doesn't carry
   its own duplicate JSON parser. json.core/decode returns string-keyed
   maps; this wraps it with keyword conversion to preserve kasane.json's
   original contract (kasane.gltf and kasane.normalize's sketch->doc use
   keyword-keyed access, e.g. `(:asset g)`/`(:_class layer)`). Used by the
   Sketch and glTF paths. See ADR-2606272100 and the kotoba-lang
   reverse-domain media/graphics standards-substrate split
   (com-junkawasaki/root)."
  (:require [json.core :as json]))

(defn- keywordize [x]
  (cond
    (map? x)        (into {} (map (fn [[k v]] [(keyword k) (keywordize v)]) x))
    (sequential? x) (mapv keywordize x)
    :else           x))

(defn parse
  "Parse a JSON string → Clojure data (objects=maps with keyword keys)."
  [s]
  (keywordize (json/decode s)))
