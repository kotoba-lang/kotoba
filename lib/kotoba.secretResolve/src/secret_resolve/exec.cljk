(ns secret-resolve.exec
  "Safe wrapper around Node's `child_process.execFileSync`.

  Node's own default `stdio` INHERITS a child's stderr straight through to
  this process's own stderr unless explicitly overridden — confirmed
  empirically (ADR-2607152322, kotoba-lang/com-backblaze-secure): calling
  `security find-generic-password -s <service> -g` prints the resolved
  secret in cleartext as part of its human-readable attribute dump, and
  without an explicit `:stdio` override that plaintext secret leaks
  straight onto the CALLING process's stderr (logs, terminal, whatever is
  watching it) — not into any value the caller's own code ever sees or
  could redact. This ns exists so every caller of a security-sensitive
  subprocess gets the safe default without having to remember it or
  rediscover the bug independently (it had already been reinvented three
  times across this workspace before this library existed: `scripts/
  b2-creds.cljs`, `com-backblaze-secure/credentials.cljs` and
  `com-backblaze-secure/b2-cli.cljs`).

  Also fixes a second real incident found in the same session: `op read`
  against a stale/expired 1Password CLI session does not fail fast — it
  hangs indefinitely on an interactive re-auth prompt that a non-TTY child
  process can never answer. Every call here gets a timeout; the default
  (5s) fits credential lookups, which must always be near-instant. Callers
  doing real data-plane work (e.g. large file transfers) should pass a
  longer `:timeout` explicitly.")

(def child-process (js/require "node:child_process"))

(def default-opts
  {:encoding "utf8"
   :timeout 5000
   :maxBuffer (* 64 1024 1024)
   ;; ["ignore" "pipe" "pipe"]: no stdin, stdout/stderr captured into the
   ;; return value below — never inherited to this process's own streams.
   :stdio ["ignore" "pipe" "pipe"]})

(defn sh
  "Run `cmd` with `args` (a seq of strings). `opts` overrides `default-opts`
  (e.g. {:timeout 300000} for a large upload/download, {:env #js {...}} to
  scope credentials to this one call only). Always returns {:exit :out
  :err} — never throws, so callers can branch on `:exit` without a
  try/catch. `:err` falls back to the exception's `.message` (e.g.
  \"spawnSync b2 ENOBUFS\") whenever the child's own stderr came back
  blank, which happens on failures like a maxBuffer overrun or a timeout
  kill that never got a chance to write anything."
  ([cmd args] (sh cmd args {}))
  ([cmd args opts]
   (try
     {:exit 0
      :out (.toString (.execFileSync child-process cmd (clj->js args)
                                      (clj->js (merge default-opts opts))))}
     (catch :default e
       {:exit (or (.-status e) 1)
        :out  (or (some-> (.-stdout e) .toString) "")
        :err  (let [stderr (some-> (.-stderr e) .toString)]
                (if (or (nil? stderr) (= stderr "")) (.-message e) stderr))}))))
