# Kotoba package registry IPFS adapter

Verified HTTP/IPFS retrieval for the pure package-registry contract owned by
`kotoba-lang/kotoba-lang` — portable `.cljc`, JVM and ClojureScript.

The adapter validates the requested CID before I/O, verifies the returned bytes
against that CID, decodes EDN, then delegates all registry validation and lock
construction to `kotoba.lang.package-registry`. IPFS is therefore a replaceable
transport, not a source of language or package semantics.

```sh
kbb -M:test
kbb -M:lint
```

## Portability

`java.net.URI`, `java.net.http` and `java.time.Duration` all sat inside
`http-fetch`, the default transport. The verification — the part this repo
exists for — never touched any of them, so it is now shared and the JVM
`HttpClient` is a `#?(:clj …)` form ClojureScript never reads.

**On ClojureScript there is no default transport, and this does not pretend
otherwise.** `js/fetch` is asynchronous and `lock-from-requests` is not;
supplying a default would mean changing the signature every existing caller
uses. `fetch-fn` was already the injection point, so on ClojureScript it has
no default and omitting it is a fail-closed `:registry/no-transport` — which
is a different answer from a transport that ran and found nothing.

`:bytes` in a fetch result is the platform's byte container: `byte[]` on the
JVM, `Uint8Array` on ClojureScript. That is what
`multiformats.core/cidv1-raw` hashes on each platform.

```sh
npm install    # @noble/hashes — io-multiformats' SHA-256 on :cljs
kbb --backend sci --classpath src:test:<deps> test/run_portable.cljk
```

Run the nbb suite from any working directory: nothing on that path reads a
file, and Node resolves `node_modules` relative to the script, so it travels
with this repo rather than with the caller's cwd.

## Mutation testing

```sh
kbb --backend sci tools/check-mutations.cljk   # every :find occurs exactly once
kbb --backend sci tools/mutate.cljk            # apply each, report what reddened
```

`tools/mutations.edn` states its scope: the transport and its verification,
not the package registry.
