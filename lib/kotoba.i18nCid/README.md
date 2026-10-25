# i18n-cid

**Content-addressed i18n catalogs for kotoba-lang — the two seams between
[`kotoba-lang/i18n`](https://github.com/kotoba-lang/i18n) catalogs and the
IPLD / kotobase content plane.**

The Unison-like property of kotoba (a definition is identified by its content,
names are mutable references) applied to translation: a catalog's identity is
its CID, identical translations share blocks byte-for-byte, and a one-string
edit costs exactly one new block + a parent-link update.

## Piece 1 — catalog blocks (`i18n-cid.core`)

- `catalog->block` — an `i18n.core/register!`-shape catalog becomes a
  canonical DAG-CBOR block (`{:cid :bytes :node}`). Keyword keys are
  stringified (`:app/title` -> `"app/title"`), nested select-maps are walked,
  keyword values are encoded losslessly as `{"$kw" ".."}`.
- `locale-index->block` — a project index block: `{"format" "i18n-catalog/1"
  "project" .. "locales" {"ja" "<cid>" ...}}`.
- `dag->catalog` / `index->locales` — round-trip, restoring keywords.
- `lake-claim` / `lake-claim-index` — admit a block into the
  [`kotobase-lake`](https://github.com/kotoba-lang/kotobase-lake) catalog
  plane, so Datalog / SQL / SPARQL / Cypher over the kotobase datom plane can
  ask what catalogs exist, for which project/locale, without a second index.

Honesty boundary: this library encodes and addresses catalog bytes and, via
`i18n-cid.pin`, knows how to ask a Pinning Service to hold them. It still does
not announce them (IPNI) or authorize writes (Biscuit) — those stay the
caller's.

## Piece 2 — the seam (`i18n-cid.seam`)

- `register-from-block!` / `register-index!` — runtime path: fetch catalogs
  from any block store (kotobase as-of query, IPFS gateway, local disk) and
  merge into `i18n.core`. Same merge semantics as `register!` (later wins), so
  static resources and CID catalogs coexist.
- `write-catalog-resource!` — build-time path: materialize a catalog block as
  `i18n/messages/<locale>.edn` so `i18n.messages/defmessages` reads it at
  macroexpansion. JVM-only. Commit the artifact; compile-time key checking is
  unchanged.

## Piece 3 — pinning (`i18n-cid.pin`)

- `pin!` — pin a catalog block's CID to an IPFS Pinning Service, filling the
  pin half of the honesty boundary above. Speaks the PSA (`/pins`) surface
  that [`kotobase-protocol-pinning`](https://github.com/kotoba-lang/kotobase-protocol-pinning)
  exposes: `POST /pins {cid, name?, origins?}`, returning the pin's request-id.
- `status` / `unpin!` — read a pin request's status (`GET /pins/{request-id}`)
  and release it (`DELETE /pins/{request-id}`). Unpin releases the pin, not the
  block — bytes stay in the shared block space.
- Transport-agnostic: `pin!` / `status` / `unpin!` take the HTTP verbs
  (`post-fn` / `get-fn` / `delete-fn`) injected by the caller, exactly as
  `i18n-cid.core` asks callers to bring their own `put!`/`get-fn`. Auth
  (CACAO capability, ADR-2608159100) belongs in the injected transport.

## Piece 4 — pack (`i18n-cid.pack`)

A Pinning Service fetches by CID, one round trip per block. A CARv2 makes a
whole project's catalog set one object, so a Worker can serve any locale with
a single ranged read. Built on
[`kotoba-lang/io-ipld-car`](https://github.com/kotoba-lang/io-ipld-car).

- `pack` — `(pack project {locale catalog ...})` encodes each catalog and the
  project index via `i18n-cid.core`, then bundles every block into one CARv2
  (`ipld.car.v2/pack`, index on, index block as the archive's only root).
  Returns `{:car-bytes :entries :index-cid :locale-cids}`. The caller's `put!`
  decides where the bytes live.
- `unpack` — `(unpack car-bytes)` reads the archive back: resolves the index
  from the roots and hands each locale block to `dag->catalog`. Returns
  `{:index-cid :project :locales :catalogs {locale catalog}}` — `:catalogs` is
  `=` to the maps that produced the archive.

## Test

```sh
kbb -M:test   # 13 tests / 45 assertions, green
```
