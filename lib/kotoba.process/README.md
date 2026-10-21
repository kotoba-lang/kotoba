# kotoba-lang/process

**Foundational process spawn for Kotoba** — pure argv/timeout/allowlist policy
plus a host-injected spawn transport. Twin of [`kotoba-lang/fs`](https://github.com/kotoba-lang/fs):
the cell never sees ambient PATH or a shell; it only sees a transport the host
granted. Zero third-party runtime deps; `.cljc` (JVM / SCI / ClojureScript / nbb).

Catalog identity: `:process/spawn` (compiler wire id **20**, ADR-t83).

## Why a protocol, not `ProcessBuilder`

Ambient `ProcessBuilder` / `child_process` is the same class of authority as
ambient `java.nio.file`. This library splits:

- **Pure policy** (`validate-spawn`, basename allowlist) — no OS
- **Transport** (`IProcess` / `os-spawn`) — host injects absolute binaries only

There is **no default PATH scan**. The host must pass
`:binaries {"git" "/usr/bin/git", …}`. Basename validation refuses path
separators in argv[0]; the transport only runs mapped absolute paths.

## Surface

`kotoba.lang.process`:

- `validate-spawn` — pure; returns `nil` or an error keyword
- `exec` — one-shot array exec: `(exec argv)` → `{:status N :stdout :stderr}`.
  Runs the command directly (no shell: JVM `java.lang.ProcessBuilder`
  directly — the same real-spawn primitive `process-host/sh` uses, this
  library does not require `clojure.java.shell`; CLJS `child_process` array
  exec), capturing stdout. Missing command fails closed (non-zero `:status`,
  no throw). Bounds apply `validate-spawn` (max-argv 64, per-arg byte cap,
  path-command rejection); optional second arg is a basename allowlist.
- `IProcess` protocol — `(spawn! proc request)`
- `echo-process` — test double (exit 0, stdout = joined argv rest)
- bounds: `max-argv`, `max-arg-bytes`, `max-stdout-bytes`, `max-timeout-ms`

`kotoba.lang.process-host` (separate namespace — keeps `process` free of OS
except the convenience `exec`):

- `os-spawn` — `#?(:clj ProcessBuilder, :cljs child_process.spawnSync)`
- `resolve-binary`, `absolute-path?`
- `sh` — policy-gated `clojure.java.shell/sh` drop-in, see below

```clojure
(require '[kotoba.lang.process :as proc]
         '[kotoba.lang.process-host :as host])

(def p (host/os-spawn {:binaries {"echo" "/bin/echo" "git" "/usr/bin/git"}}))
(proc/spawn! p {:argv ["echo" "hi"] :timeout-ms 5000 :max-stdout-bytes 65536})
;; => {:tag :ok :exit 0 :stdout "hi\n" :stderr ""}

;; Other namespaces that just need a one-shot exec (no allowlist infra)
(proc/exec ["echo" "hi"])
;; => {:status 0 :stdout "hi\n" :stderr ""}
```

## `sh` — a real, policy-gated `clojure.java.shell/sh` drop-in

`kotoba.lang.process-host/sh` is the transport this migration piece
(`clojure.java.shell`, 432 require sites workspace-wide) exists to replace.
Return shape mirrors `clojure.java.shell/sh`: `{:exit <int> :out <string>
:err <string>}` — not `os-spawn`'s `{:tag :exit :stdout :stderr}` or `exec`'s
`{:status :stdout :stderr}`. The argument grammar of `process-host/sh` is
`(sh cmd & args)` with an optional trailing options MAP; clojure.java.shell's
own grammar is keyword/value options after the leading strings
(`(sh "git" "status" :dir d)`). `process-host/java-shell-sh` parses that
grammar, and it is what `kotoba.process/sh` re-exports — the name a call site
migrated off clojure.java.shell uses (2026-09-24). It throws for `:env`,
`:in-enc`, `:out-enc` and a non-string `:in` rather than ignoring them.

```clojure
(host/sh "echo" "hi" {:allowed #{"echo"}})
;; => {:exit 0 :out "hi\n" :err ""}

(host/sh "cat" {:allowed #{"cat"} :in "piped in\n"})
;; => {:exit 0 :out "piped in\n" :err ""}

(host/sh "touch" "f" {:allowed #{"touch"} :dir "/tmp"})
;; => {:exit 0 :out "" :err ""}   ; creates /tmp/f

(host/sh "rm" "-rf" "/" {:allowed #{"echo"}})
;; => {:exit -1 :out "" :err "sh rejected: not-allowed"}
;; rm was never invoked — see "Policy enforcement" below.
```

**Synchronous, on purpose.** `sh` blocks until the child process exits and
only then returns — the same contract real `clojure.java.shell/sh` callers
depend on. There is no async/promise/future under this name; introducing
one would silently break every caller that expects a synchronous return.
JVM: `java.lang.ProcessBuilder` directly (this library does **not** require
`clojure.java.shell` itself — depending on it here would defeat the point of
migrating off it). ClojureScript/nbb: Node's `child_process.spawnSync`
(synchronous by construction, never the async `spawn`/`exec`).

**Policy enforcement, not just policy computation.** Every call routes
through the existing `validate-spawn` FIRST. If it rejects the argv — bad
shape, a path separator in argv[0], or (when an `:allowed` set is supplied)
argv[0] not in it — `sh` returns `{:exit -1 :out "" :err "sh rejected:
<reason>"}` immediately, **without ever calling ProcessBuilder or
spawnSync**. This is checked by test, not just asserted: the test suite has
the "rejected" command `touch` a sentinel file and confirms the file never
appears when the policy denies it (and *does* appear when the exact same
call is allowed) — proving the process itself never launched, not merely
that the return value looked like a rejection.

Supported opts: `:in` (string → child's stdin, then closed so `cat`-like
readers see EOF), `:dir` (working directory, string), `:allowed` (optional
`validate-spawn` basename allowlist — omit to skip it; structural checks
still apply), `:max-stdout-bytes` / `:timeout-ms` (override the library's
default bounds; values above the library's own constants are themselves
rejected by `validate-spawn`).

**Not implemented — documented, not silently approximated:**

- `:out` (stdout encoding / `:bytes`) — always returns a UTF-8 string.
- `:env` (per-call environment override) — the child inherits this
  process's environment unchanged.
- exact `clojure.java.shell` argument stringification — argv elements are
  passed through plain `str`, which differs from `clojure.java.shell`'s
  `stringify-arg` for some values (e.g. keywords). Stringify your own args
  first if you need byte-identical behavior.
- unbounded execution — real `clojure.java.shell/sh` blocks forever if the
  child never exits. `sh` always applies `:timeout-ms` (default
  `process/max-timeout-ms`, 600000ms) and force-destroys the child if
  exceeded, consistent with this library's other fail-safe bounds.

## Relation to `provider.process`

`kotoba-lang/provider` owns the **typed kit** (`provider.process` +
`provider.process-transport`) that amu/kototama bind as capability id 20.
This repo is the **foundational stdlib** the same way `fs` sits under
`provider.scoped-fs`: apps that only need spawn without KIR value codecs
depend here. The policy vocabulary (`:process/not-allowed`, …) is kept aligned.

## Install

```clojure
io.github.kotoba-lang/process {:git/sha "<sha>"}
```

## Verify

```sh
kbb -M:test                              # JVM
kbb --backend sci --classpath src:test run-tests.cljk      # nbb / ClojureScript
```

Both run the **same** `.cljc` suite (`sh`'s tests are ordinary portable
deftests — no `#?(:clj ...)`/`#?(:cljs ...)` split needed, since `sh` itself
dispatches internally): JVM `13 tests, 39 assertions, 0 failures`; nbb
`11 tests, 33 assertions, 0 failures` (2 fewer tests on nbb: two pre-existing
`#?(:clj ...)`-only `exec` tests that exercise JVM-specific
`java.lang.ProcessBuilder` exception behavior, unrelated to `sh`).

`kotoba.lang.process` itself no longer requires `clojure.java.shell` anywhere
— `exec`'s JVM branch was rewritten onto `java.lang.ProcessBuilder` directly
(the same real-spawn primitive `process-host/sh` uses), closing a
pre-existing gap where this library's own `exec` convenience function
silently depended on the exact thing it exists to replace.
