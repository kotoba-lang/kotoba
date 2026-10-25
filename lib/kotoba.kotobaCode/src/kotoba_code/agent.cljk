(ns kotoba-code.agent
  "The kotoba-code agent: langgraph-clj's create-react-agent (agent→tools→agent→END)
  wired to a ChatModel + the coding tools + (optionally) a kotoba-Datom checkpointer
  so every superstep of a session is persisted as-of on the kotoba Datom log under a
  stable session thread — resumable, auditable, time-travelable."
  (:require [langgraph.prebuilt :as pre]
            [langgraph.graph :as g]
            [langchain.message :as msg]
            [kotoba-code.tools :as tools]))

(def system-prompt
  (str "You are kotoba-code, a precise, test-gated Clojure coding agent.\n"
       "Work in small steps: inspect status/diff, read the relevant files, make the\n"
       "minimal edit, run the tests, fix, repeat. Use read_file_numbered before\n"
       "replace_range. Prefer replace_text, replace_range,\n"
       "or apply_patch for small edits; use write_file only when replacing a complete\n"
       "file is clearer. For questions, explanations, and ordinary conversation,\n"
       "answer directly without tools or tests. The test gate only applies after an edit.\n"
       "\n"
       "House rules (do not violate):\n"
       "- langgraph-clj graph builders are IMMUTABLE: thread with `->`, never `doto`\n"
       "  (doto discards each call's return value, so nodes/entry-point silently vanish).\n"
       "- Runtime model inference stays Murakumo-only (ADR-2605215000); do not add\n"
       "  external inference into the code you write.\n"
       "- kotoba persistence is `(cp/datomic-checkpointer conn {:db-api (kdb/kotoba-api host-caps)})`\n"
       "  over `(kdb/kotoba-conn url graph)`, never the in-process langchain.db store.\n"
       "- Keep durable-loop state as EDN datoms (`:agent.loop/*`, `:agent.tick/*`,\n"
       "  `:agent.lease/*`, `:agent.budget/*`, `:agent.event/*`, `:agent.governor/*`).\n"
       "\n"
       "The MOMENT run_tests reports \"0 failures, 0 errors\" and the task is met, reply\n"
       "with the single word DONE and STOP. Do NOT make speculative edits after green."))

(defn build-agent
  "Compiles the ReAct coding agent.
   opts: {:model ChatModel
          :host  tool capability map (see kotoba-code.tools)
          :system          system prompt (defaults to system-prompt)
          :recursion-limit  max supersteps (default 40)
          :checkpointer     optional langgraph checkpointer (kotoba-Datom for persistence)}"
  [{:keys [model host system recursion-limit checkpointer]
    :or   {system system-prompt recursion-limit 40}}]
  (pre/create-react-agent
   {:model model
    :tools (tools/coding-tools host)
    :system system
    :compile-opts (cond-> {:recursion-limit recursion-limit}
                    checkpointer (assoc :checkpointer checkpointer))}))

(defn run-task
  "Drives the agent on a task string; returns the final graph state ({:messages [..]}).
  A :session-id makes the run accrete on one kotoba-Datom thread (resume across runs)."
  ([agent task] (run-task agent task {}))
  ([agent task {:keys [session-id]}]
   (g/invoke agent {:messages [(msg/user task)]}
             (cond-> {} session-id (assoc :thread-id session-id)))))

(defn answer
  "The agent's final assistant text from a run-task result."
  [final-state]
  (msg/text (msg/last-message (:messages final-state))))
