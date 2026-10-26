(ns kuro.host.node
  "Node host provider for `:terminal-repo` / `:terminal-build` / `:terminal-agent`
  sessions. This is the layer `kuro.terminal`'s docstrings keep pointing at:
  the model decides *whether* a command may run and *what the receipt says*;
  this namespace is the only place that actually runs one.

  ## Runtime

  ClojureScript on Node (nbb), per the repo runtime order — the pure model
  stays `.cljc`, the effect lands in the highest runtime that can spawn a
  process. Nothing here is required to use `kuro.terminal`.

  ## What is actually enforced (deterministic, tested)

  | guarantee | mechanism |
  |---|---|
  | denial before execution | `kuro.terminal/denial` — no spawn happens on a missing capability |
  | no shell interpolation | `spawnSync` with an argv vector and `:shell false` |
  | cwd confinement | resolved path must stay under the session's repo root |
  | no ambient environment | the child env is exactly the declared manifest (`TERM=dumb` included); `process.env` is never passed |
  | bounded time | `:timeout-ms` (default 120 s) — exit 124, `:timed-out? true` |
  | bounded output | `:max-output-bytes` (default 1 MiB) — exit 125, `:truncated? true` |
  | content-addressed output | stdout/stderr CIDv1-raw in the receipt |

  ## What is NOT enforced here (say it plainly)

  A capability set is an **intent record**, not a kernel. This provider does
  not confine filesystem writes, does not block network access, and does not
  isolate the process namespace. A command granted `repo/read` can still write
  to disk — nothing stops it but the receipt that says it should not have.

  That is the documented split: ADR-2606301000 says the backing may be a
  sandbox, container, microVM, or an aiueos surface provider, and `kuro` only
  records the intent and verifies the portable shape. This is the smallest
  honest backing — enough to produce real receipts from real commands, not
  enough to run untrusted code. `:terminal-host` is refused outright."
  (:require ["node:child_process" :as cp]
            ["node:path" :as path]
            [kotoba.lang.text :as str]
            [kuro.host.cid :as cid]
            [kuro.terminal :as t]))

(def default-limits
  {:timeout-ms 120000
   :max-output-bytes (* 1024 1024)})

(defn default-timeout-ms
  "The `:timeout-ms` the sync provider applies when the caller passes none —
  the value the README table names. A fn so the table's default stays
  referenceable from tests without poking at a private map's shape."
  [] (:timeout-ms default-limits))

(defn default-max-output-bytes
  "The `:max-output-bytes` the sync provider applies when the caller passes
  none — 1 MiB, the value the README table names."
  [] (:max-output-bytes default-limits))

(def default-env
  "The child's entire environment unless the caller declares another.

  Declared, not inherited: a terminal that inherits `process.env` hands every
  token in the operator's shell to every command it runs, and no receipt can
  record what it leaked.

  One caveat, measured rather than assumed: on macOS, CoreFoundation injects
  `__CF_USER_TEXT_ENCODING` into every child below the spawn API. The manifest
  is therefore everything this provider passes, not literally everything the
  child sees."
  {"PATH" "/usr/bin:/bin:/usr/local/bin"
   "LANG" "C.UTF-8"
   "TERM" "dumb"})

(defn confine
  "Absolute path for `cwd` resolved under `repo-root`, or nil when it escapes.

  Both sides are resolved before comparison so `\"a/../../etc\"` is caught by
  the result rather than by spotting `..` in the input."
  [repo-root cwd]
  (let [root (path/resolve repo-root)
        target (path/resolve root (or cwd "."))]
    (when (or (= target root)
              (str/starts-with? target (str root path/sep)))
      target)))

(defn required-capabilities
  "Capabilities this command needs from the session's grant.

  A command declares its own via `:kuro/requires`. Running any process at all
  implies reading the repo, so `repo/read` is always required — a session with
  an empty grant can execute nothing."
  [cmd]
  (into #{"repo/read"} (map str (:kuro/requires cmd #{}))))

(defn- capture
  "[text cid byte-count] for a stdout/stderr Buffer."
  [^js buf]
  (let [buf (or buf (js/Buffer.alloc 0))]
    [(.toString buf "utf8") (cid/raw-cid buf) (.-length buf)]))

(defn- spawn-outcome
  "Normalise spawnSync's three failure shapes (timeout, output cap, and
  everything else — most often ENOENT) into an exit code plus flags.

  spawnSync reports a timeout or an output overflow as `.error` with
  `status` nil, so a naive `(or status 0)` would record a killed command as a
  success. These codes follow shell convention: 124 timeout, 127 not found."
  [^js res argv]
  (let [err (.-error res)
        code (some-> err .-code)
        status (.-status res)]
    (cond
      (= code "ETIMEDOUT") {:exit-code 124 :timed-out? true}
      (= code "ENOBUFS") {:exit-code 125 :truncated? true}
      (= code "ENOENT") {:exit-code 127 :error (str "command not found: " (first argv))}
      err {:exit-code 126 :error (str code)}
      (nil? status) {:exit-code 128 :error "terminated without status"}
      :else {:exit-code status})))

(defn run
  "Run `cmd` in `sess`, returning a `kuro.terminal` receipt.

  Returns a denial map (`:kuro/allowed? false`) **without executing** when the
  session's grant is missing a required capability, and throws when the session
  is `:terminal-host` (no host-shell backing exists — see the ns docstring) or
  when the resolved cwd escapes the repo root.

  opts: `:repo-root` (default `.`), `:env` (default `default-env`),
  `:timeout-ms`, `:max-output-bytes`, `:now` (injectable clock, default
  `js/Date.now`)."
  ([sess cmd] (run sess cmd {}))
  ([sess cmd opts]
   (when (= :terminal-host (:kuro/mode sess))
     (throw (ex-info "kuro.host.node has no host-shell backing"
                     {:mode :terminal-host :reason :unsupported-mode})))
   (let [{:keys [timeout-ms max-output-bytes]} (merge default-limits opts)
         now (:now opts #(js/Date.now))
         repo-root (:repo-root opts ".")
         cwd (or (confine repo-root (:kuro/cwd sess))
                 (throw (ex-info "terminal cwd escapes the repo root"
                                 {:repo-root repo-root
                                  :cwd (:kuro/cwd sess)
                                  :reason :cwd-escape})))
         required (required-capabilities cmd)]
     (or (t/denial sess required)
         (let [argv (:kuro/argv cmd)
               started (now)
               res (cp/spawnSync (first argv) (clj->js (vec (rest argv)))
                                 #js {:cwd cwd
                                      :env (clj->js (:env opts default-env))
                                      :shell false
                                      :timeout timeout-ms
                                      :maxBuffer max-output-bytes
                                      :encoding "buffer"})
               finished (now)
               [out out-cid out-bytes] (capture (.-stdout res))
               [err err-cid err-bytes] (capture (.-stderr res))]
           (t/receipt sess cmd
                      (merge {:stdout out
                              :stderr err
                              :stdout-cid out-cid
                              :stderr-cid err-cid
                              :stdout-bytes out-bytes
                              :stderr-bytes err-bytes
                              :started-at started
                              :finished-at finished
                              :duration-ms (- finished started)}
                             (spawn-outcome res argv))))))))
