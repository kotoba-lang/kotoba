# org.jsonrpc

JSON-RPC 2.0 in Kotoba.

- Spec: https://www.jsonrpc.org/specification
- Reverse domain of `jsonrpc.org`. There is no official multi-language SDK monorepo to PR into.
- Codec + NDJSON framing. Transport-agnostic. Not a MicroDuck / robotd rewrite.

Public operator: awai.network. Sales: Ryo Awai.
License: Apache-2.0.

## What this is

A pure codec. It turns EDN-shaped Kotoba documents into JSON-RPC 2.0 text and
back. Framing takes strings in and out. The host owns sockets, pipes, and
HTTP. This repository does not open a network or filesystem capability; the
default empty policy (`:policy/allow #{}`) is enough.

It is not a session client. Response correlation is by `id` only. Timeouts
need a host clock. Kotoba's admitted guest surface has no timer or
`capability-clock-monotonic` import here, so this library does not implement
timeouts.

## Encode and decode

```clojure
(ns hello (:export [main]))

(defn main [] :string
  (encode (request "subtract" (document [42 23]) (document 1))))
;; => {"id":1,"jsonrpc":"2.0","method":"subtract","params":[42,23]}
```

```clojure
(ns hello (:export [main]))

(defn main [] :string
  (keyword-name
   (message-kind
    (decode "{\"jsonrpc\":\"2.0\",\"method\":\"subtract\",\"params\":[42,23],\"id\":1}"))))
;; => request
```

`examples/encode_request.kotoba` and `examples/decode_request.kotoba` are
those two programs. Object keys are sorted on encode; that is still valid
JSON-RPC 2.0.

Notifications omit `id`. A success object has `result` and must not have
`error`. An error object has `error` and must not have `result`. Standard
codes: `-32700` parse, `-32600` invalid request, `-32601` method not found,
`-32602` invalid params, `-32603` internal.

Batch arrays decode as documents. An empty batch is an invalid request (a
single error object, not an array). `encode-response-batch` drops
notifications. A notification-only batch encodes to the empty string.

NDJSON is one JSON-RPC value per line (`ndjson-encode`,
`ndjson-decode-line`, `ndjson-nth-line`). That is a framing module, not a
robot client.

## Kotoba surface (verified on kotoba v0.7.2)

Language authority: [kotoba-lang/kotoba-lang](https://github.com/kotoba-lang/kotoba-lang).
CLI/implementation: [kotoba-lang/kotoba](https://github.com/kotoba-lang/kotoba)
tag **v0.7.2**. Language-repo GitHub Releases are still 0; this README does
not claim a v0.6.0 language Release.

Admitted pieces this library uses:

- typed `ns` / `defn`, records, documents, keywords, strings, `i64`
- `document`, `document-get`, `document-assoc`, `document-count`,
  `document-kind`, `document-vector-at`, `document-vector-conj`,
  `document-map-entry-at`, `document-edn-read`, `document-edn-print`
- `string-concat`, `string-substring`, `string-code-point-at`, `string=?`,
  `string-from-i64`, `string-join`, `string-contains?`

There is no admitted JSON stdlib. The JSON subset lives in this repo:

- objects, arrays, strings, integers, `true` / `false` / `null`
- string escapes `\"`, `\\`, `\n`, `\t`, `\r`
- **not** floats, **not** `\uXXXX`, **not** `\/`

Maps are Kotoba documents with keyword keys (`:jsonrpc`, `:method`, …).
`require` is forbidden, so `org.jsonrpc` is one compilation unit. NDJSON is
the `ndjson-*` export group on that namespace (it would be
`org.jsonrpc.ndjson` if modules could import each other).

`kotoba run` on this source hits the EDN-IR adapter, which does not implement
documents or `string=?`. Compile to wasm or restricted ESM instead.

## Build

```sh
kotoba compile src/org.jsonrpc.kotoba --target wasm --output org.jsonrpc.wasm --json
```

Accept `kotoba.cli/ok?` true and `kotoba.cli/code` `emitted`. The typed wasm
artifact imports `kotoba:typed`; it is not the import-free i64 hello from the
agent quickstart. Fixture execution uses `--target web` and
`instantiateKotoba` (empty grant set).

```sh
scripts/ci.sh
```

Install the CLI from the v0.7.2 release tarball or
`brew tap kotoba-lang/kotoba && brew trust kotoba-lang/kotoba && brew install kotoba`.
`kotoba -e '(+ 1 2)'` is compile-and-run, not eval; on v0.7.2 the top-level
`-e` form is `planned` / `adapter-required`. `kotoba run -e` is the contract
shape.

## Tests

`test/fixtures.kotoba` covers spec vectors: string and number ids, omitted
params, by-name vs by-position, notification has no `id`, error XOR result,
empty batch, invalid batch item, parse error, NDJSON lines, and `id`
correlation. Vectors are vendored under `test/vectors/`; CI does not contact
jsonrpc.org.
