# kotoba-lang/fs

**Layer 3 (I/O) of the kotoba foundational stdlib** — pure path manipulation
plus an `IFilesystem` **protocol** the host injects. A capability-confined cell
never touches the OS directly; it only sees a filesystem handle the host
granted. Zero third-party runtime deps; every namespace is `.cljc` (JVM / SCI /
ClojureScript / GraalVM / kotoba-WASM). See
[`docs/adr/ADR-kotoba-lang-foundational-stdlib.md`](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/adr/ADR-kotoba-lang-foundational-stdlib.md).

## Why a protocol, not the OS

The kotoba-WASM premise forbids direct OS access. `fs` splits cleanly: the
**path ops** (`join`, `split`, `basename`, …) are pure functions anyone can
call; the **effectful ops** (`read`, `write`, `list`, `exists?`, `delete`) live
behind `IFilesystem`, which the host implements and injects. An in-memory
`mem-filesystem` is provided for tests and OSS-standalone use — same seam as
`kotobase.store/IStore` and `num.protocol/IBackend`.

## Current surface

`kotoba.lang.fs`:

- Pure path ops: `join`, `split`, `basename`, `dirname`, `normalize`, `ext`,
  `relative?`, `absolute?`
- `IFilesystem` protocol: `read`, `write`, `list`, `exists?`, `delete`
- `IAsyncFilesystem` protocol: `read-async`, `write-async`, `list-async`,
  `exists-async?`, `delete-async`
- `mem-filesystem` — atom-backed in-memory impl (OSS standalone / tests)

`kotoba.lang.fs-host` (separate namespace — see below):

- `host-filesystem` — an `IFilesystem` backed by the real filesystem,
  `#?(:clj java.nio/java.io, :cljs node:fs)`, confined to a required `:root`
- `async-host-filesystem` — the same capability and refusal vocabulary through
  `CompletableFuture` on JVM and native `fs.promises` on Node
- `resolve-relative` — the pure path policy, usable on its own
- `under-root?`, `error-types`, `max-path-bytes`, `default-max-bytes`

## The real filesystem: `kotoba.lang.fs-host`

`kotoba.lang.fs` stays pure so a kotoba-WASM cell can require it. The binding
to an actual OS filesystem lives in its own namespace, the way
`provider.http-transport` sits beside `provider.http` — requiring
`kotoba.lang.fs` pulls in no `java.nio` and no `node:fs`, and a test greps both
sources to keep it that way.

```clojure
(require '[kotoba.lang.fs :as fs]
         '[kotoba.lang.fs-host :as host])

(def h (host/host-filesystem {:root "/srv/app/data" :max-bytes 1048576}))

(fs/write h "notes/x.txt" "hello")
(fs/read  h "notes/x.txt")     ;=> "hello"
(fs/list  h "notes")           ;=> ["x.txt"]
(fs/read  h "../../etc/passwd") ;=> throws, :type :fs/escape
```

The asynchronous handle performs the same canonical root proof and byte bounds
before dispatch. It never accepts a path or authority that the synchronous
handle would refuse. JVM work leaves the caller thread through a
`CompletableFuture`; Node uses `fs.promises` rather than wrapping synchronous
I/O in a resolved Promise. `eventual-error-type` recovers the stable refusal
keyword across Future/Promise/SCI wrapper causes.

**`:root` is required and there is no default** — not CWD, not `$HOME`, not
`/tmp`. Every path is resolved against it and REFUSED, never silently clamped,
when it tries to leave. The refusal codes are taken verbatim from
`provider.scoped-fs/resolve-path`:

| `:type`             | refused                                          |
|---------------------|--------------------------------------------------|
| `:fs/empty-path`    | blank path, all-blank segments                    |
| `:fs/null-byte`     | any NUL                                           |
| `:fs/backslash`     | any `\\`                                          |
| `:fs/absolute`      | leading `/`                                       |
| `:fs/home-escape`   | leading `~`                                       |
| `:fs/path-too-long` | over 1024 UTF-8 bytes                             |
| `:fs/escape`        | any `.`/`..` segment; a symlink resolving outside |
| `:fs/not-found`     | missing file or directory                         |
| `:fs/too-large`     | over `:max-bytes` (checked from `stat`, before reading) |
| `:fs/is-directory` / `:fs/not-a-directory` | wrong kind of node        |
| `:fs/io`            | a host failure, with its message under `:fs/message` |
| `:fs/bad-root`      | `:root` missing, relative, or not a directory     |

Every failure is an `ex-info` with a stable `:type`, so a caller branches on a
keyword instead of naming `java.io.IOException` (which cannot cross to cljs).

Two things this namespace deliberately does not do: there is **no
`slurp`/`spit` convenience** (that would restore the ambient authority the
protocol exists to remove), and `read` of a missing file **throws
`:fs/not-found`** rather than returning `nil` the way `mem-filesystem` does —
the one behavioural difference to check when swapping a mem handle for a host
one.

## Install

```clojure
io.github.kotoba-lang/fs {:git/sha "<sha>"}
```

## Use

```clojure
(require '[kotoba.lang.fs :as fs])

(fs/join "a" "b" "c.txt")              ;=> "a/b/c.txt"
(fs/ext "a/b/c.txt")                   ;=> "txt"
(let [m (fs/mem-filesystem)]
  (fs/write m "dir/x.txt" "hello")
  (fs/read m "dir/x.txt")              ;=> "hello"
  (fs/list m "dir")                    ;=> ["x.txt"])
```

## Verify

Both runtimes run the same suite, against a real temp directory:

```sh
kbb -M:test                                  # JVM
npm run test:cljs                                # nbb / Node
kbb --backend sci --classpath src:test:../text/src test/run_portable.cljk  # the same thing, without npm
kbb -M:lint
```
