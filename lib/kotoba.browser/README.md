# kotoba-lang/browser

Kotoba-only, WASM-only browser engine orchestrator.

This is not a Chrome/Servo wrapper and it is not a JavaScript-compatibility
browser. It is the kotoba-native browser surface, executed as kotoba-clj/WASM
guests against explicit host ABIs:

```text
navigation request
  -> capability-gated fetch
  -> HTML-like document parser
  -> kotoba:dom virtual document
  -> kotoba UI layout/draw ops
  -> WebGL/WebGPU/native host
  -> kotoba-clj/WASM document scripts
```

Existing substrates are reused:

- `kotoba-lang/dom-gpu`: current DOM ABI, virtual DOM, layout, WebGL/WebGPU hosts.
- `kotoba-lang/html`: EDN/Hiccup to HTML emitter.
- `kotoba-lang/css`: EDN to CSS emitter.
- `kotoba-lang/webgpu` (formerly kami-webgpu): EDN render-IR and GPU execution.

## Naming

`dom-gpu` (renamed from `wasm-ui`, see
`90-docs/adr/2607051200-kotoba-lang-ui-family-rename.md` in
`com-junkawasaki/root`) is the general kotoba UI substrate this repo consumes:
DOM ABI, retained tree, layout, and render host contracts. The previously
recorded plan to rename it to `kotoba-lang/ui` is superseded — that name
already belongs to an unrelated, older repo (kami-engine's HUD widget
package, itself renamed to `kami-engine-hud` in the same ADR).

`gui` remains reserved for higher-level desktop/native app shell concerns
such as windows, menus, clipboard, file pickers, IME, accessibility bridges,
and OS integration — largely covered today by `kotoba-lang/shell`.

Do not build a second DOM/layout stack in `browser`. Browser consumes `dom-gpu`.

## R0

R0 loads a trusted HTML subset into `kotoba.wasm.dom`, commits ops through the
existing ABI, and produces the same draw ops that the current WebGL/WebGPU hosts
consume. The implementation is `.cljc` for source reuse and JVM tests, but the
product boundary is WASM only: browser documents and document scripts run as
kotoba-clj/WASM guests.

```clojure
(require '[browser.core :as browser])

(browser/load-html
 {:url "kotoba://hello"
  :html "<main><h1>Hello</h1><p style=\"color: red\">Kotoba</p></main>"})
;; => {:browser/document ...
;;     :browser/tree ...
;;     :browser/draw-ops [...]
;;     :browser/ops [...]}
```

## Non-goals

- No JavaScript compatibility layer.
- No browser DOM API calls as the engine substrate.
- No ambient network/filesystem/HID/GPU access.
- No Playwright/Chrome dependency for execution.
- No JVM or native process as the production document runtime.

Document scripts should target kotoba-clj/WASM capabilities, not JS.

## OS UI

The same browser UI is intended to be the kotoba OS UI. `browser.surface` models
apps, windows, focus, and workspace state as plain data, then renders that shell
through `kotoba.wasm.dom` and the same `kotoba:dom` host ABI. A host supplies
display/input capabilities; the OS shell itself remains WASM guest state.

Surface input is reduced through data actions such as `:app/launch`,
`:window/focus`, `:window/move`, `:window/resize`, `:keyboard/key`, and
`:text/input`. `browser.input` normalizes host, DOM, and aiueos capability events
into one pointer/keyboard vocabulary before entering the WASM guest, preserving
pointer metadata such as `pointerId`, `pointerType`, `isPrimary`, and pressure
when the host supplies it.

`browser.desktop-backend` is the versioned, OS-neutral boundary for using this
surface as the aiueos desktop. It snapshots the existing retained draw ops into
atomic frames, routes normalized host input back through `browser.input`, and
emits clipboard/file-picker effects only after an explicit permission-broker
decision. See [ADR 0002](docs/adr/0002-browser-desktop-backend.md).
`browser.document-input` applies the same canonical text, selection, keyboard
editing, IME composition, pointer hover/down/up/cancel, and select-change events
to document-scoped form controls, dispatching `keydown`/`keyup` listeners,
dispatching `beforeinput` before text mutations, `change` on blur after text
value mutations, updating their state attrs, and
dispatching listener events before the page is recommitted. Document pointer
input also keeps implicit pointer capture from `pointerdown` until
`pointerup`/`pointercancel`, so captured moves continue to target the pressed
element.

## browser-use Compatibility

`browser-use` does not need to change. `browser.browser-use/kotoba-browser`
implements the existing `browseruse.browser/IBrowser` protocol over
`browser.session`, so `browseruse.actions/default-actions`, `agent/run`, and
recipes can keep their current notation while the controlled browser is the
kotoba-only session. Indexed element attrs expose document-baseURI-resolved
`href` and `src` values, so existing recipe `:href` matches and browser-use
agents can inspect relative links and image inputs as stable absolute URLs.

Use the optional alias when both projects are on the classpath:

```clojure
(require '[browser.browser-use :as kb]
         '[browseruse.browser :as bu])

(def br
  (kb/kotoba-browser
   {:start-url "kotoba://home"
    :html "<main><a href=\"kotoba://next\">Next</a><input name=\"q\"></main>"}))

(bu/-state br)
;; => {:url "kotoba://home"
;;     :elements [{:index 0 :tag "a" ...}
;;                {:index 1 :tag "input" ...}]
;;     :semantic-tree {:tag "document" :children [...]}
;;     :debug {:history-tail [...]
;;             :draw-ops [...]
;;             :accessibility-tree {...}
;;             :audit-summary {...}
;;             :host-recorded {...}}}
```

For code already written against the browser-use Playwright helper shape, use
`(browser.browser-use/kotoba-session opts)`. It returns
`{:browser br :screenshot f :select f :check f :close f}`; `:screenshot` writes
the same kotoba EDN snapshot described below.

For `browseruse.recipe/run-recipe!`, pass
`(browser.browser-use/recipe-options br)` to enable the existing `:check` and
`:select` recipe steps against kotoba document input reducers.

Kotoba-specific browser-use agents can concatenate
`(browser.browser-use/extended-actions br)` with
`browseruse.actions/default-actions`, or call
`(browser.browser-use/browser-use-actions br)` to get the combined controller.
The combined set preserves browser-use names and adds compatibility wrappers for
`get_state`, `extract`, `click`, `click_selector`, `click_at`, `type`,
`type_selector`, `clear`, `clear_selector`, `append_text`,
`append_text_selector`, `check_selector`, `uncheck`, `uncheck_selector`,
`select_selector`, `press`, `wait_for`, `diagnose`, `screenshot`, `focus_element`,
`hover_element`, `hover_at`, `scroll_selector`, `scroll_at`, `press_key`, and
`scroll_to_element`, plus `navigation_state`, `go_forward`, and `reload`.
These actions still reduce through the kotoba browser session and show up in the same
`:debug :history-tail`; selector actions resolve through the shared DOM selector
vocabulary, coordinate actions use the session hit-test path, `wait_for` checks
selector/text/URL conditions against current kotoba state without ambient sleep,
`diagnose` returns non-throwing selector/index/text/URL matches plus current
candidate elements for browser-use debugging,
`navigation_state` exposes entries, redirects, reload/error state, and error
document text,
hover updates document `:hover` state and dispatches pointer/mouse over, enter,
move, out, and leave listeners, while text replace/clear/append, checkbox/radio
check and uncheck, select value change, focus, key press, selector/coordinate
scroll, and scroll-to mutate document state through the existing input reducers.
The `extract` action returns `semantic`, `text`, `accessibility`, `draw_ops`,
`snapshot`, or full `state` data for debugging and page understanding. The
`screenshot` action captures a kotoba retained draw-op/accessibility/semantic
snapshot as data, and can write that EDN snapshot as a debug artifact on JVM
hosts.

## Account / Profile

`browser.account` and `browser.profile` provide the first pure data model for
identity and browser state partitioning. Accounts carry local or verified
identity metadata; profiles carry the active account id, storage partition,
per-origin permission grants, and history. This is not a network login provider
yet. It is the shape that later DID/passkey/CACAO and datom persistence can back.

`browser.origin` normalizes the small URL/origin subset used by policy and
storage. `browser.storage` keeps values partitioned by profile and origin so
personal/work profiles cannot read the same origin's data by accident.
`browser.net` adds the first network policy layer on top of injected fetch I/O:
profile permission decisions, profile-scoped GET response cache with
`Cache-Control: no-store` suppression and CORS-aware/requesting-origin/
credentials-mode cache reuse,
profile/origin cookies, credential
handling, `Secure`/`SameSite=None` and `__Secure-`/`__Host-` cookie acceptance
checks, `Max-Age=0` cookie deletion, positive `Max-Age` and future RFC1123
`Expires` expiry tracking, past RFC1123 `Expires` cookie deletion,
`Path`/`Domain`-scoped cookie
sending, `Access-Control-Allow-Origin` checks, and OPTIONS preflight for
cross-origin non-simple methods or headers. Credentialed cross-origin responses
must use an explicit requesting origin plus
`Access-Control-Allow-Credentials: true`; wildcard origins and wildcard
preflight method/header grants are rejected before cookie store updates. Host-only
cookies stay on the setting host, while accepted `Domain` cookies are sent to
matching subdomains; public-suffix-like `Domain` attributes are rejected;
`SameSite=Strict` cookies are suppressed on cross-site
requests; `Secure` cookies are not sent over HTTP. `HttpOnly` is tracked as
cookie metadata for script-read boundaries, while network sending still includes
the cookie; `script-cookie-header` exposes the non-HttpOnly view for
`document.cookie`, and `script-set-cookie` applies document-cookie writes
without allowing scripts to create HttpOnly cookies or bypass
Domain/SameSite acceptance policy. Multiple `Set-Cookie` values on one response
are applied in order, and overwriting a cookie clears stale
Domain/SameSite/Secure/HttpOnly metadata that no longer appears on the
replacement. When host and domain cookies with the same name both match, the
more specific host cookie wins in the generated cookie header; same-name
cookies with different paths can coexist, and the longest matching path wins.
`browser.session/net-context` derives that policy context from the active page,
profile, store, and injected fetch function so page scripts and compatibility
runtimes do not assemble their own network authority. When a script execution
state returns an updated net context, `browser.session/commit-script-state!`
copies the store back into the long-lived session and persistence provider.

## Web Compatibility Adapter

Existing websites can be supported through a separated compatibility adapter, not
through the kotoba-native browser core. `browser.compat.quickjs` defines the
first adapter contract: a QuickJS/QuickJS-NG WASM component with no ambient DOM,
network, storage, timer, or process access.

Browser-like APIs live in `browser.compat.webapi` as capability requests:
`document.querySelector` becomes `:dom/query`, `fetch` becomes `:net/fetch`,
`localStorage.setItem` becomes `:storage/put`, `localStorage.removeItem` becomes
`:storage/delete`, `navigator.clipboard.readText` becomes `:clipboard/read`,
`navigator.clipboard.writeText` becomes `:clipboard/write`, `window.open`
becomes `:window/open`, `navigator.permissions.query` becomes
`:permissions/query`, `navigator.geolocation.getCurrentPosition` becomes
`:geolocation/read`, `Notification.requestPermission` becomes
`:notification/request-permission`, `new Notification(...)` becomes
`:notification/show`, `Element.requestFullscreen` becomes
`:fullscreen/request`, `document.exitFullscreen` becomes `:fullscreen/exit`,
`navigator.mediaDevices.getUserMedia` becomes `:media/capture`, `setTimeout`
becomes `:timer/schedule`, `clearTimeout` becomes `:timer/cancel`,
`requestAnimationFrame` becomes `:timer/schedule`,
`cancelAnimationFrame` becomes `:timer/cancel`, `queueMicrotask` becomes
`:timer/microtask`, and `WebSocket` connect/send/close
become `:websocket/connect`, `:websocket/send`, and `:websocket/close`.
`crypto.getRandomValues` and `crypto.randomUUID` become
`:crypto/random-values` and `:crypto/random-uuid`. `Worker`
create/postMessage/terminate become `:worker/create`, `:worker/post-message`,
and `:worker/terminate`. `BroadcastChannel` open/postMessage/close become
`:broadcast/open`, `:broadcast/post-message`, and `:broadcast/close`.
`navigator.sendBeacon` becomes `:beacon/send`. `document.cookie` reads/writes
become `:cookie/get` and `:cookie/set`. `location.assign`, `location.replace`,
and `location.reload` become `:location/assign`, `:location/replace`, and
`:location/reload`. `history.pushState`,
`history.replaceState`, and `history.go`/`back`/`forward` become
`:history/push-state`, `:history/replace-state`, and `:history/traverse`.
`console.log`/`info`/`warn`/`error`/`debug` become `:console/log` records.
`URL` and `URLSearchParams` are pure sandbox shims for URL parsing, relative
resolution, and query manipulation, and do not emit host capability requests.
When a QuickJS execution state includes a network context, `:net/fetch` is
resolved through `browser.net`, so guest fetches can use the same cache,
cookie, credential, CORS, and preflight policy without gaining ambient network
access.
The session layer now builds that context for page script execution and persists
cache/cookie changes returned by the engine state.
The QuickJS WASM shim also maps minimal document construction APIs to DOM
mutation capabilities: `document.createElement`, `document.createElementNS`,
`document.createDocumentFragment`, `document.createTextNode`,
`document.getElementById`, `document.body`, `document.documentElement`,
`document.head`, `Element.setAttribute`, `Element.removeAttribute`,
`Element.appendChild`, `Element.removeChild`, `Element.insertBefore`,
`Element.replaceChildren`, `Element.append`, `Element.prepend`,
`Element.before`, `Element.after`, `Element.replaceWith`, `Element.remove`,
`Element.cloneNode`, `textContent` assignment, `innerHTML` assignment, and
`outerHTML` assignment. `innerHTML` and `outerHTML` use the same trusted HTML
subset parser as page loading. Appending or inserting a `DocumentFragment`
flattens its children through the same child mutation path. Text nodes expose
`data`, `nodeValue`, `substringData`, `appendData`, `insertData`, `deleteData`,
`replaceData`, and `splitText` through the `:set-text`/`:split-text` mutation
paths, and `normalize` merges adjacent text nodes through `:normalize`.
`Element.classList.add/remove/toggle` mutates the
same `class` attribute through `:dom/mutate`/`:set-attribute`, while
`classList.contains` and `classList.value` read from the injected snapshot.
`Element.toggleAttribute`, deleting `dataset.*`, and
`style.removeProperty(...)` reuse the same set/remove attribute capability path.
Before each evaluation/module load, the execution loop injects a document
snapshot into the WASM guest. The shim uses it for read APIs such as
`document.querySelector`, `document.querySelectorAll`,
`document.getElementsByTagName`, `document.getElementsByClassName`,
`document.forms`, `document.images`, `document.links`, `document.scripts`,
`Element.querySelector`, `Element.querySelectorAll`,
`Element.getElementsByTagName`, `Element.getElementsByClassName`,
`getElementById`, `children`, `childNodes`, `parentNode`, `parentElement`,
`firstChild`, `lastChild`, `firstElementChild`, `lastElementChild`,
`previousSibling`, `nextSibling`, `previousElementSibling`,
`nextElementSibling`, `id`, `className`, `classList`, `dataset`, `attributes`,
`style`, `getAttribute`, `hasAttribute`, `matches`, `closest`, `tagName`,
`nodeName`, `localName`, `namespaceURI`, `textContent`, `innerHTML`,
`outerHTML`, `document.URL`, `document.documentURI`, `document.baseURI`,
`document.currentScript`, `document.readyState`, and `document.title`; text
nodes also expose `data` and `nodeValue`. Assigning `document.title` emits a
`:set-title` DOM mutation, updates the title element, and refreshes the page
title used by session history.
`Element.contains`, `isConnected`, and `ownerDocument` are also snapshot-backed.
Document-level query and collection APIs search the connected root tree; detached
nodes remain addressable only through their existing element handles.
`document.activeElement` reads the snapshot focus id, while `element.focus()`
and `element.blur()` persist focus through DOM mutation capabilities.
The guest-side selector matcher covers the same attribute operator,
form-state pseudo-class, and selector-group subset as the host DOM bridge for
`matches`, `closest`, and snapshot-backed `querySelector*` reads.
DOM mutation requests also normalize `setAttribute("style", ...)` into the same
inline style model used by HTML loading, and `removeAttribute("style")` clears
that inline source plus computed style attrs.
Element events are also capability backed: `addEventListener`,
`removeEventListener`, `dispatchEvent`, `click()`, and the minimal `Event`
constructor emit `:event/listen`, `:event/remove`, and `:event/dispatch`
requests while synchronous in-VM handlers can run immediately. `CustomEvent`,
`MouseEvent`, and `KeyboardEvent` carry sandboxed detail, pointer, and key
metadata into the same event payload. `window` and `document` event listeners
use the same vocabulary with sandboxed global event targets. The shim supports
target/current target, bubbling through parent nodes, `preventDefault`, and
`stopPropagation`.
`MutationObserver` is available inside the QuickJS shim for script-visible DOM
changes produced through the supported attribute, child-list, and character-data
mutation APIs. Delivery is scheduled through the same deterministic
`:timer/microtask` capability queue as `queueMicrotask`.
Timers are also capability backed: `setTimeout` returns a stable timer id and
emits `:timer/schedule`, while `clearTimeout` emits `:timer/cancel` so the host
event loop can remove pending callbacks deterministically.
`requestAnimationFrame` and `cancelAnimationFrame` use the same capabilities with
`:timer/kind :animation-frame`. `queueMicrotask` emits `:timer/microtask`,
entering the deterministic microtask queue that drains before ready timers. The QuickJS WASM engine now keeps a reusable VM context, so
`:js/job` drain can call registered `timer-*` and `microtask-*` callbacks and
apply their capability requests back into page state. Session disposal now calls
the engine dispose hook, closing the reusable QuickJS VM/runtime and marking the
engine as disposed so no further host invocation is accepted.
Form control properties are mapped onto the same document model: `value`,
`checked`, `defaultChecked`, `defaultValue`, `disabled`, `required`, `readOnly`,
`multiple`, `type`, `name`, `selectionStart`, `selectionEnd`, and
`setSelectionRange` are available on element proxies, with mutable properties
persisted through DOM attribute mutations and `focus`/`blur` persisted through
document focus mutations. Form ownership and label relationships are available
through snapshot-backed `form`, `labels`, `control`, and `htmlFor` element
properties. Select controls expose snapshot-backed `options`, `selectedOptions`,
and `selectedIndex`; option `selected`/`defaultSelected` and select
`selectedIndex` setters use the existing selected/value attribute mutation path.
Link, image, and script-like properties expose baseURI-resolved `href`/`src`,
attribute-backed `alt`, `async`, `defer`, and the current `complete` snapshot
state on element proxies.
Created JS objects carry host-scoped client ids that the execution loop resolves
to real `kotoba.wasm.dom` node ids while applying requests.
`browser.compat.webcomponent` adds the minimal Custom Elements registry needed
for Web Components: `customElements.define`, `connectedCallback`, and
`attributeChangedCallback`.

## Runtime Adapters

JavaScript is not special in the execution model. Any non-kotoba language runtime
used by the browser or OS UI must be a WASM component behind the same capability
boundary: Python, Lua, Ruby, Scheme, JavaScript, and future language guests all
import explicit capabilities and export runtime entrypoints such as
`:runtime/eval`, `:runtime/call`, or `:runtime/job-drain`.

The browser may provide language-specific adapters, but they remain wrappers over
the generic rule:

```text
language runtime
  -> WASM component
  -> capability imports only
  -> profile/origin/storage partition
  -> audit datoms
```

No runtime gets ambient filesystem, network, process, DOM, HID, clipboard, GPU,
or timer access.

`browser.runtime` defines the generic descriptor shape and placeholder descriptors
for QuickJS/QuickJS-NG, Python, Lua, and Scheme. `browser.compat.quickjs` is now a
thin browser/Web API adapter over that generic runtime descriptor.

### A second JavaScript runtime, with no imports

`browser.runtime/ecma262` names a JavaScript engine written in Kotoba and
compiled by amu (`kotoba-lang/org-ecma-international-262`). It declares
`:imports #{}` -- not as an omission, but because it reaches the document by
**returning** an effect log the host replays rather than by calling out:

```text
document --snapshot--> engine --effect log--> browser.compat.ecma262 --> document'
```

`kotoba -M check` answers `:effects #{}` for that engine even with `document`
bound, which is what the rule at the top of this section asks for taken to its
end: the authority to change the page never leaves this side of the line.
`addEventListener` fits the same shape -- the registration comes back with a
handler number, and firing is a second call into the guest.

Whether the two engines agree is measured rather than assumed:
`test/runtime-differential.cljk` drives both over the same sources -- language,
DOM writes, and events -- and asserts its recorded divergences exactly, so a
divergence that appears and one that disappears both fail the run. The host
half (`browser.compat.ecma262`: build the snapshot, read the log, apply it) is
tested separately against a real document, so a bug in one half cannot hide in
the other.

```bash
npm run test:ecma262-differential   # 0 agree, 1 diverge, 2 could not answer
npm run test:ecma262-end-to-end     # real document -> real engine -> real host
```

Neither is part of `npm run check`, and deliberately so: both need the sibling
`org-ecma-international-262` checkout built, and a check that cannot run must
not be able to fail a run that was never asking for it. They exit **2** rather
than 0 when the artifact is missing — "could not answer" is not agreement.

They are also not fleet gates, for the reason `root-permit-index` is not one:
the fleet ships a single repo's tree, and this measurement needs two.

Runtime component manifests are validated as WASM-only, no-ambient-access
manifests with explicit imports, exports, memory, and fuel limits.
`browser.compat.quickjs-binary` adds the first binary integration point: it loads
and validates a QuickJS WASM binary descriptor, then attaches it to the adapter
without granting ambient host access. Binary descriptors include SHA-256
integrity metadata, and attach can require an expected digest. This is still a
binary/host contract. `browser.compat.quickjs-wasm` now wires a singlefile
QuickJS WASM guest through `quickjs-emscripten-core` for basic JavaScript source
evaluation.
`browser.compat.quickjs-execution` adds the execution loop contract around an
injected QuickJS WASM engine: eval, module load, job drain, timer scheduling, DOM
mutation/query, fetch, and storage all flow through capability requests. The
engine can be a host function for tests or a WASM engine descriptor with a valid
binary, valid no-ambient runtime manifest, and invoke function. Engine lifecycle
covers created, ready, error, and disposed states. Capability results are queued
with request ids, passed into the next engine invocation, and consumed so a real
WASM guest can receive host responses. Engine responses are normalized before
capability application:
malformed requests are dropped and recorded as failed host results while
non-map responses become `:quickjs/invalid-response`, engine invocation failures
become `:quickjs/engine-invoke-failed`, and unsupported capability keywords
still pass through the normal denial path. Known capability requests are shape
checked before side effects, so invalid DOM, fetch, storage, clipboard,
window-open, permissions-query, geolocation, notification, fullscreen, media,
websocket, crypto random, worker, broadcast channel, beacon, timer, or JS-call
requests are rejected as `:quickjs/invalid-capability-request`.
Module loads are cached and QuickJS calls can be recorded as audit datoms. The
current QuickJS WASM guest covers direct eval plus minimal `document`,
`fetch`, `localStorage`, `navigator.clipboard`, `window.open`, and
`navigator.permissions.query`/`navigator.geolocation.getCurrentPosition` plus
`Notification`, fullscreen, and media capture shims that emit host capability
requests. WebSocket construction/send/close also emit capability requests and,
by default, record sandboxed connection descriptors instead of opening ambient
sockets; a session can opt in to a REAL, RFC6455 socket instead by injecting
`:websocket-fn` (`browser.net.websocket/websocket-fn` -- a real
`java.net.http.HttpClient`-backed client on the JVM, a real host-runtime-
global-`WebSocket`-backed client in ClojureScript), in which case connect/
send/close move real bytes and a host-computed, per-eval snapshot delivers
real inbound messages to a script's `ws.onmessage` (see
`browser.compat.quickjs-execution/websocket-snapshot` and
`browser.compat.quickjs-runner`'s namespace docstring for exactly what that
proves and does not prove).
Crypto random APIs consume injected random byte/UUID queues, falling back to
deterministic zero values instead of ambient host RNG.
Worker construction/postMessage/terminate records sandboxed worker descriptors
and messages by default; a session running on a real `:cljs` QuickJS engine
with a real `:fetch-fn` (no separate opt-in flag needed -- see
`browser.compat.quickjs-runner`'s namespace docstring) instead REALLY fetches
the worker's script and REALLY evaluates it in a brand-new, real, independent
QuickJS context (`browser.compat.quickjs-wasm/create-worker-context`, its own
`self`/`postMessage`/`onmessage` global scope, not the page's own context),
with `postMessage` from the main thread delivered into the worker's context
synchronously and a host-computed, per-eval `:worker/snapshot` delivering the
worker's real replies back to a script's `w.onmessage` (see
`browser.compat.quickjs-execution/worker-snapshot`). There is no real OS-thread
parallelism, `importScripts`/module workers, or mid-script delivery -- see that
namespace's docstring for exactly what is and is not real.
BroadcastChannel open/postMessage/close records sandboxed channel descriptors
and messages instead of joining ambient browser channels.
navigator.sendBeacon records permission-gated sandboxed beacon payloads instead
of issuing ambient fire-and-forget network I/O.
document.cookie reads and writes use the same profile-scoped script cookie
projection as fetch/CORS policy, excluding HttpOnly cookies and preserving
Domain/SameSite/Secure constraints.
Location APIs record sandboxed navigation intent and update the execution
location URL without driving ambient browser/session navigation.
History APIs update sandboxed execution history entries and indices instead of
driving ambient browser/session navigation.
URL and URLSearchParams run entirely inside the QuickJS sandbox for URL parsing
and query manipulation.
Console APIs record sandboxed log messages in execution state instead of
writing to ambient host stdout/stderr.
Module
loading is wired through an explicit `:modules` source map on the QuickJS engine,
or through a profile-scoped storage module provider using
`quickjs.module:<specifier>` keys, so imports do not read ambient filesystem or
network state. `browser.compat.quickjs-wasm/engine-from-session!` derives that
provider from a restored browser session, and the Node smoke now executes an
HTML-discovered `<script type="module">` through the same QuickJS WASM engine and
capability loop.
`browser.script-engine` lets a long-lived browser session own the QuickJS engine
handle, including construction and disposal.

## Browser Engine Models

`browser.css` implements a small selector/cascade subset for tag, id, class,
attribute selectors including `=`, `~=`, `|=`, `^=`, `$=`, and `*=`,
form-state pseudo-classes `:disabled`, `:enabled`, `:checked`, `:required`,
`:optional`, `:read-only`, `:read-write`, `:invalid`, `:valid`, and `:focus`,
comma-separated selector groups in DOM queries while preserving commas inside
quoted attribute values, descendant and child combinators while preserving
whitespace inside quoted attribute values, selector specificity, `!important`
rule precedence that can
override inline normal declarations, and inline style normal precedence. The shared
`:valid` and `:invalid` matching uses the same required/minlength/maxlength
constraint vocabulary as document input, including required checkbox, radio
group, select controls, and readonly controls being barred from constraint
validation while still matching required/read-only state. `:disabled`/`:enabled`
also account for disabled optgroup ancestry and disabled fieldset ancestry,
while preserving the first legend exception. The shared
`kotoba.wasm.layout` projection maps the resulting
`display`, `color`, `font-size`, `margin`, `padding`, `border-width`,
`border-color`, `background`/`background-color`, `width`, `height`,
`min-width`, `max-width`, `box-sizing`, `flex-direction`, `flex-wrap`,
`justify-content`, `align-items`, `gap`, `position`, `left`, `top`, `z-index`,
`pointer-events`, and `opacity` style attributes into draw ops, including a basic
`display:flex` row/column projection with center, flex-end, space-between
alignment, row wrapping, and absolute-positioned children that render after
normal flow in z-index order. Opacity is inherited into node, rect, text, border,
caret, and selection draw ops without suppressing hit testing. It projects
form-control caret/selection state as rect draw ops, and emits overflow scroll
metadata plus clip push/pop ops that the WebGL/WebGPU reference hosts enforce for rects and text. The retained host also
applies those clip boundaries during hit testing, so clipped children do not
receive pointer events
outside their visible region, and both retained/session hit testing skip
`pointer-events:none` nodes so covered controls can still receive pointer input.
`browser.dom-bridge` handles the DOM query/mutation requests used by
compatibility runtimes with the same selector vocabulary. `browser.event-loop`
provides a deterministic timer/microtask queue, and
`browser.compat.quickjs-binding` defines the host binding contract for a future
QuickJS WASM component.
`browser.core/refresh-page` rebuilds tree, draw ops, and pending DOM ops from a
mutated persistent document, reusing the page's CSS rules, preserving inline
style, and clearing stale computed style when selector matches change.
`browser.session` can commit that refreshed document back through the host, so
script-produced DOM mutations are retained in page state instead of staying
inside a transient runtime state. Document commits also update the current
navigation entry, so back/forward restores the mutated page state rather than
the original parsed HTML snapshot. Provider-backed session restore also adopts
the persisted current navigation entry page as the active page state, and
`resume-current-page!` can recommit that restored page to the host without
advancing navigation.

`browser.chrome` models tabs, URL bar input, and navigation intent. It is browser
chrome state, not native UI. `browser.persistence` defines the datom-shaped
snapshot boundary for profile, storage, audit, chrome, OS surface, and session
navigation state. Snapshots are versioned, and legacy storage/session/surface
keys migrate through the same path used by session restore. Migration policy is
data: each step has a from/to version and named operations, and migrated
snapshots are validated before replay.
`browser.persistence-provider` binds that snapshot shape to real providers, with
an in-memory provider for tests and an EDN file provider for JVM tooling.

`browser.script` is the kotoba-clj/WASM document scripting hook. It calls an
injected WASM runner and applies returned capability requests through the same DOM
bridge used by compatibility runtimes.
`browser.page-script` discovers executable HTML `<script>` elements, including
module scripts, and `browser.session` can call an injected page script runner
after successful page commits. After discovered page scripts run, the same
runner receives lifecycle dispatch scripts for `DOMContentLoaded` on `document`
and `load` on `window`, so compatibility runtimes can route those events through
their existing `event/dispatch` capability loop. `document.readyState` moves
from `loading` to `interactive` before `DOMContentLoaded`, then to `complete`
before `load`.
External `script src` values are resolved against `document.baseURI`, including
the first `<base href="...">` when present, permission-gated as `:net/fetch`,
fetched only through the injected session fetch capability, and cached in
profile-scoped storage under `:quickjs.script/source`.

`browser.text-edit` models caret, selection, backward/forward delete, Home/End,
select-all, Shift+Arrow extension, and IME-style composition state for focused
windows. The same text editing model is reused for document form controls
through `browser.document-input`.
`browser.accessibility` projects a small role/name tree from kotoba documents and
OS surfaces for later host accessibility bridges and skips hidden/presentation
nodes. It covers basic landmark, heading, link, list, table, image, semantic
text, description list, figure, and form-control roles, including search, range,
number, button, and text-like input types. OS surface projection exposes the
application, launcher, workspace, windows, focus, geometry, text buffer, caret,
selection, composition, and scroll state directly from retained surface data.
`browser.accessibility/session-tree` combines the active page and OS surface into
one host-facing accessibility root with profile, URL, and focus metadata.
`browser.session/accessibility-tree` exposes that combined tree from the live or
provider-restored session as the host bridge entrypoint.
`input type=hidden` is excluded from the accessibility tree like other hidden
content and cannot be focused or clicked through host pointer input, while still
remaining available to form submit/reset data paths. Hidden inputs are also
barred from required/valid/invalid constraint validation and matching
interactive form-state pseudo-classes such as `:read-only` and `:read-write`.
`input type=file` is held behind the file-picker capability boundary. Pointer
clicks and labels do not expose ambient host paths or focus the control. Only an
explicit `:file/select` capability result can attach selected-file metadata, and
that metadata is reduced to file name/type/size before it reaches document state,
form data, or accessibility. Because it is ordinary page document state, selected
file metadata is retained through navigation-entry persistence and provider
restore without exposing ambient paths or file bytes.
Accessible
names can come from `aria-label`, `aria-labelledby`, associated labels, or
placeholders, with `alt` for image nodes and `title` as a final fallback.
Form control value, checked, disabled, selection, and focused state are
projected into both draw ops and accessibility nodes. `select multiple`
projects as a listbox with repeated selected values while disabled selected
options, including options disabled by an ancestor optgroup, remain visible as
selected option nodes but do not contribute control values.

## Host Session

`browser.session` is the R1 adapter from browser output to the `kotoba:dom` host
ABI. It commits page or OS-surface ops through `kotoba.wasm.host/commit!`, records
the last ABI batch, and keeps a small data history. It now restores and saves
profile/store/audit/chrome/surface/session snapshots through an optional persistence
provider. After restore, the session can resume the persisted current page into
the host with a `:page/resume` history event instead of creating a new navigation
entry, and can resume the persisted OS surface with a `:surface/resume` event
without reducing new input.
Successful page commits can also run discovered page scripts through an injected
script runner, so session startup/restored storage can construct a QuickJS WASM
engine and execute page module scripts without ambient filesystem or network
access. The session then dispatches page lifecycle events through that runner in
browser order: discovered scripts, `DOMContentLoaded`, then `load`, with
`document.readyState` advancing to `interactive` and `complete`.
The session owns a `browser.script-engine` manager for QuickJS lifecycle state,
so callers can explicitly ensure or dispose the engine instead of constructing it
ad hoc per page load.
Each committed page increments a session page generation. Async engine starts can
be completed with their original generation token; completions from older
navigations are disposed and recorded as stale instead of becoming the current
page engine.
`browser.script-scheduler` is the host bridge for this lifecycle: it starts an
engine through the session begin API, wires CLJS Promise settlement into
complete/fail, and exposes an abort hook for navigation cancellation.
Pending starts create a host abort signal. In browser/CLJS hosts that signal is a
real `AbortController.signal`; aborting a navigation calls `abort()` on the
controller. QuickJS WASM engine creation receives that signal and rejects aborted
startup, and URL-backed binary loading passes the signal into `fetch`.
Failed navigation is recorded as data and keeps an error document in session state
without committing that error HTML to the host by default.

`browser.session/apply-input-event!` reduces a canonical or aiueos-style input
event through `browser.input`, updates the OS surface, and commits the resulting
surface ops through the same host ABI.
`browser.session/navigate!`, `back!`, `forward!`, and `reload!` provide the first
navigation lifecycle model, including bounded redirects, same-document fragment
history entries, error documents, relative/protocol-relative/query-only
`Location` resolution with fragment preservation, absolute `Location`
dot-segment normalization, and case-insensitive redirect `Location` lookup with
redirect-hop cookie propagation through profile storage.

## R2 Browser Work

The next browser maturity step is tracked in this order:

1. broaden layout beyond the current block/flex box subset;
2. connect document model and DOM mutation to persistent page state;
3. expand QuickJS document bindings beyond query/fetch/storage shims;
4. add fetch/cache/cookie/CORS/security models;
5. add rendered caret/selection affordances and host IME bridge details;
6. connect compositor/window manager/accessibility bridges.

The first vertical slice of item 2 is implemented: mutated `kotoba.wasm.dom`
documents can be refreshed into page tree/draw/ops and committed back to the
session host.
The first vertical slice of item 3 is also implemented for QuickJS: the WASM shim
can create nodes, set attributes, append children, and assign text content through
capability requests, and the resulting execution document can be committed to the
session.
It also supports `document.body`, `getElementById`, and `replaceChildren` through
document snapshot backed element proxies and the existing `remove-children`
mutation.
`removeChild` and `insertBefore` are backed by explicit `kotoba.wasm.dom`
`remove-child` and `insert-before` ops.
The first vertical slice of item 5 is implemented for QuickJS-backed documents:
`input.value`, `input.checked`, selection offsets, and synchronous `input` events
work through document attrs plus `:event/dispatch` capability requests.
Host-side document input is also wired: `browser.session/apply-document-input-event!`
reduces text, keyboard editing, selection, composition, and select-change events
into form-control node attrs, dispatches composition/input/blur-time change
events through the document event model, and recommits the document through the
host ABI.
HTML loading now initializes form-control default state from initial
`value`/`checked`/`selected` attrs and textarea text content so reset and submit
paths do not depend on hand-authored `default-*` attrs.
The render/accessibility slice now carries form control state as well: input,
textarea, and select values, carets, and selections are visible in draw ops, and
label-derived names plus value/checked/disabled button and control state,
selection, and composition state are present in the accessibility projection;
input type roles and values are covered for submit/reset/button, range, search,
number, email, URL, telephone, password, and generic text-like controls;
password values are masked in the accessibility projection so host bridges and
automation do not receive raw secrets;
required and invalid validation state is projected as well. Fieldset-derived
disabled state, including the first legend exception, is projected consistently
with document input and CSS. ARIA state and relationship attributes such as
`aria-checked`, `aria-disabled`, `aria-required`, `aria-readonly`,
`aria-invalid`, `aria-pressed`, `aria-expanded`, `aria-selected`,
`aria-current`, `aria-controls`, `aria-describedby`, `aria-level`,
`aria-posinset`, `aria-setsize`, `aria-sort`, grid row/column indices/counts,
range values, orientation, and live-region metadata are projected for host UI
and automation. Table headers distinguish column headers from `scope="row"` row
headers.
CSS-hidden `display:none` nodes and other
hidden/presentation subtrees are excluded from both the accessibility tree and
accessible name text collection.
Scroll containers now expose overflow/scroll position in node and accessibility
metadata, layout emits clip boundaries for host renderers, and retained-host
hit testing respects the same active clip stack. Browser input now normalizes
wheel events into the shared pointer vocabulary and reduces them to window
scroll actions on the kotoba-only OS surface. Document-scoped wheel events can
also resolve the target scroll container from page draw-op coordinates, update
`scroll-left`/`scroll-top` attrs, dispatch `scroll`, and recommit the page
document through the same host ABI path.
Document-scoped click events use the same page draw-op coordinate resolution to
dispatch `click`, focus editable controls, emit blur/focus transitions, and
route subsequent text/key input to the focused document node. Disabled form
controls do not focus, dispatch click, or accept text editing. Readonly controls
can focus and update caret/selection state but do not mutate value, dispatch
input/composition mutations, or block submit validation; they remain successful
form controls for submit data. Checkbox clicks toggle checked state, dispatch
`input`/`change`, and recommit through the same document input path. Radio
clicks check the target and uncheck enabled peers in the same `name` group.
Select option clicks and `:select/change` events update selected option/value,
dispatch `input`/`change`, and recommit through the same path. Disabled options
and disabled select controls, including disabled optgroup ancestry and
fieldset-derived disabled state outside the first legend, are ignored for both
click and `:select/change` so they do not mutate value or produce a host commit.
Anchor clicks resolve the nearest `<a href>` ancestor, record link navigation
metadata such as `target`, `rel`, and `referrerpolicy`, convert explicit
current-navigation referrer metadata into the request `referer` header, and
enter the same session navigation lifecycle without committing the old document
when no click/focus document state changed.
Enter on an explicitly targeted anchor activates the same default action; Space
remains reserved for form control activation and scrolling behavior.
Non-current targets such as `_blank` record a `:link/context-request` without
fetching or navigating the current page. Context requests carry `rel`,
`referrerpolicy`, computed `opener?`, and referrer metadata; `_blank` is treated
as noopener, and `rel=noreferrer` suppresses the referrer for both context
requests and current navigation.
Fragment-only links resolve against the current page URL and enter same-document
fragment history without a fetch or render commit.
Links with `download` do not navigate or fetch through the page navigation path;
they record a `:link/download-request` and expose a
`:capability :download/request` record with the resolved URL and suggested
filename for an explicit download adapter.
A disabled selected option does not contribute select form data and does not
satisfy required/valid matching.
`select multiple` contributes one repeated form-data entry per enabled selected
option; with no enabled selection it is required-invalid and contributes no
entry.
Label clicks forward through `for` or nested controls and reuse the same focus,
checked, event dispatch, and commit path while respecting disabled fieldset
state and the first legend exception. Focused button, `input type=button`,
checkbox, and radio controls also activate from Space/Enter; `type=button`
controls dispatch click but do not submit, reset, navigate, or fetch. Submit
buttons and `input type=submit` dispatch form `submit` events, and Enter in
text inputs submits the ancestor form through the same document input/session
commit path. Submit results and events
carry constructed `:form/data` entries for named successful controls; submitters
with no `name` or an empty `name` still submit but do not add a payload entry, so later
navigation/fetch capability adapters can consume the payload without ambient DOM
access; hidden inputs are included in that data without becoming visible or
host-focusable controls, and their `required` attrs do not block submission.
Disabled submit/reset controls do not focus, dispatch click, activate from
keyboard, submit transport, or reset form state.
Resetters outside a form can associate through the `form` attribute and reset
the associated controls through the same document input/session commit path;
descendant controls whose `form` attribute names another owner are excluded from
the ancestor form and reset with their explicit owner instead.
Value-bearing input types such as `number` and `range` submit their `value` and
participate in required validation without becoming text-edit controls.
`input type=file` is not serialized or validated until the file-picker
capability supplies explicit selected-file metadata, preventing host paths from
leaking through click/focus/label handling, form data, or accessibility values.
`input type=image` submitters contribute coordinate entries as `name.x` and
`name.y` from the host pointer event.
GET form submits resolve `action` against the current page URL, encode
the form data into the query string, record `target`/`enctype` metadata, and
enter the normal session navigation lifecycle for current targets; unknown
method values fall back to GET. Non-current form targets such as `_blank` or
named frames record `:form/context-request` with the resolved URL, method,
enctype, form data, referrer metadata, and POST body metadata without fetching
or navigating the current page; `referrerpolicy=\"no-referrer\"` suppresses the
referrer. `method=\"dialog\"` records `:form/submit-dialog` with form data and
target/enctype metadata without fetching or navigating. POST form submits send
`application/x-www-form-urlencoded` bodies by default, support
`formenctype=\"text/plain\"` body/header overrides, support deterministic
`multipart/form-data` bodies for successful controls, and go through
`browser.net/fetch-resource`, so profile permission, cookies, CORS, and store
updates apply for current targets before successful same-origin or CORS-allowed
responses commit as pages; explicit GET/POST `referrerpolicy` metadata is converted
into the request `referer` header, while `no-referrer` suppresses it. File inputs
remain omitted from multipart until the explicit file-picker capability supplies
selected-file metadata; selected files contribute filename metadata only, not
ambient paths or file bytes. Denied or CORS-blocked submissions do not replace
the current page.
Redirect responses from POST submits record `:form/submit-redirect` with
target/enctype metadata and enter the normal navigation lifecycle. Submitter
`formaction`, `formmethod`, `formenctype`, and `formtarget` override the owning
form action/method/enctype/target when building the transport request.
Controls and submitters outside the form can associate through the `form`
attribute and participate in submit dispatch, form data, and navigation/fetch.
Required form controls now perform value-missing validation before submit, and
text controls also enforce `minlength`/`maxlength` as too-short/too-long
validation. Invalid controls dispatch `invalid`, keep validation state on the
document for accessibility projection, the reducer returns `:invalid?`, and
session transport is not started; subsequent text input, checkbox/radio
activation, select changes, reset, or successful submit clear stale validation
state. Page refresh recomputes CSS against the updated validation state, so
`:valid`/`:invalid` styles do not leave stale computed attrs after submit,
typing, or reset. `novalidate` and `formnovalidate`, including on external
submitters associated through `form`, skip required and length validation.
Disabled fieldsets suppress descendant focus, editing, validation, submit data,
and activation, including descendants associated to an external form, while
leaving controls inside the first legend enabled.
Reset buttons and `input type=reset` restore associated controls from
`default-value`/`default-checked`/`default-selected`, including non-text
value-bearing inputs such as number/range and all default-selected options in
`select multiple` even when an option is disabled by an ancestor optgroup;
disabled selected options keep selected state but do not become control values.
Reset also respects `form` ownership overrides, dispatches form `reset`, and
recommits through the same document input path.
The first vertical slice of item 4 is implemented as `browser.net`: injected
fetches can be wrapped with profile permission checks, profile-scoped GET cache
with `no-store` suppression and CORS-aware/requesting-origin/credentials-mode
reuse, cookies,
`Secure`/`SameSite=None` and `__Secure-`/`__Host-` acceptance checks,
`Max-Age=0` deletion, positive `Max-Age` and future RFC1123 `Expires` expiry
tracking,
`Path`/`Domain`/`SameSite=Strict` matching,
public-suffix-like `Domain` rejection,
past RFC1123 `Expires` deletion, multiple `Set-Cookie` values, credentials,
`HttpOnly` metadata plus script-readable/read-write cookie projection, CORS
checks, `Secure` send suppression on HTTP, stale metadata cleanup on overwrite,
same-name host-cookie precedence, same-name path variant cookies, and
non-simple request preflights, and QuickJS
`:net/fetch` can opt into that context. Credentialed cross-origin fetches
require explicit origin and `Access-Control-Allow-Credentials: true`, and
credentialed preflights require explicit allowed methods and header names.

## Model Verification

The browser repo owns the CLJC browser/session/document/script model. Host
packages own concrete WebGL/WebGPU smoke bundles.

```sh
cd orgs/kotoba-lang/browser
kbb -M:test
```

The smoke content/model remains as CLJC data in
[browser.visual-smoke-model](/Users/junkawasaki/github/com-junkawasaki/orgs/kotoba-lang/browser/src/browser/visual_smoke_model.cljk)
and is covered by `browser.visual-smoke-model-test`.
