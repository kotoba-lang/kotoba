# Native SQLite in Kotoba and Amu

Status: design baseline for JUN-768. This document does not claim a SQLite
engine, filesystem provider, or Itonami integration is implemented.

## Goal

Make SQLite files readable and writable through Kotoba source compiled by Amu
selfhost. The first consumer is Itonami's existing `cron/notepad.db` table:

```sql
CREATE TABLE IF NOT EXISTS cron_notepad (
  job_id TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (job_id, key)
)
```

The native implementation owns SQLite file parsing, schema validation, query
semantics, journaling, locking, recovery, and commit. Amu supplies only
resource-scoped byte filesystem operations. No SQL executor, C library,
subprocess, JVM, Node, Python, or silent host fallback may participate in the
qualified runtime/build/package path.

## Existing source and constraints

- `kotoba.sql.conn` in this repository is a portable API implemented in
  `.cljk`: JDBC on JVM and `node:sqlite` under kbb. It is an oracle source for
  behavior, not a native provider.
- Kotoba has `:bytes` primitives and `kotoba.bytes`. SQLite pages are binary;
  UTF-8 string file operations are insufficient.
- Amu KX64 has no SQLite API. The raw byte filesystem contract still needs
  native lowering/provider/admission and source-bound execution evidence.
- The AIUEOS object-route `extern-*` mechanism is a different execution path
  and cannot qualify product kexe. C compiler/loader/runtime are excluded by
  the Kotoba and Amu selfhost contracts.

## Ownership and API boundary

The high-level Kotoba library owns SQLite v3 semantics. Amu owns the native
byte capability provider and its resource/authority boundary. The capability
does not accept SQL text and does not hold database handles. Kotoba receives
bounded byte snapshots and returns a validated new image plus the exact write
set; Amu validates each path and commits through the scoped filesystem
provider. This keeps SQL meaning and schema admission in canonical Kotoba.

The public API will expose a narrow typed database/session surface rather than
JDBC-shaped ambient handles. Initial operations are schema/open validation,
ordered read of `(job_id,key,value,updated_at)`, upsert by `(job_id,key)`,
delete by `(job_id,key)`, and delete by `job_id`. Errors are typed and fail
closed. The API boundary is designed to grow into a general SQLite v3 engine;
the first admitted SQL surface is the Itonami notepad workload, not arbitrary
SQL compatibility.

## Format and transaction work order

1. Pure Kotoba SQLite v3 codec: 100-byte database header encode/decode,
   empty one-page database image construction, page-size and encoding
   validation, 1..9-byte varints, serial types, record encode/decode, bounded
   table-leaf cell encoding, and checked page offsets. No file writes in this
   unit.
2. Schema and B-tree reader: validate `sqlite_schema`, resolve the table and
   composite primary-key index, walk leaf/interior pages, and reject malformed
   pointers, cycles, overflow chains, unsupported collations, and unsupported
   schema forms.
3. Native I/O: add the Amu raw byte read/write/browse/lock operations with
   explicit resource scope, size limits, atomic replacement, and symlink/path
   refusal. Binary payloads must not be re-encoded through strings.
4. WAL/rollback compatibility: read and checkpoint existing WAL state, honor
   locks/busy state, then implement atomic mutation/recovery. Itonami enables
   WAL today, so a main-file-only writer is not sufficient.
5. Itonami operations and `remove`: preserve other job rows, enforce current
   value/key/total-size limits, and qualify positive, refusal, crash, and
   restart cases.

Each implementation unit is compiled and run through an Amu selfhost-built
compiler. An independent SQLite implementation may create/read fixtures as a
dated oracle only; oracle success never substitutes for Kotoba/Amu execution.

## Required evidence

- Golden byte vectors for header, varint boundaries, serial types, record
  widths, and malformed/truncated inputs.
- Standard SQLite oracle readback of native-created databases and native
  readback of oracle-created databases, with fixed fixture digests.
- Source-pinned Amu-native checks for permissions/scope, busy locks, schema
  mismatch, corruption, WAL recovery, transaction interruption, and preserving
  unrelated job rows.
- Linux x86_64 and ARM64 gates before Itonami wiring; platform scope must be
  reported for each actual runtime result.

## Known open decisions

- The exact maximum database/page/WAL size and out-of-memory refusal contract.
- Whether rollback-journal and WAL write modes are both admitted in the first
  implementation or WAL read/checkpoint is staged separately.
- Fair locking and concurrent writers under the current Amu filesystem
  capability model.
- Which subset of SQLite schema/index/collation/encoding versions is admitted;
  every unsupported form must fail closed before mutation.

## Implementation checkpoint (2026-11-02)

The Kotoba package now has source for the fixed database header, signed-i64
varints, four-TEXT notepad records, generic record-layout spans, B-tree page
headers/cell pointers, table-leaf cells, and table-interior cell boundaries.
It can also encode a table-leaf cell when its payload fits on the page; it
refuses negative rowids and payloads requiring overflow pages.
On 2026-11-02, source-locked Amu Mac ARM64 runtime fixtures passed for positive
codec calls, malformed/truncated refusal sentinels, and negative-varint empty
encoding. A separate source-locked fixture constructs empty database images
for page sizes 512, 16,384, 32,768 and 65,536 bytes; it decodes the generated
header, validates page 1 as an empty table-leaf root (including the 65,536-byte
zero offset representation), and refuses page size 513. The builder creates
zero-filled pages by concatenating bounded byte chunks after a large-vector
probe trapped. The images have not yet been exported for independent SQLite
readback. Zero-length data uses `bytes-from-vector-i64`; a standalone guest
probe using `bytes-empty` exited 139, so that Amu runtime issue remains open.

These checks qualify only the exercised codec calls on macOS ARM64. No full
page-tree walk, `sqlite_schema` reader, overflow traversal, SQL operation
layer, independent SQLite readback of the generated image, Amu byte-provider
durability/locking, WAL/recovery, or database mutation path is qualified. An
earlier complex scratch harness returned E6015; smaller pinned source-lock
graphs now pass, so E6015 is not evidence that the general Mac multi-module
source-lock route is absent.
