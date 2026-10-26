# kuro

`kuro` is the Kotoba **terminal** model for [`kobo`](https://github.com/kotoba-lang/kobo)
— the interactive terminal / console layer of the Kotoba workbench
(ADR-2606301000). If you are looking for a terminal, a console, a shell
session, a TTY surface, or command execution with an audit trail in this
workspace, this is the repository. The name carries none of that, which is why
this paragraph does.

`kuro.terminal` is portable `.cljk` and contains no
direct shell, PTY, filesystem, network, thread, or clock access. A host
provides those effects; `kuro` defines the data contract that makes terminal
sessions auditable.

```text
kuro = terminal session + command intent + effective grant + receipt
```

**Status: R2** — the model is stable and a real backing runs commands with
streaming output, stdin and cancellation. Not a PTY (see *Not a PTY* below).

## Model

Terminal modes are explicit:

| mode | purpose |
|---|---|
| `:terminal-repo` | default grant: repo read, tmp write, no secrets |
| `:terminal-build` | build grant: repo read/write, cache, bounded net |
| `:terminal-agent` | durable agent tick terminal |
| `:terminal-host` | signed opt-in escape hatch |

The host may implement the backing with a local sandbox, container, microVM, or
aiueos surface provider. `kuro.terminal` only records the intent and verifies
the portable shape.

A receipt is uniformly `:kuro/*`. Host-supplied result keys are namespaced on
the way in and keys outside the declared set are dropped, so one host cannot
widen the shape another host will not produce.

## Example

```clojure
(require '[kuro.terminal :as t])

(def session
  (t/session "s1" "repo-cid" :terminal-repo
             {:kuro/cwd "."
              :kuro/grant {:capabilities #{"repo/read" "tmp/write"}}}))

(def cmd (t/command ["kbb" "-M:test"]))

(t/receipt session cmd {:exit-code 0 :stdout "ok\n" :stderr ""})
```

## Running commands for real — `kuro.host.node`

`kuro.host.node` is the Node (nbb) host provider for one-shot commands. It is ClojureScript, not `.cljc`, because the effect belongs to
the host and the model stays portable without it.

```clojure
(require '[kuro.host.node :as host])

(host/run session (t/command ["git" "status" "--short"]) {:repo-root "."})
;; => {:kuro/type :kuro/receipt :kuro/exit-code 0
;;     :kuro/stdout "…" :kuro/stdout-cid "bafkrei…" :kuro/duration-ms 41 …}
```

### What it enforces

| guarantee | mechanism |
|---|---|
| denial before execution | missing capability ⇒ denial map, no spawn |
| no shell interpolation | argv vector, `:shell false` |
| cwd confinement | resolved path must stay under the repo root |
| no ambient environment | the child env is the declared manifest; `process.env` is never passed |
| bounded time | `:timeout-ms`, default 120 s ⇒ exit 124, `:kuro/timed-out?` |
| bounded output | `:max-output-bytes`, default 1 MiB ⇒ exit 125, `:kuro/truncated?` |
| content-addressed output | stdout/stderr as CIDv1-raw/sha2-256 (`bafkrei…`) |

### The mode is a grant scope, not an isolation level

The default mode is `:terminal-repo`, not `terminal-safe`. It was renamed on
2026-08-04 because nothing here confines the filesystem or the network, and
"safe" was the one word in the vocabulary claiming otherwise — read by an
operator deciding what to run.

Every receipt carries `:kuro/isolation`, defaulting to `:none`. A host that
really confines (container, microVM, aiueos surface provider) puts its own
value there. **A receipt that omits it would be read as though it had been
isolated**, so it is never omitted.

### What it does not enforce

A capability set is an **intent record, not a kernel.** This provider does not
confine filesystem writes, does not block network access, and does not isolate
the process namespace. A command granted only `repo/read` can still write to
disk; nothing stops it but the receipt saying it should not have.

That is the documented split — the backing may be a sandbox, container, microVM,
or aiueos surface provider. This is the smallest honest backing: enough to
produce real receipts from real commands, not enough to run untrusted code.
`:terminal-host` has no backing here at all and is refused.

One measured caveat: on macOS, CoreFoundation injects
`__CF_USER_TEXT_ENCODING` into every child below the spawn API. The manifest is
everything this provider passes, not literally everything the child sees.

## Streaming, stdin, cancellation — `kuro.host.stream-node`

`run` is synchronous: it returns only when the command is over, which makes a
ten-minute build and an infinite loop look identical to the caller. The
streaming provider fixes that.

```clojure
(require '[kuro.host.stream-node :as sh])

(def h (sh/start session (t/command ["npm" "test"])
                 {:repo-root "."
                  :on-chunk (fn [st chunk] (print (:text chunk)))
                  :on-exit  (fn [receipt] ...)}))

((:write h) "y\n")      ; stdin
((:close-stdin h))
((:kill h))              ; SIGTERM
@(:stream h)             ; the live kuro.stream value, readable at any moment
```

`sh/run-async` wraps it in a Promise resolving to the receipt.

The same guarantees apply — capability check before spawn, argv with no shell,
cwd confinement, declared environment, deadline, output cap. The cap is
enforced across **both** streams together by `kuro.stream`, which also records
how many bytes it dropped: a silently-cut receipt is indistinguishable from a
short success.

`dropped-bytes` counts **bytes the host actually read from the pipe and then
discarded**. When the cap fires, the provider stops reading and kills the
child, so bytes still sitting unread in the OS pipe are *not* counted: the sum
`stdout-bytes + stderr-bytes + dropped-bytes` is a lower bound on what the
child wrote, not an exact total. This is deliberate — kuro is a pipe, not a
PTY, and the host cannot count what it never read. `kuro.stream` drops
chunk-wise (a chunk that does not fit whole is dropped whole), so what is kept
is always an exact prefix of the emitted output.

## Surviving the host — `kuro.checkpoint`

A `kuro.stream` value lives only in memory: if the host dies, both *what was
running* and *how far it got* die with it. `kobo.agent`'s durable loop cannot
sit on that.

```clojure
(require '[kuro.checkpoint :as cp])

(cp/->edn @(:stream h))                  ; a plain EDN value — write it anywhere
(cp/restore saved)                       ; back, as a stream
```

Pure `.cljk`: this namespace converts, it does not persist. **Writing is the
host's job**, so the choice of file / kotobase / DataLad does not reach here.

Two things it refuses to pretend:

- **A restored run is never `:running`.** Its process did not survive the
  host, so it comes back `:orphaned` (with `:kuro/restored-from` keeping what
  it was). Returning `:running` would invite the caller to send stdin to a
  corpse.
- **`cp/abandon` closes an orphan into a receipt** — exit 129 and a stated
  reason by default, or whatever the host actually knows. A run that cannot be
  closed leaves an open hole in the ledger.

`:max-chunk-bytes` truncates the saved body and records
`:kuro.checkpoint/dropped-bytes`; the byte counters keep the pre-truncation
truth. Off by default — capping is the storage's business, not this layer's.

## Long-running sessions — `kuro.host.supervisor`

`kuro.host.stream-node` gives you one live handle per command and leaves the
bookkeeping to you. `kuro.host.supervisor` is a registry above that: it spawns
under a name, streams output into the registry, and keeps sessions addressable
while they run and after they exit.

```clojure
(require '[kuro.host.supervisor :as sup])

(def s (sup/new-supervisor))
(sup/start! s "build" session (t/command ["npm" "test"])
            {:repo-root "." :on-exit (fn [receipt] ...)})

(sup/session-states s)        ; => {"build" :running}
(sup/read-window s "build")   ; the chunks streamed since the last read
(sup/receipt-of s "build")    ; the receipt, once the process has exited
```

### What it enforces

| guarantee | mechanism |
|---|---|
| no session on denial | a grant denial in `start!` registers nothing and creates no child |
| exact-once delivery per window | `read-window` advances the window cursor (tmux semantics) — re-reading a window does not replay |
| detach is honest | `detach-window!` stops delivery, **not** the child; output keeps accumulating in the registry and the gap is readable later |
| attach is forward-only | `attach-window!` / `reattach-window!` start at the current position — nothing already streamed is replayed, nothing after is lost |
| restore is honest | restoring a `snapshot` into a fresh supervisor yields `:orphaned` with `:suspended` attachments — never `:running` — because the process did not survive |
| no invented receipts | `kill!` on a restored (handle-less) session marks it finished **without a receipt**; a process this host never ran has no host-measured exit values |
| names and windows are distinct | `start!` binds the session under `name` and the window under `:window-id` (default `name`); a caller-supplied `:window-id` is the attachment id, while state and receipts stay keyed by session name |

### What it does not do

- **Persistence is the caller's job.** The supervisor is an in-memory registry;
  bridging to `kuro.checkpoint` / disk is explicit (`sup/snapshot` produces the
  EDN-able value; nothing writes it for you).
- It is still a pipe, not a PTY — everything in *Not a PTY* above applies.
- Receipts still carry `:kuro/isolation` and only declared `:kuro/*` keys; the
  supervisor neither widens them nor bypasses the grant check.


## Reading real output — ANSI escape sequences (`kuro.ansi`)

Command output is not plain text. `kuro.ansi` turns it into styled lines.

```clojure
(ansi/lines "\u001b[32mok\u001b[0m\nnext")
;; => [[{:text "ok" :style {:fg "green"}}] [{:text "next" :style {}}]]
```

Handled: SGR (bold/dim/italic/underline/inverse/strike, 8 + bright + 256 +
truecolor, resets), `\r` in-line overwrite, `\b`, tab expansion, and `CSI K`
erase — which is what actually collapses a progress bar (a bare `\r` leaves
the tail, on a real tty too). OSC 8 hyperlinks drop the URI and the sequence
but keep the linked words — a hyperlink wraps visible text, and losing the
words would make the log lie. Everything else — cursor addressing, scroll
regions, alternate screen, window-title OSC — is **discarded**, never printed.

### Not a PTY

The child is connected to **pipes**, not a pseudo-terminal. `isatty` is false,
so many programs disable colour and switch to line buffering; full-screen
programs (`vim`, `top`) do not work; there is no terminal size and no
SIGWINCH. The declared environment sets `TERM=dumb` rather than lying about
it.

`kuro.ansi` is a line-oriented reader, not a screen emulator — it has no
cursor grid and no scrollback. A real PTY needs a native addon (node-pty or
equivalent), which is a dependency decision this repo has not taken.

## A browser backing — `kuro.fs` + `kuro.host.stream-browser`

In a browser there is no process to spawn and no disk — so the host seam is
filled differently, and the receipts say so.

### `kuro.fs` — a filesystem whose substrate is a CID DAG

`kuro.fs` is portable `.cljk` (the same source runs on the JVM, under nbb,
and in a browser via the shadow-cljs build). Paths map onto a content-
addressed DAG: a directory is an IPLD map block, a file is a unixfs file
DAG (`tech-ipfs-specs-unixfs` — not re-implemented here). The host injects
two effects:

    put-block : bytes -> cid
    get-block : cid -> bytes | nil

The production wiring is an OPFS-backed cache in front of the kotobase
gateway (`kuro.host.opfs`); tests use an in-memory atom. Writes are
immutable — every write produces a new root, so undo is remembering a
previous root. Denied work (path traversal, missing paths, non-empty-dir
removal) produces recorded receipts, not exceptions — an empty receipt list
must not mean both refused and never asked.

### `kuro.host.opfs` — the block store Worker

A dedicated Worker holds OPFS sync access handles (a Worker-only API) and
speaks a closed op vocabulary (`put` / `get` / `delete` / `publish` /
`stats` / `drop-cache`). CIDs are minted with WebCrypto sha-256 inside the
Worker; the math is parity-locked with `kuro.host.cid` (node:crypto) and the
independent Python mint at `scripts/cid_mint.py` (pinned by
`test:kuro.host.opfs/python-mint-parity` and gated in CI — a mint nobody
runs would be a claim nobody checks). `publish` verifies each block's bytes hash to its
claimed CID before counting it. `delete` is **idempotent**: removing a cid
that is not cached succeeds with `{removed: false}` (never an error), while a
real failure (open handle, permission, quota) surfaces as a `:kuro.opfs/error`
reply — a bare `ok: false` that cannot distinguish "not cached" from "failed"
is not the contract. `drop-cache` reports `{removed: n}` — a partial failure
mid-removal is visible in the reply, not collapsed into a generic
`worker-error` with no count. OPFS is origin-scoped **cache** — durable
custody is kotobase (`PUT/GET kotobase.net/ipld/:cid`), and publish is an
explicit op, never automatic.

### `kuro.host.stream-browser` — terminal host over a guest component

The `stream-node` shape (start / write / kill / on-chunk / on-exit) with a
guest-component backing instead of a spawned process. Commands are guest
invocation specs (guest CID + export + args); **argv vectors are denied with
`:argv-not-a-process`** — a browser has no processes, and a receipt that
pretended otherwise would lie about what ran.

### Isolation, on the record

Every browser-host receipt carries `:kuro/isolation :browser-origin`, which
records: ran in a Worker, no DOM, no ambient authority, effects only through
capability-gated host imports. It does **not** claim kernel-level
sandboxing — a capability set is an intent record, not a kernel (same rule
as above). The gate is real where it can be: the host refuses to satisfy a
guest's `fs_read` import unless the grant covers it, and fs/write implies
nothing about fs/read (separate leaves).

### Verified end-to-end

- real OPFS round-trip with WebCrypto-minted CIDs (byte-identical across
  node:crypto, WebCrypto-in-Worker, and an independent Python mint)
- a real WASM guest (assembled with wasm-tools) streaming its output into
  `kuro.stream` and finishing with an isolated receipt
- `kuro.fs` itself running in the browser (shadow-cljs build) writing,
  listing, and reading back byte-identical through the OPFS store
- a guest reading a `kuro.fs`-written file through a gated `fs_read` import,
  with the un-granted capability refused
- a real WASM guest running *inside a Worker* (not the page): the page only
  postMessages a start request, and the guest's memory and i32 exit code cross
  the worker boundary as a `kuro.stream` stdout chunk and an exit message

See `test/browser/verify_*.cljk` (one file per entry above) and ADR-2609041240.

## Browser JS / Python function tools

The browser backing can also consume agent function calls named `js` and
`python`. Each call runs in a fresh Worker and returns JSON results, UTF-8
stdout/stderr, selected files, and a terminal receipt. A main-thread timeout
or AbortSignal terminates even a synchronous infinite loop.

```sh
npm ci
npm run build:browser-tools
npm run serve:browser-tools
# Open http://127.0.0.1:8123
```

The build serves fixed QuickJS/Wasm and Pyodide assets locally, with no CDN.
The Python runtime exposes its JS bridge and requires an extra
`tool/python-js-bridge` grant; it is for trusted code on a dedicated origin.
It does not provide untrusted-tenant network/storage confinement or a hard
Python memory limit.

```js
import {createToolHost, toolDefinitions, toToolMessage} from './client.js';
const host = createToolHost({capabilities: ['tool/js']});
const response = await host.call({id: 'call_1', type: 'function', function: {
  name: 'js', arguments: JSON.stringify({code: 'inputs.a + inputs.b', inputs: {a: 20, b: 22}})
}});
// response.result === 42; response.receipt['kuro/exit-code'] === 0
const message = toToolMessage(response); // role: tool, tool_call_id: call_1
// Pass toolDefinitions to the model and message back into its conversation.
```

`kuro.host.tool-browser/create` derives admission from a terminal session.
Its `call-with-filesystem` adapter imports explicit paths from `kuro.fs` and
writes explicit exports back through the existing block-store effects.
See [the browser tools decision](docs/adr/0001-browser-js-python-tool-calls.md)
for capability, isolation, memory, filesystem, and async boundaries.

The current Hermes Agent was also probed inside this actual browser Python
host. Its pure iteration budget works, but the unmodified agent import,
thread-backed tool pool, and subprocess requirements are blocked. See the
[Hermes browser verification and raw evidence](docs/verification/hermes-browser.md)
before treating a working Python tool as a working browser-local Hermes agent.

## Tests

```sh
kbb -M:test                     # portable model + ansi + stream (JVM)
npm install
npm run test:parity                 # the SAME .cljk suites under ClojureScript (nbb; kbb's SCI backend)
npm run test:host                   # both Node host providers (nbb)
```

All three run in CI.

`test:parity` exists because "portable `.cljc`" was a claim nobody checked. For
one day `kuro.ansi` was green on the JVM and **silently produced no output at
all under ClojureScript** — `(int c)` is `NaN` there, so the CSI scanner never
found a final byte and discarded everything. The consumer that broke was
`kobo`'s server, which runs on nbb. A `.cljc` namespace tested on one runtime
can be entirely dead on the other.

### Experimental Hermes browser profile

The [Hermes browser profile](docs/verification/hermes-browser-profile.md) adds
locked Wasm-compatible dependencies, browser model transport, serial execution,
and Kuro JS/Python tools to the original Hermes conversation loop. Local Chromium
qualification uses a model fixture. [Streaming and browser conversation
restart/resume](docs/verification/hermes-browser-streaming.md) are verified;
real-model qualification is recorded separately. Native process tools are not
qualified. Reproduce with `prepare:hermes-browser` and `test:hermes-browser`.

The browser Hermes local relay uses Hugging Face dedicated Inference Endpoints.
See [connection and verification instructions](docs/verification/hermes-browser-streaming.md#real-model-qualification).
Live inference remains unqualified until the Endpoint accepts an authorized token;
the recorded live attempt returned 401. Browser fixture tests do not prove live inference.
