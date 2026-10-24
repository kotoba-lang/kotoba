# kotoba-lang/org-w3-aria

A genuine, dependency-free WAI-ARIA accessibility-tree projection library.
`aria.core` computes an ARIA accessibility tree from a plain-map DOM-shaped
document:

```clojure
{:root <node-id>
 :focus <node-id-or-nil>
 :nodes {<node-id> {:node/id <node-id>
                    :node/type :element   ; or :text
                    :tag :div             ; keyword tag name, element nodes only
                    :attrs {:id "..." :class "..." :role "..." ...}
                    :children [<node-id> ...]}
                    ;; :text nodes instead have :node/type :text and a
                    ;; :text "..." string key, no :tag/:attrs/:children
         ...}}
```

This is the same shape `kotoba.wasm.dom` / `kotoba-lang/browser` produce, but
this library itself does not depend on either of those — it only expects
that map shape, nothing more. Callers hand it a plain map; `aria.core/tree`
and `aria.core/accessible-node` hand back a plain `:a11y/*`-keyed
accessibility tree.

Split out of `kotoba-lang/browser` (ADR-2607051500), where it lived as the
pure, host-independent half of `browser.accessibility` (the other half —
`browser`'s own OS-shell "surface" window-manager projection — stayed behind
in `browser.accessibility`, which now depends on this library for the
underlying per-document ARIA projection).

**Name provenance**: follows this org's `org-<standards-body>-<spec>` naming
convention (see `org-khronos-glb`, `org-w3-webgpu`) — WAI-ARIA is a W3C/WAI
specification, hence `org-w3-aria`.

## Maturity

| | |
|---|---|
| Role | ui-substrate |
| Tests | `kbb -M:test` |
| Dependencies | none (`:deps {}`) |
| WHATWG/W3C compatibility | not a goal (implements the parts of WAI-ARIA `kotoba-lang/browser` needs, not the full spec) |

## Test

```bash
kbb -M:test
```
