(ns com-backblaze-secure.audit
  "Append-only JSONL audit ledger, one line per MCP tool call: {ts tool
  bucket capability outcome}. Callers MUST have already run any result
  through com-backblaze-secure.redact — this ns does not redact for you,
  it only appends whatever plain data it is given.")

(def fs (js/require "node:fs"))
(def os (js/require "node:os"))
(def path (js/require "node:path"))

(defn default-path []
  (.join path (.homedir os) ".com-backblaze-secure" "audit.jsonl"))

(defn expand-home [p]
  (if (and p (re-find #"^~(/|$)" p))
    (.join path (.homedir os) (subs p 1))
    p))

(defn append!
  [audit-path entry]
  (let [resolved (expand-home audit-path)
        dir (.dirname path resolved)]
    (when-not (.existsSync fs dir) (.mkdirSync fs dir #js {:recursive true}))
    (.appendFileSync fs resolved (str (.stringify js/JSON (clj->js entry)) "\n"))))
