# ADR-0003: Brave-class web-compatible browser with bounded Chrome extension compatibility

- Status: proposed
- Date: 2026-10-26
- Tracking: [KOTOBA-146](https://linear.app/kotobalabs/issue/KOTOBA-146) (plan), [KOTOBA-147](https://linear.app/kotobalabs/issue/KOTOBA-147) (this ADR)

## Context

Owner decision 2026-10-26: build a **Brave-class browser from the kotoba
stack** — a real browser shell with measured web compatibility and
Chrome-compatible extension APIs. This ADR fixes that scope; implementation
runs through the phase issues under KOTOBA-146.

Facts measured before writing this ADR (2026-10-26):

- `kotoba-lang/browser` is at ADR-0001 maturity R1.5: navigation, trusted HTML
  subset into `kotoba.wasm.dom`, CSS selector/cascade subset, `browser.chrome`
  (tabs/URL bar/navigation intent), profile/per-origin permission and storage
  partition, a11y projection, audit datoms, QuickJS WASM shims that turn
  `document.querySelector`/`fetch`/`localStorage`/`navigator.*` into capability
  requests, and `browser.runtime/ecma262` with a differential test against the
  QuickJS path.
- Web-compat measurement already exists as differential harnesses against a
  real browser: `kotoba-lang/htmldom/conformance` measures tree shape at
  **115/122 = 94%** versus real headless Blink; `kotoba-lang/cssom/conformance`
  measures layout versus real headless **Brave 151 over CDP**, and has
  repeatedly found real bugs.
- Chrome/extension API compatibility has **no design record**: grep for
  `manifest_version` / `chrome.runtime` / `WebExtension` across
  `kotoba-lang/browser`, `kotoba-lang/aiueos` and `cloud-itonami` returns no
  design hit. The only requirement source is `cloud-itonami/mamori` README:111 —
  a WebExtension that reads the Cookie Store / CMP (TCF) consent string, maps
  vendors to `recordGrant`/`scanImport`, and drives one-click site-settings
  deny (design text only, not implemented).
- ADR-0001 `## Why kotoba-only means WASM-only` (L139–144) explicitly declares
  web compatibility "a different project"; `README.md` L5 and L64 repeat it as
  non-goals.
- The shared app contract (workspace `AGENTS.md`) requires per-operation
  consent (L42), states that a browser permission prompt is not a substitute
  for Kotoba operation consent (L44), and scopes browser consent to the
  displayed operation (L65).

## Decision

### Ruling 1 — relationship to ADR-0001: supersede the exclusion, inherit the architecture

ADR-0003 **supersedes ADR-0001's scope exclusion** — its
`Why kotoba-only means WASM-only` rationale and the README non-goals
"No JavaScript compatibility layer" / "not a JavaScript-compatibility browser"
— and **adopts ADR-0001's Decision architecture and invariants unchanged** for
the wider scope:

- no ambient network/filesystem/HID/clipboard/GPU/process access; every effect
  leaves through an explicit capability import visible at the ABI boundary;
- production document and extension execution is kotoba-clj/WASM or an admitted
  WASM component behind capability imports; JVM/CLJS execution is tests and
  tooling only;
- host effects are recorded as audit datoms;
- document structure is data (EDN/DOM ops); rendering is draw ops.

ADR-0001's warning is not overturned, it is absorbed: web compatibility does
pull in JavaScript semantics, WebIDL, legacy DOM behavior, layout and storage
quirks, service workers, CSP and cross-origin edge cases. This ADR starts that
"different project" **under the same invariants**, and makes it measurement-
first precisely because the warning was right about scale.

Follow-up required on acceptance: `README.md` L5/L64 non-goals are rewritten to
point here. This ADR alone does not edit them, so the repository has one
authority for the change.

### Ruling 2 — Chrome compatibility is a bounded, declared, consent-mapped subset

"Compatible" adopts the ADR-0072 definition pattern: a **documented subset of
manifest keys, namespace APIs, argument shapes and semantics, tested against
frozen fixtures** — not unrestricted parity, not vendor affiliation.

Mapping rules:

1. **MV3 `manifest.json` parses into a `kotoba.app.client-runtime.v1`
   descriptor.** Declared `chrome.*` namespaces carry their operation sets;
   `content_scripts.matches` / `host_permissions` become endpoint origins;
   `permissions` become data categories. Validation and operation brokering use
   the canonical `kotoba-lang/wasm-webcomponent/src/kotoba-client-runtime.js`
   (present on `origin/main`; product-local copies remain prohibited).
2. **Install-time consent = descriptor approval**, displayed with the
   extension's identity, origins, namespaces and data categories.
3. **Two runtime tiers over that approval:**
   - *declared reads inside the approved scope* (`chrome.cookies.get` on an
     approved origin, `chrome.storage.local.get`, `chrome.tabs.query` bounded
     to declared match patterns) are allowed after descriptor validation and
     audited as datoms;
   - *state-changing or scope-expanding operations* (`cookies.set`/
     `remove`, `tabs.create`/`remove`, `scripting.executeScript` into a page,
     `permissions.request`, any fetch to an undeclared endpoint) require
     **fresh per-operation consent immediately before invocation; denial sends
     nothing**.
4. **Fail closed**: undeclared namespace, origin, argument shape or permission
   errors; never a silent grant, never an app-origin proxy.
5. **A browser or OS permission prompt — including the extension install
   prompt — is never treated as Kotoba operation consent** (AGENTS.md L44
   extended to extensions; L65 unchanged).
6. **`declarativeNetRequest` rules are declarative data** validated at install
   time against the descriptor; there is no runtime-ambient request-rewriting
   path.

Stated deviation, part of the documented subset: an extension written for
Chrome's ambient authority will meet descriptor approval and fresh-consent
prompts where Chrome proceeds silently, and undeclared capabilities fail
closed. That is a contract requirement, not a bug to hide.

### Ruling 3 — the compatibility score is a pinned fixture corpus

No "Chrome API compatible" claim exists outside this corpus:

- **MV3 manifest keys (v1):** `manifest_version` (3), `permissions`,
  `host_permissions`, `content_scripts`, `background.service_worker`, `action`,
  `commands`.
- **`chrome.*` namespace slice (v1):** `chrome.runtime`
  (`onMessage`/`sendMessage`/`getURL`/`id`), `chrome.storage`
  (`local`/`sync` get/set/remove), `chrome.tabs` (`query`/`get` read;
  `create`/`update`/`remove` consent tier), `chrome.cookies` (`get`/`getAll`
  read; `set`/`remove` consent tier), `chrome.scripting` (`executeScript`
  within declared matches).
- **Negative fixtures (mandatory):** undeclared origin, undeclared permission,
  overscoped `tabs.query`, deny-then-network (proves no request is sent),
  undeclared `chrome.*` namespace.
- **Acceptance test:** mamori's WebExtension design (README:111) runs against
  the kotoba browser runtime — CMP/TCF consent read, vendor mapping, one-click
  deny.
- **Web-compat side** uses the existing Brave-oracle conformance harnesses
  (`htmldom`, `cssom`), recorded in a ledger with negative controls
  (a deliberately broken parser must lower the score).

### JS engine stance

Both engines stay. The QuickJS WASM path (`browser.compat.quickjs-wasm`) is
the **engine of record for compatibility scoring** because it executes real
page and extension JavaScript today. `browser.runtime/ecma262` (kotoba-written,
effect-log, `:imports #{}`) converges under the existing differential test
(`test/runtime-differential.cljk`); scoring switches to it only when the
differential shows parity on the fixture corpus. Both are capability-gated
identically.

### What "Brave-class" means here

Shell + measured compatibility + extension compatibility: `browser.chrome`
tabs/URL bar, profile and per-origin permission UI, storage partition, and
extension management UI, presented through the ADR-0002
`browser.desktop-backend` contract on macOS and aiueos. It does **not** mean a
Chromium fork, and it does not mean a browser-store distribution.

## Non-goals

- Embedding Chromium, Servo or WebKit as the rendering engine — policy 3 is
  the kotoba-stack route; an embed proposal would be a separate ADR.
- DRM (Widevine), proprietary media codecs, extension web-store distribution,
  vendor account sync.
- The full WebIDL surface or complete service worker / CSP / cross-origin
  semantics on day one — scope is the pinned corpus, and the score says what
  is and is not covered.
- Relaxing the consent contract to chase extension compatibility.

## Phases

| Phase | Issue | Evidence required |
| --- | --- | --- |
| 1. This ADR accepted, corpus pinned | KOTOBA-147 | ADR `accepted`, fixture corpus committed |
| 2. One-command compat scoring vs real Brave, with negative controls | KOTOBA-148 | ledger run, broken-parser control lowers score |
| 3. Web-compat layer expansion under the invariants | KOTOBA-149 | score improves over baseline; existing suites (browser 444 tests / 2503 assertions, cssom 497 / 1004) stay green |
| 4. WebExtension runtime, mamori as acceptance test | KOTOBA-150 | mamori contract test passes; deny sends no request |
| 5. Desktop shell | KOTOBA-151 | live screenshot/recording ledger; JUN-93 shared-Browser integration remains consistent |

## Consequences

- The repository gains a web-compatibility and extension-compatibility program
  with a pinned, measurable definition instead of an open-ended "browser
  parity" ambition; every claim routes back to a ledger and a fixture.
- Capability invariants and the per-operation consent contract survive intact;
  extension ambient authority is converted into declarations and two-tier
  consent rather than granted.
- Scope is genuinely large — ADR-0001's warning stands. The mitigation is the
  phase gates: each phase is admitted by measured evidence, and a phase that
  cannot produce its ledger does not advance.
- On acceptance, `README.md` L5/L64 need the follow-up edit named in Ruling 1,
  and KOTOBA-148–151 proceed from Todo.