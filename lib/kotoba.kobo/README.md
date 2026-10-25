# kobo

`kobo` is the Kotoba **workbench**: code editor, **terminal / console surface**,
durable agent loop model, and audit-oriented repository view (ADR-2606301000).
If you are looking for a terminal, a console, a shell surface, or an IDE-shaped
development environment in this workspace, `kobo` and
[`kuro`](https://github.com/kotoba-lang/kuro) are it. Neither name says so,
which is why this paragraph does.

The model is portable `.cljc`. It does not own filesystem, shell, network,
secrets, browser, or desktop effects. Those are host capabilities.

```text
kobo = editor + terminal + grants + receipts + repo facts
kuro = terminal model used by kobo
```

**Status: R2** — `npm run console` serves a live workbench on 127.0.0.1: run a
command, watch its output stream in, send stdin, kill it. Editing is not
wired; see *Not yet built*.

## Boundaries

| layer | role |
|---|---|
| `kobo.workbench` | panes, buffers, terminal sessions, receipts, denials |
| `kobo.editor` | buffers, deterministic patch application, diagnostics |
| `kobo.grant` | capability intersection and denial explanation |
| `kobo.ui` | the read-only workbench console (kotoba-ui / appkit) |
| `kobo.host.node` | runs one command to completion, via `kuro.host.node` |
| `kobo.host.stream-node` | runs a command **live** — output, stdin, kill — via `kuro.host.stream-node` |
| `kuro.terminal` | terminal sessions and command receipts |
| host / aiueos | actual process, PTY, container, microVM, filesystem, network |

## Example

```clojure
(require '[kobo.workbench :as wb]
         '[kobo.host.node :as host]     ; nbb / Node only
         '[kobo.ui :as ui])

(-> (wb/workbench "repo-cid")
    (wb/open-buffer (wb/buffer "README.md" "# hello\n"))
    (wb/open-terminal "t1" :terminal-repo)
    (host/run "t1" ["git" "status" "--short"] {:repo-root "."})
    (ui/console))
;; => "<!doctype html>…kobo — workbench console…"
```

A command whose capabilities the session does not grant is **recorded as a
denial**, not dropped — otherwise an empty receipt list means both "refused"
and "never typed".

## Use it — `npm run console`

```sh
npm install
npm run console                              # http://127.0.0.1:7777/
npm run console -- --port 8080 --repo-root ../kuro
```

It prints a URL and a per-start token. Open the URL: you get the console with
a command bar — type an argv, hit **Run**, watch output arrive as it is
produced, send **stdin**, **Kill** it.

### This endpoint starts processes — how it is kept narrow

| | |
|---|---|
| bind | **127.0.0.1 only.** There is no `--host` flag; a "you could set 0.0.0.0" shape eventually gets set to 0.0.0.0 |
| write paths | `POST /run` `/stdin` `/kill` require the per-start `X-Kobo-Token` **header** — a custom header forces a CORS preflight, so another page cannot silently POST here |
| origin | non-localhost browser origins are refused |
| token | printed on stdout, never put in a URL (URLs land in history) |
| execution | unchanged from `kuro` — capability check, argv with no shell, cwd confinement, declared env, deadline, output cap. **The server relaxes none of it** |

**It is still not isolation.** A capability set is an intent record, not a
kernel: a command you run here touches this machine's disk and network. This
is a local tool for your own repo, not a sandbox for untrusted code.

### The browser glue is the one piece of raw JavaScript

`kobo` has no ClojureScript browser build (nbb targets Node), so the ~20 lines
that wire clicks to `fetch` and an `EventSource` to `innerHTML` are an inline
`<script>` string. It is marked **non-authoritative**: no logic goes there. The
day it needs a branch is the day to decide whether kobo gets a cljs build.

## Running a command live

`kobo.host.node/run` returns only when the command is over. For anything that
takes time, put the workbench in an atom and stream into it:

```clojure
(require '[kobo.host.stream-node :as sh])   ; nbb / Node only

(def w (atom (-> (wb/workbench "repo-cid") (wb/open-terminal "t1" :terminal-repo))))

(def h (sh/start w "t1" ["npm" "test"] {:repo-root "."}))
((:write h) "y\n")   ; stdin
((:kill h))           ; stop it
```

While it runs it is in `:kobo/running` (the live `kuro.stream` value); when it
exits it moves to `:kobo/receipts`. The console renders both, in separate
sections — "not finished yet" and "finished, exit 0" are different facts and
must not share a row.

## The console

`kobo.ui/console` renders the read-only half of the workbench the ADR
describes: terminal sessions with their effective grants, command receipts
(argv, outcome, duration, stdout/stderr CID), refusals, open buffers,
diagnostics — and **command output with its ANSI colours interpreted**, via
`kuro.ansi`.

Terminal colours are mapped onto HIG palette tokens, never to inline hex: the
console keeps the design system's light/dark switching and contrast
guarantees. Two deliberate infidelities — terminal `black` and `white` mean
"the opposite of this terminal's background", not absolute colours, so both
render as the default label colour. 256-colour and truecolour spans lose their
colour but keep their text. **A readable approximation beats an unreadable
faithful one.** Output is capped at 200 lines on screen, and the cap says how
many lines it dropped.

Following the operator-console convention used across kotoba-lang (`dtn`,
`card`, `ekyc`, `securities`, …), it exposes **no write surface** — no
`<form>`, no `<button>`. Command entry and editing are not wired, and a text
box that cannot send anywhere is worse than an absent one.

Built on the `kotoba-ui` + `appkit` stack: layout from `shell`, colors and
type from tokens, one theme map. Every render is scored by the deterministic
HIG/WCAG audit (`design-quality`, ADR-2607132300) with a ≥ 95 gate in CI —
currently **100.0**, no short axes.

### Not yet built

The ADR's full workbench is five panes (file tree, editor tabs, graph/audit,
terminal tabs, status). This is the read-only subset. Missing: event wiring and command entry (the console is still read-only), a
real PTY (the child is on pipes, so full-screen programs do not work), the
`kobo.agent` durable loop, `kobo.repo` (the kotoba-rad/git bridge), the file
tree, and the LSP bridge.

## Rendering in the kotoba browser

The console is rendered by **`kotoba-lang/browser`** — this workspace's own
WASM/`kotoba:dom` engine — as a CI gate, not only by Chrome. If the workbench
UI cannot be drawn by our own browser, our own tools do not work on each other.

```sh
npm run test:browser-render     # monorepo only, see below
```

It asserts the document lays out, that the page's own `<style>` reaches the
engine (over 100 CSS rules — it was **0** until browser learned to read
`<style>` on 2026-08-04), that the workbench's content is really drawn as
glyphs, and that no escape sequence survives into one.

It lives behind its own alias and path because `kotoba-lang/browser` cannot be
consumed by git coordinate: `dom-gpu` ↔ `cssom` ↔ `htmldom` reference each
other with `:local/root`, a cycle git deps cannot express. So the gate runs
where sibling checkouts exist — in the monorepo, or in a CI job that clones
them the way browser's own CI does. **That constraint is inherited from
browser, not invented here.**

## Tests

```sh
kbb -M:test                 # model + console + design-quality gate (JVM)
npm install && npm run test:host  # host wiring + the HTTP server (nbb), for real
```

`test:host` spawns real processes and drives the real server over real HTTP —
including that a coloured command's output reaches the served page as classes.
That last check exists because `kuro.ansi` was once JVM-green and cljs-dead,
and this server is the cljs side.

Monorepo work can point the deps at sibling checkouts with `-M:local:test`.
