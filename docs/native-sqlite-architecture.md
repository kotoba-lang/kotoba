# Native SQLite in Kotoba and Amu

Status: evolving design and evidence record for JUN-768. It does not claim a
complete SQLite engine or Itonami integration is implemented.

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
  for raw byte reads/writes and range reads (`kotoba-lang/amu/seed/72-linux-fs2.kotoba`).
  A KSL2-pinned Kotoba program has now written a SQLite image through that
  provider and an independent read-only SQLite oracle has accepted it on
  macOS ARM64. This qualifies the exercised FS2 export path only; it does not
  qualify SQLite locking, journal/WAL handling, or atomic commits.
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
3. Native I/O: use Amu's existing resource-scoped raw-byte FS2 operations and
   complete the Kotoba SQL adapter with explicit resource scope, size limits,
   atomic replacement, and symlink/path refusal. Binary payloads must not be
   re-encoded through strings. Locking and durability still require evidence.
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
exported for independent SQLite readback at that checkpoint. The later
source-pinned export and oracle acceptance below supersede this statement.
Zero-length data uses `bytes-from-vector-i64`; a standalone guest
probe using `bytes-empty` exited 139, so that Amu runtime issue remains open.

These initial checks qualified only the exercised codec calls on macOS ARM64.
The later dated checkpoint below supersedes its statements about page-tree
reading, `sqlite_schema` reading, overflow traversal, SQLite readback, and
bounded mutation. Durability/locking, WAL/recovery, atomic commits, broader
database layouts, Linux gates, Itonami wiring, and legacy SQLite data
conversion remain open. An earlier complex scratch harness returned E6015;
smaller pinned source-lock graphs now pass, so E6015 is not evidence that the
general Mac multi-module source-lock route is absent.

## Verified progress (2026-11-02, supersedes earlier checkpoint limits)

Amu full-bootstrap ARM64 compiled and ran a KSL2-pinned Kotoba program through
the FD3-scoped native FS2 packager with `PATH=/nonexistent`. Kotoba emitted a
12,288-byte SQLite image; read-only Python 3.15.0 `sqlite3` / SQLite 3.54.1
opened it with `mode=ro&immutable=1`, returned `PRAGMA integrity_check = ok`,
and read the expected 4096-byte pages and `cron_notepad` table plus composite
primary-key autoindex. This is an independent oracle readback, not a build or
runtime dependency. Source hashes and result are in
[`native-export-readback-20261102.json`](../lib/kotoba.sql/evidence/native-export-readback-20261102.json).

Subsequent exact-source native receipts qualify bounded operations on the
same three-page image: first-row insertion, increasing appends, unique
composite-key insertion in arbitrary order, exact-key deletion, per-job
deletion preserving unrelated rows, and update of an existing row preserving
rowid/key. Each fixture reads results through the Kotoba reader, writes
through Amu FS2, and uses a read-only SQLite 3.54.1 oracle for integrity and
row/index readback. See the
[`native evidence directory`](../lib/kotoba.sql/evidence/), including the
[`unordered insert and delete receipt`](../lib/kotoba.sql/evidence/notepad-unordered-insert-native-20261102.json).
The unordered fixture inserts job-a keys before and between existing keys in
the PK index while retaining table rowid order, refuses a duplicate, then
deletes one key and verifies the surviving rowids. A first implementation
attempt exposed an intermediate-image page-placement error; the corrected
source replaces the table page in place and the source-locked native run now
passes. This does not establish general SQL upsert semantics: a duplicate
key is refused and existing-row update is a separate bounded operation.

The native header codec now also exposes a validated in-memory page-count
replacement. Its source-locked Amu ARM64 fixture accepts a valid new page
count, advances the change counter and version-valid-for together, and refuses
zero, out-of-range, and malformed headers. At that checkpoint it did not yet
append pages or implement overflow writes. See
[`header page-count receipt`](../lib/kotoba.sql/evidence/notepad-page-count-header-native-20261102.json).

The first-row writer now uses this header operation with SQLite's table-leaf
local-payload formula and overflow-page chain format. An exact-source Amu
ARM64 run wrote a 16-KiB value into four overflow pages, emitted a seven-page
image through FD3-scoped FS2, and verified the value through Kotoba. Read-only
SQLite 3.54.1 reported `integrity_check=ok`, page_count 7, the expected row,
and the unique composite primary-key index. Receipt:
[`first-row overflow writer`](../lib/kotoba.sql/evidence/notepad-overflow-first-row-writer-native-20261102.json).
This qualifies overflow only while inserting the first row into the exact
empty image. A subsequent exact-source Amu ARM64 fixture appended a second
row, updated the 16-KiB row (rebuilding its four-page overflow chain), deleted
the second row, checked successful and missing-key reads in Kotoba, and
exported the seven-page image through FD3-scoped FS2. Read-only Python
`sqlite3` / SQLite 3.54.1 reported `integrity_check=ok`, one expected row with
all 16,384 value bytes and the updated timestamp, four overflow pages, and the
unique composite primary-key index. The receipt is
[`overflow mutation`](../lib/kotoba.sql/evidence/notepad-overflow-mutation-native-20261102.json).
This qualifies only the exact sqlite_schema page-1 image with one table leaf
and one index leaf. Arbitrary layouts, page splits, delete/reinsert
combinations beyond the exercised sequence, and persistence transactions
remain unqualified.

The Kotoba API now also has `upsert-notepad-row`, applying the Itonami
`set-note` contract to byte inputs: SQLite last-write-wins behavior, a
128 UTF-16-code-unit key cap, a 16-KiB UTF-8 value cap, and a 64-KiB
per-job key-plus-value aggregate check. Its source-pinned Amu ARM64 fixture
verified replacement, a 128-character BMP key, 16-KiB value, blank and
129-character key refusals, and refusal above the value cap. SQLite 3.54.1
read-only readback accepted the exported seven-page database and its three
rows. The aggregate-cap boundary is not qualified: current single-leaf roots
cannot hold enough admitted rows to reach it, so multi-page B-tree writes are
needed. Supplementary-plane UTF-16 length and complete JVM whitespace parity
also remain open. Receipt:
[`native upsert contract`](../lib/kotoba.sql/evidence/notepad-upsert-contract-native-20261102.json).

The implementation remains a bounded codec, reader, initializer, and
single-leaf mutation slice, not a complete SQLite engine or transactional
storage layer. It does not yet qualify arbitrary database layouts, page-split
writes, atomic/crash-safe persistence, locks/concurrent writers, WAL or
rollback-journal recovery, Linux x86_64/ARM64, or Itonami operations. Itonami
launcher wiring and the selected one-time offline converter remain paused
until those native gates pass.

## FS2 storage adapter boundary (initial checkpoint, 2026-11-02)

The native FS2 export and independent read-only SQLite readback above qualify
image export and the exercised Amu path only. They do not qualify a Kotoba
storage adapter or atomic database replacement. The current macOS ARM64 runtime
packager source describes a scoped FS2 callback slice for forms D/A/B/C/E/F
(`amu/seed/macos-fs2-runtime-packager.kotoba`); the Linux FS2 seed contains
additional temp-create, unlink, rename, and fsync operations. Those extra
operations are required for the planned staged replacement protocol and have
not been qualified by the macOS artifact.

A KSL2-pinned Amu full-bootstrap ARM64 run now exercised the Kotoba FS2 adapter:
one form-B whole-image write of the seven-page fixture and one form-A raw-byte
read, followed by Kotoba lookup of the 16-KiB value. Read-only Python 3.15.0
`sqlite3` / SQLite 3.54.1 reported `integrity_check=ok`, the expected rows and
composite primary-key index, page_count 7, and four overflow pages. The receipt
is [`native storage roundtrip`](../lib/kotoba.sql/evidence/notepad-storage-roundtrip-native-20261102.json).
The Mac provider requires an FD3-scoped basename for form B/C. The passing
reader uses the already exercised pair-backed string request to raw-byte
response shape; an initial kind-9-to-kind-9 read stopped in the Mac FS2 wrapper.
At this initial checkpoint, the results qualified direct whole-file write/read
only. Form B wrote directly to the destination, so atomic replacement and
crash durability were not established then. The later atomic native upsert
qualification below supersedes those adapter limits for its exact macOS
ARM64 source path. WAL or rollback-journal support, concurrent locking,
power-loss recovery, Linux qualification, and Itonami storage cutover remain
open.

## Atomic native upsert qualification (2026-11-02; supersedes the adapter limits above)

A source-pinned Kotoba program compiled by the Amu full-bootstrap ARM64
selfhost compiler and ran through the Amu FS2 FD3-scoped runtime with
`PATH=/nonexistent`. The Kotoba adapter serialized image publication with an
Amu FS35 persistent file lock, requested a fresh randomized staging basename
using FS2 N, wrote the replacement using FS2 B, then called FS35 file fsync,
atomic rename, and parent-directory fsync. Two successive SQLite image
publications passed. The test pre-seeded stage-like names and verified that
their contents remained unchanged while the persistent lock file remained. A
follow-up source-pinned fixture placed each of `-wal`, `-shm`, and `-journal`
next to the database in turn; Kotoba returned refusal status 6 and preserved
the main database bytes and sidecar in all three cases. The check runs under
Kotoba's FS35 writer lock and treats an unknown `EXISTS` response as a refusal.

This sidecar check does not implement SQLite's standard byte-range locking and
cannot prevent an unrelated SQLite process from creating a journal after the
check. It establishes fail-closed behavior for sidecars already present, not
full concurrent SQLite compatibility. Standard SQLite lock coordination and
WAL/rollback recovery remain required before wiring a live consumer.

Python 3.15.0 `sqlite3` / SQLite 3.54.1 opened the final file read-only and
immutable. `PRAGMA integrity_check` returned `ok`; readback confirmed the
last-write-wins value and timestamp, all three expected rows, the primary-key
autoindex, seven 4096-byte pages, and four overflow pages. The fixture also
accepted a 128-character BMP key and 16-KiB value, and refused a blank key, a
129-character key, and a value above 16 KiB. No hosted or native SQL fallback
was used. See [`atomic native upsert receipt`](../lib/kotoba.sql/evidence/notepad-upsert-atomic-native-20261102.json)
for source hashes and measured details.

This narrows the earlier statement that no Kotoba storage adapter or atomic
replacement had been qualified: the exact macOS ARM64 adapter path above is
now qualified for sequential image replacement with fresh randomized names.
An abandoned random stage after a crash remains inert and is not currently
collected. Sidecars already present are refused, but SQLite byte-range lock
coordination and races with external SQLite processes remain unqualified. It
does not qualify concurrent-process contention or lock fairness,
power-loss injection between commit steps, general SQLite transaction
semantics, WAL/rollback-journal handling, arbitrary page layouts or splits,
Linux x86_64/ARM64, or Itonami cutover. Random orphan-stage collection and those gates remain open.
