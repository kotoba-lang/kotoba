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
- Amu KX64 has no SQLite API. Amu already has a resource-scoped FS2 provider
  for raw byte reads/writes and range reads (`kotoba-lang/amu/seed/72-linux-fs2.kotoba`);
  this task still needs a Kotoba SQL adapter and exact source-pinned execution
  evidence for the selected Amu runtime/target. Existing provider candidate
  checks do not qualify SQLite locking, journal/WAL handling, or atomic commits.
- The AIUEOS object-route `extern-*` mechanism is a different execution path
  and cannot qualify product kexe. C compiler/loader/runtime are excluded by
  the Kotoba and Amu selfhost contracts.

## Ownership and API boundary

The high-level Kotoba library owns SQLite v3 semantics. Amu owns the native
FS2 byte provider and its resource/authority boundary. The capability does not
accept SQL text and does not hold database handles. Kotoba receives bounded
byte snapshots and returns a validated new image plus an explicit commit
protocol; the adapter uses only scoped FS2 operations and must not treat a raw
write as atomic. SQLite locking, journal/WAL recovery, and commit ordering stay
in canonical Kotoba semantics and require separate qualification.

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
   validation, 1..9-byte varints, generic serial-type record encode/decode,
   bounded table-leaf cell and page encoding, ordered cell append, and checked
   page offsets. No file writes in this unit.
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
headers/cell pointers, table-leaf cells, table-interior cell boundaries, and
`sqlite_schema` table/primary-key autoindex record encoding.
It can also encode a table-leaf cell when its payload fits on the page; it
refuses negative rowids and payloads requiring overflow pages. A separate
page builder places a cell into a bounded table-leaf page, including the
page-1 B-tree header offset, but its page image excludes the 100-byte database
header and is not a complete database file. Ordered append supports increasing
rowids while contiguous free space remains; it refuses out-of-order rows and
does not compact freeblocks or split pages. The generic record encoder accepts
serial types plus concatenated raw values, validates their total widths and
header size, and refuses reserved serial types 10 and 11. The Itonami
four-TEXT encoder now delegates to that implementation.
On 2026-11-02, source-locked Amu Mac ARM64 runtime fixtures passed for positive
codec calls, malformed/truncated refusal sentinels, and negative-varint empty
encoding. A separate source-locked fixture constructs empty database images
for page sizes 512, 16,384, 32,768 and 65,536 bytes; it decodes the generated
header, validates page 1 as an empty table-leaf root (including the 65,536-byte
zero offset representation), and refuses page size 513. The builder creates
zero-filled pages by concatenating bounded byte chunks after a large-vector
probe trapped. The leaf-cell and single-cell page writers pass positive and
refusal checks at 512 bytes, and the page writer also passes at 65,536 bytes.
The ordered append fixture placed and decoded two cells in rowid order on both
page-2 and page-1 leaf pages and refused an out-of-order rowid.
The generic record encoder round-trips through the decoder, including a
64-column record whose header-size varint occupies two bytes; its negative
fixtures refuse reserved serial types and mismatched value widths. Schema
entry fixtures encode the Itonami `cron_notepad` table DDL with rootpage 2 and
its primary-key autoindex row with rootpage 3 and NULL SQL; rootpage-width and
invalid-rootpage cases are also checked. A bounded initial `cron_notepad`
database-image builder now combines the header, two `sqlite_schema` rows, an
empty table root, and an empty primary-key autoindex root into a three-page
file image. This is a schema initializer, not a general database writer or a
query/update engine. The source-locked native fixture assembles and checks
three-page images at 512 and 4,096-byte page sizes, validates both generated
`sqlite_schema` records against the admitted DDL/root pages, rejects a
one-page empty image, and refuses page size 513; the image has not yet been
exported for independent SQLite readback.
Zero-length data uses `bytes-from-vector-i64`; a standalone guest
probe using `bytes-empty` exited 139, so that Amu runtime issue remains open.

These checks qualify only the exercised codec calls on macOS ARM64. No full
page-tree walk, `sqlite_schema` reader, overflow traversal, SQL operation
layer, independent SQLite readback of the generated image, Amu byte-provider
durability/locking, WAL/recovery, or database mutation path is qualified. The
initial image is not wired into Itonami, and legacy SQLite data conversion is
still a separate planned offline step. An
earlier complex scratch harness returned E6015; smaller pinned source-lock
graphs now pass, so E6015 is not evidence that the general Mac multi-module
source-lock route is absent.
