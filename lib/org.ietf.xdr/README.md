# org-ietf-xdr

**XDR (IETF RFC 4506) — schema-driven, portable `.cljc`, zero dependencies.**

The codec every ONC RPC protocol is written in. NFS, MOUNT, NLM and the
portmapper all describe themselves in the XDR language and then say nothing
further about bytes, because XDR has already said it.

```clojure
(require '[xdr.core :as xdr])

(def diropargs [:struct [:dir [:opaque* 64]] [:name [:string 255]]])

(xdr/encode diropargs {:dir handle :name "hello.txt"})
(xdr/decode diropargs bytes)   ; => {:value {...} :end 84}
```

A schema is an ordinary EDN value, reviewable next to the RFC it came from
rather than hidden in generated output — the same choice `dev-protobuf`
makes.

## The rules that decide whether a decoder works

- **Everything is a multiple of four bytes.** Opaque and string data carry
  up to three bytes of padding that are not part of the length. A decoder
  that forgets to skip them reads every later field from the wrong offset.
- **There are no optional fields, only optional *data*** (§4.19): a boolean
  followed by the value. NFS uses it in almost every reply.
- **Unions encode their discriminant**, and `void` arms are how a protocol
  says "on failure there is nothing else".
- **`decode` returns `:end`**, not just a value. A stream carries more than
  one message and the caller has to know where this one stopped.

## Bytes

Platform bytes in and out (`byte[]` / `Uint8Array`). Opaque payloads stay as
platform bytes inside decoded values rather than becoming integer vectors —
a 64 KiB NFS READ through a boxed vector is the difference between a
filesystem and a demonstration.

## Hyper

`hyper` and `unsigned hyper` are 64 bits wide, and one of the two hosts has no
number of that size. A decoded hyper is therefore:

- **JVM** — a `long`, or a `clojure.lang.BigInt` for the unsigned range at
  2^63 and above, which is what `+'` already produced.
- **ClojureScript** — a JavaScript `BigInt`, always. Not a plain number below
  2^53 and a `BigInt` above it: NFS's `fileid3`, `cookie3` and `writeverf3`
  are full-width `uint64` and the high bit is ordinary in all three, so a
  magnitude-dependent type is code that works against one server and throws
  `Cannot mix BigInt and other types` against the next.

`encode` takes either a `BigInt` or a plain number on ClojureScript, but
refuses a plain number past `Number.MAX_SAFE_INTEGER` — at that point the
caller has already lost the value and the bytes written would be some other
number's. Anything outside -2^63 … 2^64-1 is refused on both hosts rather
than truncated to its low 64 bits.

This is the same answer `blake2.word`, `kotoba.kir.cljs-i64` and `ipld.value`
give. `io-multiformats` and `dev-protobuf` give a different one — refuse
everything above 2^53 — and both scope it to codecs whose values do not reach
there, which XDR's does.

## Test

```bash
kbb -M:test                          # JVM
kbb --backend sci --classpath src:test run-tests.cljk  # ClojureScript
```

Expectations are byte strings produced independently of the encoder under
test. The stronger oracle is one layer up: the bytes macOS's own NFS client
sends, pinned in `org-ietf-nfs`.

## License

Apache-2.0.
