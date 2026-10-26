# Identity

Identity answers one question: **what makes two references the same object?**
The canonical public form is `ipfs://{cidv1-base32}` (ADR-2608145100).

## Output-addressed identity

`CID = hash(bytes)`. Git blobs, IPFS blocks, Holochain `EntryHash` values,
Unison terms, and Nix NARs are output-addressed: bytes come first and names come
later.

## Input-addressed identity

An input address hashes a recipe, call, derivation, or closed input set. Nix
`.drv` files, RPC call objects, and package-lock closures use this form. The
protocol does not choose input addressing *instead of* output addressing: the
recipe is itself bytes and therefore also has an output CID. The distinction is
what the hash identifies, not a different public URI grammar.

| Object | Address kind |
|---|---|
| distributed HTML, Wasm, or datom snapshot | output |
| build expression or RPC call object | input; the recipe object also has an output CID |
| Holochain `ActionHash` | output of signed action bytes |
| Holochain `DnaHash` | output of DNA-definition bytes, not a name |

CIDv0 (`Qm…`) remains a historical L0 shape but is rejected as a public label.
HTTPS is transport/location, not identity. The executable algebra is
`kotoba.protocol.address` (`output`, `input`, `recipe-as-output`, and
`holochain-kind`).
