# computer-use-clj

Anthropic-computer-use-style desktop automation agent in **portable
Clojure** — every namespace is `.cljc`, designed for
**Clojure-on-WASM hosts** (SCI, ClojureScript, GraalVM, kotoba-clj) as
well as the JVM. The desktop itself is an injected host capability;
the action history is persisted through a **Datomic API**.

Built on [langgraph-clj](https://github.com/com-junkawasaki/langgraph-clj)
/ [langchain-clj](https://github.com/com-junkawasaki/langchain-clj).
Sibling of [browser-use-clj](https://github.com/com-junkawasaki/browser-use-clj).

```
src/computeruse/
  computer.cljc        IComputer protocol (host capability) + mock virtual screen
  tool.cljc            the computer tool — Anthropic action vocabulary → protocol dispatch
  agent.cljc           sampling loop (langgraph StateGraph) + action log as datoms

  backend.cljc         IBackend — WHERE the screen is (observe!/act!/probe!), 10 ids
  backends.cljc        the four implemented backends
  bots.cljc            multi-bot resident layer: roster, action gate, receipts
  model_adapters.cljc  interpretation adapters (claude-cli / murakumo / openai-compat)
  json.cljc            dependency-free JSON, so the CLI runs under nbb
  hostfs.cljc          the filesystem seam
bin/cua_bot_run.cljk   the resident CLI (nbb)
resources/computeruse/backends.edn   the backend registry, with measured qualification
```

## Design

- **Computer = injected host capability** — implement `IComputer`
  (xdotool/screencapture, a VNC sandbox, an OS-automation MCP).
  Screenshots are passed through untouched, so a real host can return
  Anthropic image content blocks while the bundled `mock-computer`
  returns a deterministic text rendering of a virtual screen.
- **Anthropic action vocabulary** — the `computer` tool speaks
  screenshot / key / type / mouse_move / left_click / right_click /
  middle_click / double_click / scroll / cursor_position, defined as a
  custom tool with an explicit `input_schema` (API-compatible without
  the server-defined tool type; hosts that want
  `{:type "computer_20250124" …}` can send that wire format and reuse
  `computeruse.tool/dispatch`).
- **Datomic API premise** — every action becomes a datom
  (`:caction/action`, `:caction/input`, …): "every click in session
  s1" is a Datalog query. Graph checkpoints (resume /
  human-in-the-loop) come from langgraph-clj.

## Selectable execution backends

`IComputer` says *what* you can do to a desktop. `IBackend`
(`computeruse.backend`, ADR-0003) says **where the screen is** — and a
resident bot picks one with a single keyword.

```clojure
(require '[computeruse.backend :as b] '[computeruse.backends])

(def be (b/create-backend :window-scoped {:app "Google Chrome"} {}))

(b/probe! be)    ;=> {:available? true :why "12 on-screen windows; target matches window 2985" …}
(b/observe! be)  ;=> {:png-path "/tmp/cua-win2985-….png" :window {…} :width 1300 :height 800
                 ;    :frame-stats {:stddev 94.4 :blank? false}}
(b/act! be {:kind :script :applescript "tell application \"Google Chrome\" to …"})
(b/act! be {:kind :key :combo "cmd+l"})
;=> {:refused true :reason :backend/unsupported-action-kind …}   ; never a silent no-op
```

Ten ids, fixed. The registry
(`resources/computeruse/backends.edn`) carries each one's isolation
properties — **does it take the operator's focus and cursor?** — and a
per-capability `:qualification` with **the date it was measured**.

| id | what it is | focus? | observe / act (measured 2026-08-29) |
|---|---|---|---|
| `:macos-local` | this machine's whole desktop | **yes** | qualified / **refused** — deny-by-default, needs `:allow-foreground true` |
| `:window-scoped` | one window by CGWindowID | no | **qualified** / qualified (`:script` only) |
| `:agent-space` | a background macOS Space | no | pending / pending |
| `:fleet-node` | a murakumo node over ssh | no | **unavailable** / unavailable |
| `:macos-vm` | a macOS guest VM | no | pending / pending |
| `:linux-container` | a container with Xvfb | no | pending / pending |
| `:cf-browser` | Cloudflare Browser Rendering | no | pending / pending |
| `:cf-sandbox` | a Cloudflare Sandbox container | no | pending / pending |
| `:saas-sandbox` | a hosted computer-use sandbox | no | pending / pending |
| `:host-object` | no screen — a probe command's verdict | no | **qualified** / refused (observation-only) |

Notes on the measured ones, because the table is not the evidence:

- **`:window-scoped` does not focus the window it captures.**
  `screencapture -l <id>` was measured to leave the frontmost
  application unchanged. Its act path is app-scripting only;
  `:pointer` / `:key` / `:type` are refused **permanently** by name,
  because synthetic global input lands wherever the OS focus is, and
  this workstation runs many concurrent agent sessions in terminal
  panes competing for it.
- **Refusing the action kinds was not enough — measured 2026-08-29.**
  In a real session the model wrote `tell application "Google Chrome"
  to activate` followed by `tell application "System Events" to key
  code 116`, and the gate allowed it four steps running because the
  *kind* was `:script`. The `:script` **content** is now checked too:
  System Events `keystroke` / `key code` / `key down|up` / `click at`,
  and `do shell script` / `run script`, refuse with
  `:backend/synthetic-input-in-script` before reaching `osascript`.
  This is a denylist over a language with indirection, so it is a
  floor, not a proof — the structural guarantee is that the kinds are
  refused. A script may still `activate` an app (focus without input);
  when it does, the act result carries `:activated-app? true` so the
  receipt shows it.
- **`:fleet-node` is implemented and does not work today.** judah,
  simeon and zebulun are all ssh-reachable and all have
  `/usr/sbin/screencapture`, but the ssh session has no window server:
  `could not create image from display`, exit 1, no file. `probe!`
  measures that on every call rather than assuming it. Nothing was installed
  on any node.
- **The six `:pending` ids are selectable and honest**: `observe!` and
  `act!` refuse with `:backend/not-implemented`, and `probe!` answers
  `:unmeasured` — never `false`, which would claim a measurement
  nobody took. Each carries a concrete `:unblock` condition.

A capture that worked and a black rectangle both exit 0, so every
visual observation carries `:frame-stats` (a 32px downsample's byte
stddev). A blank frame ends the session as `:could-not-measure`, not
as a passing observation.

## Resident bots

A roster is a vector of entries; one bot is one session.

```clojure
{:bot/id "uiux-bots-page-qa"          ; [a-z0-9][a-z0-9-]{0,63}
 :bot/goal "verify the three live sections render"
 :bot/backend :window-scoped          ; one keyword — this is the promotion knob
 :bot/target {:app "Google Chrome" :url "https://itonami.cloud/bots/"}
 :bot/interval-s 21600
 :bot/max-steps 8                     ; ≤ 24
 :bot/allowed-actions #{:script}      ; ⊆ #{:pointer :key :type :script}
 :bot/budget-tokens 30000}
```

Validation is fail-closed and every rejection has its own reason
literal (`:bot/unknown-backend`, `:bot/blank-goal`,
`:roster/duplicate-id`, …). Backend ids are checked against the
registry, not against a copy of the list.

The loop is **observe → interpret → gate → act**, and the gate is
deterministic and runs before *every* act:

| reason | when |
|---|---|
| `:gate/step-ceiling-reached` | step ≥ `:bot/max-steps` |
| `:gate/budget-exhausted` | tokens ≥ `:bot/budget-tokens` |
| `:gate/malformed-action` | not an action map / unknown kind |
| `:gate/action-kind-not-allowed` | not in `:bot/allowed-actions` |
| `:gate/frame-dimensions-unknown` | the frame did not report its size |
| `:gate/coordinate-outside-frame` | the coordinate is outside it |

A refusal is **recorded in the receipt with its literal** and fed back
to the model as history — never dropped. `:gate/frame-dimensions-unknown`
exists so that a backend which does not report its size cannot earn
unbounded clicks by omission.

### The CLI

```sh
kbb --backend sci bin/cua_bot_run.cljk --roster <path.edn> --bot <bot-id> \
    --receipts-dir <dir> [--dry-run] [--adapter claude-cli|murakumo|openai-compat]
```

Exit codes are three-valued and stay three-valued:

| exit | meaning |
|---|---|
| 0 | the session completed (outcome in the receipt) |
| 1 | the session ran and failed |
| 2 | it could not be measured — invalid roster, unknown bot, backend unavailable, dead adapter, blank frame |

**The nbb path is the one that was verified** (nbb v1.4.208; `nbb.edn`
supplies the classpath, and no namespace the CLI reaches has a
third-party dependency, so it runs from a bare checkout). The library
also compiles and tests on the JVM (`kbb -M:test`), but there is no
JVM entry point for the CLI.

Each session writes a receipt EDN — `{:bot-id :backend :frames
:actions :outcome :started :finished :tokens-used}` — into
`--receipts-dir`. Screenshots stay out of git.

### Two real sessions (2026-08-29, before landing)

`:host-object` / `isekai-touch-qa` — **exit 0**, `:done`, 29s, 999
tokens, zero acts. It ran network-isekai's deterministic touch gate and
concluded from its verdict: *"jintori scene verified responding with
touch stick input handling: 7/7 tests passed, compilation successful,
axis-based input detection working"*.

`:window-scoped` / `uiux-bots-page-qa` — **exit 1**, `:failed`, 7 steps,
8 frames, 10,822 tokens. It captured a Chrome window eight times without
focusing it and ended the session itself with `{:done true :success
false}`: *"Grok runtime and Workstation loops sections are visible and
rendering live data with current timestamps (not stale). No empty
sections or error displays observed in visible content. Hyakka section
not visible in current viewport — unable to confirm its status."*

That is the correct three-valued answer, not a defect: a session that
confirmed two of three sections and said so is not `:done`, and it is
not `:could-not-measure` either. In the same session the script guard
fired in production — step 1's `keystroke "l" using command down` … `key
code 36` was refused and never reached `osascript`.

### Model adapters

An adapter is `(fn [{:keys [prompt image-path]}] → {:text :tokens :adapter})`.
Measured 2026-08-29, both were proved to **actually read the image**,
not merely to accept one:

| adapter | evidence | time |
|---|---|---|
| `:claude-cli` (default) | described a Japanese conversation about bread storage that is visible only inside the screenshot | 9.3s |
| `:murakumo` | answered "the ChatGPT desktop application window" for a capture of the ChatGPT window | 64s |

Neither answer is derivable from the prompt or the file name.

`:murakumo` resolves the `murakumo-main` alias (env override → the
alias entry → an endpoint-only fallback); no concrete model id is
written down anywhere. ⚠ Measured the same day: the endpoint the alias
entry itself declares returned **HTTP 404** for both a text and a
vision request, and `https://api.murakumo.cloud/v1/chat/completions`
answered. The resolver tries the declared endpoint first, falls back,
and records which one answered.

`:claude-cli` shells `claude -p --allowedTools Read --output-format
json`, with the subprocess's cwd set to the directory holding the
screenshot — Claude Code will not `Read` outside its working
directory, and a bot whose frames live in `/tmp` would otherwise get an
"I cannot see an image" answer that looks exactly like a model that
looked and saw nothing. It needs no `--dangerously-skip-permissions`
(measured: `permission_denials` empty).

The existing `computeruse.openai-model` ChatModel adapter is unchanged
and still drives the langgraph loop on the JVM;
`computeruse.bots/backend->computer` binds that loop to any backend.

## Quickstart

```clojure
(require '[computeruse.computer :as c]
         '[computeruse.agent :as agent]
         '[langchain.model :as model]
         '[langchain.db :as db])

;; host capability: real IComputer impl, or the mock virtual screen:
(def vm (c/mock-computer
         {:size [1280 800]
          :windows [{:title "Editor" :rect [0 0 800 600] :content ""}
                    {:title "Terminal" :rect [800 0 480 600] :content "$ "}]}))

(def conn (db/create-conn agent/log-schema))

(agent/run
 {:model (model/anthropic-model {:api-key … :http-fn host-fetch …})
  :computer (:computer vm)
  :display {:width 1280 :height 800}
  :task "Run make test in the terminal"
  :history-conn conn
  :session-id "s1"
  :max-steps 25})
;; => {:result "…" :done true :messages […] :steps n}

;; the audit trail is datoms:
(db/q '[:find ?step ?action
        :where [?e :caction/step ?step] [?e :caction/action ?action]]
      (db/db conn))
```

Extra tools (bash, editors, …) sit alongside the computer tool:

```clojure
(agent/run {:tools [my-bash-tool my-editor-tool] …})
```

## Mapping from upstream

See [docs/adr/0001-architecture.md](docs/adr/0001-architecture.md) for
the computer-use → computer-use-clj correspondence (action vocabulary,
sampling loop, tool wire format) and the host-capability split.

## Credentials from a vault (no raw secrets)

The agent never types a literal password. `computeruse.vault/IVault`
is an injected host capability; the `computer` tool gains a
`type_secret` action that takes a vault *reference*
(`{"item":"Vultr","field":"password"}` or `"op://Vault/Item/field"`),
resolves it through the vault CLI, and types it at the IComputer layer.
The secret never enters the prompt, the message history, or the
Datomic action log (which records only the ref).

```clojure
(require '[computeruse.vault :as vault])
(agent/run {:vault (vault/op-vault {})        ; 1Password: `op` signed in
            ;; or (vault/bw-vault {})         ; Bitwarden: BW_SESSION set
            :computer (macos/macos-computer)
            :system "...use type_secret for credential fields; never type a raw secret..."
            ...})
```

- `op-vault` → `op read op://Vault/Item/field` or `op item get … --reveal`
- `bw-vault` → `bw get password|username|totp <item>` (+ custom fields)
- `mock-vault` → deterministic map for tests

## Local model (Ollama / OpenAI-compatible)

`computeruse.openai-model/openai-model` drives the agent with a LOCAL
model instead of the Anthropic API — vision via image_url, tool-calling
via OpenAI `tools`. `examples/jvm_host.cljk` provides the JVM host caps
(an :http-fn that shells out to `curl`, JSON via data.json).

```sh
# Gemma 4 E4B QAT on Ollama, controlling this desktop:
OPENAI_BASE_URL=http://127.0.0.1:11434/v1 OPENAI_MODEL=gemma4:e4b-it-qat \
VAULT=op VULTR_VAULT_ITEM=Vultr \
  kbb -M:gemma -m vultr-ip-allow 203.0.113.7 32
```

Notes from running Ollama 0.30.x: tool params of `type:"object"` must
include `properties` (a bare object 404s the whole request); tool-call
`arguments` must be a JSON string (not EDN); java.net.http POSTs were
rejected by Ollama's request framing, so the host :http-fn uses curl.
Small models (4-8B) drive navigation/keys/screenshots but are often too
weak to complete multi-step portal UIs reliably — use a larger model or
the Anthropic backend (`MODEL=anthropic`) for hard tasks.

## Real host: macOS

`computeruse.macos/macos-computer` implements IComputer over the live
macOS desktop (screencapture + sips screenshots as Anthropic image
blocks, System Events keys, cliclick mouse — `brew install cliclick`,
grant Screen Recording + Accessibility). Coordinates are auto-scaled
between the model-sized screenshot and display points.

`examples/vultr_ip_allow.cljk` uses it for a real ops task — adding an
IP to a Vultr API key's Access Control list in an already-signed-in
browser session. Hard guardrails in the system prompt: the agent never
types into credential fields and bails out (success=false) when a
login/2FA page appears; it only ever adds the one requested entry.

`examples/sumitclub_meisai.cljk` is a read-only variant — fetching a
card 利用明細 (statement) from sumitclub.jp. Login goes through
`type_secret` (vault ref, never a raw credential), the system prompt
forbids every state-changing control on the site, and the extracted
rows are persisted via a custom `save_statement` tool as EDN, ready
for downstream ingestion. It runs on a **local model by default**
(Ollama serving gemma 4 QAT — tools + vision capable), so statement
data never leaves the machine; `examples/jvm_host.cljk` provides the
JVM host capabilities and the `LLM=ollama|gemini|anthropic` switch
(gemini = Gemini's OpenAI-compatible endpoint with `GEMINI_API_KEY`).

`examples/ngc_free_org.cljk` prepares the frontmost browser for a free
individual NVIDIA NGC organization registration:

```sh
kbb -M:dev:examples -m ngc-free-org
```

The `computeruse.ngc/free-registration-system-prompt` is intended for an
AI-driven inspection loop. It prohibits credential entry, MFA, terms
entry, MFA, terms acceptance, and account creation until it has called the
shared `request_human_approval` tool. The macOS host presents this request as a
native alert containing only the summary, action, and external impact:

```sh
LLM=ollama kbb -M:examples -m ngc-free-org-agent
```

```sh
SUMITCLUB_VAULT_ITEM=sumitclub \
  kbb -M:dev:examples -e "(require 'sumitclub-meisai) (sumitclub-meisai/-main)"
```

```sh
ANTHROPIC_API_KEY=… kbb -Sdeps '{:paths ["src" "examples"]
                 :deps {io.github.kotoba-lang/langgraph
                        {:git/sha "a332a770a0d2b5193f81b54483bb954fb29ef8d7"}}}' \
        -M -e "(require 'vultr-ip-allow) (vultr-ip-allow/-main \"203.0.113.7\")"
```

## Real host: a physical iPhone, through iPhone Mirroring

`computeruse.ios-mirroring/iphone-mirroring-computer` implements IComputer
over a **physical iPhone** as macOS 15+ mirrors it. There is no `adb` for
iOS — Appium / WebDriverAgent / XCUITest are not here, and `simctl` is
simulator-only and has no `tap` — so the channel is the mirroring window
itself: `screencapture -R` over its rect for the screenshot, `cliclick`
inside it for taps and swipes, System Events for keys.

```clojure
(ios/iphone-mirroring-computer {:model-width 480})
```

Two corrections distinguish it from the Android driver, and both are silent
when wrong, so both are pinned by tests: the model's coordinates are offsets
into a **crop**, so the content origin has to be added back; and the scale is
points-per-model-pixel, taken from the window rect in **points**, never from
the Retina capture's pixels.

`key "home"` / `"appswitcher"` / `"spotlight"` map to iPhone Mirroring's own
`⌘1` / `⌘2` / `⌘3`, which is how the phone is navigated — there is no home
button to tap. `right_click` is a press-and-hold, iOS's actual secondary
gesture. Swipes send interpolated motion samples in one `cliclick`
invocation; a press and a release with nothing between them is read by iOS as
a tap.

Acting before the first screenshot **refuses** rather than assuming a 1:1
scale — an unmeasured mapping puts every tap somewhere plausible and wrong,
which is the failure this driver exists to prevent. Resizing uses `sips
--resampleWidth`, not `-Z`: `-Z` caps the *largest* dimension, which on a
portrait phone pins the height and leaves the image about 220px wide. `-Z` is
right in `computeruse.macos` only because a desktop display is landscape.

It cannot do multitouch (one pointer), cannot be frame-accurate (the picture
is a live video stream), and stops the moment someone picks the phone up.
Turn-based and slow real-time games are the honest target.

`examples/iphone_game_agent.cljk` drives it as a game player:

```sh
kbb -M:dev:gemma -e "(require 'iphone-game-agent) (iphone-game-agent/-main \"Solitaire\")"
```

The pure half — coordinate mapping, gesture paths, key scripts — is tested
(`test/computeruse/ios_mirroring_test.cljk`, runs on cljs too). The shell-outs
are not, and cannot be without a Mac, a paired iPhone and two granted
permissions.

## Tests / example

```sh
kbb -M:test     # 75 tests, 477 assertions
kbb -M:lint     # clj-kondo, errors fail
kbb -Sdeps '{:paths ["src" "examples"]
                 :deps {io.github.kotoba-lang/langgraph
                        {:git/sha "a332a770a0d2b5193f81b54483bb954fb29ef8d7"}}}' \
        -M -e "(require 'desktop-agent) (desktop-agent/-main)"
```

Workspace development against local checkouts: `kbb -M:dev:test`.
