# Hermes browser execution profile

This profile runs the pinned Hermes `AIAgent` initializer, original conversation
loop, OpenAI SDK parsing, tool registry, middleware, and message projection in
Kuro's Pyodide Worker. It is an experimental Kuro adapter, not upstream Hermes
browser support. It does not replace the conversation loop with a demo agent.

The original unmodified compatibility result remains in `hermes-browser.md`.
This profile supplies the dependencies and adapts the browser execution seams.

## Reproduce

```sh
npm ci
npm run build:browser-tools
npm run prepare:hermes-browser -- /path/to/hermes-agent
npm run test:hermes-browser
```

The Hermes checkout must be at `4f649c65e35beed816f9a9ec5647d33133a25abf`.
Only tracked source, dependency metadata, and LICENSE are archived. Credentials,
profiles, native environments, history, and untracked files are excluded.
The Worker checks the source archive hash and qualified revision before import.
Package URLs, versions, and SHA-256 values are locked in
`hermes-browser-dependencies.json`; the preparer verifies each wheel and caches
it under ignored `target/browser-tools`. Tests make no external requests.
For a custom Chromium binary, set `KURO_CHROMIUM_PATH`.

## Browser connections

- A dedicated Hermes Worker waits on a bounded SharedArrayBuffer RPC. The UI
  answers asynchronously; separate Kuro tool Workers execute JS and Python.
  COOP `same-origin` and COEP `require-corp` response headers are required.
- OpenAI SDK uses an HTTPX transport adapter, which passes JSON chat completion
  requests to browser `fetch`. Configure `modelEndpoint` (full chat-completions
  URL), `model`, `contextLength`, and optional `modelHeaders` on the client.
  Header credentials stay on the client, outside the Hermes source snapshot.
  Browser CORS/TLS rules apply; credentials are omitted and redirects rejected.
- Hermes's daemon tool pool becomes a serial foreground executor with Futures
  and context propagation. No native threads are emulated. Logging is
  synchronous. Tool activity stamps start/finish; client deadlines replace
  background heartbeat/watchdog threads for this profile.
- JS/Python tools register in the named `kuro_browser` toolset. Model calls use
  the normal Hermes registry/middleware path and return actual Kuro receipts.
  The original tool-call id is preserved in both the wire message and receipt
  envelope. No terminal/subprocess/browser automation tool is advertised.
- Each run has a fresh runtime and ephemeral Hermes home. Abort or deadline
  terminates the Hermes Worker, aborts model fetch and cancels child tool calls.
  Cancellation discards the in-flight turn; browser sessions retain the last
  committed conversation for restart/resume when `session/persist` is granted.

## Verification and limits

`hermes-browser-adapter.json` records real Chromium qualification:
Hermes import → original initialization/loop → local HTTP model fixture → two
actual tool calls → both results 42 with exit 0 and correct call ids → second
model request → final answer. The system prompt remains byte-identical across
the two model requests. A pending model request can be cancelled while the UI
continues ticking. Missing `network/model` denies model access.

The model fixture is deterministic, not live inference. See [hermes-browser-streaming.md](hermes-browser-streaming.md) for subsequently
qualified SSE streaming and saved conversation restart/resume. Compression,
full native session persistence, memory/background review,
subagents, cron, remote backends, and native process tools are not qualified.
Model metadata must be configured; metadata HTTP probes are explicitly disabled.
A guarded transformation in the ephemeral source disables process-liveness
inspection in remote file sync, eliminating its eager `psutil` import without
pretending that a process API exists. The installed native Hermes is untouched.

The 42-package profile uses Pyodide's Wasm Pydantic 2.12.5/Core 2.41.5 instead
of Hermes's native pins 2.13.4/Core 2.46.4; requests 2.33.1 and ruamel.yaml
0.19.1 also differ from native pins. This is a separately qualified browser
profile, not an exact reproduction of Hermes's full native dependency lock.
The tested OpenAI SDK is 2.24.0. Native wheels are never copied into Wasm.

Python exposes its JS bridge and runs only trusted code on a dedicated origin;
capability grants route intent, not browser-level network confinement. This
profile provides neither Linux containers nor a secure multi-tenant sandbox.

The integration test requires this fork snapshot and is run locally. Existing
browser-tools CI covers the generic tools; Hermes qualification is not yet a
CI gate. The pre-existing `browser-e2e` CLJK namespace build failure remains
outside this change. PR #135 is draft and unmerged.
