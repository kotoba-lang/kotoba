(ns sigma.model
  "Sigma detection rules as EDN. A rule is a plain Clojure map keyed by
  namespaced :sigma/* keys. No I/O, no third-party deps — portable .cljc
  (JVM, ClojureScript, SCI).

  A Sigma rule has the shape:

    {:sigma/id    \"uuid-or-custom\"
     :sigma/title \"Brute Force Login Attempt\"
     :sigma/level :high
     :sigma/logsource {:sigma/product \"windows\" :sigma/service \"security\"}
     :sigma/detection
       {:sigma/selections
          {\"sel\"  {\"EventID\" [4625] \"TargetUserName|contains\" [\"adm\"]}
           \"filt\" {\"IpAddress\" [\"127.0.0.1\"]}}
        :sigma/condition \"sel and not filt\"}}

  Selections are string-keyed maps; field keys may carry |modifiers
  (e.g. \"User|contains\", \"Cmd|endswith|all\", \"Hash|re\").
  The condition string references named selections with and/or/not,
  quantifiers (1 of sel*, all of them), and parentheses.")

(def known-levels
  "Sigma severity levels."
  #{:informational :low :medium :high :critical})

(def known-modifiers
  "Allowed field-key pipe-modifiers."
  #{"contains" "startswith" "endswith" "re" "all" "gt" "lt"})

;; --- builder (threadable) ---

(defn rule
  "Build a bare Sigma rule map.
  opts: {:level :logsource :tags :description :status}"
  ([id title] (rule id title nil))
  ([id title opts]
   (cond-> {:sigma/id        id
            :sigma/title     title
            :sigma/detection {:sigma/selections {} :sigma/condition ""}}
     (:level       opts) (assoc :sigma/level       (:level opts))
     (:logsource   opts) (assoc :sigma/logsource   (:logsource opts))
     (:tags        opts) (assoc :sigma/tags        (:tags opts))
     (:description opts) (assoc :sigma/description (:description opts))
     (:status      opts) (assoc :sigma/status      (:status opts)))))

(defn add-selection
  "Add or replace named selection `sel-name` in rule `r`.
  `criteria` is a string-keyed map: {\"EventID\" [4625] \"User|contains\" [\"adm\"]}."
  [r sel-name criteria]
  (assoc-in r [:sigma/detection :sigma/selections sel-name] criteria))

(defn set-condition
  "Set the condition expression string on rule `r`."
  [r condition]
  (assoc-in r [:sigma/detection :sigma/condition] condition))

;; --- queries ---

(defn selections
  "Return the named-selections map from rule `r`."
  [r]
  (get-in r [:sigma/detection :sigma/selections] {}))

(defn condition
  "Return the condition string from rule `r`."
  [r]
  (get-in r [:sigma/detection :sigma/condition] ""))

(defn selection-names
  "Return the set of selection names defined in rule `r`."
  [r]
  (set (keys (selections r))))
