# kototama maturity ladder

Honest status of kototama as a **Wasm tender** (Solo5 pattern: host = tender,
guest = Wasm component). Not a marketing scorecard.

## Levels

| Level | Title | Status | What is real |
|---|---|---|---|
| **R0** | Contract / dry-run | **stable** | `kototama.contract` HostCaps + import surface; organism membrane refuses live publish |
| **R1** | Tender execution (JVM/Chicory) | **stable** | `kototama.tender` runs real `.wasm`; fuel + memory limits; aiueos adapter; session report; source lint; host-free + host-import fixtures from `kotoba wasm emit` |
| **R2** | Browser-native host parity | **advanced-partial** | parity matrix; 19/58 browser-linkable (derived from `kototama.browser/parity-score` -- the 39 browser `:no` are the transport/TLS, pg wire/pool, scram-sha256 and kagi-sign imports, each an explicit native-boundary waiver in `host-impl`); network imports use explicit inject or the shared Worker+SAB bridge (`wasm-webcomponent` PR #15); host-free web fixtures |
| ~~R3~~ | Fleet multi-tenant tender | **retired** | moved out of this repo 2026-07 to `kotoba-lang/fleet` (shared-store fleet, ADR-0008 superseded); `guest/maturity-levels` has no `:r3` and `guest-test` asserts its absence |
| T6 placement | `kotoba-lang/fleet` | **external** | stable shared-store gate consumes this tender |

**Current tender level: R2 advanced-partial** (R1 stable underneath). Fleet
placement is independently versioned and gated in `kotoba-lang/fleet`.

The R2 status and ratio above are not written by hand: `kototama.browser/r2-status`
derives them from `parity-score` (`:qualified` only when every contract import
is browser-linkable), `kototama.guest/maturity-levels` embeds
`browser/r2-level`, and `kototama.maturity-test` fails when this row disagrees
with the computed value. `kbb -M:doctor` exits 2 (not 0, not 1) when this
file is absent, because "could not compare" is not "compared and agreed".

## R1 acceptance gates

```bash
kbb -M:test
kbb -M:doctor
kbb -M:cli run test/kototama/fixtures/kotoba-compiled-fact.wasm
kbb -M:cli run test/kototama/fixtures/kotoba-compiled-peak-cells.wasm
```

### Checked-in emit fixtures (`test/kototama/fixtures/`)

| Guest | Imports | Expected `main` |
|---|---|---|
| `kotoba-compiled-fact.wasm` | none | `120` (= 5!) |
| `kotoba-compiled-peak-cells.wasm` | none | `240` (Williams integer proxy @ S=4096) |
| `kotoba-compiled-sha256-hex.wasm` | `sha256_hex` | writes empty-string digest |
| `kotoba-compiled-gen-keypair.wasm` | `gen_keypair` | 64 bytes seed+pub |
| `kotoba-compiled-http-fetch.wasm` | `http_fetch` | `-1` (loopback URL refused by the SSRF denylist -- proves compiler↔tender linkage, not a live round trip) |
| `kotoba-compiled-cbor-encode.wasm` | `cbor_encode` | 5-byte CBOR map(1) `{"a":"b"}` |
| `kotoba-compiled-json-encode.wasm` | `json_encode` | `{"a":"b"}` |
| `kotoba-compiled-json-extract-field.wasm` | `json_extract_field` | `"v"` extracted from `{"k":"v"}` |
| `kotoba-compiled-cbor-encode-nested.wasm` | `cbor_encode` | 25-byte CBOR map(1) `{"s":{"t":"eip4361","s":"sigvalue"}}` (dotted-path nesting) |
| `kotoba-compiled-json-encode-nested.wasm` | `json_encode` | `{"s":{"t":"eip4361","s":"sigvalue"},"p":{"resources":["a","b"]}}` |
| `kotoba-compiled-http-post-headers.wasm` | `http_post_headers` | `-1` (loopback URL refused by the SSRF denylist -- same non-live-network proof as `kotoba-compiled-http-fetch.wasm`) |
| `amu-compiled-i64-main.wasm` | none | `42` — guest **amu wove** (`wasm32-kotoba-v1`), not `kotoba wasm emit` |
| `amu-compiled-clock-now.wasm` | `kotoba:cap`/`call` id 7 | wall millis — i64 `clock/now` seed ABI; kit `:wasm-aot` stays pending (variant schema) |

## R2 acceptance gates

```bash
node web/verify.mjs
node web/verify-kgraph.mjs
node web/verify-actor-host.mjs
node web/verify-host-free.mjs   # demo + fact + peak-cells under browser Wasm
kbb -M:cli parity           # JVM vs browser import matrix
```

### Browser import parity (actor:host)

| Import | JVM tender | Browser tab | Node (JS) |
|---|---|---|---|
| gen-keypair / sign / verify | yes | yes (noble sync) | yes |
| sha256-hex / clock / log-* | yes | yes | yes |
| llm-infer | yes | **yes** (Worker-hosted, via a caller-supplied proxy URL) | inject |
| http-post | yes | **yes** (Worker-hosted, cross-origin-isolated) | inject |
| cbor-encode / json-encode / json-extract-field (ADR-2607230943) | yes | **yes** (byte-for-byte JS port in `actor-host.js`, parity locked by `verify-codec-host.mjs`) | yes |
| http-fetch (ADR-2607230943) | yes | **yes** (shared SAB network bridge) | inject |
| http-post-headers (com-junkawasaki/root, third wave) | yes | **yes** (shared SAB network bridge) | inject |

Score today: **19/58** browser-linkable (`kbb -M:cli parity` prints the
matrix; the earlier "14/14" here counted only the first three waves of
actor:host imports, before the transport/TLS, pg and scram families -- 39
explicit browser `:no` -- joined the contract surface). The three pure-computation codec
imports (`cbor-encode`/`json-encode`/`json-extract-field`) are now a
byte-for-byte JS port in `wasm-webcomponent`'s `actor-host.js`, with byte
parity against the JVM outputs locked by that repo's
`test/verify-codec-host.mjs` (the R1 fixture values). `http-fetch` and
`http-post-headers` reuse the same SAB/Worker transport as `http-post`
(`wasm-webcomponent` PR #15; history:
9/9 -> second wave 9/13 -> third wave 9/14 -> codec port 12/14 -> 14/14). `http-post`
is real in a browser tab
as of `wasm-webcomponent` PR #8 (2026-07-16): `http-post-bridge.js`'s
`createSabHttpPostBridge` (SharedArrayBuffer+`Atomics.wait`, needs COOP/COEP
response headers) is wired into `actor-host.js`'s `http_post`, and the guest
itself runs inside a dedicated Worker (`kotoba-wasm-worker-host.js` /
`kotoba-wasm-worker-element.js`'s `<worker-http-post-demo>`) since
`Atomics.wait` is disallowed on the main/DOM thread — see
`examples/actor-host/worker-http-post.html` and
`test/browser/verify_http_post_browser.cljs` (real headless Chromium, real
HTTP round-trip, `npm run test:http-post-browser`). `llm-infer` is real in a
browser tab too as of `wasm-webcomponent` PR #11 (2026-07-16): it reuses the
SAME bridge instance as `http-post` (`kotoba-wasm-worker-host.js` passes one
bridge as both `httpPostBridge` and `llmInferBridge`), POSTing the raw
prompt bytes to a caller-supplied `llmInferUrl` and reading the raw
completion text back — deliberately NOT a direct call to a real LLM
provider, since a browser tab can never hold a provider API key without
shipping it to every visitor; `llmInferUrl` must point at a
developer-controlled proxy that holds any real credential server-side. See
`examples/actor-host/worker-llm-infer.html` and
`test/browser/verify_llm_infer_browser.cljs`
(`npm run test:llm-infer-browser`). An opt-in URL allowlist
(`:allowed-url-prefixes`/`allowedUrlPrefixes`) for `http-post` also landed
separately (`kototama` PR #32 / `wasm-webcomponent` PR #10). See "What we
deliberately do not claim" below for what's still not claimed (JSPI as the
default `http-post`/`llm-infer` wire).

### http-post in a real browser tab: landed 2026-07-16, after two false starts

This doc previously went through two wrong states on this exact point, in
both directions — worth recording so a future read of this file (or its
git history) doesn't re-litigate either mistake:

1. An earlier version claimed an `http-post-bridge.js` (SAB+COOP bridge)
   already existed and scored this 8/9 — it didn't; confirmed absent from
   `wasm-webcomponent`'s working tree and history at the time, corrected to
   7/9 (`kototama` PR #30).
2. That correction was itself about to go stale in the other direction:
   `wasm-webcomponent` PR #8 found that a *different*, independently
   written `http-post-bridge.js` had since been merged directly to that
   repo's `main` (bypassing PR review) with a real bug -- `TextDecoder.
   decode()` called on a view directly over the `SharedArrayBuffer`, which
   browsers reject outright -- meaning the bridge existed but had never
   actually completed a real request. PR #8 fixed that bug (`.slice()`
   instead of `.subarray()`), fixed a second real bug (a Worker-startup
   race between constructing the bridge and the first synchronous call),
   and proved the whole path end-to-end in real headless Chromium. `8/9` is
   the actual, verified state as of that PR, not a documentation-only
   correction like the first one was.

### llm-infer in a real browser tab: landed 2026-07-16, reusing http-post's bridge (9/9)

`wasm-webcomponent` PR #11 closed the remaining gap by generalizing, not
duplicating, PR #8's bridge: `kotoba-wasm-worker-host.js` constructs ONE
`createSabHttpPostBridge` instance and passes it to `actorHostImports` as
BOTH `httpPostBridge` and `llmInferBridge` — `llm_infer` POSTs the raw
prompt bytes through it to a caller-supplied `llmInferUrl` and reads the
raw completion text back, metered against `maxLlmInfers` the same in-band
`-1` way `http_post` already was (a real, previously-missing per-call
counter — only the pre-flight import-declaration count, always ≤1, was
checked before). `llmInferUrl` is intentionally NOT a built-in call to any
real LLM provider: a browser tab can never hold a provider API key without
shipping it to every visitor, so the actual provider call must live behind
a developer-controlled proxy the caller supplies the URL for.

Host library today: `actor-host.js`, `http-post-bridge.js`,
`kotoba-wasm-worker-host.js`, `kotoba-wasm-worker-element.js`, `kgraph.js`.

### Second wave: http-fetch/cbor-encode/json-encode/json-extract-field, JVM-only for now (2026-07-23, 9/13)

`com-junkawasaki/root` ADR-2607230943 added 4 new `actor:host` imports for
a future news-collecting fleet actor (kawaraban/cloud-itonami) that builds
CACAO token bytes and XRPC request/response bodies from a `.kotoba` guest:
`http-fetch` (GET, reusing `kotoba-core-contracts`' pre-existing
`http/fetch` id 205 rather than a new one), `cbor-encode`, `json-encode`,
and `json-extract-field` (the latter two share one `data/json` capability
id, same "one shared id for a small family" pattern `kami/engine` and
`graph/kotoba` already use). All 4 are implemented in `kototama.tender`
(JVM/Chicory) only -- no `wasm-webcomponent actor-host.js` port exists
yet, so the score moves from 9/9 to **9/13**, an honest new gap, not a
regression in what was already real. `http-fetch` reuses `http-post`'s
SSRF/DoS hardening (`blocked-http-post-destination?`/
`contract/url-allowed?`/connect+request timeouts) verbatim; `cbor-encode`/
`json-encode`/`json-extract-field` are pure computation with no
network/secret/write effect at all, so a browser/Node port (should one
ever be built) would need no SAB+Atomics bridge the way `http-post`/
`llm-infer` did -- just a JS port of the same flat key\<TAB\>value-pairs
parsing + encode/scan logic.

### Third wave: http-post-headers + cbor/json dotted-path nesting (2026-07-23, 9/14)

`com-junkawasaki/root` (this ADR) closes the two follow-ups the second
wave's own ADR-2607230943 explicitly flagged and `com-etzhayyim-kawaraban`
`wasm/README.md`'s Phase B independently re-confirmed against a real port
attempt (findings 4 and 5):

1. **`http-post-headers`** -- a SEPARATE host-import from `http-post`
   (`http_post_headers`, `(url-ptr url-len body-ptr body-len headers-ptr
   headers-len out-ptr out-cap) -> bytes-written|-1`), reusing `http-post`'s
   own `http/post` capability id 223, SSRF/DoS hardening
   (`blocked-http-post-destination?`/`contract/url-allowed?`/connect+request
   timeouts), and `:max-http-posts` RuntimeLimits budget verbatim -- a Wasm
   import's arity is part of the compiled guest's own import section, so
   `http-post` itself could not simply grow a headers parameter without
   breaking every already-compiled guest that imports it. HEADERS reuses the
   SAME flat `key<TAB>value`, LF-separated wire format `cbor-encode`/
   `json-encode` already use (`parse-flat-pairs`) -- a header block is
   inherently flat, so it never needed the nesting extension below. This
   closes `com-etzhayyim-kawaraban` `wasm/README.md` finding 5 (no way to
   send `Authorization: Bearer <jwt>`, blocking a `com.atproto.repo.
   createRecord` port).
2. **cbor-encode/json-encode dotted-path nesting** -- NO new capability id
   or host-import needed (unlike (1) above): a key segment MAY now be
   dot-separated (`"s.t"`, `"resources.0"`, `"p.resources.0"`) to address one
   level of OBJECT/ARRAY nesting -- a numeric segment selects an array
   position, any other segment selects an object field. A key with no dot is
   byte-for-byte unchanged from the pre-extension flat behavior (a strict
   superset, not a replacement -- see `kototama.tender`'s `build-nested-tree`/
   `tree-node->cbor`/`tree-node->json` docstrings). Verified byte-exact
   against the REAL `cloud_itonami.media.cacao/->wire` CBOR envelope and
   `cloud_itonami.media.aozora/create-record!`'s real
   `com.atproto.repo.createRecord` JSON body (cheshire-generated, matching
   production's own JSON writer) for fixed inputs -- closes finding 4 (no
   nested-map support, blocking a byte-faithful CACAO token).

Both are JVM-only so far (no `wasm-webcomponent actor-host.js` port), so the
score moves from 9/13 to **9/14** -- an honest new gap, not a regression.
`http-post-headers`'s eventual browser port could reuse `http-post`'s own
Worker+SAB+Atomics bridge (just widen the message payload with a headers
field); the nesting extension needs no bridge at all (pure computation,
same as `cbor-encode`/`json-encode` already are) -- just a JS port of
`build-nested-tree`'s tree-building logic alongside the existing flat-pairs
parsing.

## T6 placement integration

The independent [`kotoba-lang/fleet`](https://github.com/kotoba-lang/fleet)
package owns leases, budgets, checkpoints, recovery, audit, epoch fencing,
the ten fleet CLI commands, and systemd packaging. It depends on this repo in
one direction and calls `kototama.tender`; kototama does not depend on fleet.

Run its acceptance gate from that repository:

```bash
kbb -M:test
kbb -M:cli fleet-gate
bash deploy/staging-smoke.sh
```

## Guest source rules (emit subset)

1. **No defn docstrings** — string parsed as arity.
2. **`(defn main [] …)`** required.
3. Allowed: multi-defn, recursion, let, integer `/`, `ns`.
4. Host imports only module `"kotoba"` fields in `guest/wasm-field-by-import-id`.

## Closed loops

```
R1: .kotoba --lint--> wasm emit --> .wasm --> tender/run-report (Chicory)
R2: .wasm --> browser/Node WebAssembly + actor-host.js | host-free {}
R3: lease --> governor --> plan-tick --> (inject tender) --> apply-tick-result
           --> checkpoint EDN          (retired here; lives in kotoba-lang/fleet)
```

## What we deliberately do **not** claim

- Full browser network imports (http-post) without JSPI/COOP-COEP
- Production multi-node fleet scheduling
- That every kotoba language feature emits to Wasm
