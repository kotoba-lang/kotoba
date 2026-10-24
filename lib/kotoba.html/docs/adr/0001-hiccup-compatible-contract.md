# ADR-0001: Hiccup-compatible HTML contract

- Status: Accepted
- Date: 2026-07-20

## Decision

`kotoba-lang/html` follows Hiccup semantics for element vectors, tag/id/class sugar, attribute maps,
sequence children, fragments, class collections, style maps, boolean attributes, void elements and escaped
text/attributes. Trusted raw markup is explicit through `kotoba.html/raw`; untrusted input is always escaped.

The portable Hiccup tree is the shared UI data contract. HTML rendering and `kotoba:dom` compilation are
separate consumers; applications must not use rendered HTML strings as the native intermediate format.
Extensions must remain additive and must not reinterpret valid Hiccup forms.

## Addendum — `.kotoba` string pipeline (2026-07-27)

Per ADR-2607270100 §10 / ADR-2607279200 Delivery #6, `kotoba/html_core.kotoba` ports the
string-producing core (escape, attrs, style, void/closed elements, RAWTEXT breakout) as form A
(call-graph composition, no recursive value tree). `html.core` is unchanged for consumers.
Byte-equality is gated by `test/html/kotoba_parity_test.cljk` against key-sorted `html.core` runs.
This is an oracle-backed experiment ahead of W4; do not treat it as the final HTML API.
