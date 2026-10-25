(ns browseragent.schema
  "Datomic-API-compatible schema for the super-agent.

  Every piece of runtime state — the task, the *owned browser session*,
  the plan (with its replan history), each MoA delegation, each
  sub-agent action, semantic memory and generated artifacts — is a
  datom. \"Which tabs is the agent looking at?\", \"every URL this task
  visited\", \"how many times did we replan?\" are all Datalog queries,
  and `langchain.db/as-of` time-travels the whole thing.

  Merge `schema` into your db schema; it already includes the
  browser-use action-log attributes so one conn carries everything."
  (:require [browseruse.agent :as bua]))

(def schema
  (merge
   bua/log-schema  ; :session/id :action/session :action/step :action/name …
   {;; ── task ────────────────────────────────────────────────
    :task/id        {:db/unique :db.unique/identity}
    :task/prompt    {}
    :task/status    {}                                  ; :running :done :failed

    ;; ── owned browser session (the agent's *own* browser) ───
    :browser/id      {:db/unique :db.unique/identity}
    :browser/task    {:db/valueType :db.type/ref}
    :browser/profile {}                                 ; user-data-dir / profile key
    :browser/current {}                                 ; current URL
    :browser/tabs    {}                                 ; pr-str of open tab URLs
    :browser/status  {}                                 ; :open :idle :handed-over :closed

    ;; ── plan (planner output; replans append, as-of keeps history) ─
    :plan/task     {:db/valueType :db.type/ref}
    :plan/step     {}                                   ; ordinal
    :plan/goal     {}
    :plan/assignee {}                                   ; sub-agent kw (:web :coder …)
    :plan/status   {}                                   ; :todo :doing :done :skipped

    ;; ── delegation (the MoA routing decision + outcome) ────
    :deleg/task   {:db/valueType :db.type/ref}
    :deleg/step   {}
    :deleg/agent  {}                                    ; :web :research …
    :deleg/model  {}                                    ; which model handled it
    :deleg/goal   {}
    :deleg/result {}

    ;; ── semantic memory (extracted facts / entities / sources) ─
    :mem/task       {:db/valueType :db.type/ref}
    :mem/kind       {}                                  ; :fact :entity :source
    :mem/key        {:db/index true}
    :mem/value      {}
    :mem/source-url {}

    ;; ── artifacts (slides / sheet / doc / page / file) ─────
    :artifact/task  {:db/valueType :db.type/ref}
    :artifact/kind  {}
    :artifact/title {}
    :artifact/body  {}
    :artifact/mime  {}}))
