# Merge review — 2026-10-04

Reviewed the complete browser tools/Hermes diff against origin/main: grant
admission before Worker construction, honest isolation receipts, cancellation
and byte limits, pinned runtime/source closure, SSE accumulation and callback
ordering, conversation commit/CAS/locking, and native credential boundaries.

Corrections made during review:

- Use dedicated Hugging Face Endpoints, with no configured Hermes provider
  fallback. Native HF token resolution never passes credentials into browser
  storage. Add a runnable localhost relay and prefilled conversation UI.
- Reject DNS-rebinding Host headers and foreign-origin inference requests;
  enforce selected model, input limits, four active requests, total deadline,
  response backpressure and child cleanup.
- Include endpoint query parameters in the session runtime identity.
- Repair the existing shadow-cljs/stock-nbb `.cljk` discovery failure by generating
  byte-identical compatibility sources from tools.deps' resolved classpath.
  Authoritative `.cljk` files and dependency pins remain unchanged. Repair the
  browser-test inventory guard to cover the current `.cljk` filenames.

Local validation: host 87 tests/292 assertions; parity 84/426; filesystem tool
adapter; browser build; all five existing browser E2Es; real Chromium JS/Python
tools; original Hermes JSON loop; original Hermes SSE, fragmented tool calls,
UI callbacks, browser restart/resume and session consistency. All passed.

The actual HF endpoint returned 401 UNAUTHORIZED, with a failed Hermes turn,
no tool execution and no committed session. That credential-dependent live
qualification remains explicitly blocked; fixture success is not live evidence.
The browser profile is for trusted Python with an ambient JS bridge, and is not
full native Hermes or an untrusted-tenant container. No blocking implementation
finding remains after these fixes; live-provider qualification requires an
authorized endpoint token.
