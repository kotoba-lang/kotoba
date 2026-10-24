# org-ietf-oncrpc

**ONC RPC version 2 (IETF RFC 5531) — the call/reply envelope and its record
marking, as pure `.cljc` functions over bytes.**

```clojure
(require '[oncrpc.core :as rpc] '[oncrpc.record :as record])

(rpc/dispatch {100003 {3 {0 (fn [call bs args-at] result-bytes)}}}
              message-bytes)     ; => reply bytes

(record/frame reply)             ; one message → one record
(record/parse buffer)            ; => {:message bs :end n} | nil (need more)
```

## Three details that cost the most

- **The arguments are not in the envelope.** A call is a fixed header
  followed by program-specific bytes, so `decode-call` returns `:args-at`
  rather than a value.
- **An accepted reply carries a verifier before its status.** Omit it and
  the reply decodes as garbage one field later.
- **A reader must accumulate fragments until the last-fragment bit.**
  Treating every fragment as a message works against every small call and
  then corrupts the first 64 KiB write — the first time a client has any
  reason to split one.

Every failure path produces a *reply*. A filesystem client that receives
nothing does not fail: it retries forever and the mount hangs with no
indication of why.

## What it is not

No transport, no threads, no sockets — the deploy shell owns those, the same
arrangement `org-ietf-webdav` uses for HTTP. No AUTH_DH, no RPCSEC_GSS:
`AUTH_NONE` and `AUTH_SYS` are what a loopback export needs, and claiming
more authentication than is implemented is worse than offering less.

## Test

```bash
kbb -M:test                                   # JVM
kbb --backend sci --classpath "$(kbb -Spath)" run-tests.cljk  # ClojureScript
```

The ClojureScript run needs `org-ietf-xdr` on the classpath, which is also
why it did not exist until now: `xdr.core` used `+` and `*` in their
auto-promoting spellings, which ClojureScript does not have, so nothing here
loaded on that runtime while `kbb -M:test` kept passing.

## License

Apache-2.0.
