# kotoba-code

A **model-neutral, test-gated, kotoba-Datom-backed terminal coding agent** for kotoba-lang.

**Active implementation: the `.kotoba` guest.** The operator entry is
`kotoba/main.kotoba` (see `kotoba/operator-entries.edn`). Today it is a
command-admission and model-routing guest, not yet the full agent: it admits
the catalog commands (`help`, `version`, `tools`, `commands`, `capabilities` →
status 11), returns usage (2) for blank or unknown commands, classifies a
model id as `murakumo` / `subscription` (`codex:`, `claude:`) / `openrouter`,
and answers every host-listen command (`task`, `interactive`, `tui`, `doctor`,
`check`, `persist`, `infer`) with the explicit **HOLD** status 90. HTTP
inference, kotoba-Datom persistence, filesystem/git tools and the TUI are not
implemented in the guest; HOLD is reported rather than a fake `ok`.

**Leftover JVM implementation: the `.cljk` sources.** `src/kotoba_code/` —
with `src/kotoba_code/main.cljk` as its library dispatch — is the earlier
agent: a full-screen terminal UI, a line-mode interface for pipes, and
one-shot/headless commands sharing capability-confined tools, a rollback gate,
a durable budget, leases and a resumable session log. It drives any
OpenAI-compatible model (GLM/Kimi/Qwen via OpenRouter, or the Murakumo gateway)
through a ReAct loop with `read_file` / `write_file` / `run_clojure` /
`run_tests` tools and persists each session's turn history as-of on the kotoba
Datom log. It was the kotoba-lang successor to the throwaway Python bake-off
harness (`_modelbake/refactor_runner.py`) and is built on the kotoba-lang
`langchain` and `langgraph` libraries plus `error`/`bytes`/`io`/`process`/`edn`/`text`/`json`.
`deps.edn` keeps that graph as the leftover library graph; it is not an
operator start path.

## How to start now

Working operator start is compile + `instantiateKotoba`. There is no
`kotoba -M` and no `kbb -M` / `kbb -M` start path. `:run` is gone
(including `:jvm-opts --enable-native-access=ALL-UNNAMED`). Do not wrap
Datalevin/LMDB JNI as a C `.so`.

```sh
kotoba compile kotoba/main.kotoba --target wasm --output target/kotoba/main.wasm --json
kotoba compile kotoba/main.kotoba --target web --output target/kotoba/main.mjs --json
sh scripts/kotoba-compile.sh
sh scripts/kotoba-run.sh
bin/kotoba-code
```

`kotoba run kotoba/main.kotoba` is the intended public command. On
Release CLI it is `kotoba/runtime-rejected` (typed forms) until the CLI
accepts this guest. That is a named CLI source-run gap, not a working
start. Do not treat `exec kotoba run` as the live operator path.

Language pin is `kotoba-lang@b19e058603e30a0ea8f6f8b4ec8c5622d4371a16`
(green main test run 33838649365). See `kotoba-lang.pin.edn`.
Previous pin `6b2f2e8e` (intended-retarget; never shipped on this repo's main).
Older pin `245493fc` (kotoba-code#8) is not current.
Emit CLI is Release kotoba; the pin is the language SHA. HOLD/Release is
not lifted.

Native sealed kexe (only if/when `bin/amu` is on aarch64-macos). Not short
`aarch64`:

```sh
bin/amu check kotoba/main.kotoba --jvm-free
bin/amu compile kotoba/main.kotoba --target aarch64-macos --jvm-free --output main.kexe
bin/amu verify main.kexe
```

Linux kexe-verify is HOLD (`scripts/amu-native.sh` exits 78, not fake `:ok`).
No in-repo `bin/kotoba` emit wrapper (**ADAPTER-EMIT HOLD**). Leftover JVM
library tests live in `.github/workflows/leftover-jvm.yml`
(`workflow_dispatch` only, labeled leftover). Default CI is job
`kotoba-operator`.

## System One Coding (kotoba-harness)

kotoba-code can assemble its own typed kotoba functions with
[kotoba-lang/kotoba-harness](https://github.com/kotoba-lang/kotoba-harness):
TypeSafe Jev chooses typed blocks one hole at a time (never source text), the
harness emits kotoba typed-subset source, and kotoba verifies it
(`kotoba -M check`, then the module plus fixed exhaustive checks compiled to
wasm32-browser and run through `instantiateKotoba`). The search backtracks
outward when the policy reports that no candidate fits, so a wrong outermost
operation can still be repaired.

`system-one/budget.edn` is kotoba-code's durable outer-loop budget
(`budget-left`, `may-call`; 256 exhaustive cases). The harness commit is pinned
in `kotoba-harness.pin.edn` and fetched into
`${XDG_CACHE_HOME:-~/.cache}/kotoba-harness/<sha>` on first use (network),
outside this repository so nbb never loads this repository's `nbb.edn` for it,
and reused only while that checkout is the pinned commit with a clean worktree
(override with `KOTOBA_HARNESS_HOME`).

```sh
sh bin/kotoba-code-system-one validate   # no kotoba CLI, no model; also run in CI
sh bin/kotoba-code-system-one known      # kotoba verification of known bodies
sh bin/kotoba-code-system-one wrong      # negative control (rejected)
OPENROUTER_API_KEY=... sh bin/kotoba-code-system-one jev
```

`known`/`wrong`/`jev` need a kotoba CLI that provides `-M check` and
`-M compile --target wasm32-browser`, and `KOTOBA_BROWSER_HOST` pointing at
amu's `runtime/browser-host.mjs`. `jev` spends OpenRouter credit (fractions of
a cent per run). Receipts land in `target/system-one/`.

## Three pillars → one project

| Pillar | What it gives | Reused from |
|---|---|---|
| **kotoba-clj** | `openai-model` (tool-calling) → OpenRouter/Murakumo; messages; tool exec; `kotoba-db` | `langchain-clj` |
| **langgraph-clj** | `create-react-agent` loop + `datomic-checkpointer` | `langgraph-clj` |
| **kotoba-datomic** | session state persisted on the kotoba Datom log (resume / as-of / fleet-shared) | kotoba-server XRPC |

kotoba-code itself adds the **tool surface** (`tools.cljc`, I/O injected via a
sandboxed host), the **agent** wiring (`agent.cljc`), the **gate + rollback**
(`gate.cljc`, never leave a broken tree), and a small **durable outer-loop EDN
model** (`durable.cljc`). `host.clj` is the JVM I/O (HTTP, allowlisted shell, fs,
patch application, git rollback); `main.clj` is the CLI.

## House rules baked into the system prompt (lessons from the bake-off)

- langgraph-clj graph builders are **immutable** — thread with `->`, never `doto`.
- runtime model inference stays **Murakumo-only** (ADR-2605215000).
- kotoba persistence is `datomic-checkpointer` with `:db-api (kdb/kotoba-api …)`, never the in-process demo store.
- stop the moment tests are green; no speculative edits after green.

## Choosing a model for a job

kotoba-code is model-neutral, so "which model" is a measurement, not a setting.
Two harnesses live in `scripts/`, and they answer different questions:

| harness | question | gate |
|---|---|---|
| `compare-openrouter-models.sh` | can this model write **Clojure**? | `kbb -M:test` on a synthetic fixture |
| [`scripts/orbench`](scripts/orbench/README.md) | can this model write **Kotoba**? | the Kotoba compiler — inspect / test on jvm-kir+js+wasm / aarch64 native |

orbench holds out real landed ports from `kotoba-lang/murakumo` as its oracle,
feeds real compiler diagnostics back as an agent loop, and separates *could not
measure* (rate-limited, truncated) from *measured and wrong*. Findings and the
2026-08 free-model results are in ADR-2800004600 (`com-junkawasaki/root`).

## Inference backend status

`kotoba-code` itself does **not** call Ollama directly. The CLI currently chooses:

- OpenRouter by default, through `langchain.model/openai-model`
- Murakumo when the model id starts with `murakumo:`, through the murakumo.cloud internal inference gateway at `https://murakumo.cloud/api/v1/messages`

Ollama can still sit behind an OpenAI-compatible gateway, but it is not a first-class
dependency here. In this workspace the direct `ollama` mention is in the yukkuri
asset scorer, not in `kotoba-code`.

`src/kotoba_code/inference.cljk` adds the CLJC boundary for local/web inference:

```clojure
(require '[kotoba-code.inference :as infer])

(def plan
  (infer/select-plan {:target :web
                      :model "cid:your-model"
                      :format :kotoba-fp8}))

(-> (infer/load-weights! "/models/tiny.kotoba.fp8")
    ;; CLJS returns a Promise. CLJ returns the map immediately.
    )

(def backend
  (infer/kotoba-wasm-backend
   {:infer (fn [{:keys [plan weights prompt]}]
             ;; call the loaded Kotoba WASM module here
             {:text (str "model=" (:model plan) " prompt=" prompt)})}))

(infer/infer! {:backend backend
               :plan plan
               :weights {:byte-length 123}
               :prompt "hello"})
```

The target profiles are intentionally runtime-neutral:

| Target | Inference preference | Training preference |
|---|---|---|
| Web | Kotoba WASM, ONNX Runtime WebGPU, ONNX Runtime WASM | ONNX Runtime Web training, remote Murakumo |
| macOS / Apple Silicon | Candle Metal, llama.cpp Metal, Kotoba WASM, Murakumo HTTP | MLX, PyTorch MPS, remote Murakumo |
| Windows + Intel Arc | ONNX Runtime DirectML, OpenVINO, llama.cpp SYCL/Vulkan, Kotoba WASM | OpenVINO/PyTorch XPU, remote Murakumo |
| Linux + CUDA | vLLM CUDA, llama.cpp CUDA, Candle CUDA, Murakumo HTTP, Kotoba WASM | PyTorch CUDA, Burn CUDA, remote Murakumo |

Kotoba WASM is AOT for the program: `kotoba-clj` compiles safe Clojure/EDN-subset
source into WASM component bytes ahead of execution. Model weights are not AOT;
they are runtime data loaded by CID, URL, file path, or browser `fetch`.

WebGPU/wgpu can optimize per GPU family, but the practical split is:

- browser: use WebGPU through ONNX Runtime Web or a Kotoba WASM host that delegates compute to WebGPU
- native Rust: use `wgpu` for portable kernels, or vendor stacks when they are clearly faster
- CUDA production: prefer vLLM/llama.cpp/Candle CUDA behind Murakumo
- Intel Arc production: prefer DirectML/OpenVINO/SYCL or Vulkan before assuming browser WebGPU is enough

## Use

```bash
# working operator start: compile + instantiateKotoba. There is no kotoba -M.
kotoba compile kotoba/main.kotoba --target wasm --output target/kotoba/main.wasm --json
kotoba compile kotoba/main.kotoba --target web --output target/kotoba/main.mjs --json
sh scripts/kotoba-compile.sh
sh scripts/kotoba-run.sh
bin/kotoba-code
# intended public command (CLI source-run gap until the CLI accepts this guest):
# kotoba run kotoba/main.kotoba

# leftover JVM library tests (workflow_dispatch leftover-jvm.yml only; not start)
# kbb -X:test
# kbb -M:test
# kbb -M:lint

# leftover JVM library dispatch (not a start path; no :run alias):
# kbb -M -m kotoba-code.main --help

# leftover JVM library (not operator start; guest treats task / infer / persist / tui as host-listen HOLD)
# export OR_KEY=sk-or-...
# kbb -M -m kotoba-code.main "make the failing test pass" /path/to/project
# kbb -M -m kotoba-code.main "make the failing test pass" /path/to/project z-ai/glm-5.2
# kbb -M -m kotoba-code.main --interactive /path/to/project z-ai/glm-5.2
# leftover nbb Ink TUI is host-listen HOLD, not start:
# npm install && kbb --backend sci -m kotoba-code.ink-main

# leftover nbb subscription flags used to ride bin/kotoba-code when that
# wrapper spawned kbb -M:run / nbb Ink. Guest treats infer as host-listen HOLD.
# kbb --backend sci -m kotoba-code.ink-main

# leftover JVM library model IDs (not start):
# kbb -M -m kotoba-code.main "inspect this project" /path/to/project codex:
# kbb -M -m kotoba-code.main "inspect this project" /path/to/project claude:sonnet

# leftover compatibility name (not start; does not exec kotoba run)
# bin/claude

# The Ink UI owns the terminal while a turn is running, so tool events and
# streamed input cannot corrupt the composer. Ctrl-C cancels the active turn.

### Ink slash commands

- `/help` — show the command catalog
- `/clear` — clear visible conversation output
- `/resume` — resume an interrupted durable loop
- `/status` — show the working-tree status
- `/doctor` — run readiness diagnostics
- `/loop [resume|stop|reset]` — inspect or control the durable supervisor loop
- `/subtask <task>` — start an independent read-only background agent
- `/subtask --write <task>` — edit inside an isolated git worktree
- `/agents` — list background agents
- `/agents <id>` — show a background agent result
- `/agents cancel <id>` — cancel a running background agent
- `/agents diff <id>` — inspect an isolated agent patch
- `/agents apply <id>` — check and apply its patch to the parent workspace
- `/agents cleanup <id>` — remove its completed worktree and any unapplied changes
- `/model [model-id]` — show or change the active model
- `/codex [model]` — switch to the Codex subscription backend
- `/claude [model]` — switch to the Claude subscription backend
- `/openrouter [model]` — switch to OpenRouter
- `/exit` — exit the TUI

# leftover JVM library diagnostics (not start; guest classifies doctor/check/task as host-listen HOLD)
# kbb -M -m kotoba-code.main --doctor /path/to/project z-ai/glm-5.2
# kbb -M -m kotoba-code.main --check /path/to/project z-ai/glm-5.2
# kbb -M -m kotoba-code.main --version
# kbb -M -m kotoba-code.main --tools
# kbb -M -m kotoba-code.main --capabilities-edn
# kbb -M -m kotoba-code.main "…" /path/to/project murakumo:gemma3:4b
```


Diagnostics, inspection, history, and operator-control commands only require a
valid project root. Provider credentials are reported as readiness state, so
`--doctor` still prints a report without `OR_KEY`/`OPENROUTER_API_KEY`, while
`--check` exits non-zero when credentials or loop state are not ready and prints
the recommended `NEXT` action before the final `READY` line. `--check-edn`
includes the same `:next-action` in its EDN payload for supervisors that want a
single readiness probe. Actual task execution and interactive OpenRouter
sessions still require model credentials.

Durability knobs:

- `KC_GATE_ROUNDS` — test-gate repair retries inside one task, default `1`
- `KC_LOOP_ROUNDS` — durable supervisor tick budget across tasks, default `1000`
- `KC_LOOP_ID` — durable loop id, default `KC_SESSION`
- `KC_WORKER_ID` / `KC_LEASE_TTL_MS` — lease owner and TTL for multi-worker supervisors
- `KC_LOCAL_LOG=false` — disable the local supervisor log under `~/.kotoba-code/sessions`; readiness then requires kotoba-Datom persistence
- `KC_TOOL_TRANSCRIPT=false` — hide the compact tool-call transcript after each task
- `KC_LIVE_TOOLS=false` — hide live `[tool:start]` / `[tool:end]` progress lines
- `KC_MURAKUMO_URL` — Murakumo Anthropic gateway URL, default `https://murakumo.cloud/api/v1/messages`
- `KC_HTTP_TIMEOUT_MS` — HTTP request timeout for model/kotoba calls, default `120000`
- `KC_RUN_TIMEOUT_MS` — whole task timeout; on expiry partial edits are rolled back and a durable error tick is recorded
- `KC_PROCESS_TIMEOUT_MS` — external process timeout for `run_tests`, `run_clojure`, `shell`, git status/diff, and patch application, default `120000`
- `KC_MODEL_RETRY_ATTEMPTS` / `KC_MODEL_RETRY_BACKOFF_MS` — transient model/API retry budget, defaults `4` and `1500`
- `KC_MAX_TOKENS` — per-response output limit. OpenRouter defaults to `2048`
- `KC_CREDIT_FALLBACK_MODEL` — model used when OpenRouter returns HTTP 402.
  Defaults to the tool-capable `cohere/north-mini-code:free`; set another
  available model explicitly if OpenRouter availability changes.
- `KC_SUBSCRIPTION_TIMEOUT_MS` — timeout for each `codex exec` or `claude -p`
  inference round. Defaults to `300000` (5 minutes).
  so small conversations are not rejected by reserving an unnecessarily large
  completion budget; raise it explicitly for unusually large generated files.

Numeric `KC_*` values, boolean toggles (`true` / `false`), and
`KC_MURAKUMO_URL` are validated before task execution.
Invalid values are shown as a `configuration` readiness warning in `--doctor` /
`--check`; actual task execution exits with a clear configuration error instead
of a stacktrace.

`--budget` / `--budget-edn` include the current governor `decision` and `reason`.
When the durable budget is exhausted the governor moves to `:hold`; new tasks are
refused before any model call and recorded as `:refusal` ticks.
`--state-edn` combines readiness, budget/governor state, runtime identity
(`loop-id`, session, worker, model), local log metadata, and the latest local
supervisor tick for external process supervisors. It also reports the latest
lease owner/expiry and corrupt local log lines so supervisors do not silently
trust partial history. The state snapshot uses a streaming
local-log summary for counts, errors, latest lease, latest tick, and lightweight
run metrics instead of materializing full history. The `:metrics` map includes
tick counts by status, event counts by type, the latest run summary, latest tool
error payload, and the latest error/refusal/control payloads for retry and
escalation decisions.
`--state-edn` also includes `:next-action`, a small machine-readable
recommendation such as `:run-task`, `:resume`, `:reset-budget`,
`:inspect-history`, `:inspect-worktree`, `:set-provider-key`,
`:repair-local-log`, or `:wait-for-lease`, with the matching CLI/interactive
command when there is a direct operator action. If git status is non-empty before
a task starts, `:next-action` recommends `--status` / `:status` so operators can
commit, stash, or intentionally accept existing changes before rollback-protected
execution. `:repair-local-log` includes the configured log path,
corrupt-line count, and up to three parse errors so lightweight wrappers can
surface the repair target without fetching full state. If the latest interrupted
run summary reports tool errors, `:next-action` points at `--history-edn` /
`:history-edn` first so an operator can inspect failed tool calls before
resuming; it includes the latest failed tool name and redacted result tail when
available. Interrupted runs with no failed tool call but an incomplete run
summary, such as timeout, exception, rollback failure, or not-green gate result,
also point at history before resume so wrappers do not blindly continue after a
failed tick.
`--next-action-edn` returns only that recommendation for lightweight wrappers
that do not need the full readiness/log snapshot.
`--state-edn` also includes `:lease-status` with `:valid?`, `:stale?`,
`:conflict?`, and `:takeover?`; `--doctor` / `--check` mark readiness false when
another worker still owns a valid latest lease, while stale leases from another
worker are marked as takeovers. Actual task execution also refuses before any
model/tool call when a valid latest lease belongs to another worker, and it does
not append a refusal tick because that would overwrite the active worker's lease.
When a task is allowed to start, kotoba-code first commits a zero-usage `:lease`
tick before the model call, so other workers see the loop as claimed while the
inner agent run is in progress. The final run/control/refusal/reset ticks release
the lease by writing an already-expired lease, so other workers do not wait for
the full TTL after the active run has ended. Before committing a run result,
kotoba-code re-checks that its pre-run lease claim is still the latest local log
entry; if another worker has claimed the loop meanwhile, it rolls back local
changes and skips the result commit.
Final run ticks include a `:run-summary` event with status, elapsed
milliseconds, clipped task text, tool-call count, tool-error count, gate rounds,
and post-run `git status` dirtiness. They distinguish dirty worktrees from git inspection
failures with `:git-status-error?`. They also record whether rollback ran and
whether it reported an error; rollback failures are returned as data instead of
masking the original model/gate failure. This keeps long-running terminal
sessions auditable without parsing the human transcript.
Supervisor logs and compact tool transcripts redact common secret shapes before
printing or persisting payloads: `Authorization: Bearer ...`, `api_key=...`,
`token=...`, `password=...`, `secret=...`, and `sk-*` / `sk-or-*` style keys.
Human-facing runtime identifiers and local supervisor log filenames are also
redacted when they are derived from `KC_SESSION`, `KC_LOOP_ID`, or
`KC_WORKER_ID`. `KC_SESSION` is also redacted and bounded before being persisted
as durable loop session metadata; `KC_LOOP_ID` remains the durable loop identity.
`KC_WORKER_ID` is redacted and bounded before being persisted as the durable
lease owner.
Sensitive tool input keys such as `:api_key`, `:token`, and `:password` are
redacted in durable tool-call events. Tool inputs are stored as bounded summaries
with text previews, character counts, and truncation flags instead of full
payloads, so large `write_file` / `apply_patch` calls do not bloat the local log.
Durable answer and error events are also clipped after redaction, keeping verbose
model output or stack traces from growing the supervisor log without bound.
Unexpected model/gate exceptions are also converted into durable `:error` ticks
after rollback when the worker still owns the claim; rollback failures are
included in the error payload, and the lease is released instead of leaving only
the pre-run claim until TTL expiry. Run summaries record `:timeout?`,
`:exception?`, rollback flags, and git status flags; human `--history` output
surfaces those flags when present so operators can distinguish timeout rollback,
rollback failures, model/gate exceptions, git inspection failures, and test
failures.
If kotoba/Datomic remote persistence fails after the local supervisor log is
written, kotoba-code prints a warning and keeps the terminal run/control command
on its local-first path.
If the local supervisor log itself cannot be written, the command fails before
advancing in-memory loop state; local auditability is the commit point unless
`KC_LOCAL_LOG=false` is explicitly set. Corrupt-line parse errors reported in
readiness, state, log, and next-action payloads are redacted and bounded before
printing. For durable terminal-agent operation,
`--doctor` / `--check` require either a healthy local log or an enabled
kotoba-Datom checkpointer; disabling the local log without kotoba persistence is
reported as not ready. Local log appends use a per-path JVM lock
plus an OS file lock so multiple terminal supervisors sharing a `KC_LOOP_ID`
write complete EDN lines instead of interleaving commits. `--doctor`, `--check`,
and `--state-edn` preflight the configured local log path and report unwritable
paths before a run.
`--reset-budget` records an auditable operator control tick, restores the durable
budget from the current `KC_LOOP_ROUNDS` setting plus default token/tool budgets,
and returns the loop to `:active`.
Control events include `:effective?`; `:resume` clears interrupted/stopped status
but does not hide an exhausted budget, so supervisors should use
`:reset-budget` when `:blocked-by :budget-exhausted` appears.
Model calls retry only transient failures such as network errors, 408/409/425/429,
and 5xx provider responses. Non-transient failures such as bad credentials are
returned immediately instead of burning the retry/backoff budget.

Interactive commands:

- `/help` or `:help` — show terminal commands
- `/clear` or `:clear` — start fresh with empty local interactive context
- `/compact` or `:compact` — summarize recent local interactive context
- `/context` or `:context` — show what is currently in the local interactive context
- `/config` or `:config` — show or set local session config values
- `/model` or `:model` — show or switch the active session model
- `/permissions` or `:permissions` — show or set local session permission state
- `/sandbox` or `:sandbox` — show or set local session sandbox state
- `/usage` or `:usage` — show the current budget and local interactive context summary
- `/rename` or `:rename` — change the local interactive session label
- `:version` — show kotoba-code version, compatibility schema, and default model
- `:version-edn` — print the version probe as EDN
- `:tools` — list the active agent tool names
- `:tools-edn` — print the agent tool catalog as EDN
- `:commands` — print the interactive command catalog as EDN
- `:capabilities` — print supervisor capabilities as EDN
- `:budget` — show the durable supervisor budget for this terminal session
- `:budget-edn` — print the durable supervisor budget as EDN
- `:doctor` — show terminal-agent readiness checks
- `:doctor-edn` — print terminal-agent readiness checks as EDN
- `:check` — doctor plus `READY true/false`
- `:check-edn` — print terminal-agent readiness checks and next action as EDN
- `:state` — print the current supervisor state as EDN
- `:next-action` — print the recommended next action as EDN
- `:log` — show the local supervisor log path
- `:log-edn` — print local supervisor log metadata as EDN
- `:history [N]` — show recent supervisor ticks from the local log
- `:history-edn [N]` — print recent supervisor ticks as EDN
- `:last` — show the latest supervisor tick
- `:last-edn` — print the latest supervisor tick as EDN
- `:interrupt [REASON]` — mark the durable loop as waiting for human action
- `:resume` — return an interrupted/stopped terminal session to active
- `:reset-budget [REASON]` — reset the durable budget and return to active
- `:stop [REASON]` — mark the durable loop as stopped; tasks are refused until `:resume`
- `:read PATH [START] [END]` — print a file with line numbers for range edits
- `:status` — project-scoped `git status --short -- .`
- `:diff` — project-scoped `git diff -- .`
- `:test` — run the configured test command
- `/exit` or `:exit` — exit
- `:quit` — exit

Interactive command input accepts either `:` or `/` prefixes for the command
catalog above, so `/help`, `/status`, and `/read ...` behave the same as their
`:` forms. Unknown commands still remain in the terminal loop instead of being
sent to the model.

Interactive command handlers are isolated per input. If an inspection/control
command such as `:status`, `:diff`, `:test`, or `:read` throws unexpectedly,
kotoba-code prints an `ERROR: interactive command failed ...` line and keeps the
terminal loop alive for the next command.
Unknown `:`-prefixed inputs are rejected as unknown interactive commands instead
of being sent to the model, so typos like `:stop-now` cannot accidentally become
agent tasks or control actions. Dash-prefixed inputs inside interactive mode are
also rejected instead of becoming agent tasks, so pasted one-shot commands like
`--stop` or typos like `--histroy` are safe. Unknown interactive and
dash-prefixed one-shot commands print a `Did you mean ...?` hint when the typo is
close to a catalog command; unknown dash-prefixed one-shot inputs still exit `2`.

The one-shot `--test` command exits `0` only when the configured runner output
contains `0 failures, 0 errors`; red suites exit `1`.

Agent tools:

- `read_file`, `read_file_numbered`, `list_dir`, `search`
- `replace_text` for exact single-occurrence edits
- `replace_range` for 1-based inclusive line-range edits
- `apply_patch` for unified diffs
- `write_file` for full-file replacement
- `run_clojure`, `run_tests`
- `git_status`, `git_diff`
- `shell` for a restricted allowlist of read/build commands

Read tools are bounded as well: `read_file` refuses very large files and
`read_file_numbered` caps and streams each range, so agents inspect large files
in explicit line windows instead of flooding the loop. `list_dir` truncates very large
directories, and `search` rejects oversized or invalid regex patterns while
skipping oversized source files, so read-only exploration cannot crash or flood
the terminal loop. Unlistable directories and per-file read failures during
search are returned/skipped as tool-level outcomes instead of crashing the
agent graph. `git_status` and `git_diff` return `ERROR:`-prefixed tool results
on git failure or timeout, letting doctor/interactive checks distinguish a bad
repo state from an empty clean diff.
The `shell` tool is intentionally narrower than a terminal: it rejects shell
metacharacters, parent traversal, absolute paths, and home-directory paths even
for allowlisted commands. It does not allow `cat` / `sed` read bypasses or
symlink-following search flags; use dedicated tools for filesystem edits and
reads.
Filesystem tool paths are resolved canonically, so symlinks that point outside
the project root are denied for writes, range/text edits, and patch application.
Rollback removes newly created files and prunes empty parent directories it
created, so failed gated runs do not leave stray generated directory trees.
The rollback journal is cleared after rollback and after each committed run
result, so a later failed task cannot undo paths from a previous successful task
in a long-lived interactive session. If git rollback itself fails, the rollback
error is surfaced to the gate/supervisor and the journal is kept so the operator
can retry rollback after repairing the repository state.

If the latest local supervisor log marks the loop `:interrupted` or `:stopped`,
both interactive and one-shot tasks are refused until `:resume` records an
operator-controlled transition back to `:active`. `--history` / `:history` show
these control ticks alongside normal task ticks, including redacted operator
reasons and whether the control action changed loop state. `--history-edn` and
`--last-edn` expose the same local log entries, including lease owner/expiry, for
scripts and supervisors.
History tail commands stream the local log and keep only the requested valid
entries in memory while still tracking corrupt lines. Oversized local-log lines
are treated as corrupt instead of being parsed, so a damaged supervisor log does
not make `--state-edn`, `--history-edn`, or readiness probes unbounded. Human
`--history` / `:history` output warns when corrupt lines were skipped and points
operators at `--log-edn` / `--state-edn` before trusting partial history.
Machine-readable `--history-edn` / `--last-edn` keep stdout as parseable EDN and
send the same corrupt-line warnings to stderr. History counts must be
integers from `1` to `10000`; invalid non-interactive counts exit `2`, while
invalid interactive `:history` counts print an error and keep the terminal loop
alive instead of silently falling back. `--read` and interactive `:read` also
validate token count and positive line-number ranges before reaching host I/O.
`--version` / `--version-edn` are lightweight compatibility probes that do not
require a project root, provider credentials, or a local supervisor log.
`--tools` lists the same catalog in a compact human-readable form. `--tools-edn`
exposes the tool set, capability kind, descriptions, argument schemas, per-tool
limits, and operational notes for external supervisors. `--commands-edn` exposes
the CLI command surface, including exact usage strings and typo suggestion policy
for each command, and `--interactive-commands-edn` exposes the in-session
terminal command surface with exact `:` command usage strings and suggestion
policy; both work without a project root or provider key.
Tool calls normalize string keys to keywords and validate schema-required
arguments before reaching host I/O, so malformed model calls fail close to the
tool boundary with a clear `TOOL_ERROR` result instead of crashing the graph.
They also validate the simple schema types used by the tool surface (`string`,
`integer`) and numeric `minimum` constraints such as 1-based line numbers, and
reject unknown argument keys so misspelled tool inputs do not get silently
ignored. Large edit payloads are capped (`write_file`, `replace_text`,
`replace_range`, and `apply_patch`) so a single model tool call cannot flood the
terminal loop or host process with unbounded content. Unexpected host tool
exceptions are also returned as `TOOL_ERROR`, giving the agent a chance to
inspect/correct rather than ending the durable run immediately. `TOOL_ERROR`
results are marked as tool errors in compact transcripts and durable tool-call
events, so `:history` / `:history-edn` can distinguish failed tool attempts from
ordinary tool output.
`--capabilities-edn` returns a versioned supervisor-facing bundle of tool
catalog, one-shot command catalog, interactive command catalog, next-action
catalog, state-report shape, history-entry shape, readiness-report shape,
log-report shape, capabilities-report shape, defaults, and relevant environment
keys so wrappers can perform one compatibility probe before starting a durable
run. Schema version `10` includes command usage strings, command suggestion
policy, `--check-edn` next-action payloads, full exit-policy coverage, the
`:unexpected-failure` exit-code key, local supervisor log line-size limits, and
the full bounded `:run-summary` payload shape including rollback and git flags,
interactive rejection of dash-prefixed one-shot command input, and
`:inspect-worktree` next-action guidance for pre-existing git changes.
The report also exposes the `--log-edn` metrics shape for supervisor
compatibility checks, plus host-enforced tool limits such as
maximum edit/patch/read sizes, numbered-read line ranges, directory listing
caps, search pattern size, and transcript summarization caps; external
supervisors should use those values to split large inspections or edits before
asking the model to call a tool.
The environment section also declares validated boolean toggles and their
accepted values (`"true"` / `"false"`) so wrappers can reject typos before
launching a run.
Each next-action catalog entry includes the expected `:fields` for that action,
so wrappers can render recommendations without guessing optional payload keys.
The interactive catalog marks commands as exact-token matches and reports that
unknown `:`/`/`-prefixed input and dash-prefixed input are rejected while
non-command input becomes an agent task.
The command catalog marks each command with `:side-effect` (`:read-only`,
`:process`, `:control-log-write`, or `:agent-run`) and declared `:exit-codes`.
The shared exit-code contract is `0` for success, `1` for not-ready/not-green
runtime outcomes or unexpected failures, and `2` for usage or configuration
errors. The
`:exit-code-policy` section spells out the command-specific cases: `--doctor`
and `--doctor-edn` are diagnostic and return `0` even when `:ready?` is false,
while `--check` and `--check-edn` are readiness gates and return `1` when the
terminal agent is not ready to run. The policy covers every CLI command in the
command catalog, including `--interactive` and the one-shot `--test` verifier.
Unexpected top-level failures are caught before the JVM prints a stacktrace;
kotoba-code prints a redacted `ERROR: unexpected failure: ...` line and exits
`1`.
Fixed-arity one-shot commands reject extra arguments with exit `2` instead of
silently ignoring them, and unknown dash-prefixed commands exit `2` before any
model call. Control commands that collect an operator reason remain
multi-word. Non-interactive `--interrupt` / `--stop` / `--reset-budget` preserve
multi-word operator reasons with or without an explicit model id. Use `--` before
the reason when a custom model id would otherwise be ambiguous. Refused tasks are
also recorded as zero-usage `:refusal` ticks, preserving the loop status while
keeping an audit trail of attempted work. Operator reasons are redacted and
clipped before they are written to durable history.

Apache-2.0.
