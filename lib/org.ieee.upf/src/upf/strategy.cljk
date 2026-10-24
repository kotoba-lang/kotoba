(ns upf.strategy
  "UPF `set_isolation` / `set_level_shifter` model — isolation and
  level-shifter strategies attached to a power domain, plus
  domain-applicability filtering.")

(defn set-isolation
  "Build an isolation strategy map. `clamp-value` is `0` or `1` (the value
  the isolation cell drives while `isolation-condition` holds);
  `location` is `:coarse` or `:fine`."
  [strategy-name applies-to-domain isolation-condition clamp-value location]
  {:strategy-name strategy-name
   :applies-to-domain applies-to-domain
   :isolation-condition isolation-condition
   :clamp-value clamp-value
   :location location
   :kind :isolation})

(defn set-level-shifter
  "Build a level-shifter strategy map. `location` is `:self`, `:parent`,
  or `:fanout` (where the shifter cell is placed relative to the domain)."
  [strategy-name applies-to-domain location]
  {:strategy-name strategy-name
   :applies-to-domain applies-to-domain
   :location location
   :kind :level-shifter})

(defn applicable-strategies
  "Filter `strategies` (a mix of `set-isolation` / `set-level-shifter`
  maps) down to those whose `:applies-to-domain` matches `domain-name`."
  [strategies domain-name]
  (filterv #(= (:applies-to-domain %) domain-name) strategies))
