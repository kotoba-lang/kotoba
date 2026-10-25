(ns cmmn.ports
  "Host-injected ports for executing a CMMN case. cmmn-clj defines the protocols;
  the host supplies concrete implementations (call a service, evaluate an expression,
  schedule a human task, …). The interpreter in `cmmn.execute` is pure orchestration
  over these — no I/O of its own.")

(defprotocol ITask
  "Side-effect of a task plan-item. `run` receives the item map and the current
  context, and returns the (possibly updated) context map."
  (run [this item ctx] "item → ctx → ctx'"))

(defprotocol IGuard
  "Evaluation of a sentry `:cmmn/if` condition string against the current context."
  (allow? [this cond-string ctx] "cond-string → ctx → boolean"))

(defn default-ports
  "ITask is identity (ctx unchanged).
  IGuard reads (get ctx (keyword cond-string)) truthiness; absent key → true (open guard)."
  []
  {:task  (reify ITask
            (run [_ _ ctx] ctx))
   :guard (reify IGuard
            (allow? [_ cond-string ctx]
              (if (nil? cond-string)
                true
                (let [k (keyword cond-string)]
                  (if (contains? ctx k)
                    (boolean (get ctx k))
                    true)))))})
