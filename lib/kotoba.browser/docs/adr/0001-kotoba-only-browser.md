# ADR-0001: kotoba-only WASM browser

Status: accepted

Date: 2026-07-01

Maturity: R1.5 host adapter + input/text reducer + profile model + browser-use IBrowser compatibility/debug adapter + QuickJS WASM engine contract/integrity/lifecycle/session ownership/host scheduler/reusable context disposal/AbortController signal/generation-gated async completion/manifest validation/response validation/capability shape validation/basic source eval/Web API shims/document construction bindings/MutationObserver shim/module loader/storage-backed module provider/session construction/page module script execution/script-src fetch-cache-permission + persistent DOM mutation refresh/commit + compat execution contract + runtime manifest validation + document scripting hook + versioned persistence/session provider + migration policy + navigation lifecycle/audit + a11y projection + WebGL/WebGPU smoke implemented

Companion metadata: `docs/adr/0001-kotoba-only-browser.toml`

## Decision

Build `kotoba-lang/browser` as a kotoba-only, WASM-only browser, not a
web-compat JavaScript browser.

The browser reuses `wasm-ui` as the existing UI substrate:

- `kotoba.wasm.dom` for virtual document state and deterministic DOM ops.
- `kotoba:dom` WIT ABI for guest/host boundary.
- `kotoba.wasm.layout` for R0 layout and draw ops.
- existing WebGL/WebGPU/native hosts for presentation.

The browser adds the missing engine layer in phases:

R0 implemented:

1. navigation and history as data;
2. capability-gated fetch;
3. HTML-like parser into `kotoba.wasm.dom`;
4. inline style bridge into `kotoba.wasm.dom` style attributes;
5. OS UI surface model: apps, windows, focus, panels, and workspace state rendered
   through the same `kotoba:dom` ABI.
6. session adapter that commits page/surface ops to a `kotoba:dom` host;
7. input reducer that maps pointer/keyboard/text events to OS surface actions;
8. minimal account/profile/storage-partition/permission model;
9. origin normalization and profile-scoped storage model;
10. QuickJS/QuickJS-NG compatibility adapter contract as capability requests.
11. generic rule that language runtimes are WASM components behind capability
    adapters.
12. generic runtime descriptors for QuickJS, Python, Lua, and Scheme.
13. CSS selector/cascade subset, DOM query/mutation bridge, deterministic
    timer/microtask loop, browser chrome model, and persistence snapshot contract.

R1 implemented:

1. kotoba-clj/WASM document scripting only;
2. QuickJS/QuickJS-NG WASM binary loading and adapter attachment contract;
3. real persistence provider binding for profile/storage/audit datoms;
4. WebGPU visual smoke from this repo.
5. injected QuickJS WASM execution loop contract for eval/module/job/capability
   imports, including DOM, fetch, storage, timer, and unsupported capability
   paths.
6. session startup/save wiring for persistence providers, including storage and
   navigation history restore.
7. navigation lifecycle for redirect, back, forward, reload, and error document
   state, with audit datoms.
8. text editing model for caret, selection, backward/forward delete, Home/End,
   select-all, Shift+Arrow extension, composition, and keyboard editing keys.
9. accessibility tree projection with hidden/presentation filtering.
10. versioned snapshot migration policy, validation, replay, and runtime manifest
    validation.
11. QuickJS WASM binary integrity, engine instance lifecycle/readiness,
    manifest validation, capability result queue/handoff, response validation,
    capability request shape validation, module cache, and execution audit.
12. singlefile QuickJS WASM guest wiring for basic JavaScript source evaluation
    through the existing execution loop.
13. QuickJS guest shims for `document.querySelector`, `fetch`, and
    `localStorage` that emit host capability requests through the existing loop.
14. QuickJS guest module loader backed by an explicit engine `:modules` source
    map, with no ambient filesystem or network module reads.
15. profile-scoped storage module source provider using
    `quickjs.module:<specifier>` keys.
16. QuickJS engine option construction from restored browser session storage.
17. HTML page script discovery and session script-runner hook for page-load
    module execution.
18. long-lived browser-session ownership of QuickJS engine construction and
    disposal.
19. `<script src>` URL resolution, permission-gated fetch, and profile-scoped
    source cache.
20. page-generation tokens for async script engine starts, so stale completions
    after navigation are disposed instead of adopted.
21. host scheduler bridge that wires CLJS Promise settlement into session
    complete/fail and exposes navigation abort.
22. host abort signal creation for pending script engine starts, with CLJS
    `AbortController.abort()`, QuickJS WASM startup signal checks, and
    URL-backed WASM binary fetch signal propagation.

R1 specified, not implemented:

1. deeper cancellation adapters for host APIs whose third-party WASM
   initialization cannot be physically interrupted after it has entered library
   code.

## Naming

`wasm-ui` is too implementation-specific for the role it now plays. It is no
longer just "WASM UI"; it is the kotoba DOM/UI host ABI.

Preferred long-term naming:

- `kotoba-lang/ui`: canonical substrate for DOM ABI, retained virtual tree,
  layout, event ABI, and render host contracts.
- `kotoba-lang/gui`: later, OS/native shell integration: windows, menus, file
  dialogs, clipboard, accessibility bridges, IME, drag/drop, and desktop app
  conventions.

For now, keep the physical repo name `wasm-ui` to avoid breaking manifests. New
browser code should refer to it conceptually as `ui`.

## Architecture

The browser has two privileged WASM guest roles:

- Document guest: owns a document, mutates `kotoba.wasm.dom`, and emits `kotoba:dom`
  ops. R0 document input is an HTML-like trusted subset; R1 document scripts are
  kotoba-clj/WASM.
- Surface guest: owns OS UI shell state such as apps, windows, focus, launcher,
  workspace, and panels. It renders those as ordinary `kotoba:dom` nodes. Native
  windows/widgets are not the shell state.

Host responsibilities are intentionally narrow:

- fetch bytes for a granted URL/request;
- apply `kotoba:dom` ops to a UI host;
- present frames through WebGL/WebGPU/native renderer backends;
- translate pointer/keyboard/display events into capability-scoped input records;
- persist or query datoms when that capability is granted.

The core invariant is that document and OS UI behavior do not receive ambient
network, filesystem, HID, clipboard, GPU, or process access. They receive only
host capabilities that are visible at the ABI boundary.

Language runtimes follow the same invariant. JavaScript compatibility is only one
instance of a generic runtime-adapter rule: QuickJS/Boa/SpiderMonkey, Python, Lua,
Ruby, Scheme, and other language guests must run as WASM components. The browser
may wrap them with ergonomic APIs, but every effect still leaves the guest through
an explicit capability import and can be audited as datoms.

## Why kotoba-only means WASM-only

Chrome and Servo are useful references for architecture, but web compatibility
pulls in JavaScript semantics, WebIDL, legacy DOM behavior, layout quirks, storage
quirks, service workers, CSP, and cross-origin edge cases. That is a different
project.

Kotoba needs a deterministic, inspectable, capability-gated browser surface where
document behavior is kotoba data/code. The production execution unit is a
kotoba-clj/WASM guest. JVM/CLJS execution is allowed for tests and tooling only,
not as the document runtime.

- document structure is EDN/DOM ops;
- rendering is EDN/draw ops/render-IR;
- scripting is kotoba-clj/WASM;
- non-kotoba language runtimes are WASM components;
- host effects are explicit capabilities;
- state is datom-auditable.

## Coverage

R0 coverage is intentionally narrow but executable. The current evidence is:

| Requirement | Status | Evidence |
|---|---:|---|
| HTML-like input builds a `kotoba.wasm.dom` document | covered | `browser.core-test/html-loads-into-kotoba-dom-and-draw-ops` |
| DOM ops are emitted and can be ABI-encoded | covered | `browser.core-test/html-loads-into-kotoba-dom-and-draw-ops` |
| layout/draw ops are produced through existing UI substrate | covered | `browser.core-test/html-loads-into-kotoba-dom-and-draw-ops`, `browser.surface-test/os-surface-renders-through-kotoba-dom` |
| navigation uses injected fetch, not ambient I/O | covered | `browser.core-test/navigation-uses-capability-fetch` |
| failed navigation does not become a document | covered | `browser.core-test/navigation-error-is-data` |
| inline style subset reaches `kotoba.wasm.dom` style attrs | covered | `browser.core-test/inline-style-and-void-tags-are-bridged` |
| CSS selector/cascade subset handles attribute selectors, form-state pseudo-classes including disabled optgroup ancestry, validation-barred hidden/file inputs, and important precedence | covered | `browser.css-test/parses-attribute-selectors-and-important-declarations`, `browser.css-test/parses-attribute-selector-operators`, `browser.css-test/selector-list-split-ignores-commas-inside-attribute-values`, `browser.css-test/selector-tokenization-ignores-whitespace-inside-attribute-values`, `browser.css-test/parses-form-state-pseudo-classes`, `browser.css-test/cascade-applies-attribute-selectors-and-important-precedence`, `browser.css-test/cascade-important-rule-overrides-inline-normal-style`, `browser.css-test/cascade-applies-attribute-selector-operators`, `browser.css-test/cascade-applies-form-state-pseudo-classes` |
| CSS box/text/flex/position sizing style subset reaches draw ops | covered | `browser.core-test/css-box-and-text-styles-project-into-draw-ops`, `browser.core-test/css-background-color-alias-projects-into-draw-ops`, `browser.core-test/css-sizing-projects-min-max-width-and-border-box-into-draw-ops`, `browser.core-test/css-position-projects-absolute-z-index-into-draw-ops`, `browser.core-test/css-opacity-projects-into-draw-ops`, `browser.core-test/css-flex-layout-projects-row-and-column-into-draw-ops`, `browser.core-test/css-flex-layout-projects-justify-and-align-into-draw-ops`, `browser.core-test/css-flex-layout-projects-wrap-into-draw-ops`, `browser.session-test/document-click-hit-test-prefers-higher-z-index-absolute-node`, `browser.session-test/document-click-hit-test-skips-pointer-events-none-overlay`, `browser.session-test/document-click-hit-test-keeps-transparent-overlay-targetable`, `kotoba.wasm.abi-runtime-test/layout-projects-min-max-width-and-border-box-sizing`, `kotoba.wasm.abi-runtime-test/layout-projects-absolute-position-and-z-index-order`, `kotoba.wasm.abi-runtime-test/layout-projects-opacity-to-node-rect-text-and-descendants`, `kotoba.wasm.abi-runtime-test/layout-projects-flex-row-and-column`, `kotoba.wasm.abi-runtime-test/layout-projects-flex-justify-and-align`, `kotoba.wasm.abi-runtime-test/layout-projects-flex-wrap`, `kotoba.wasm.retained-host-test/retained-hit-test-skips-pointer-events-none-nodes` |
| hidden nodes and `input type=hidden` are excluded from accessibility projection and names | covered | `browser.accessibility-test/accessibility-tree-skips-hidden-and-presentation-nodes` |
| implicit semantic/link/list/table/image/form/input-type roles project into accessibility | covered | `browser.accessibility-test/document-projects-accessibility-tree`, `browser.accessibility-test/implicit-roles-cover-links-lists-tables-and-input-types`, `browser.accessibility-test/labels-project-form-control-accessible-names` |
| button/control, multiple select values including optgroup descendants, and fieldset-derived disabled state project into accessibility | covered | `browser.accessibility-test/form-controls-project-accessibility-state`, `browser.accessibility-test/disabled-fieldset-projects-accessibility-state` |
| ARIA states, relationships, structure, range values, and live regions project into accessibility | covered | `browser.accessibility-test/aria-state-projects-accessibility-state`, `browser.accessibility-test/aria-structure-and-range-project-accessibility-state`, `browser.accessibility-test/aria-live-region-projects-accessibility-state` |
| OS surface applications/windows/focus/geometry/text state project into accessibility | covered | `browser.accessibility-test/os-surface-projects-accessibility-tree` |
| active/restored browser session combines page and OS surface accessibility roots through the session API | covered | `browser.accessibility-test/browser-session-projects-combined-accessibility-tree`, `browser.accessibility-test/restored-session-exposes-host-accessibility-tree` |
| form controls project value/caret/selection state into draw ops | covered | `browser.core-test/form-controls-project-value-state-into-draw-ops`, `browser.core-test/form-control-caret-and-selection-project-into-draw-ops`, `kotoba.wasm.abi-runtime-test/layout-projects-form-control-caret-and-selection` |
| overflow/scroll state projects to clip ops and a11y | covered | `browser.core-test/overflow-scroll-projects-clip-and-scroll-offset-into-draw-ops`, `browser.accessibility-test/scroll-containers-project-accessibility-state`, `kotoba.wasm.abi-runtime-test/layout-projects-overflow-scroll-and-clip-ops` |
| OS UI apps/windows/focus render through `kotoba:dom` | covered | `browser.surface-test/os-surface-renders-through-kotoba-dom` |
| OS UI actions are pure data reducers | covered | `browser.surface-test/actions-drive-os-surface`, `browser.surface-test/focus-close-and-unknown-actions-are-pure` |
| pointer click focuses windows | covered | `browser.input-test/pointer-click-focuses-topmost-window` |
| pointer drag moves windows | covered | `browser.input-test/pointer-drag-moves-window-by-titlebar` |
| pointer drag resizes windows | covered | `browser.input-test/pointer-drag-resizes-window-from-corner` |
| keyboard and text input target focused windows | covered | `browser.input-test/keyboard-and-text-input-target-focused-window`, `browser.surface-test/keyboard-and-text-actions-are-recorded-on-focused-window` |
| keyboard editing keys update focused text model | covered | `browser.input-test/keyboard-editing-keys-drive-focused-text-model` |
| DOM/aiueos input events normalize to one vocabulary | covered | `browser.input-test/dom-and-aiueos-events-normalize-to-same-vocabulary` |
| pointer wheel events reduce to OS surface scroll actions | covered | `browser.input-test/pointer-wheel-scrolls-window-under-pointer` |
| retained host hit testing respects active clip stack and pointer-events suppression | covered | `kotoba.wasm.retained-host-test/retained-hit-test-respects-active-clip-stack`, `kotoba.wasm.retained-host-test/retained-hit-test-skips-pointer-events-none-nodes` |
| document input events update text/value input and textarea state | covered | `browser.document-input-test/text-input-updates-form-control-value-selection-and-dispatches`, `browser.document-input-test/composition-events-update-form-control-composition-state`, `browser.document-input-test/key-events-drive-selection-delete-home-end-and-select-all`, `browser.document-input-test/text-control-dispatches-change-on-blur-after-value-mutation`, `browser.document-input-test/disabled-form-controls-do-not-focus-or-edit`, `browser.document-input-test/disabled-fieldset-controls-do-not-submit-or-validate`, `browser.document-input-test/readonly-form-controls-focus-and-select-but-do-not-mutate-value`, `browser.document-input-test/readonly-controls-submit-data-but-do-not-block-validation`, `browser.session-test/document-input-events-update-page-document-and-commit`, `browser.session-test/document-text-change-dispatches-on-blur-through-session`, `browser.session-test/document-ime-events-commit-composition-through-session` |
| checkbox clicks toggle checked state and dispatch form events | covered | `browser.document-input-test/checkbox-click-toggles-checked-and-dispatches-input-change`, `browser.session-test/document-checkbox-click-toggles-and-commits-through-session` |
| radio clicks check target and uncheck same-name peers | covered | `browser.document-input-test/radio-click-checks-target-and-unchecks-group`, `browser.session-test/document-radio-click-checks-group-and-commits-through-session` |
| select option changes update value, dispatch events, recommit, reject disabled select/options including disabled optgroup and fieldset-derived disabled state, omit disabled selected options from payload/validity, and submit multiple selections as repeated entries | covered | `browser.document-input-test/select-option-click-updates-value-and-form-data`, `browser.document-input-test/disabled-selected-option-is-not-successful-or-valid`, `browser.document-input-test/optgroup-disabled-options-are-not-successful-valid-or-selectable`, `browser.document-input-test/multiple-select-submits-each-enabled-selected-option`, `browser.document-input-test/disabled-select-does-not-update-value-or-dispatch-events`, `browser.document-input-test/fieldset-disabled-select-does-not-update-value-or-dispatch-events`, `browser.session-test/document-select-change-commits-through-session`, `browser.session-test/disabled-selected-option-is-omitted-from-session-submit-query`, `browser.session-test/optgroup-disabled-option-is-omitted-from-session-submit-query`, `browser.session-test/multiple-select-submits-repeated-query-entries`, `browser.session-test/disabled-select-change-does-not-commit-through-session`, `browser.session-test/fieldset-disabled-select-change-does-not-commit-through-session` |
| label clicks activate associated form controls while respecting disabled fieldset and first legend state | covered | `browser.document-input-test/label-click-activates-associated-control`, `browser.document-input-test/nested-label-click-activates-descendant-control`, `browser.document-input-test/disabled-fieldset-labels-only-activate-first-legend-controls`, `browser.session-test/document-label-click-activates-control-and-commits-through-session`, `browser.session-test/disabled-fieldset-labels-only-activate-first-legend-controls-through-session` |
| focused controls activate from keyboard, including input type=button click dispatch without submit/reset | covered | `browser.document-input-test/focused-controls-activate-from-keyboard`, `browser.session-test/focused-document-control-activates-from-keyboard-through-session`, `browser.session-test/type-button-controls-do-not-submit-reset-or-fetch-through-session` |
| form submit default actions dispatch submit events with text/value input form data, omit nameless submitter payload entries, add image submitter coordinates, support GET/POST/dialog transport decisions with target/enctype metadata, keep non-current targets at a context boundary with referrer metadata, external submitters, disabled submit suppression, and type=button suppression | covered | `browser.document-input-test/submit-buttons-dispatch-form-submit`, `browser.document-input-test/nameless-submitters-submit-form-without-successful-entry`, `browser.document-input-test/disabled-submit-and-reset-controls-do-not-run-default-actions`, `browser.document-input-test/disabled-focused-submit-and-reset-controls-ignore-key-activation`, `browser.document-input-test/enter-in-text-input-dispatches-form-submit`, `browser.document-input-test/image-submit-button-adds-click-coordinate-entries`, `browser.document-input-test/form-attribute-associates-external-controls-and-submitters`, `browser.session-test/document-submit-button-dispatches-submit-and-commits-through-session`, `browser.session-test/disabled-submit-button-does-not-submit-or-fetch-through-session`, `browser.session-test/disabled-focused-submit-key-does-not-submit-or-fetch-through-session`, `browser.session-test/type-button-controls-do-not-submit-reset-or-fetch-through-session`, `browser.session-test/get-form-submit-navigates-with-form-data-query`, `browser.session-test/get-form-referrerpolicy-origin-sends-origin-referer`, `browser.session-test/nameless-submitters-navigate-without-query-entry`, `browser.session-test/image-form-submit-navigates-with-coordinate-query`, `browser.session-test/submitter-formaction-overrides-form-action`, `browser.session-test/submitter-formmethod-overrides-form-method`, `browser.session-test/submitter-formtarget-records-context-request-without-current-navigation`, `browser.session-test/unknown-formmethod-falls-back-to-get-navigation`, `browser.session-test/dialog-formmethod-records-submit-without-fetch-or-navigation`, `browser.session-test/form-attribute-external-submitter-navigates-with-associated-controls`, `browser.session-test/post-form-submit-fetches-through-net-policy-and-commits-response`, `browser.session-test/post-formenctype-text-plain-overrides-urlencoded-body`, `browser.session-test/post-form-referrerpolicy-origin-sends-origin-referer`, `browser.session-test/post-form-referrerpolicy-no-referrer-suppresses-referer`, `browser.session-test/post-form-non-current-target-records-context-request-without-fetch`, `browser.session-test/post-multipart-form-data-omits-file-input-without-picker-capability`, `browser.session-test/post-form-submit-denied-by-permission-does-not-call-host-fetch`, `browser.session-test/cross-origin-post-form-submit-is-blocked-without-cors`, `browser.session-test/cross-origin-post-form-submit-commits-when-cors-allows-origin`, `browser.session-test/post-form-submit-redirect-enters-navigation-lifecycle` |
| form validation blocks invalid submit transport, bars readonly controls from constraint validation while preserving submit data, and supports novalidate/formnovalidate for required and length constraints, including external submitters | covered | `browser.document-input-test/required-controls-block-submit-and-dispatch-invalid`, `browser.document-input-test/text-length-validation-blocks-submit`, `browser.document-input-test/readonly-controls-submit-data-but-do-not-block-validation`, `browser.document-input-test/novalidate-and-formnovalidate-skip-required-validation`, `browser.session-test/invalid-required-form-submit-does-not-navigate`, `browser.session-test/readonly-invalid-looking-controls-submit-and-navigate`, `browser.session-test/external-formnovalidate-submitter-skips-required-validation-and-navigates`, `browser.session-test/invalid-text-length-submit-does-not-navigate`, `browser.session-test/external-formnovalidate-submitter-skips-text-length-validation-and-navigates`, `browser.session-test/validation-state-recomputes-css-after-submit-and-text-input`, `browser.accessibility-test/required-invalid-form-state-projects-accessibility-state` |
| disabled fieldsets suppress descendant controls except first legend, including descendants associated to external forms | covered | `browser.document-input-test/disabled-fieldset-controls-do-not-submit-or-validate`, `browser.session-test/fieldset-disabled-external-associated-control-is-omitted-from-submit`, `browser.css-test/cascade-applies-form-state-pseudo-classes`, `browser.dom-bridge-test/query-selector-supports-form-state-pseudo-classes`, `browser.quickjs-execution-test/quickjs-dom-query-uses-shared-form-state-pseudo-classes`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-selector-vocabulary-matches-host-subset`, `browser.accessibility-test/disabled-fieldset-projects-accessibility-state` |
| validation state clears on control mutation and CSS refresh recomputes pseudo-class styles | covered | `browser.document-input-test/required-controls-block-submit-and-dispatch-invalid`, `browser.session-test/validation-state-recomputes-css-after-submit-and-text-input`, `browser.accessibility-test/required-invalid-form-state-projects-accessibility-state` |
| form reset default actions restore associated text/value/check/select controls including select multiple defaults and disabled optgroup selected state, dispatch reset events, support external resetters and `form` ownership overrides, and suppress disabled resetters | covered | `browser.document-input-test/reset-buttons-reset-associated-form-controls`, `browser.document-input-test/form-attribute-associates-external-resetters`, `browser.document-input-test/disabled-submit-and-reset-controls-do-not-run-default-actions`, `browser.document-input-test/disabled-focused-submit-and-reset-controls-ignore-key-activation`, `browser.session-test/document-reset-button-resets-and-commits-through-session`, `browser.session-test/external-resetter-resets-associated-form-through-session`, `browser.session-test/disabled-reset-button-does-not-reset-or-commit-through-session`, `browser.session-test/disabled-focused-reset-key-does-not-reset-or-commit-through-session` |
| document wheel events update scroll containers and recommit page state | covered | `browser.document-input-test/wheel-events-update-scroll-container-and-dispatch-scroll`, `browser.document-input-test/wheel-events-ignore-non-scrollable-targets`, `browser.session-test/document-wheel-events-update-scroll-container-and-commit`, `browser.session-test/document-wheel-events-resolve-scroll-container-from-page-coordinates` |
| document click events dispatch handlers, focus editable controls from coordinates, activate anchor navigation from click and Enter including fragment-only links through the session lifecycle, convert current link referrer metadata into request headers, suppress current and context link referrers with `rel=noreferrer`, keep non-current targets at a context boundary with opener/referrer metadata, and keep download links at an explicit capability boundary | covered | `browser.document-input-test/click-events-dispatch-and-focus-editable-targets`, `browser.document-input-test/link-click-produces-navigation-default-action`, `browser.document-input-test/link-enter-key-activates-navigation-default-action`, `browser.document-input-test/download-link-click-produces-download-boundary-metadata`, `browser.document-input-test/focus-transition-dispatches-blur-before-next-focus`, `browser.session-test/document-click-events-resolve-target-from-page-coordinates`, `browser.session-test/document-link-click-navigates-through-session`, `browser.session-test/document-link-referrerpolicy-origin-sends-origin-referer`, `browser.session-test/document-link-noreferrer-suppresses-current-navigation-referer`, `browser.session-test/document-link-enter-key-navigates-through-session`, `browser.session-test/document-blank-target-link-records-context-request-without-current-navigation`, `browser.session-test/document-noreferrer-target-link-suppresses-context-referrer`, `browser.session-test/document-fragment-link-click-enters-same-document-navigation`, `browser.session-test/document-download-link-click-records-boundary-without-navigation` |
| hidden inputs submit as form data but are not host-focusable/clickable, validation participants, interactive form-state pseudo matches, QuickJS shim matches, or accessibility-visible | covered | `browser.document-input-test/click-events-dispatch-and-focus-editable-targets`, `browser.document-input-test/submit-buttons-dispatch-form-submit`, `browser.document-input-test/required-controls-block-submit-and-dispatch-invalid`, `browser.css-test/cascade-applies-form-state-pseudo-classes`, `browser.dom-bridge-test/query-selector-supports-form-state-pseudo-classes`, `browser.quickjs-execution-test/quickjs-dom-query-uses-shared-form-state-pseudo-classes`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-selector-vocabulary-matches-host-subset`, `browser.accessibility-test/accessibility-tree-skips-hidden-and-presentation-nodes` |
| file inputs do not expose ambient host paths through click/focus/label handling, but explicit file-picker metadata can enter document/form/a11y state and survive provider restore | covered | `browser.document-input-test/click-events-dispatch-and-focus-editable-targets`, `browser.document-input-test/file-input-label-click-does-not-activate-file-picker-boundary`, `browser.document-input-test/file-select-event-applies-explicit-file-picker-result`, `browser.document-input-test/submit-buttons-dispatch-form-submit`, `browser.document-input-test/required-controls-block-submit-and-dispatch-invalid`, `browser.session-test/document-click-events-resolve-target-from-page-coordinates`, `browser.session-test/document-file-label-click-does-not-commit-without-file-picker-capability`, `browser.session-test/post-multipart-form-data-omits-file-input-without-picker-capability`, `browser.session-test/post-multipart-form-data-includes-explicit-file-picker-metadata`, `browser.session-test/restored-session-preserves-selected-file-metadata`, `browser.css-test/cascade-applies-form-state-pseudo-classes`, `browser.dom-bridge-test/query-selector-supports-form-state-pseudo-classes`, `browser.quickjs-execution-test/quickjs-dom-query-uses-shared-form-state-pseudo-classes`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-selector-vocabulary-matches-host-subset`, `browser.accessibility-test/implicit-roles-cover-links-lists-tables-and-input-types`, `browser.accessibility-test/selected-file-metadata-projects-accessible-filename-only` |
| page ops commit through `kotoba.wasm.host/commit!` | covered | `browser.session-test/load-html-commits-page-ops-to-host` |
| failed navigation does not commit stale/error HTML | covered | `browser.session-test/navigate-commits-only-successful-pages` |
| navigation lifecycle: redirect, case-insensitive relative/protocol-relative/query-only redirect `Location` with fragment preservation, absolute `Location` dot-segment normalization, redirect-hop cookies, same-document fragment history, back, forward, reload, error document | covered | `browser.session-test/navigation-lifecycle-supports-redirect-back-forward-reload-and-error-document`, `browser.session-test/navigation-redirect-persists-cookie-for-next-hop`, `browser.session-test/navigation-redirect-resolves-relative-location`, `browser.session-test/same-document-fragment-navigation-updates-history-without-fetch-or-render` |
| OS surface actions commit through host ABI | covered | `browser.session-test/surface-actions-commit-os-ui-to-host` |
| OS surface state persists through provider restore and can resume into the host | covered | `browser.session-test/os-surface-state-restores-and-resumes-through-provider`, `browser.persistence-test/persistence-snapshot-combines-profile-storage-and-audit-datoms` |
| input events reduce and commit through host ABI | covered | `browser.session-test/input-events-reduce-and-commit-os-ui-to-host` |
| account/profile identity model | covered | `browser.profile-test/account-carries-local-or-verified-identity`, `browser.profile-test/browser-state-selects-active-profile` |
| profile storage partitions and permission grants | covered | `browser.profile-test/profile-partitions-storage-and-permissions` |
| internal default permission and explicit deny decisions | covered | `browser.profile-test/permission-decision-allows-internal-defaults-and-denies-unknown` |
| origin normalization | covered | `browser.origin-test/origin-normalizes-scheme-and-authority`, `browser.origin-test/same-origin-compares-normalized-origin` |
| profile-scoped storage isolation | covered | `browser.storage-test/storage-is-partitioned-by-profile-and-origin`, `browser.storage-test/storage-delete-removes-partitioned-value` |
| fetch permission/cache/cookie/CORS/preflight policy layer | covered | `browser.net-test/same-origin-fetch-stores-cookie-and-cache`, `browser.net-test/cache-policy-skips-no-store-and-non-get-responses`, `browser.net-test/cached-cross-origin-response-misses-when-cors-origin-does-not-match`, `browser.net-test/cross-origin-cache-is-partitioned-by-requesting-origin`, `browser.net-test/cross-origin-cache-is-partitioned-by-credentials-mode`, `browser.net-test/set-cookie-enforces-secure-and-samesite-none-constraints`, `browser.net-test/secure-cookie-is-not-sent-over-http`, `browser.net-test/set-cookie-enforces-secure-and-host-prefixes`, `browser.net-test/set-cookie-max-age-zero-deletes-profile-cookie`, `browser.net-test/set-cookie-max-age-positive-expires-and-purges-on-send`, `browser.net-test/set-cookie-expires-past-deletes-profile-cookie`, `browser.net-test/set-cookie-future-expires-is-tracked`, `browser.net-test/multiple-set-cookie-values-are-applied-in-order`, `browser.net-test/set-cookie-httponly-is-tracked-for-script-boundary`, `browser.net-test/script-set-cookie-cannot-create-httponly-cookie`, `browser.net-test/script-set-cookie-respects-domain-and-samesite-policy`, `browser.net-test/cookie-overwrite-clears-stale-metadata`, `browser.net-test/cookie-header-respects-set-cookie-path`, `browser.net-test/same-name-cookies-can-coexist-across-paths`, `browser.net-test/cookie-header-respects-domain-scope`, `browser.net-test/set-cookie-rejects-public-suffix-like-domain-scope`, `browser.net-test/cookie-header-prefers-host-cookie-over-domain-cookie-with-same-name`, `browser.net-test/cookie-header-respects-samesite-strict`, `browser.net-test/credentialed-fetch-sends-profile-cookie`, `browser.net-test/cross-origin-credentialed-fetch-requires-explicit-origin-and-credentials`, `browser.net-test/cross-origin-fetch-requires-cors-header`, `browser.net-test/cross-origin-non-simple-fetch-runs-preflight`, `browser.net-test/cross-origin-preflight-denial-blocks-fetch`, `browser.net-test/cross-origin-preflight-wildcard-headers-are-not-credentialed`, `browser.net-test/cross-origin-preflight-wildcard-methods-are-not-credentialed`, `browser.net-test/fetch-denied-by-profile-permission-does-not-call-host-fetch` |
| successful navigation is remembered in profile history | covered | `browser.session-test/successful-page-commit-remembers-profile-navigation` |
| QuickJS compat adapter is a WASM capability boundary | covered | `browser.compat-test/quickjs-adapter-is-wasm-capability-boundary` |
| browser-like Web APIs emit capability requests, including sandboxed console messages, sandboxed clipboard read/write, document.cookie profile cookie projection, sandboxed Location API navigation intent, window context requests, profile-backed permission queries, permission-gated geolocation reads, notification requests, fullscreen requests, media capture requests, sandboxed WebSocket requests, deterministic crypto random requests, sandboxed Worker requests, sandboxed BroadcastChannel requests, permission-gated beacon requests, and sandboxed History API requests; pure URL and URLSearchParams shims run without host requests | covered | `browser.compat-test/webapi-shims-emit-capability-requests`, `browser.compat-test/webapi-event-listen-and-dispatch-requests`, `browser.compat-test/webapi-console-log-request-is-data`, `browser.compat-test/denied-webapi-request-is-data`, `browser.quickjs-execution-test/quickjs-engine-can-cancel-animation-frame-timers`, `browser.quickjs-execution-test/quickjs-global-event-listeners-record-sandboxed-targets`, `browser.quickjs-execution-test/quickjs-console-records-sandboxed-log-messages`, `browser.quickjs-execution-test/quickjs-clipboard-capability-uses-sandboxed-store`, `browser.quickjs-execution-test/quickjs-document-cookie-uses-script-readable-profile-cookie-policy`, `browser.quickjs-execution-test/quickjs-location-records-sandboxed-navigation-intent`, `browser.quickjs-execution-test/quickjs-window-open-records-context-request`, `browser.quickjs-execution-test/quickjs-permissions-query-uses-profile-grants`, `browser.quickjs-execution-test/quickjs-geolocation-read-requires-profile-grant`, `browser.quickjs-execution-test/quickjs-geolocation-read-denies-without-profile-grant`, `browser.quickjs-execution-test/quickjs-notification-permission-and-show-use-profile-grant`, `browser.quickjs-execution-test/quickjs-notification-show-denies-without-profile-grant`, `browser.quickjs-execution-test/quickjs-fullscreen-request-records-context-request-with-profile-grant`, `browser.quickjs-execution-test/quickjs-fullscreen-request-denies-without-profile-grant`, `browser.quickjs-execution-test/quickjs-media-capture-requires-camera-and-microphone-grants`, `browser.quickjs-execution-test/quickjs-media-capture-denies-missing-microphone-grant`, `browser.quickjs-execution-test/quickjs-websocket-connect-send-close-records-sandboxed-connection`, `browser.quickjs-execution-test/quickjs-websocket-connect-denies-without-target-origin-grant`, `browser.quickjs-execution-test/quickjs-crypto-random-uses-sandboxed-provider`, `browser.quickjs-execution-test/quickjs-crypto-random-defaults-are-deterministic-without-provider`, `browser.quickjs-execution-test/quickjs-worker-create-message-terminate-records-sandboxed-worker`, `browser.quickjs-execution-test/quickjs-worker-create-denies-without-script-origin-grant`, `browser.quickjs-execution-test/quickjs-broadcast-channel-records-sandboxed-messages`, `browser.quickjs-execution-test/quickjs-broadcast-message-denies-when-channel-is-not-open`, `browser.quickjs-execution-test/quickjs-beacon-send-records-sandboxed-request-with-profile-grant`, `browser.quickjs-execution-test/quickjs-beacon-send-denies-without-target-origin-grant`, `browser.quickjs-execution-test/quickjs-history-state-records-sandboxed-entries`, `browser.quickjs-execution-test/quickjs-history-traverse-bounds-without-ambient-navigation`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-animation-frame-timer-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-global-event-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-console-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-clipboard-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-document-cookie-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-window-open-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-location-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-url-and-search-params`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-permissions-query-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-geolocation-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-notification-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-fullscreen-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-media-capture-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-websocket-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-crypto-random-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-worker-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-broadcast-channel-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-beacon-capability`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-history-capability` |
| Web Components lifecycle maps to JS capability calls | covered | `browser.compat-test/custom-elements-registry-emits-lifecycle-calls` |
| compat requests are auditable | covered | `browser.compat-test/compat-requests-can-be-audited` |
| QuickJS execution calls are auditable | covered | `browser.audit-test/quickjs-events-are-auditable`, `browser.quickjs-execution-test/quickjs-module-loads-are-cached-and-calls-are-audited` |
| non-kotoba language runtimes are WASM capability adapters | decided | `browser` follows `aiueos` ADR-0008; no native/JVM runtime execution in production |
| generic runtime descriptors have no ambient access | covered | `browser.runtime-test/runtime-descriptors-have-no-ambient-access`, `browser.runtime-test/placeholder-runtimes-use-same-shape` |
| runtime component manifests reject ambient/native imports | covered | `browser.runtime-test/runtime-manifest-validation-rejects-ambient-or-native-imports` |
| QuickJS compat adapter is backed by generic runtime descriptor | covered | `browser.compat-test/quickjs-adapter-is-backed-by-generic-runtime-descriptor` |
| CSS selector cascade | covered | `browser.css-test/parses-simple-selector-rules`, `browser.css-test/cascade-applies-tag-id-class-and-inline-precedence`, `browser.css-test/cascade-applies-descendant-child-and-specificity` |
| DOM query/mutation bridge | covered | `browser.dom-bridge-test/query-selector-uses-css-selector-subset`, `browser.dom-bridge-test/query-selector-supports-descendant-and-child-combinators`, `browser.dom-bridge-test/query-selector-supports-attribute-selectors`, `browser.dom-bridge-test/query-selector-supports-form-state-pseudo-classes`, `browser.dom-bridge-test/query-selector-supports-selector-groups`, `browser.dom-bridge-test/mutation-bridge-creates-and-appends-nodes`, `browser.dom-bridge-test/mutation-bridge-set-and-remove-style-attribute-updates-inline-style-model` |
| HTML form default-state initialization for text/value/check/select controls, including disabled optgroup selected state without control value | covered | `browser.core-test/html-load-initializes-form-control-default-state`, `browser.document-input-test/reset-buttons-reset-associated-form-controls`, `browser.session-test/document-reset-button-resets-and-commits-through-session` |
| mutated document refreshes tree/draw/ops with existing CSS rules | covered | `browser.core-test/refreshed-page-renders-mutated-document-with-existing-css-rules`, `browser.core-test/refreshed-page-recomputes-css-and-clears-stale-computed-style` |
| script DOM mutation can be committed to persistent page state, retained in the current navigation entry, restored through the persistence provider, and resumed into the host | covered | `browser.session-test/script-document-state-commits-persistent-page-document`, `browser.session-test/script-document-state-updates-current-navigation-entry`, `browser.session-test/restored-session-uses-persisted-current-page-state`, `browser.session-test/script-document-state-recomputes-css-and-clears-stale-style`, `browser.session-test/script-style-attribute-mutation-commits-inline-style-model` |
| deterministic event loop, timers, microtasks | covered | `browser.event-loop-test/microtasks-run-before-ready-timers`, `browser.event-loop-test/timers-become-ready-when-time-advances` |
| QuickJS WASM binding contract | covered | `browser.quickjs-binding-test/quickjs-binding-records-evaluate-and-module-load-requests`, `browser.quickjs-binding-test/quickjs-binding-drains-deterministic-event-loop` |
| injected QuickJS WASM execution loop | covered | `browser.quickjs-execution-test/quickjs-engine-eval-applies-capability-imports`, `browser.quickjs-execution-test/quickjs-engine-module-fetch-storage-and-unsupported-capabilities`, `browser.quickjs-execution-test/quickjs-execution-does-not-apply-denied-capability-requests` |
| QuickJS WASM binary integrity | covered | `browser.quickjs-binary-test/quickjs-binary-integrity-is-checked-before-attach` |
| QuickJS WASM engine instance contract | covered | `browser.quickjs-execution-test/quickjs-wasm-engine-contract-requires-valid-binary-and-invoke`, `browser.quickjs-execution-test/quickjs-wasm-engine-lifecycle-starts-and-disposes`, `browser.quickjs-execution-test/quickjs-wasm-engine-rejects-invalid-runtime-manifest` |
| QuickJS capability result queue and handoff | covered | `browser.quickjs-execution-test/quickjs-engine-eval-applies-capability-imports`, `browser.quickjs-execution-test/quickjs-engine-module-fetch-storage-and-unsupported-capabilities`, `browser.quickjs-execution-test/quickjs-execution-does-not-apply-denied-capability-requests`, `browser.quickjs-execution-test/quickjs-capability-results-preserve-request-ids`, `browser.quickjs-execution-test/quickjs-passes-pending-capability-results-to-next-invocation` |
| QuickJS engine response validation | covered | `browser.quickjs-execution-test/quickjs-engine-response-validation-drops-malformed-requests`, `browser.quickjs-execution-test/quickjs-engine-response-validation-rejects-non-sequential-requests`, `browser.quickjs-execution-test/quickjs-engine-response-validation-rejects-non-map-response` |
| QuickJS capability request shape validation | covered | `browser.quickjs-execution-test/quickjs-capability-request-validation-blocks-invalid-known-shapes` |
| QuickJS engine invocation failure propagation | covered | `browser.quickjs-execution-test/quickjs-engine-invocation-failure-is-recorded-and-audited` |
| QuickJS module cache | covered | `browser.quickjs-execution-test/quickjs-module-loads-are-cached-and-calls-are-audited` |
| actual QuickJS/QuickJS-NG source evaluation | covered | `browser.quickjs-wasm-test/quickjs-wasm-descriptor-is-wasm-engine-boundary` |
| QuickJS guest Web API shims emit host capability requests | covered | `browser.compat-test/webapi-event-listen-and-dispatch-requests`, `browser.quickjs-execution-test/quickjs-engine-eval-applies-capability-imports` |
| QuickJS document construction bindings emit DOM mutation requests | covered | `browser.quickjs-execution-test/quickjs-dom-mutations-resolve-client-node-ids`, `browser.quickjs-execution-test/quickjs-create-element-ns-persists-namespace-attribute`, `browser.quickjs-execution-test/quickjs-document-fragment-append-flattens-children`, `browser.quickjs-execution-test/quickjs-clone-node-mutates-detached-copy-and-appends-by-client-id`, `browser.quickjs-execution-test/quickjs-inner-html-mutates-through-host-parser`, `browser.quickjs-execution-test/quickjs-outer-html-mutates-through-host-parser`, `browser.quickjs-execution-test/quickjs-text-node-data-mutates-through-set-text`, `browser.quickjs-execution-test/quickjs-text-node-split-and-normalize-mutate-document`, `browser.quickjs-execution-test/quickjs-style-attribute-mutation-updates-inline-style-model`, `browser.compat-test/webapi-document-create-element-ns-is-create-element-request`, `browser.compat-test/webapi-document-create-fragment-is-create-fragment-request`, `browser.compat-test/webapi-clone-node-is-clone-node-request`, `browser.compat-test/webapi-set-inner-html-is-set-inner-html-request`, `browser.compat-test/webapi-set-outer-html-is-set-outer-html-request`, `browser.compat-test/webapi-set-text-is-set-text-request`, `browser.compat-test/webapi-split-text-and-normalize-are-dom-mutation-requests`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-namespace-element-construction`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-document-fragment-construction`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-clone-node-binding`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-inner-html-binding`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-outer-html-binding`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-text-node-data-bindings`, `browser.dom-bridge-test/mutation-bridge-clones-node-subtrees`, `browser.dom-bridge-test/mutation-bridge-sets-inner-html-with-trusted-parser`, `browser.dom-bridge-test/mutation-bridge-sets-outer-html-with-trusted-parser`, `browser.dom-bridge-test/mutation-bridge-updates-text-node-data`, `browser.dom-bridge-test/mutation-bridge-splits-text-node`, `browser.dom-bridge-test/mutation-bridge-normalizes-adjacent-text-nodes` |
| QuickJS body/getElementById/replaceChildren/querySelector/classList/traversal/focus/URL/baseURI/currentScript/forms/images/links/scripts/readyState and media/script element property bindings | covered | `browser.quickjs-execution-test/quickjs-dom-replace-children-resolves-selector-and-client-ids`, `browser.quickjs-execution-test/quickjs-class-list-mutates-class-attribute-through-dom-bridge`, `browser.quickjs-execution-test/quickjs-focus-and-blur-mutations-update-document-focus`, `browser.quickjs-execution-test/quickjs-dom-query-uses-shared-attribute-selector-vocabulary`, `browser.quickjs-execution-test/quickjs-dom-query-uses-shared-form-state-pseudo-classes`, `browser.quickjs-execution-test/quickjs-dom-query-uses-shared-selector-groups`, `browser.quickjs-execution-test/quickjs-evaluate-projects-current-script-into-document-snapshot`, `browser.quickjs-execution-test/quickjs-evaluate-projects-document-base-uri-for-url-property-bindings`, `browser.compat-test/webapi-class-list-set-is-class-attribute-mutation`, `browser.compat-test/webapi-surface-includes-scoped-element-query-selectors`, `browser.compat-test/webapi-surface-includes-document-root-and-collection-bindings`, `browser.compat-test/webapi-surface-includes-dom-traversal-properties`, `browser.compat-test/webapi-surface-includes-focus-bindings`, `browser.compat-test/webapi-surface-includes-form-owner-and-label-bindings`, `browser.compat-test/webapi-surface-includes-select-option-bindings`, `browser.compat-test/webapi-surface-includes-form-control-property-bindings`, `browser.compat-test/webapi-surface-includes-node-mutation-convenience-methods`, `browser.compat-test/webapi-surface-includes-attribute-convenience-methods`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-class-list-mutation`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-scoped-element-query-selectors`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-tag-and-class-collection-bindings`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-dom-traversal-properties`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-focus-bindings`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-form-owner-and-label-bindings`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-select-option-bindings`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-form-control-property-bindings`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-node-mutation-convenience-methods`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-attribute-convenience-methods`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-selector-vocabulary-matches-host-subset`, `browser.dom-bridge-test/query-selector-uses-css-selector-subset`, `browser.dom-bridge-test/document-snapshot-includes-parent-children-and-text`, `browser.dom-bridge-test/document-snapshot-includes-ready-state`, `browser.dom-bridge-test/mutation-bridge-focus-and-blur-updates-document-focus` |
| document title projection and mutation | covered | `browser.core-test/html-title-is-exposed-as-page-title`, `browser.dom-bridge-test/document-snapshot-includes-ready-state`, `browser.dom-bridge-test/mutation-bridge-sets-document-title`, `browser.quickjs-execution-test/quickjs-evaluate-passes-document-snapshot-to-engine`, `browser.quickjs-execution-test/quickjs-document-title-mutates-through-dom-bridge`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-focus-bindings`, `browser.session-test/successful-page-commit-remembers-profile-navigation` |
| QuickJS removeChild/insertBefore bindings | covered | `browser.quickjs-execution-test/quickjs-dom-remove-child-and-insert-before-resolve-client-ids`, `browser.quickjs-execution-test/quickjs-document-fragment-append-flattens-children`, `browser.dom-bridge-test/mutation-bridge-inserts-and-removes-child-nodes`, `browser.dom-bridge-test/mutation-bridge-appends-document-fragment-children` |
| QuickJS document snapshot read bindings | covered | `browser.dom-bridge-test/document-snapshot-includes-parent-children-and-text`, `browser.quickjs-execution-test/quickjs-evaluate-passes-document-snapshot-to-engine` |
| QuickJS element event bindings | covered | `browser.compat-test/webapi-event-listen-and-dispatch-requests`, `browser.dom-bridge-test/event-bridge-registers-and-dispatches-listeners`, `browser.dom-bridge-test/event-bridge-removes-listeners-before-dispatch`, `browser.quickjs-execution-test/quickjs-event-listen-and-dispatch-apply-through-dom-bridge` |
| QuickJS MutationObserver shim | covered | `browser.compat-test/webapi-surface-includes-mutation-observer-binding`, `browser.quickjs-wasm-test/quickjs-wasm-webapi-shim-exposes-mutation-observer-binding` |
| QuickJS form control text/value input bindings | covered | `browser.quickjs-execution-test/quickjs-form-control-state-mutates-document-and-dispatches-input` |
| QuickJS-mutated document can commit through session | covered | `browser.quickjs-execution-test/quickjs-mutated-document-commits-through-session` |
| QuickJS module loader | covered | `browser.quickjs-wasm-test/quickjs-wasm-descriptor-is-wasm-engine-boundary` |
| QuickJS storage-backed module source provider | covered | `browser.quickjs-wasm-test/quickjs-wasm-module-provider-can-read-profile-storage` |
| URL bar, tabs, navigation intent | covered | `browser.chrome-test/url-bar-commit-produces-navigation-intent`, `browser.chrome-test/tabs-can-be-focused-and-finished` |
| persistence snapshot contract for profile/storage/audit/chrome/surface/session | covered | `browser.persistence-test/persistence-snapshot-combines-profile-storage-and-audit-datoms`, `browser.persistence-test/persistence-adapter-contract-has-no-ambient-access` |
| versioned snapshot migration policy | covered | `browser.persistence-test/persistence-migrates-legacy-snapshot-shapes`, `browser.persistence-test/persistence-validates-current-snapshot-schema`, `browser.persistence-provider-test/providers-load-migrated-legacy-snapshots` |
| kotoba-clj/WASM document scripting hook | covered | `browser.script-test/document-script-applies-dom-capability-requests`, `browser.script-test/document-script-denies-unknown-capability-request` |
| real persistence provider binding | covered | `browser.persistence-provider-test/memory-provider-saves-loads-and-appends-datoms`, `browser.persistence-provider-test/edn-file-provider-persists-browser-state` |
| persistence provider session startup/save wiring | covered | `browser.session-test/session-restores-and-saves-through-persistence-provider`, `browser.session-test/navigation-audit-is-persisted-after-back-forward-and-reload` |
| session navigation snapshot datoms | covered | `browser.persistence-test/persistence-snapshot-combines-profile-storage-and-audit-datoms` |
| datom audit schema | covered | `browser.audit-test/audit-events-are-datom-shaped-and-replayable`, `browser.session-test/session-records-audit-datoms-for-page-surface-and-input` |
| QuickJS WASM binary integration contract | covered | `browser.quickjs-binary-test/quickjs-binary-descriptor-validates-wasm-magic`, `browser.quickjs-binary-test/quickjs-binary-can-attach-to-adapter` |
| text editing caret, selection, composition | covered | `browser.text-edit-test/caret-selection-and-composition-edit-text`, `browser.text-edit-test/forward-delete-home-end-shift-and-select-all-edit-text`, `browser.input-test/keyboard-editing-keys-drive-focused-text-model`, `browser.input-test/keyboard-selection-delete-home-end-and-select-all-drive-focused-text-model` |
| accessibility tree projection | covered | `browser.accessibility-test/document-projects-accessibility-tree`, `browser.accessibility-test/implicit-roles-cover-links-lists-tables-and-input-types`, `browser.accessibility-test/accessibility-tree-skips-hidden-and-presentation-nodes`, `browser.accessibility-test/form-controls-project-accessibility-state`, `browser.accessibility-test/labels-project-form-control-accessible-names`, `browser.accessibility-test/focused-document-control-projects-accessibility-state`, `browser.accessibility-test/aria-state-projects-accessibility-state`, `browser.accessibility-test/aria-structure-and-range-project-accessibility-state`, `browser.accessibility-test/aria-live-region-projects-accessibility-state`, `browser.accessibility-test/os-surface-projects-accessibility-tree`, `browser.accessibility-test/browser-session-projects-combined-accessibility-tree`, `browser.accessibility-test/restored-session-exposes-host-accessibility-tree` |
| document keyboard listener dispatch | covered | `browser.document-input-test/keyboard-events-dispatch-keydown-and-keyup-listeners`, `browser.session-test/focused-document-control-dispatches-keyboard-listeners-through-session` |
| document beforeinput dispatch | covered | `browser.document-input-test/text-input-updates-form-control-value-selection-and-dispatches`, `browser.document-input-test/composition-events-update-form-control-composition-state`, `browser.document-input-test/keyboard-events-dispatch-keydown-and-keyup-listeners`, `browser.session-test/focused-document-control-dispatches-keyboard-listeners-through-session` |
| document pointer hover events | covered | `browser.document-input-test/pointer-move-updates-hover-state-and-dispatches-hover-events`, `browser.session-test/document-pointer-move-resolves-hover-target-from-page-coordinates`, `browser.browser-use-test/kotoba-extended-actions-drive-focus-hover-key-and-scroll-to` |
| document pointer down/up/cancel events | covered | `browser.document-input-test/pointer-down-and-up-dispatch-listeners-without-click-activation`, `browser.session-test/document-pointer-down-and-up-resolve-target-from-page-coordinates` |
| document pointer capture | covered | `browser.document-input-test/pointer-down-and-up-dispatch-listeners-without-click-activation`, `browser.session-test/document-pointer-capture-routes-move-until-release` |
| pointer metadata preservation | covered | `browser.input-test/dom-and-aiueos-events-normalize-to-same-vocabulary`, `browser.document-input-test/pointer-down-and-up-dispatch-listeners-without-click-activation`, `browser.session-test/document-pointer-down-and-up-resolve-target-from-page-coordinates` |
| page script discovery | covered | `browser.page-script-test/page-script-discovers-inline-classic-and-module-scripts` |
| page script src URL resolution | covered | `browser.page-script-test/page-script-resolves-src-against-page-url`, `browser.session-test/script-src-resolves-against-document-base-uri` |
| browser-use IBrowser compatibility adapter | covered | `browser.browser-use-test/kotoba-browser-implements-browser-use-protocol-with-existing-actions`, `browser.browser-use-test/kotoba-browser-can-load-static-html-for-debug`, `browser.browser-use-test/browser-use-state-resolves-link-and-image-input-urls-against-base-uri`, `browser.browser-use-test/kotoba-extended-actions-drive-focus-hover-key-and-scroll-to`, `browser.browser-use-test/kotoba-browser-use-actions-include-compat-wrapper-and-snapshot`, `browser.browser-use-test/kotoba-browser-use-actions-drive-selector-and-coordinate-form-input`, `browser.browser-use-test/kotoba-browser-use-wait-for-checks-current-state`, `browser.browser-use-test/kotoba-browser-use-diagnose-reports-targeting-state-without-throwing`, `browser.browser-use-test/kotoba-browser-use-extracts-semantic-page-state`, `browser.browser-use-test/browser-use-recipe-runs-against-kotoba-browser-without-browser-use-changes`, `browser.browser-use-test/browser-use-recipe-checks-and-selects-through-kotoba-host-capability-opts`, `browser.browser-use-test/kotoba-session-mirrors-playwright-session-host-shape` |
| session script runner hook after page commit | covered | `browser.session-test/load-html-runs-discovered-page-scripts-through-runner` |
| session page-load lifecycle dispatch order and readyState transitions | covered | `browser.session-test/load-html-dispatches-page-lifecycle-after-discovered-scripts`, `browser.session-test/load-html-without-script-runner-still-completes-document-ready-state` |
| script src permission/fetch/cache path | covered | `browser.session-test/script-src-fetches-through-permission-and-caches-source`, `browser.session-test/script-src-denied-by-permission-does-not-fetch-or-run` |
| QuickJS fetch can use network policy context | covered | `browser.quickjs-execution-test/quickjs-net-fetch-can-use-profile-cache-cookie-and-cors-policy`, `browser.quickjs-execution-test/quickjs-net-fetch-records-cors-block`, `browser.quickjs-execution-test/quickjs-net-fetch-denied-by-profile-permission-does-not-call-host-fetch` |
| session-owned QuickJS engine lifecycle | covered | `browser.session-test/session-owns-script-engine-lifecycle` |
| generation-gated async script engine completion | covered | `browser.session-test/stale-script-engine-completion-is-disposed-after-navigation`, `browser.session-test/script-runner-receives-page-generation` |
| host scheduler for engine Promise completion and abort | covered | `browser.script-scheduler-test/scheduler-starts-synchronous-engine-into-session-atom`, `browser.script-scheduler-test/scheduler-aborts-pending-engine-start` |
| host abort signal passed to engine factory and aborted on navigation | covered | `browser.script-scheduler-test/scheduler-passes-abort-signal-to-engine-factory-and-aborts-it` |
| WASM binary fetch receives host abort signal | covered | `browser.compat.quickjs-binary/load-url` accepts `:signal` |
| QuickJS engine construction from restored session storage | covered | `browser.quickjs-wasm-test/quickjs-wasm-engine-options-can-be-built-from-session-storage` |
| QuickJS page-load module script execution through capability loop | covered | `browser.session-test/load-html-runs-discovered-page-scripts-through-runner`, `browser.script-scheduler-test/scheduler-starts-synchronous-engine-into-session-atom` |
| WebGL/WebGPU visual host adapters | moved | Host repos own concrete canvas bundles; this repo retains the CLJC smoke model in `browser.visual-smoke-model-test`. |

Verification command:

```sh
cd orgs/kotoba-lang/browser
kbb -M:test
```

## Maturity Ladder

R0 implemented:

- trusted HTML-like subset parser;
- capability fetch entry point;
- DOM op emission via `kotoba.wasm.dom`;
- layout/draw-op projection via `kotoba.wasm.layout`;
- OS surface data model for apps/windows/focus;
- pure surface action reducer;
- canonical input reducer for pointer, keyboard, and text events;
- minimal account/profile model with profile-scoped storage keys and permission grants;
- origin normalization and pure profile-scoped storage;
- QuickJS/QuickJS-NG compatibility adapter contract;
- runtime-adapter rule for non-kotoba languages as WASM components;
- generic runtime descriptors for QuickJS, Python, Lua, and Scheme;
- runtime component manifest validation for WASM/no-ambient/explicit import limits;
- CSS selector/cascade subset with tag/id/class/attribute selectors, including
  `=`, `~=`, `|=`, `^=`, `$=`, and `*=`, form-state pseudo-classes
  `:disabled`, `:enabled`, `:checked`, `:required`, `:optional`,
  `:read-only`, `:read-write`, `:invalid`, `:valid`, and `:focus`,
  with `:valid`/`:invalid` connected to required/minlength/maxlength
  constraints for text controls, required checkbox/radio groups, and required
  selects; `:disabled`/`:enabled` include disabled optgroup ancestry and
  disabled fieldset ancestry with the first legend exception,
  comma-separated selector
  groups in DOM queries without splitting commas inside quoted attribute values,
  descendant and child combinators without splitting whitespace inside quoted
  attribute values, specificity,
  `!important` rule precedence that can override
  inline normal declarations, inline normal precedence, draw-op projection for
  `display`, text color/size, margin, padding, border,
  `background`/`background-color`, dimensions, form-control caret/selection
  rects, overflow scroll metadata, clip push/pop
  ops enforced by WebGL/WebGPU reference hosts, retained-host hit testing that
  respects active clip boundaries, and a shared DOM query/mutation bridge
  selector vocabulary;
- HTML load initializes form-control default state from initial
  `value`/`checked`/`selected` attrs and textarea text content, including the
  implicit first selected option for single selects;
- deterministic event loop for timers and microtasks;
- shared input vocabulary for pointer click/move/drag/resize, keyboard, text,
  composition, and wheel-to-window-scroll actions;
- browser chrome model for tabs, URL bar, and navigation intent;
- versioned persistence snapshot contract for profile/storage/audit/chrome/surface/session datoms.

R1 implemented:

- browser-host adapter that commits `:browser/ops` to a real `kotoba:dom` host;
- input events committed through the same session/host adapter;
- datom-shaped audit log for browser/session/compat effects;
- QuickJS WASM binding, binary loading/attachment, and injected execution loop
  contracts for eval/module/job plus DOM/fetch/storage/timer schedule/cancel
  capabilities,
  without vendoring a JS-evaluating engine instance yet;
- QuickJS WASM binary integrity, engine lifecycle/readiness contract, capability
  result queue/handoff, manifest validation, response validation, capability
  request shape validation including clipboard read/write, window-open
  context requests, profile-backed permission queries, permission-gated
  geolocation reads, notification requests, fullscreen context requests, media
  capture requests, sandboxed WebSocket requests, deterministic crypto random
  requests, sandboxed Worker requests, sandboxed BroadcastChannel requests, and
  permission-gated beacon requests, module cache, and execution audit datoms;
- persistence provider binding for memory and EDN-file backed snapshots;
- persistence provider wiring into session startup and save paths, including
  storage, OS surface, and navigation history restore;
- legacy snapshot migration policy, validation, and replay through
  provider/session restore paths;
- kotoba-clj/WASM document script hook through injected runners and capability requests;
- HTML page script discovery and session script-runner hook for page-load
  execution, followed by `DOMContentLoaded` on `document` and `load` on
  `window`, with `document.readyState` moving from `loading` to `interactive`
  and then `complete`;
- `<script src>` URL resolution against `document.baseURI` including
  `<base href>`, permission-gated fetch, and profile-scoped source cache;
- session-owned QuickJS engine construction/disposal manager;
- generation-gated async script engine begin/complete flow that disposes stale
  completions after navigation;
- host scheduler bridge for engine Promise completion/failure and navigation
  abort;
- host abort signal creation for pending engine starts, with CLJS
  `AbortController.abort()`, QuickJS startup abort checks, and fetch signal
  propagation for URL-backed WASM binary loading;
- QuickJS engine construction from restored session storage and page module
  script execution through the existing capability loop;
- navigation lifecycle for bounded redirects, case-insensitive
  relative/protocol-relative/query-only redirect `Location` resolution,
  fragment preservation, absolute `Location` dot-segment normalization,
  redirect-hop cookie propagation, same-document fragment history, sandboxed
  History API requests, back, forward,
  reload, and error document state, with audit datoms;
- text editing state for caret, selection, backward/forward delete, Home/End,
  select-all, Shift+Arrow extension, composition, and keyboard editing keys;
- accessibility tree projection for role/name/heading level with
  hidden/presentation/`input type=hidden` filtering, semantic/link/list/table/image/form/input-type roles, and names from `aria-label`,
  `aria-labelledby`, associated labels, `alt`, placeholders, and `title`;
- browser WebGL visual smoke using existing `wasm-ui` WebGL host;
- browser WebGPU visual smoke using existing `wasm-ui` WebGPU host.

R1 next:

- first-class aiueos `:runtime` kind and language/engine manifest keys;
- deeper cancellation adapters for host APIs whose third-party WASM
  initialization cannot be physically interrupted after it has entered library
  code;
- additional future migration steps as schemas evolve.

R2 roadmap:

1. broaden CSS/layout/render tree coverage beyond the current block box subset;
2. connect document model and DOM mutation to persistent page state;
3. expand QuickJS document bindings beyond query/fetch/storage shims;
4. add fetch/cache/cookie/CORS/security models;
5. add rendered caret/selection affordances and host IME bridge details;
6. connect compositor/window manager/accessibility bridges.

R2 started:

- mutated `kotoba.wasm.dom` documents can be refreshed into page tree/draw/ops
  with existing CSS rules;
- script-produced document state can be committed back to the session host,
  retained as persistent page state, and restored from the current navigation
  entry after back/forward traversal or provider-backed session restore; restored
  pages can be recommitted to the host with a `:page/resume` history event
  without advancing navigation.
- OS surface state, including windows, focus, text buffers, and geometry, is
  stored in provider snapshots and can be recommitted to the host with a
  `:surface/resume` history event without reducing new input.
- OS surface accessibility projection exposes application, launcher, workspace,
  windows, focus, geometry, text buffer, caret, selection, composition, and
  scroll state directly from retained surface data.
- session-level accessibility projection combines active page and OS surface
  roots into one host-facing tree with profile, URL, and focused-window metadata.
- `browser.session/accessibility-tree` exposes that combined accessibility tree
  from live and provider-restored sessions as the host bridge entrypoint.
- QuickJS document construction bindings for `body`, `createElement`,
  `createElementNS`, `createDocumentFragment`, `createTextNode`, `getElementById`, `documentElement`, `head`,
  `setAttribute`, `removeAttribute`, `appendChild`, `removeChild`,
  `insertBefore`, `replaceChildren`, `append`, `prepend`, `before`, `after`,
  `replaceWith`, `remove`, `cloneNode`, `textContent` assignment,
  `innerHTML` assignment, `outerHTML` assignment, and `document.title`
  assignment emit DOM mutation
  capabilities with client-id to node-id and DocumentFragment child flattening
  resolution; Text `data`/`nodeValue`, `splitText`, `normalize`, and
  CharacterData mutation helpers emit `:set-text`, `:split-text`, and
  `:normalize`, and `classList.add/remove/toggle` writes the same `class`
  attribute through `:dom/mutate`/`:set-attribute`; `toggleAttribute`,
  `dataset` deletion, and `style.removeProperty` reuse the same set/remove
  attribute capability path;
- QuickJS receives a document snapshot at evaluation/module-load boundaries and
  can read `document.querySelector`, `document.querySelectorAll`,
  `document.getElementsByTagName`, `document.getElementsByClassName`,
  `document.forms`, `document.images`, `document.links`, `document.scripts`,
  descendant-scoped `Element.querySelector`, `Element.querySelectorAll`,
  `Element.getElementsByTagName`, `Element.getElementsByClassName`,
  `children`, `childNodes`, `parentNode`, `parentElement`, `firstChild`,
  `lastChild`, `firstElementChild`, `lastElementChild`, `previousSibling`,
  `nextSibling`, `previousElementSibling`, `nextElementSibling`, `id`,
  `className`, `classList`, `dataset`, `attributes`, `style`, `getAttribute`,
  `hasAttribute`, `matches`, `closest`, `tagName`, `nodeName`, `localName`,
  `namespaceURI`, `textContent`, `document.URL`, `document.documentURI`,
  `document.baseURI`, `document.currentScript`, `document.readyState`, and `document.title`,
  plus `Element.contains`, `isConnected`, and `ownerDocument`,
  without ambient browser DOM access; document-level query and collection APIs
  search the connected root tree while element-scoped queries can still operate
  on detached element handles;
  guest-side selector matching
  covers the same attribute operator and form-state pseudo-class subset as the
  host DOM bridge for `matches`, `closest`, and snapshot-backed
  `querySelector*`;
- QuickJS element, window, and document events can register/remove/dispatch
  through `:event/listen`, `:event/remove`, and `:event/dispatch` capabilities,
  with synchronous `addEventListener`, `removeEventListener`, `dispatchEvent`,
  `click()`, target/currentTarget, bubbling, `preventDefault`,
  `stopPropagation`, minimal `Event`, and sandboxed `CustomEvent`, `MouseEvent`,
  and `KeyboardEvent` constructors in the WASM shim;
- QuickJS exposes a minimal `MutationObserver` shim for supported script-visible
  attribute, child-list, and character-data mutation APIs. Delivery is
  scheduled through the same deterministic `:timer/microtask` capability queue
  as `queueMicrotask`, while records expose target, added/removed nodes,
  attribute names, and opt-in old values;
- QuickJS timers emit `:timer/schedule` from `setTimeout`, `:timer/cancel`
  from `clearTimeout`, `:timer/schedule`/`:timer/cancel` with
  `:timer/kind :animation-frame` from `requestAnimationFrame`/
  `cancelAnimationFrame`, and `:timer/microtask` from `queueMicrotask`; the
  deterministic host event loop drains microtasks before ready timers and can
  remove pending timer callbacks before drain;
- QuickJS WASM uses a reusable VM context so `:js/job` drain can invoke
  registered timer and microtask callbacks and feed their capability requests
  back through the same execution loop; the session-owned engine dispose hook
  closes the reusable VM/runtime and prevents further host invocation;
- QuickJS form control proxies expose `value`, `checked`, `type`, `name`,
  `selectionStart`, `selectionEnd`, and `setSelectionRange`, and persist
  `value`/`checked` through document attr mutations and `focus`/`blur` through
  document focus mutations while `input` events travel through the same event
  capability path;
- QuickJS link, image, and script-like proxies expose attribute-backed `href`,
  `alt`, `async`, `defer`, baseURI-resolved `href`/`src`, and current
  `complete` snapshot state through the same element proxy surface;
- `browser.browser-use/kotoba-browser` implements the existing
  `browseruse.browser/IBrowser` protocol over `browser.session` as an optional
  adapter, so browser-use actions, agents, and recipes can operate a kotoba-only
  browser without changing browser-use itself; its state `:debug` projection
  includes history tail, draw ops, accessibility tree, audit summary/events, host
  recording state, last batch, navigation entries/redirect/error summary, and
  document-input result; the adapter also
  exposes baseURI-resolved `href`/`src` attrs for agent inspection and `:href`
  recipe targeting, and supplies recipe `:check` and `:select` host capability
  opts over the same document input reducer; kotoba-specific browser-use agents
  can additionally use `kotoba-session`, which mirrors browser-use's
  Playwright session map shape with `:browser`, `:screenshot`, `:select`,
  `:check`, and `:close`, use the combined `browser-use-actions` controller, or
  concatenate `extended-actions` for `get_state`, `extract`, `click`,
  `click_selector`, `click_at`, `type`, `type_selector`, `clear`,
  `clear_selector`, `append_text`, `append_text_selector`, `check_selector`,
  `uncheck`, `uncheck_selector`, `select_selector`, `press`, `screenshot`,
  `wait_for`, `diagnose`, `focus_element`, `hover_element`, `hover_at`,
  `scroll_selector`, `scroll_at`, `press_key`, `scroll_to_element`,
  `navigation_state`, `go_forward`, and `reload`;
  selector actions resolve through the shared DOM selector vocabulary,
  coordinate actions use the session hit-test path, `wait_for`
  checks selector/text/URL conditions against current kotoba state without
  ambient sleep, `diagnose` returns non-throwing selector/index/text/URL match
  state plus candidate elements for browser-use debugging, `navigation_state`
  exposes entries, redirects, reload/error state, and error document text, and text
  replace/clear/append, checkbox/radio check and
  uncheck, select value change, scroll, and hover all dispatch through the same
  document input reducer; hover updates document `:hover` state and dispatches
  pointer/mouse over, enter, move, out, and leave listener events; `extract`
  returns semantic DOM, visible text, accessibility tree, draw ops, full state,
  or snapshot data for page understanding/debugging; `screenshot` captures the retained
  draw-op/accessibility/semantic snapshot as data and can write it as a JVM EDN
  artifact;
- host-side document input events reduce through `browser.document-input` into
  `input`/`textarea` `value`, selection, composition attrs, and `select`
  selected option/value attrs, dispatch pointerdown/pointerup/pointercancel/hover,
  keydown/keyup, beforeinput, composition/input/blur-time change events with
  pointer metadata preserved when supplied, keep implicit pointer capture from
  `pointerdown` until `pointerup` or `pointercancel`, then recommit through
  `browser.session/apply-document-input-event!`;
- document-scoped wheel events can resolve target scroll containers from page
  draw-op coordinates, update `scroll-left`/`scroll-top` attrs, dispatch
  `scroll`, refresh layout draw ops, and recommit the page document through the
  same host ABI path;
- document-scoped click events can resolve target nodes from page draw-op
  coordinates, dispatch `click`, focus editable controls, emit blur/focus
  transitions, route subsequent text/key input to the focused document node, and
  suppress focus/click/text editing for disabled form controls while allowing
  readonly controls to focus and change selection without mutating value, avoid
  blocking constraint validation, and remain successful submit controls; anchor
  clicks resolve the nearest `<a href>` ancestor and enter the same session
  navigation lifecycle with link target metadata; Enter on a targeted anchor
  activates the same default action while Space remains reserved for form
  controls and scrolling; non-current targets such as `_blank` record a context
  request without fetching or navigating the current page and include `rel`,
  `referrerpolicy`, computed `opener?`, and referrer metadata; `_blank` is
  treated as noopener, and `rel=noreferrer` suppresses the referrer;
  fragment-only links resolve against the current page URL and enter
  same-document fragment history without fetch or render commit;
  links with `download` record a `:download/request` capability boundary instead
  of fetching, writing files, or navigating through page navigation;
- checkbox clicks toggle checked state, dispatch `input`/`change`, and recommit
  through the same document input path;
- radio clicks check the target, uncheck enabled peers in the same `name` group,
  dispatch `input`/`change`, and recommit through the document input path;
- select option clicks and `:select/change` events update selected option/value,
  dispatch `input`/`change`, and recommit through the document input path;
  disabled select controls, disabled optgroup ancestry, fieldset-derived
  disabled select controls outside the first legend, and disabled options are
  ignored and do not mutate value or produce a host commit; disabled selected
  options do not contribute select payload entries or satisfy required/valid
  matching; `select multiple`
  contributes repeated entries for each enabled selected option and is
  required-invalid when no enabled option is selected;
- label clicks resolve `for` targets or nested controls, then activate the
  associated form control through the same focus, checked-state, event dispatch,
  and document commit path while respecting disabled fieldset state and the
  first legend exception;
- focused button, `input type=button`, checkbox, and radio controls activate
  from Space/Enter through the same document input path; `type=button` controls
  dispatch click but do not submit, reset, navigate, or fetch;
- submit buttons, `input type=submit`, and Enter in text inputs dispatch form
  `submit` events with constructed `:form/data` for named successful controls,
  omit submitter payload entries when `name` is absent or empty,
  then recommit through the same document input path; GET submits resolve
  `action` against the current page URL, encode form data into the query string,
  and enter the normal session navigation lifecycle for current targets with
  target/enctype metadata; unknown method values fall back to GET; non-current
  form targets such as `_blank` or named frames record `:form/context-request`
  with resolved URL, method, enctype, form data, referrer metadata, and POST body
  metadata without fetching or navigating the current page; `referrerpolicy="no-referrer"`
  suppresses that referrer; `method="dialog"` records
  `:form/submit-dialog` with form data and target/enctype metadata without
  fetching or navigating; POST submits send `application/x-www-form-urlencoded`
  bodies by default, support `formenctype="text/plain"` body/header overrides,
  support deterministic `multipart/form-data` bodies for successful
  controls, and pass through `browser.net/fetch-resource` so profile permission,
  cookies, CORS, and store updates apply for current targets before successful
  same-origin or CORS-allowed responses commit as pages; explicit GET/POST
  `referrerpolicy` metadata is converted into the request `referer` header,
  while `no-referrer` suppresses it; file inputs remain omitted from
  multipart until the explicit file-picker capability supplies selected-file
  metadata, and selected files contribute filename metadata only, not ambient
  paths or file bytes; denied or CORS-blocked submissions do not replace the
  current page; POST redirect responses record `:form/submit-redirect` with
  target/enctype metadata and enter the normal navigation lifecycle; submitter
  `formaction`, `formmethod`, `formenctype`, and `formtarget` override the owning
  form action/method/enctype/target when building the transport request; controls and submitters
  outside the form can associate through the `form` attribute and participate in
  submit dispatch, form data, and navigation/fetch;
- disabled submit/reset controls, including external submitters with
  `formaction`/`formmethod`, do not focus, dispatch click, activate from
  keyboard, submit transport, reset form state, or produce a host commit;
- resetters outside the form can associate through the `form` attribute and
  reset the associated controls through the same document input/session commit
  path; descendant controls whose `form` attribute names another owner are
  excluded from the ancestor form and reset with their explicit owner instead;
- required form controls perform value-missing validation before submit, and
  text controls enforce `minlength`/`maxlength` as too-short/too-long validation;
  invalid controls dispatch `invalid`, keep validation state on the document for
  accessibility projection, the reducer returns `:invalid?`, session transport
  does not start, and subsequent control mutation/reset/successful submit clears
  stale validation state; readonly controls are barred from constraint
  validation while still submitting their values; page refresh recomputes
  `:valid`/`:invalid` CSS so computed styles do not survive submit, text input,
  or reset transitions;
  `novalidate`/`formnovalidate`, including on external submitters associated
  through `form`, skip required and length validation;
- `input type=file` stays behind an explicit file-picker capability: click/focus
  and labels do not expose host paths, while `:file/select` can attach
  selected-file name/type/size metadata for accessibility and successful form
  data without exposing ambient paths or file bytes; this metadata is retained
  as page document state through provider restore;
- disabled fieldsets suppress descendant focus/editing/activation, validation,
  and successful form-data entries, including descendants associated to external
  forms, while preserving controls inside the first legend;
- reset buttons and `input type=reset` restore associated controls from
  `default-value`/`default-checked`/`default-selected`, including every
  default-selected option in `select multiple` even when disabled by an ancestor
  optgroup; disabled selected options keep selected state but do not become
  control values; reset dispatches form `reset` and recommits through the same
  document input path;
- form control state is projected into render draw ops and the accessibility
  tree so host UI/automation can inspect label-derived names, value, checked,
  disabled button/control state, optgroup-disabled option state,
  fieldset-derived disabled state with first legend exception, input type
  roles/values for submit/reset/button, range,
  search, number, email, URL, telephone, password, and generic text-like controls,
  masked password values, `select multiple` listbox values,
  ARIA checked/disabled/required/readonly/invalid/pressed/
  expanded/selected/current state, controls/description relationships,
  table row/column header distinction, sort state, structural positions,
  grid row/column indices/counts, range values,
  orientation, live-region metadata, readonly, selection, composition,
  focused state, caret, selection
  highlight, overflow, and scroll state without ambient DOM access; hidden,
  presentation, and `display: none` subtrees are excluded from both the
  accessibility projection and accessible name text collection;
- `browser.net` wraps injected fetch with profile permission decisions,
  profile-scoped GET response cache with `Cache-Control: no-store` suppression
  and CORS-aware/requesting-origin/credentials-mode reuse,
  cookies, `Secure`/`SameSite=None` and `__Secure-`/`__Host-` cookie
  acceptance checks, `Max-Age=0`
  cookie deletion, positive `Max-Age` and future RFC1123 `Expires` expiry
  tracking, past RFC1123 `Expires` cookie deletion, `Path`/`Domain`-scoped
  cookie sending, public-suffix-like `Domain` rejection,
  `SameSite=Strict` cross-site suppression, ordered multiple
  `Set-Cookie` values, `HttpOnly` script-boundary metadata and non-HttpOnly
  script-readable/read-write projection, stale metadata cleanup on overwrite,
  `Secure` send suppression on HTTP, same-name host-cookie precedence,
  same-name path variant cookies, credential handling, CORS checks, and
  non-simple cross-origin request preflight;
  credentialed cross-origin responses require an explicit requesting origin and
  `Access-Control-Allow-Credentials: true`, and credentialed preflights require
  explicit allowed methods and header names; QuickJS `:net/fetch` can opt into that policy
  through execution `net-context`;
- `browser.session/net-context` derives the active page/profile/store/fetch
  policy context for page script execution, and `commit-script-state!` persists
  returned cache/cookie store updates back into the long-lived browser session;
- `document.cookie` reads/writes now cross the QuickJS capability loop and use
  the same script-readable cookie projection as the network policy layer;
- Location APIs now cross the QuickJS capability loop as sandboxed navigation
  intent rather than mutating the long-lived browser session directly;
- `URL` and `URLSearchParams` are now available as pure QuickJS sandbox shims
  for URL parsing, relative resolution, and query manipulation;
- `console.log`/`info`/`warn`/`error`/`debug` now record sandboxed console
  messages without ambient host stdout/stderr writes;
- `kotoba.wasm.dom` now has explicit `remove-child` and `insert-before` ops for
  single-child structural edits;
- `browser.browser-use/kotoba-browser` now lets existing browser-use actions,
  agents, and recipes drive this browser through the unchanged `IBrowser`
  protocol, including baseURI-resolved `href`/`src` state attrs for inspection
  and `:href` recipe matching, plus optional extended browser-use-style actions
  for state read, semantic/text/accessibility extraction, indexed/selector/
  coordinate click, indexed/selector text replace/clear/append, selector
  checkbox/radio check, indexed/selector checkbox uncheck, selector select value
  change, current-state wait checks, key press, snapshot capture, focus, hover,
  selector/coordinate scroll, scroll-to-element, forward/reload navigation, and
  navigation lifecycle diagnostics.

R2 later:

- datom-backed origin and storage partitions;
- datom audit replay into live session state;
- OS shell panels, modal surfaces, and host adapters for clipboard/file-picker
  capabilities;
- browser-agent supervisor integration over the browser-use-compatible adapter.

## Risks

- The R0 parser is intentionally not WHATWG HTML. It must stay labelled as a
  trusted subset until a spec-oriented parser exists.
- `wasm-ui` still carries its historical name. Renaming to `ui` should be done as
  a separate manifest-aware migration.
- OS UI through `kotoba:dom` means host escape hatches are tempting; all native
  affordances must be capability imports, not direct calls from document code.

## Consequences

- We can ship a small browser sooner.
- Existing `browser-use`/`browser-agent` can drive this browser through the same
  surface APIs.
- Sites requiring JavaScript web compatibility are out of scope.
- If web compatibility or another language runtime becomes required later, it
  should be a separate WASM capability adapter, not the core design.
- Production document execution does not run on JVM/native; it runs through WASM
  plus the `kotoba:dom` and capability host ABIs.
- The kotoba OS UI should not be a separate native widget toolkit. It is a
  privileged kotoba browser surface, rendered and audited through the same path as
  documents.
