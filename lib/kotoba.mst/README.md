# mst

`kotoba-lang/mst` is the shared CLJC home for AT Protocol Merkle Search Tree
pure primitives.

It is intentionally smaller than a PDS implementation. It owns only deterministic
MST rules that every PDS/AppView/repo implementation must agree on:

- AT repo key validation: `<collection>/<rkey>`
- MST layer computation: SHA-256 leading zero bits counted in 2-bit groups
- shared-prefix helpers for tree entry compression

The byte/CID/CAR layer belongs in `kotoba-lang/atproto`, backed by
`kotoba-lang/dag-cbor` and `kotoba-lang/multiformats`.

## Test

```bash
kbb -M:test
```

## License

MIT
