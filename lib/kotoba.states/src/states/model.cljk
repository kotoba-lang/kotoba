(ns states.model
  "ASL-as-EDN: a plain-data representation of an AWS Step Functions state machine
  (Amazon States Language). No I/O, no third-party deps — portable .cljc (JVM,
  ClojureScript, SCI).

  A state machine is a map keyed by namespaced `:states/*` keys. States are
  name-keyed for O(1) lookup; order is not relied on:

    {:states/comment  \"Order pipeline\"
     :states/start-at \"Validate\"
     :states/states
     {\"Validate\"  {:states/type     :task
                    :states/resource \"arn:aws:lambda:us-east-1:123:function:Validate\"
                    :states/next     \"Route\"}
      \"Route\"     {:states/type    :choice
                    :states/choices [{:states/variable \"$.status\"
                                      :states/op      :string-equals
                                      :states/value   \"ok\"
                                      :states/next    \"Ship\"}]
                    :states/default \"Reject\"}
      \"Ship\"      {:states/type :succeed}
      \"Reject\"    {:states/type :fail}}}")

;; --- ASL state type taxonomy ---

(def state-types
  "All valid :states/type values in ASL."
  #{:task :choice :pass :wait :succeed :fail :parallel :map})

(def terminal-types
  "State types that are always terminal (no :states/next required)."
  #{:succeed :fail})

;; --- queries ---

(defn state-ids
  "Return the set of state name strings in `machine`."
  [machine]
  (set (keys (:states/states machine))))

(defn state
  "Return the state map for name `id` in `machine`, or nil."
  [machine id]
  (get-in machine [:states/states id]))

(defn start-at
  "Return the StartAt state name for `machine`."
  [machine]
  (:states/start-at machine))

(defn terminal?
  "True if `state-map` is a terminal state: type :succeed/:fail, or :states/end true."
  [state-map]
  (boolean (or (contains? terminal-types (:states/type state-map))
               (:states/end state-map))))
