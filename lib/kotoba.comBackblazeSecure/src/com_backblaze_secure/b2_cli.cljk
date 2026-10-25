(ns com-backblaze-secure.b2-cli
  "Thin subprocess wrapper around the official `b2` CLI
  (https://github.com/Backblaze/B2_Command_Line_Tool) — no B2/S3 signing is
  reimplemented here, per this workspace's \"consume existing infra, don't
  rebuild it\" convention.

  Every call passes credentials via `B2_APPLICATION_KEY_ID` /
  `B2_APPLICATION_KEY` environment variables scoped to that single
  subprocess invocation only (this is the `b2` CLI's own documented
  env-var auth flow). It never calls `b2 account authorize`, which persists
  to `~/.b2_account_info` as global mutable state and was the exact
  mechanism that leaked a scoped key into a chat transcript in the session
  that motivated this repo (ADR-2607152322) — per-call env vars avoid both
  the persistent side effect and any cross-bucket session bleed between
  concurrent tool calls.

  Every public fn's result is passed through com-backblaze-secure.redact
  before returning — callers (com-backblaze-secure.server) must not bypass
  these fns to shell out to `b2` directly."
  (:require [kotoba.lang.text :as str]
            [com-backblaze-secure.redact :as redact]))

(def child-process (js/require "node:child_process"))

;; The whole stdio server is single-threaded and synchronous
;; (execFileSync) — see README "Known limitations": one slow `b2` call
;; blocks every other tool call until it finishes or times out. A fixed
;; ceiling here means a dead network / hung transfer fails loudly instead of
;; wedging the server forever; override via COM_BACKBLAZE_SECURE_B2_TIMEOUT_MS
;; for legitimately large uploads/downloads.
(defn- timeout-ms []
  (let [v (aget js/process.env "COM_BACKBLAZE_SECURE_B2_TIMEOUT_MS")]
    (if (and v (not= v "")) (js/parseInt v 10) 300000)))

;; Node's execFileSync defaults maxBuffer to 1MB and throws ENOBUFS past
;; that — confirmed empirically: `b2 ls --json -r` on a bucket with a few
;; hundred files already exceeds 1MB. A recursive JSON file listing is
;; exactly the kind of output this server needs to return whole (no
;; pagination is implemented), so the ceiling is raised; very large buckets
;; can still exceed even this and will fail loudly rather than truncate
;; silently — see README "Known limitations".
(defn- max-buffer-bytes []
  (let [v (aget js/process.env "COM_BACKBLAZE_SECURE_B2_MAX_BUFFER_BYTES")]
    (if (and v (not= v "")) (js/parseInt v 10) (* 200 1024 1024))))

(defn- run
  [creds args]
  (let [env (js/Object.assign (js-obj) js/process.env
                               #js {"B2_APPLICATION_KEY_ID" (:key-id creds)
                                    "B2_APPLICATION_KEY"     (:app-key creds)})]
    (try
      ;; Explicit :stdio, same reasoning as com-backblaze-secure.credentials/sh
      ;; — `execFileSync` inherits child stderr to our own stderr by default,
      ;; and `b2` CLI output must go through `redact` before it lands
      ;; anywhere, never straight to this process's own stderr.
      {:exit 0
       :out (.toString (.execFileSync child-process "b2" (clj->js args)
                                       #js {:encoding "utf8" :env env :timeout (timeout-ms)
                                            :maxBuffer (max-buffer-bytes)
                                            :stdio (clj->js ["ignore" "pipe" "pipe"])}))}
      (catch :default e
        {:exit (or (.-status e) 1)
         :out  (or (some-> (.-stdout e) .toString) "")
         ;; `.-stderr` is often an empty (not nil) string on a non-CLI
         ;; failure like ENOBUFS/ETIMEDOUT — fall back to `.-message` (which
         ;; carries e.g. "spawnSync b2 ENOBUFS") whenever stderr is blank,
         ;; not just when it's nil/absent.
         :err  (let [stderr (some-> (.-stderr e) .toString)]
                 (if (str/blank? stderr) (.-message e) stderr))}))))

(defn- parse-json [s]
  (try (js->clj (.parse js/JSON s) :keywordize-keys true)
       (catch :default _ {:raw s})))

(defn- json-result [creds args]
  (let [{:keys [exit out err]} (run creds args)]
    (redact/redact
     (if (zero? exit) (parse-json out) {:error (or err out)}))))

(defn- text-result [creds args]
  (let [{:keys [exit out err]} (run creds args)]
    (redact/redact
     (if (zero? exit) {:ok true :stdout (str/trim out)} {:error (or err out)}))))

(defn bucket-info
  "b2 bucket get <bucket> (always prints JSON, no --json flag exists on this
  subcommand). Deliberately scoped to exactly one bucket per call — this
  workspace's B2 application keys are routinely bucket-restricted
  (`Requires capability: listBuckets`, but the underlying key still only
  ever sees the one bucket it is scoped to), so a generic `b2 bucket list`
  call fails outright for a restricted key (confirmed empirically: \"ERROR:
  Application key is restricted to buckets: [...]\"). server.cljs calls this
  once per allowlisted bucket, each with that bucket's own credentials, and
  aggregates the results — it never assumes one key can enumerate buckets
  it wasn't scoped to."
  [creds bucket]
  (json-result creds ["bucket" "get" bucket]))

(defn list-file-names
  "b2 ls b2://<bucket>[/<prefix>] --json [-r]. `prefix` narrows the listing
  to one \"folder\"; `recursive?` (default true) matches the tool's
  original recursive contract. Server-side result-count truncation to keep
  MCP responses a sane size lives in com-backblaze-secure.server, not here
  — this fn always returns the CLI's full (redacted) parsed listing."
  ([creds bucket] (list-file-names creds bucket nil true))
  ([creds bucket prefix] (list-file-names creds bucket prefix true))
  ([creds bucket prefix recursive?]
   (let [uri (str "b2://" bucket (when-not (str/blank? prefix) (str "/" prefix)))]
     (json-result creds (cond-> ["ls" uri "--json"] recursive? (conj "-r"))))))

(defn file-info
  "b2 file info b2://<bucket>/<path> — no --json flag on this subcommand;
  stdout is captured as redacted text."
  [creds bucket remote-path]
  (text-result creds ["file" "info" (str "b2://" bucket "/" remote-path)]))

(defn download-file
  "b2 file download b2://<bucket>/<path> <local-path>."
  [creds bucket remote-path local-path]
  (let [{:keys [exit err]} (run creds ["file" "download" (str "b2://" bucket "/" remote-path) local-path])]
    (if (zero? exit)
      {:ok true :local-path local-path}
      (redact/redact {:error err}))))

(defn upload-file
  "b2 file upload <bucket> <local-path> <remote-name>."
  [creds bucket local-path remote-name]
  (text-result creds ["file" "upload" bucket local-path remote-name]))

(defn delete-file
  "b2 rm b2://<bucket>/<path> — deliberately never passes -r/--with-wildcard
  from this tool surface, so a single call can only ever remove the exact
  object named, never a wildcard/recursive sweep."
  [creds bucket remote-path]
  (text-result creds ["rm" (str "b2://" bucket "/" remote-path)]))
