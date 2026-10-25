(ns probe.core
  "The two seams between kotoba-lang/i18n catalogs and the content plane.

  Piece 1 (`catalog->dag` / `dag->catalog`): an i18n EDN catalog becomes an
  IPLD DAG-CBOR block addressed by CIDv1 — one block per locale catalog, and
  an index block linking every locale of one project. Translation diffs cost
  exactly one new block + a parent-link update; unchanged translations are
  shared block-for-block because their bytes are identical.

  Piece 2 (`lake-claim`): the catalog block is admitted to the kotobase-lake
  catalog plane, so Datalog/SQL/SPARQL/Cypher over the datom plane can ask
  what catalogs exist, for which locale/project, with which coverage —
  without a second index.

  Both pieces are pure: no HTTP, no sockets, no clock. Callers bring the
  put!/get-fn of their block store and ingest their own quads.

  Honesty boundary: this library encodes and addresses catalog bytes. It does
  not pin them (IPFS), announce them (IPNI), or authorize writes (Biscuit).
  Those are the caller's boundaries.\""
  (:require [ipld.core :as ipld]
            [kotobase.lake.catalog :as lake]))
