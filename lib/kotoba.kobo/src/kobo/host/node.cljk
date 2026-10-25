(ns kobo.host.node
  "Runs a workbench terminal's command for real, via `kuro.host.node`.

  This closes the loop the rest of `kobo` only models: open a terminal, run
  something, and the receipt — or the denial — lands back in the same
  workbench value the console renders. Both outcomes are recorded, because a
  workbench that drops refusals shows an empty receipt list whether the
  command was denied or never typed.

  ClojureScript on Node (nbb): everything else in `kobo` is portable `.cljc`,
  and this namespace is where that stops. See `kuro.host.node`'s docstring for
  what the backing does and does not enforce — it is not an isolation
  boundary."
  (:require [kobo.workbench :as wb]
            [kuro.host.node :as host]
            [kuro.terminal :as t]))

(defn run
  "Run `argv` in the workbench's `terminal-id`, returning the updated workbench.

  opts are passed to `kuro.host.node/run` (`:repo-root`, `:timeout-ms`,
  `:max-output-bytes`, `:env`, `:now`), plus `:kuro/requires` for capabilities
  the command needs beyond `repo/read`."
  ([w terminal-id argv] (run w terminal-id argv {}))
  ([w terminal-id argv opts]
   (let [sess (or (wb/terminal w terminal-id)
                  (throw (ex-info "no such terminal in this workbench"
                                  {:terminal-id terminal-id
                                   :open (vec (keys (:kobo/terminals w)))})))
         cmd (t/command argv (select-keys opts [:kuro/requires]))
         outcome (host/run sess cmd opts)]
     (if (false? (:kuro/allowed? outcome))
       (wb/record-denial w (assoc outcome :kuro/argv argv))
       (update w :kobo/receipts conj outcome)))))
