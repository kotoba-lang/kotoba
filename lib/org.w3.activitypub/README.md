# kotoba-lang/org-w3-activitypub

Safety-bounded ActivityPub document helpers for actors, collections,
inbox/outbox links, and request boundaries.

`src/activitypub.kotoba` is the sole production source. It is compiled by
`kotoba-lang/compiler` to restricted JavaScript or typed WebAssembly; Clojure
is used only as the compiler/test host and is not a production runtime.

The public ABI accepts and returns canonical typed documents. Invalid host
objects and unsupported document shapes are rejected instead of being
coerced. Cross-target tests require the same observable semantics, typed ABI,
effects, resource bounds, and fail-closed behavior.

## Test

```bash
kbb -M:test
kbb -M:lint
```
