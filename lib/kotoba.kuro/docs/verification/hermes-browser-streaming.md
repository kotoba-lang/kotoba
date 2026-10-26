# Streaming and saved browser conversations

The browser profile now supports the original Hermes `_StreamingCall` SSE
accumulator and OpenAI SDK streaming parser. It pulls raw byte chunks through
bounded Worker RPC, preserving split UTF-8 and fragmented tool arguments.
`onDelta` receives visible text while the upstream connection is still open;
`onReasoning` receives Hermes reasoning callbacks separately. Hermes remains
synchronous inside its Worker; browser fetch and the UI remain asynchronous.

## Reproduce and use

```sh
npm run build:browser-tools
npm run prepare:hermes-browser -- /path/to/hermes-agent
npm run test:hermes-streaming
```

```js
import {createHermesBrowser} from './hermes.js';
const agent = createHermesBrowser({
  model: 'your-model', modelEndpoint: '/your-chat-completions-proxy',
  capabilities: ['tool/js', 'tool/python', 'tool/python-js-bridge',
                 'network/model', 'session/persist']
});
const result = await agent.run({sessionId: 'my-conversation', prompt: 'Calculate 42'},
  {signal: abortController.signal, onDelta: text => display(text)});
const saved = await agent.load('my-conversation');
// After reload/restart, use the same model, endpoint, toolset and sessionId.
await agent.run({sessionId: 'my-conversation', prompt: 'What did we calculate?'});
```

`streaming` defaults to true; explicitly set false for JSON-only endpoints.
The bundled `hermes.html` is a small interface for send, stop, and saved-history
inspection; configure a usable endpoint. `/live-model` is the verification
relay path, not a deployed production endpoint.

## Commit and restart semantics

IndexedDB stores the conversation messages, tool results/receipts, exact cached
system prompt, session id, runtime identity and monotonically increasing
revision. It never stores `modelHeaders` or provider credentials. The host awaits
an IndexedDB transaction completion with strict durability before reporting
`saved: true`. Browser storage can still be evicted or explicitly cleared; this
is browser-local conversation persistence, not cloud backup or the full native
Hermes SQLite session DB.

Only completed, successful, non-partial turns commit. Worker termination,
model failures and cancellation retain the previous committed turn. In-flight
tool actions are not automatically replayed after a crash. Web Locks reject a
second simultaneous turn for one session; an atomic IndexedDB revision check
also prevents stale writers. Model/endpoint/toolset/profile mismatches reject
resume before contacting the model. Saved incomplete tool rounds are rejected.

The test actually closes Chromium and relaunches a persistent test profile,
then runs a second Hermes conversation turn from the saved snapshot. It verifies
stable system-prompt bytes, the original message/receipt history, revision 1→2,
fragmented SSE and tool arguments, token usage, cancellation while reading SSE,
concurrent-turn denial, identity mismatch and revision conflict. The server
waits for an acknowledgement from `onDelta` before ending the first text stream,
so receiving deltas only after completion cannot pass.

Evidence: `hermes-browser-streaming.json`. This test uses a model fixture and
does not certify live inference.

## Real-model qualification

The relay uses Hugging Face **dedicated Inference Endpoints**, with the
OpenAI-compatible `/v1/chat/completions` API. The served model must support
streaming and function tool calls. No inference router or Murakumo fallback is used.
API reference: https://huggingface.co/docs/text-generation-inference/en/reference/api_reference

```sh
# Set HF_TOKEN in the local environment, or point HF_TOKEN_PATH to a private
# token file. Otherwise the standard HF_HOME/token cache is used.
npm run test:hermes-live -- /path/to/native/hermes-agent https://<id>.<region>.aws.endpoints.huggingface.cloud served-model
npm run serve:hermes-hf -- /path/to/native/hermes-agent https://<id>.<region>.aws.endpoints.huggingface.cloud served-model
# Open the printed localhost /hermes.html URL; model settings are prefilled.
```

The native checkout supplies only its `venv/bin/python` and HTTPX dependency;
its model/provider configuration is not read or changed. Tokens stay in the
native relay process, never the Worker, UI, logs or IndexedDB. The relay only
accepts localhost Host headers and same-origin POSTs, pins the dedicated HF
hostname and selected model, bounds inputs/outputs and total request time,
refuses redirects, and cancels upstream work on disconnect. It is a local
helper rather than a deployed public credential proxy.

The live test passes only after actual model-selected JS and Python tool
results, visible streaming deltas, and a completed conversation turn.
`hermes-browser-live.json` records upstream failure rather than fixture success.

Observed on 2026-10-04: the existing dedicated Endpoint returned HTTP 401
`UNAUTHORIZED`. Hermes reported a failed turn, emitted no visible text deltas,
ran no tools, and did not commit a session. Both cached tokens also returned
401 from the endpoint management API. A currently authorized token and reachable,
tool-capable Endpoint are required to finish live qualification. No Endpoint
was provisioned or reconfigured and no provider credential was changed.
