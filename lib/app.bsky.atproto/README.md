# atproto

`kotoba-lang/atproto` is the shared EDN/CLJC contract library for AT Protocol
components used by `kotoba-lang/kotoba`, `app-aozora`, and future actors.

It is not an application PDS. It owns portable protocol vocabulary and pure
record helpers so app-specific Workers stop redefining the same constants.

Initial scope:

- NSID and collection metadata
- repo URI helpers
- standard `app.bsky.actor.profile` record construction
- route metadata for common PDS/AppView XRPC surfaces
- migration map from current `app-aozora` implementation namespaces
- SDK coverage map aligned with the official AT Protocol SDK feature axes:
  client, identifiers, bsky helpers, lexicon, identity, streaming, service auth,
  crypto, repo, plc, OAuth server, and reusable server/PDS contracts

Cryptographic byte-level pieces are split by responsibility:

- `kotoba-lang/mst`: MST layer/key primitives
- `kotoba-lang/dag-cbor`: DAG-CBOR encoding
- `kotoba-lang/multiformats`: CID/base encodings
- `kotoba-lang/did`: DID parsing/document helpers
- this repo: AT Protocol contract/API shape tying those libraries together

## SDK coverage

The coverage map lives in `resources/atproto/sdk_coverage.edn` and is exposed by
`atproto.sdk`. Keep AT Protocol-facing API shape in this repo, while keeping
lower-level reusable substrates in their own repos:

- keep separate: `kotoba-lang/mst`, `kotoba-lang/dag-cbor`,
  `kotoba-lang/multiformats`, `kotoba-lang/did`
- keep here: `atproto.client`, `atproto.identifiers`, `atproto.bsky`,
  `atproto.lexicon`, `atproto.identity`, `atproto.streaming`, `atproto.auth`,
  `atproto.crypto`, `atproto.repo`, `atproto.plc`, `atproto.oauth`,
  `atproto.server`

Recommended extraction order from `app-aozora`: identifiers, lexicon, repo,
identity, service auth, streaming, OAuth, client, bsky helpers, PLC, server/PDS.

## Test

```bash
kbb -M:test
```

## License

MIT
