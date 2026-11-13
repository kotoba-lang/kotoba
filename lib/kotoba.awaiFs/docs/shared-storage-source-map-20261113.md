# Shared storage and views: source map (2026-11-13)

AWAI-531. Owner direction: Kotoba and Kotobase own shared form, block, codec,
identity and database contracts. Yataverse and Awai FS are views over those
contracts. This document records a source audit and migration boundary; it is
not evidence that the views already use a single runtime or that PostgreSQL,
Native I/O or distributed durability is qualified.

## Audited revisions and current boundaries

| Surface | Source and current scope |
| --- | --- |
| Logical file identity | Kotoba `lib/kotoba.awaiFs/src/awai/fs/logical_file.kotoba`, `schema/v1.json` and `corpus/v1.json`: bounded logical-file/chunk-profile v1; exact DAG-CBOR and CID; no physical offsets. This is a first-party, versioned Kotoba contract, despite the historical `awai.fs` namespace. |
| Codec primitives | `lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba` and `lib/kotoba.ioMultiformats/src/multiformats/{cid,byte_cid,sha256}.kotoba`. The file codec delegates rather than defining another hash or CID. |
| CAR | `lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba`: bounded Native constructor for the legacy indexless leaves-root profile, not a general reader or a logical-file root. Its total output limit is 65536 bytes. |
| Kotoba filesystem | `lib/kotoba.fs/src/kotoba/fs/filesystem.cljk` and `kotoba.lang.fs` provide separate effect interfaces. These existing host/oracle surfaces do not prove a Native logical-file adapter or POSIX database filesystem. |
| Kotobase | `lib/kotoba.kotobaseStorage/src/kotobase/storage/core.cljk`: immutable `IBlockStore`, mutable `IRefStore`, and explicit linearizable versus single-writer ref capabilities. Native equivalence and a logical-file bridge remain unqualified. |
| Ayatori | `lib/kotoba.ayatori/src/ayatori/{remote,pack,query}.cljk`: verified block reads, CAR ranges and query over arrangement snapshots. Query and authority are not implied by storing a CID. |
| Yataverse | `kotoba-lang/yataverse` at `c875a39db9a2ddd79c9666284673696ae02fd9b9`, `src/client.mjs`: verified CID-based byte access. The proposed shared view is an architectural target; this host client is not proof of a Native integration. |
| Awai Otehon | `network-awai/network-awai-apex` main `f913f784c18fac0810e233ddec95fc7ef112c005`: `src/awai/fs/{chunk_profile,large_file,car,node_store,wal}.cljc`, `oracle/awai-fs-format/v1/`. It implements additional physical storage and recovery surfaces, separate from Kotoba Native. |

This map was inspected against `kotoba-lang/kotoba` main
`8ffd40460ddb05b4cf5bcc38ca4b8a17dfa377ed`. The Otehon consumer's
`oracle/awai-fs-format/v1/logical-file-sources.json` pins Kotoba revision
`851d4431b9d749858e95d20b7cfe3c78dd9a2168`; the five listed source, schema,
corpus, provenance and imports SHA-256 values matched this audited Kotoba
tree byte-for-byte. This proves source identity for those five files, not
end-to-end execution through the Native storage adapter.

## Required convergence, in dependency order

1. Keep existing v1 bytes, CIDs, link restrictions and corpus unchanged.
   Explicitly dispatch legacy leaves-root and logical-file-root formats; never
   reinterpret one root as the other. New formats need a distinct version and
   corpus, not a silent redefinition.
2. Port only the shared logical operations from the Awai implementation into
   their appropriate Kotoba owners. Keep the fixed file-creation chunk profile
   distinct from pack layout, media alignment, prefetch and queue tuning. A
   physical repack preserves logical block bytes, file root and range results;
   rechunk is an explicit new logical root.
3. Connect Kotoba FS and Kotobase to the same verified block/identity contract
   with scoped, bounded host adapters. Preserve Kotobase's separately declared
   ref concurrency profile; a B2 single-writer ref is not linearizable CAS.
   Do not infer a transaction from immutable blocks or a successful upload.
4. Expose Yataverse CID access and Awai FS file/directory/range access as
   separately authorized views. Ayatori owns query projections; private-tree
   and query semantics remain AWAI-173/174. Kura owns placement and repair.
   Source pins and adapter readback must establish each actual connection.
5. Complete the single-node Pack/index/WAL/root storage and recovery path,
   then qualify the same positive and rejection corpus on the Native artifact.
   Only then qualify independent nodes, receipts, fencing and repair. OS-cache
   loss, power loss and node loss are separate evidence from process SIGKILL.

## Non-equivalences to preserve

- A matching content ID verifies addressed bytes, not secrecy, freshness,
  authorization, retention or availability.
- The existing Otehon/hosted execution path, its tests and local deployment are
  not Native artifact, real device power-loss, independent-node or production
  qualification. No silent runtime fallback is allowed.
- The `Filesystem` protocols in `kotoba.fs` and the `IBlockStore`/`IRefStore`
  protocols in `kotobaseStorage` are different contracts, not an implemented
  shared adapter merely because both have read/write vocabulary.
- PostgreSQL as a Kotobase backend, the limited PostgreSQL wire query surface,
  a PostgreSQL backup stored in Awai, and PostgreSQL `PGDATA` on an Awai mount
  are four different integration claims. None follows from this source map.

Tracking: AWAI-531 (format/index), AWAI-532 (I/O/recovery), AWAI-534
(placement/repair), AWAI-173/174 (private tree/query), AWAI-2858 (research).
