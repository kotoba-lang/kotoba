# Hermes Agent in the Kuro browser runtime: compatibility verification

For the subsequent adapted execution profile, see [hermes-browser-profile.md](hermes-browser-profile.md). The result below applies to the unmodified standard-library-only profile.

Verified 2026-10-03 in real headless Chromium through Kuro's Python tool.

**Result: the current unmodified Hermes Agent does not run in this browser
runtime.** The probe completed successfully; the agent's import and execution
requirements did not. No Hermes conversation, inference, or agent tool round
trip completed. The working Kuro Python tool is not evidence that Hermes runs.

## Exact inputs and scope

- Hermes source: local installed checkout of the NousResearch Hermes Agent
  with the com-junkawasaki fork remote, commit
  `4f649c65e35beed816f9a9ec5647d33133a25abf`.
- Kuro runtime source: `e03ca046da5c4cb99be8efc3b1aeff64e8e5a4ea`.
- Pyodide 314.0.7, reporting Python 3.14.2 and `sys.platform = emscripten`.
- Source snapshot: 2,083 tracked source/metadata/license files, archive SHA-256
  `b13d47333b965d00b1e841702194f53b741c37aea834f93bb9d3bab7d2c7b603`.
- The real Kuro `createToolHost` and Python Worker were used. No substitute
  agent loop, patched Hermes module, dependency stub, or emulated thread was
  used. Hermes profiles, configuration, credentials, installed packages,
  histories, and native environment were not copied. HERMES_HOME was an empty
  directory inside the browser's ephemeral `/workspace`.
- No external service request occurred. A local static OpenAI-shaped JSON
  response tested transport only, without a live model or model inference.

## Results

| Probe | Observed result | Interpretation |
|---|---|---|
| Kuro Python invocation | Exit 0, JSON report returned | Probe infrastructure works; does not mean Hermes succeeded |
| Actual Hermes `IterationBudget` | Consume true/true/false, refund restores one iteration | This original pure/thread-lock module works |
| `from run_agent import AIAgent` | `ModuleNotFoundError: No module named 'dotenv'` at `run_agent.py:119` → `hermes_cli.env_loader` | Full agent import is blocked by missing dependencies |
| Hermes `DaemonThreadPoolExecutor.submit` | `RuntimeError: can't start new thread` | The actual tool execution mechanism fails, independently of missing SDK packages |
| Python `Thread.start` | Same runtime error | Thread creation is unavailable in this profile |
| Python subprocess | `OSError: [Errno 138] emscripten does not support processes.` | Native terminal/child-process tools cannot be reused as-is |
| Python socket constructor | Succeeds | Constructor only; not proof of TCP connectivity |
| Python SSL context constructor | Succeeds | Constructor only; not proof of HTTPS transport |
| Python urllib HTTP to local fixture | `URLError: <urlopen error timed out>` | Existing stdlib socket transport did not deliver the request in this profile |
| Browser `fetch` to that same fixture | Exact fixture content returned | Browser transport works, but Hermes SDK/streaming integration remains untested |
| OpenAI/Pydantic/HTTPX/etc. imports | Packages absent | This Kuro profile currently supplies Python's standard library, not Hermes's dependency closure |

The import failure alone is fixable by supplying dependencies. It is **not**
the sole reason for the negative result: the actual Hermes tool pool and OS
mechanisms also fail without changing any source.

## Required work to earn browser-local Hermes execution

1. Package and verify the exact Hermes dependency closure for Emscripten.
   Native extension wheels, notably Pydantic Core, need the appropriate Wasm
   ABI/version; host macOS/Linux wheels are not browser artifacts.
2. Add a supported browser execution profile to Hermes's real agent core.
   Replace thread-backed provider calls, stale monitors, and tool pools with
   browser/async scheduling. Preserve cancellation, iteration budgets,
   conversation alternation, and prompt caching rather than replacing the
   agent with a small unrelated loop.
3. Bind the real provider transport to browser fetch/streaming through an
   authorized gateway. Keep provider credentials server-side. This probe
   checked only local fixture delivery, not production authentication or SSE.
4. Route tool requests to Kuro's JS/Python function tools and explicit FS
   snapshot/persistence interfaces. Native shell/PTY/process tools need a
   separate admitted remote provider or remain unavailable.
5. Qualify a complete original-agent turn: prompt → real model call → tool
   request → Kuro execution → result with matching call ID → final answer;
   then cancellation/recovery and durable session resume.

Running native Hermes behind a browser UI is a separate viable topology; it
does not establish that Hermes itself is running inside Kuro/Pyodide. No
backend-hosted Hermes deployment was performed in this verification.

## Reproduction and evidence

```sh
npm ci
npm run build:browser-tools
npx playwright install chromium
node scripts/verify-hermes-browser.mjs /path/to/hermes-agent \
  4f649c65e35beed816f9a9ec5647d33133a25abf
```

Use `KURO_CHROMIUM_PATH` only when supplying an existing Chromium executable.
The script creates a tracked-source-only archive in ignored build output,
serves it locally, runs the original imports/mechanisms inside Kuro's Worker,
and writes [the raw JSON evidence](hermes-browser-probe.json). Its process
exit 0 means the **probe** completed; inspect `verdict.status` and individual
checks for the actual agent result. The source checkout is left untouched.

References for the platform constraints:
[Pyodide compatibility](https://pyodide.org/en/stable/usage/wasm-constraints.html),
[Pyodide FAQ](https://pyodide.org/en/stable/usage/faq.html),
[supported micropip wheel formats](https://micropip.pyodide.org/en/latest/project/usage.html).
