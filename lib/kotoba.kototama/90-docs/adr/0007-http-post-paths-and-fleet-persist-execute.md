# ADR-0007: http-post paths + fleet disk/B2 + tender execute

- **Status:** accepted
- **Date:** 2026-07-10

## Decision

### http-post (R2)

In `wasm-webcomponent` `actor-host.js`:

1. **inject** `opts.httpPost` (Node/tests) — primary verified path
2. **SAB+COOP** `http-post-bridge.js` `createSabHttpPostBridge` for
   crossOriginIsolated browsers
3. **JSPI** detected via `httpPostCapabilities().jspi` — not default wire

### fleet persist + execute (R3)

- `kototama.fleet-store`: disk always; B2 when env creds present
- `kototama.fleet-exec`: `make-execute` → tender/run-report; `bootstrap-and-run!`
- CLI `fleet-run <wasm>`

## Status

R2 remains advanced-partial (llm still Node-only). R3 = skeleton+persist.

## Addendum (2026-07-16): the SAB+COOP `http-post` bridge was never built

Re-auditing `wasm-webcomponent` while working on kototama's own maturity
docs found that item 2 above (**SAB+COOP** `http-post-bridge.js` /
`createSabHttpPostBridge`) and item 3 (`httpPostCapabilities().jspi`) do
not exist anywhere in that repo's working tree or git history — confirmed
by direct search, not just a stale grep. `actor-host.js`'s own current
header comment is accurate and was already honest about this: `http-post`
is "the one import that's fundamentally unavailable" in a browser tab today
and is deliberately absent from the exported import object (a guest
declaring it fails to link with a clear error), not silently
degraded. Only item 1 (Node/test `opts.httpPost` inject) is real. This
Decision's http-post section described a plan as already landed; it wasn't
-- `docs/maturity.md` and the top-level `README.md` repeated the same
"8/9 browser-linkable, http-post via inject / SAB+COOP bridge" claim and
have been corrected to 7/9 (`llm-infer` Node-inject only, `http-post` not
implemented in-browser) in the same pass. Building the actual bridge (or
adopting JSPI once broadly shipped) remains real, not-yet-scheduled future
work -- tracked as a to-do, not re-claimed as done here.

## Addendum (2026-07-16, later same day): the bridge now exists and works -- 8/9

Independently of the addendum above, `wasm-webcomponent` `main` had
*already* gained a different, independently-written `http-post-bridge.js`
(`aa34a68`/`b20a69f`, merged directly, bypassing PR review, around the same
time the previous addendum's audit ran) implementing exactly item 2 above
(`createSabHttpPostBridge`). That bridge had a real bug -- `TextDecoder.
decode()` was called on a `Uint8Array` view directly over the
`SharedArrayBuffer` (`payload.subarray(...)`), which browsers reject
outright ("The provided ArrayBufferView value must not be shared") -- so
every real request would have failed closed; it had never actually been
exercised end-to-end. `wasm-webcomponent` PR #8 fixed that (`.slice()`
instead of `.subarray()`), fixed a second real bug (calling `postSync`
immediately after constructing the bridge is a confirmed-live deadlock --
the inner Worker hasn't started yet), added the Worker-hosted guest
element this bridge actually requires (`kotoba-wasm-worker-host.js` /
`kotoba-wasm-worker-element.js`, since `Atomics.wait` can't run on the
main/DOM thread), and proved the whole path in real headless Chromium
(`test/browser/verify_http_post_browser.cljs`, `npm run
test:http-post-browser`) -- a real HTTP round-trip through a
cross-origin-isolated page.

`http-post` is genuinely `8/9`-real now, corrected again in
`docs/maturity.md`/`README.md`/`src/kototama/browser.cljk`/
`src/kototama/guest.cljk`/`test/kototama/browser_test.cljk`. Item 3
(JSPI) and `llm-infer`'s browser path remain not built. This is the third
state this ADR has recorded for the same claim (landed → not built →
actually landed) -- each correction was made against directly-verified
evidence (a real E2E run, not another grep), which is why this one should
be trusted more than either of its predecessors.
