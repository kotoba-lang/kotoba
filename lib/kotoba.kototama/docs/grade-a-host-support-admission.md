# Grade A host-support admission

This document records the executable evidence for Grade A gap T-03.

`kototama.browser/host-impl` is the versioned matrix for the complete
`actor:host` import surface on JVM, browser, and Node. The matrix is no longer
only maturity-report data: `host-admission` evaluates requested imports and
`admit-host!` rejects an unavailable or incompletely configured surface before
guest instantiation.

Production conditional requirements are:

| Host | Import | Required host evidence |
|---|---|---|
| JVM | `log-read`, `log-write` | explicitly injected store |
| JVM | `llm-infer` | explicitly injected LLM client |
| Browser | `http-post` | cross-origin isolation, Worker, HTTP bridge |
| Browser | `llm-infer` | cross-origin isolation, Worker, LLM proxy |
| Node | `http-post` | explicitly injected HTTP provider |
| Node | `llm-infer` | explicitly injected LLM provider |

The JVM tender invokes this admission before compatibility validation, Wasm
parsing, linking, or execution. Its historical in-memory store and
environment-derived LLM client remain available only to the development
profile; they are not production fallbacks.

Verification:

```sh
kbb -M:test -n kototama.browser-test -n kototama.tender-test
```

The browser and Node execution implementation lives in
`kotoba-lang/wasm-webcomponent`. T-03 is qualified at 14/14 imports; that runtime
calls the same admission contract (or a mechanically verified equivalent)
before `WebAssembly.instantiate`, with an end-to-end negative test for every
conditional import.
