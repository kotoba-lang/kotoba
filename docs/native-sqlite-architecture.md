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
mutation slice, not a complete SQLite engine or transactional storage layer.
It does not yet qualify arbitrary database layouts, atomic/crash-safe
persistence, locks/concurrent writers, WAL or rollback-journal recovery, Linux
x86_64, or Itonami operations. Itonami launcher wiring and the selected
one-time offline converter remain paused until the required native gates pass.

### First interior-root split (2026-11-03)

An exact-source Amu selfhost Linux ARM64 fixture filled the admitted
three-page `cron_notepad` image, split both the table and primary-key index
roots into two child leaves, published the seven-page result through native
FS2, reopened it, and read a value through Kotoba. It refused the next upsert
because a second split was not yet implemented. The separate, one-time
read-only Python 3.15.0 / SQLite 3.54.1 oracle checked the same output digest,
reported `integrity_check=ok`, and read the four expected ordered keys and
unique primary-key index. The oracle is evidence for this artifact only and
does not participate in the native gate. Receipts:
[`Linux ARM64 native split`](../lib/kotoba.sql/evidence/interior-root-split-native-linux-arm64-20261103.json)
and
[`read-only SQLite readback`](../lib/kotoba.sql/evidence/interior-root-split-readonly-oracle-20261103.json).

This qualifies only the first split from the exact generated schema image on
Linux ARM64. Repeated updates on an already-interior root, arbitrary SQLite
layouts, Linux x86_64, transactions/atomicity, locks/concurrency,
WAL/rollback-journal recovery, crash recovery, and Itonami integration remain
open. A subsequent repeated-upsert native gate is in progress and is not
counted as qualified here.

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
next to the database in turn; Kotoba reads returned `[0]`, writes returned
status 6, and both operations preserved the main database bytes and sidecar in
all three cases. The checks run under Kotoba's FS35 writer lock and treat an
unknown `EXISTS` response as a refusal.

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
collected. Reads and writes refuse sidecars already present, but SQLite byte-range lock
coordination and races with external SQLite processes remain unqualified. It
does not qualify concurrent-process contention or lock fairness,
power-loss injection between commit steps, general SQLite transaction
semantics, WAL/rollback-journal handling, arbitrary page layouts or splits,
Linux x86_64/ARM64, or Itonami cutover at that checkpoint. Random orphan-stage collection and those gates remain open.

## ARM64 native publication qualification (2026-11-02)

An Amu selfhost F2 compiler built source-locked Kotoba fixtures into static
`aarch64-linux` programs and ran them with `PATH=/nonexistent` on Linux ARM64.
The positive fixture created the notepad image, upserted one row, published
the image through FS2, reopened it through Kotoba, and verified the value.
Separate controls confirmed refusal with pre-existing `-wal`, `-shm`, and
`-journal` files while preserving both the database and each sidecar. The
native receipt records the Amu source revision, compiler and fixture
hashes; no host SQLite oracle was used for this Linux run. This qualifies that
Linux execution path only; it does not establish x86_64 Linux or standard
SQLite locking and journal recovery. A separate dated, read-only SQLite 3.54.1 oracle check then
reported `integrity_check=ok`, the expected row and primary-key autoindex,
4096-byte pages, and three pages; see
[`Linux read-only oracle receipt`](../lib/kotoba.sql/evidence/notepad-upsert-linux-arm64-readonly-oracle-20261102.json).

The providers expose different FS2 N behavior. On macOS, requesting a parent
directory returned the refusal payload `Z`, while requesting `.` returned a
randomized 12-hex file basename. On Linux, N under the database parent creates
a randomized directory with a 6-character lowercase alphanumeric suffix.
Kotoba now validates these response shapes, uses provider-relative FS2 B paths,
and selects the matching file/directory cleanup form. This is based on the
measured Amu provider contracts; other providers and suffix formats are not
qualified.

The current source passed the existing Amu full-bootstrap macOS ARM64 positive
and refusal harness and the source-locked Amu selfhost Linux ARM64 gate, both
with `PATH=/nonexistent`. The Linux gate used Amu revision
`ce982703375bedc0039b61b1a821407d228ea98a`, matching Kotoba CI's pinned
dependency. Receipts are tracked at
[`macOS ARM64`](../lib/kotoba.sql/evidence/notepad-upsert-macos-arm64-native-20261102.json),
[`Linux ARM64`](../lib/kotoba.sql/evidence/notepad-upsert-linux-arm64-native-20261102.json),
and the separate [Linux read-only oracle](../lib/kotoba.sql/evidence/notepad-upsert-linux-arm64-readonly-oracle-20261102.json).
The native receipts share database source SHA-256
`98698cc6d9aed02f5168cac239b416cf557edd756634be93601fa91d9e141759`. Mac
covered sequential publication, bounded overflow rows, refusal controls, and
read-only SQLite oracle readback. Linux covered native publication/reopen and
the three sidecar refusal controls; a separate read-only SQLite 3.54.1 oracle
checked integrity and the expected row/index. This qualifies these exact
ARM64 provider routes only. Linux x86_64, standard SQLite byte-range locking,
external-process races, WAL/recovery, crash injection/recovery, and Itonami
wiring remain open.

## Existing SQLite mutation and wider rowid qualification (2026-11-02)

The source-pinned Amu selfhost F2 Linux ARM64 Kotoba gate now also opens a
standard SQLite 3.54.1 `cron_notepad` file, updates an existing row, inserts a
row for another job, deletes one job, publishes through the Kotoba FS2/FS35
path, then reopens and reads the result through Kotoba. The separate
read-only/immutable SQLite 3.54.1 oracle reports `integrity_check=ok`, confirms
the admitted schema and unique composite primary-key index, and reads the
expected surviving rows. A companion standard three-page fixture updates
rowid 128 and inserts rowids 129 and 130; Kotoba reopens it successfully, and
the independent read-only oracle confirms all three rows and integrity.
Exact Amu pin, compiler/program/source hashes, and results are recorded in
[`Linux native mutation receipt`](../lib/kotoba.sql/evidence/notepad-high-rowid-native-linux-arm64-20261102.json),
[`legacy mutation readback`](../lib/kotoba.sql/evidence/legacy-notepad-mutation-readonly-oracle-20261102.json),
and [`high-rowid readback`](../lib/kotoba.sql/evidence/high-rowid-native-readonly-oracle-20261102.json).

This extends the measured Linux ARM64 behavior from creating and reopening an
initial image to bounded mutation of the exact admitted four-TEXT schema and
positive rowids through 130. At this receipt's source revision, B-tree root
splitting was not implemented and databases whose existing table or index
roots were interior pages failed closed. A later source change adds a first
split implementation; it is not yet runtime-qualified. Arbitrary SQLite
schemas, WAL or rollback-journal recovery, standard byte-range/concurrent
locking, crash recovery, Linux x86_64, and Itonami wiring also remain open.
Python is used only for the separate dated read-only oracle and is not part of
the native path.

## Interior-page encoder prerequisite (2026-11-02)

Kotoba now exposes bounded encoders for table-interior cells, index-interior
cells, and one-cell table/index interior pages. The source-pinned Amu selfhost
Linux ARM64 fixture checked child pointers, table separator rowid, index
payload framing, page headers/right-child values, and refusal of invalid child
numbers, a negative separator, and an index interior root on page 1. The exact
Amu pin and source/program hashes are in the
[`interior-page encoder receipt`](../lib/kotoba.sql/evidence/interior-page-encoder-native-linux-arm64-20261102.json).

This receipt qualifies page-construction primitives only. At that source
revision Kotoba did not walk or mutate these interior table/index roots, split
overflowing roots, rebalance pages, or verify a two-leaf database through a
SQLite oracle. The later first-split source change is described below; the
native qualification remains pending.

The same exact-source Amu fixture now also decodes the generated index-interior
cell boundary and checks its left child, payload size, and payload span. The
updated receipt is
[`index-interior decoder receipt`](../lib/kotoba.sql/evidence/index-interior-decoder-native-linux-arm64-20261102.json).
This still does not traverse an index tree or prove database-level ordering;
the positive payload here is only a page-codec vector.

## Kotoba-built table/index interior-root image (2026-11-02)

A source-pinned Amu selfhost Linux ARM64 fixture composes a seven-page
SQLite database through Kotoba: the table and composite primary-key index each
have an interior root, and their child leaves hold two rows/keys. Kotoba
publishes the image through FS2, reopens it, and reads both values through its
table reader. The upsert path refuses mutation of this pre-existing interior-
root shape. A separate Python 3.15.0 / SQLite
3.54.1 read-only immutable oracle reports `integrity_check=ok`, page_count 7,
both expected rows, and the composite primary-key autoindex. Native and oracle
receipts are
[`native interior-root gate`](../lib/kotoba.sql/evidence/interior-root-native-linux-arm64-20261102.json)
and [`interior-root readback`](../lib/kotoba.sql/evidence/interior-root-readonly-oracle-20261102.json).

Two initial oracle runs caught fixture construction errors (a duplicated
promoted index separator and an incorrect rowid serial type); the corrected
image passes independent integrity check. This verifies Kotoba's page
construction and table reading for this two-leaf image, but not the dynamic
split code below or index-tree traversal. Existing interior-root mutation
remains unsupported. WAL/recovery, concurrent SQLite locking, crash recovery,
Linux x86_64, and Itonami wiring remain open.

## First bounded table/index root split (2026-11-02; qualified on Linux ARM64 2026-11-03)

Kotoba commit `34c10ebd25a40b77d946037d8b76d60adf864b52` adds a first split
path to notepad upsert. When an exact three-page `cron_notepad` with single-
leaf table and index roots can no longer append, Kotoba materializes its rows,
adds the new row, rebuilds table and composite-PK index leaves, and constructs
one-cell interior roots. The scope admits only child leaves that fit and
rejects overflow rows and malformed inputs. A later bounded extension accepts
repeat upserts only for this exact two-leaf table/index root shape; it does not
support deeper trees or general B-tree rebalancing.

The source-pinned native fixture and Linux ARM64 gate fill the database to the
split, publish with FS2, reopen and look up a value through Kotoba, and require
a subsequent upsert to refuse. The corrected exact-source run and independent
oracle are recorded below. This qualifies only this bounded first split; it
does not qualify another mutation of the interior-root result.

### Split artifact readback and native fixture correction (2026-11-03)

The first exact-pin Linux ARM64 run `41475188287` produced the seven-page
database through Kotoba and FS2, but its native fixture returned 13 because
the KNV1 readback check inspected byte offset 6 for the first value byte even
though a 1,150-byte value has a two-byte SQLite varint length; the value begins
at offset 7. That run's SQLite oracle passed, but the native fixture was not
qualified at that point.

A separate Python 3.15.0 / SQLite 3.54.1 read-only immutable oracle opened the
artifact and reported `integrity_check=ok`, page size 4096, page count 7, the
expected table and composite primary-key index, and four ordered rows with
1,150-byte values. Artifact SHA-256 and row details are recorded in the
[dated split oracle receipt](../lib/kotoba.sql/evidence/interior-root-split-readonly-oracle-20261103.json).
The oracle confirms the generated artifact only; it is not a Kotoba runtime or
CI dependency. The fixture assertion was corrected, and exact-pin Linux ARM64
run `41478551197` passed the native SQLite image publication/readback and
sidecar-refusal step. Its artifact has the same SHA-256 and again passed the
separate immutable read-only SQLite oracle (`integrity_check=ok`, 4096-byte
pages, seven pages, four ordered rows, and the composite primary-key index).
The native and oracle receipts are
[`split native receipt`](../lib/kotoba.sql/evidence/interior-root-split-native-linux-arm64-20261103.json)
and [`split oracle receipt`](../lib/kotoba.sql/evidence/interior-root-split-readonly-oracle-20261103.json).

This qualifies the first split from the exact three-page schema image when its
single-leaf table/index roots fill, plus FS2 publish/reopen/readback. The
subsequent bounded repeat-upsert qualification is recorded below. Further
splits/rebalancing, arbitrary SQLite layouts, WAL or rollback-journal handling,
atomic/crash-safe transactions, concurrent locking, Linux x86_64, and Itonami
integration remain open.

## Bounded repeat upserts on the two-leaf roots (2026-11-03)

Exact-head Linux ARM64 run
[`41507315368`](https://github.com/kotoba-lang/kotoba/actions/runs/41507315368)
passed the Amu selfhost native SQLite fixture. Starting from the exact
Kotoba-generated two-leaf table/index root image, the fixture performed three
successful 970-byte-value upserts, refused a fourth capacity-exceeding upsert,
published the three-row extension through FS2, reopened it, and read all three
inserted values through the Kotoba reader. The native gate also passed the
existing SQLite and sidecar refusal fixtures in the same job.

The emitted repeat database is 28,672 bytes, page size 4096, with seven pages.
A separate Python 3.15.0 / SQLite 3.54.1 immutable read-only connection reported
`integrity_check=ok`, the expected `cron_notepad` schema and composite primary
key autoindex, and eight ordered rows (five initial rows plus the three
inserted rows), each with a 970-byte value. This oracle validates the emitted
file's standard SQLite readability; it is not part of the native path and does
not establish general SQLite correctness. Exact source, artifact, and oracle
details are in the [repeat native receipt](../lib/kotoba.sql/evidence/interior-root-repeat-native-linux-arm64-20261103.json)
and [separate read-only oracle receipt](../lib/kotoba.sql/evidence/interior-root-repeat-readonly-oracle-20261103.json).

This expands qualification only to three repeat upserts that fit in the exact
two-leaf image and fail-closed refusal when the next row exceeds that bounded
capacity. It does not qualify deeper splits, arbitrary page layouts, WAL or
rollback-journal processing, atomic/crash-safe transactions, concurrent
locking, Linux x86_64, or Itonami integration.

## Existing-key update and deletion under interior roots (2026-11-03)

Exact-head Amu selfhost run
[`41516926597`](https://github.com/kotoba-lang/kotoba/actions/runs/41516926597)
passed loaderless rebuild, compiler verification, All12, and the native Linux
ARM64 SQLite publication/readback/sidecar gate at head
`9930187571af20c7d0fdf0924e6a97c8e99f5074`. The Amu pin was
`ce982703375bedc0039b61b1a821407d228ea98a`; the native compiler SHA-256 was
`02f50955fa2fdc33efed05bcc47ba39dc0e70014f0b0f290b8200af2cb99900e`.

The two-leaf-root fixture updated an existing value, preserved the other rows,
published through FS2, reopened, and read the replacement through Kotoba. It
also deleted one key and checked the survivor in memory, then deleted one job,
collapsed the one-row table/index trees to three leaf pages, published and
reopened through FS2, and read back the other job through Kotoba. A separate
Python 3.15.0 / SQLite 3.54.1 immutable read-only check reported
`integrity_check=ok` for both emitted artifacts: the seven-page update image
has eight rows, while the three-page delete image contains only the preserved
`job-b/cursor` row. The native and oracle details are recorded in the
[interior-root mutation receipt](../lib/kotoba.sql/evidence/interior-root-delete-native-linux-arm64-20261103.json)
and [separate read-only oracle receipt](../lib/kotoba.sql/evidence/interior-root-mutation-readonly-oracle-20261103.json).

This qualifies only the exact two-leaf-root fixtures and the tested one-row
root-collapse deletion on Linux ARM64. Deletion that leaves two or more rows,
arbitrary/deeper trees, WAL or rollback-journal processing, standard SQLite
locking, crash consistency, Linux x86_64, and Itonami integration remain open.

## Multi-row deletion within the admitted two-leaf roots (2026-11-03)

The exact-head Amu selfhost ARM64 run
[`41520888287`](https://github.com/kotoba-lang/kotoba/actions/runs/41520888287)
passed loaderless rebuild, compiler verification, All12, and the native SQLite
publication/readback/sidecar step. From the eight-row repeated-upsert fixture,
Kotoba deleted `repeat-a`, rebuilt both table/index leaves with seven rows,
published through FS2, reopened the image, and verified both missing and
preserved values through Kotoba. The native result is recorded in the
[multi-row deletion receipt](../lib/kotoba.sql/evidence/interior-root-multi-delete-native-linux-arm64-20261103.json).

A separate Python 3.15.0 / SQLite 3.54.1 immutable read-only connection
reported `integrity_check=ok`, page size 4096, page count 7, and exactly the
seven expected remaining keys. See the [read-only oracle receipt](../lib/kotoba.sql/evidence/interior-root-multi-delete-readonly-oracle-20261103.json).
This qualifies one key deletion leaving seven rows on this exact two-leaf
image. It does not qualify arbitrary multi-row deletion, deeper or arbitrary
trees, WAL/recovery, standard SQLite locking, crash consistency, Linux x86_64,
or Itonami integration.

## Native Linux gate scope (2026-11-03)

Rechecked Kotoba Actions run
[41478551197](https://github.com/kotoba-lang/kotoba/actions/runs/41478551197),
source revision `c19db0cae7347f2e733dc74bf3283e7fce9d7fe3`: the Amu
selfhost/Kotoba CLI job passed, including the native ARM64 SQLite publication,
readback, and sidecar refusal step. The separate x86 native controller job was
cancelled, and the overall workflow conclusion is `cancelled`. Therefore this
is evidence for that ARM64 SQLite gate only, not a successful full workflow or
x86 SQLite qualification. The source-pinned FS2 export plus independent,
read-only SQLite 3.54.1 readback described above remains a bounded result.
WAL/recovery, locking, crash consistency, broader layouts, x86_64 qualification,
and Itonami integration remain open.

## FS2 export and independent SQLite readback checkpoint (2026-11-03)

The initial codec checkpoint's statement that the generated image had not yet
been exported is superseded. Kotoba now exports its SQLite image through the
source-pinned Amu selfhost FS2 path; the native fixture reopens the published
image and reads the exercised values through Kotoba. A separate, dated Python
3.15.0 / SQLite 3.54.1 connection opens the artifact read-only and immutable,
reports `integrity_check=ok`, and checks the expected schema, rows, and
composite primary-key index. The latest bounded multi-row deletion evidence is
in the [native receipt](../lib/kotoba.sql/evidence/interior-root-multi-delete-native-linux-arm64-20261103.json)
and [read-only SQLite receipt](../lib/kotoba.sql/evidence/interior-root-multi-delete-readonly-oracle-20261103.json).

This establishes a bounded FS2 export/reopen and independent SQLite
readability result on the tested Amu/Kotoba ARM64 route. The SQLite oracle is
measurement evidence only; it is not part of the required runtime, build, or
CI path. It does not establish standard SQLite locking, WAL/rollback recovery,
crash-safe transactions, arbitrary page-tree support, or Itonami integration.
Kotoba PR #1172 remains open and draft at exact head
`bfd9665ad03e16baa57df2a1280c2c4a3dd06fde`; workflows
[`41557323188`](https://github.com/kotoba-lang/kotoba/actions/runs/41557323188)
and
[`41557322925`](https://github.com/kotoba-lang/kotoba/actions/runs/41557322925)
and all required PR checks passed. These include native ARM64 SQLite
publication/readback/sidecar refusal, native controller x86, Amu selfhost and
Kotoba CLI requests, native text on ARM64/x86_64, and wasm32 compile. The
separate bounded Linux x86_64 SQLite legacy-file mutation remains recorded in
the following section; it used the experimental Amu profile and does not make
that profile canonical.

## Delete a job from generated two-leaf roots (2026-11-03)

Exact-head run
[`41539246706`](https://github.com/kotoba-lang/kotoba/actions/runs/41539246706)
passed the Amu selfhost/Kotoba CLI native ARM64 job at commit
`678c0e3d06cf37006574b74dfde0ed0860b43af2`. The KSL2-pinned Kotoba fixture
created a two-leaf table/index root, deleted all rows for one job, collapsed
both roots to empty leaves, published and reopened through FS2, and confirmed
the deleted key was absent through Kotoba. The resulting SQLite image is
12,288 bytes with SHA-256
`dcdf3bcb14056d2643244e79cfdd1c2e8f9a74ce182cf7ada1f998f571a92ee1`.

An immutable read-only Python 3.15.0 / SQLite 3.54.1 check of the byte-identical
image reported `integrity_check=ok`, 4096-byte pages, three pages, no rows, and
the expected `cron_notepad` table and composite primary-key autoindex. The
local run used the pinned Amu compiler and runner whose SHA-256 values match
the CI receipt; the CI artifact itself records the matching database digest.
Receipts:
[`native ARM64`](../lib/kotoba.sql/evidence/interior-root-job-delete-native-linux-arm64-20261103.json)
and
[`read-only SQLite oracle`](../lib/kotoba.sql/evidence/interior-root-job-delete-readonly-oracle-20261103.json).

This qualifies this generated two-leaf job deletion and root collapse only.
It does not qualify arbitrary page trees, transaction/WAL recovery, standard
SQLite locking, crash consistency, Linux x86_64, or Itonami integration. The
separate x86 controller and wasm compile jobs had not completed when the
receipt was written.


## Bounded native Linux x86_64 legacy-file mutation (2026-11-03)

Exact-head Kotoba run [41554671902](https://github.com/kotoba-lang/kotoba/actions/runs/41554671902) at `38646de7e0b6063a8d56c0b63bb9b3c62fdabd29` passed the Amu selfhost/Kotoba ARM64 and CLI gates, wasm32-browser compile, and native Linux x86_64 controller job. The x86 SQLite step pins Amu candidate `897c816bedb15f851558c2f857bfd2be3ef25d41`, builds project compiler F1/F2/F3 to identical SHA-256 `ca6ad35ac07b60e7dd958e84797707c33176f7c4c7b34ac946ff6a9fd1e0f206`, then compiles and runs the Kotoba guest through KX64. It uses explicit wires `3,35,37,38,39`; no host SQL engine participates in the native gate.

Kotoba read the standard legacy `cron_notepad` fixture (SHA-256 `93d06242db9db564fd637caf9740d58d078f73d0bca20cba3d33a6cce2da61bd`), updated `job-update/cursor`, inserted `job-keep/note`, deleted `job-delete`, published through scoped FS2/FS35, reopened, and verified preserved/updated/deleted values through Kotoba. The published 12,288-byte SQLite image SHA-256 is `1f7068cc99ea96f9317381fe36127f583bba9a3fd12d10e0cfacafb4e55ca78e`.

A separate one-time Python 3.15.0 / SQLite 3.54.1 immutable read-only check reports `integrity_check=ok`, three 4096-byte pages, the expected `cron_notepad` table and composite primary-key autoindex, and exactly the three expected rows. The native and oracle receipts are [native x86 receipt](../lib/kotoba.sql/evidence/legacy-notepad-mutation-native-linux-x86-20261103.json) and [read-only oracle receipt](../lib/kotoba.sql/evidence/legacy-notepad-mutation-readonly-oracle-linux-x86-20261103.json).

This adds one bounded standard-file mutation shape on Linux x86_64. The Amu project profile remains a pinned candidate and is not canonical until its independent full gate passes. General SQLite API/layout coverage, WAL and rollback-journal recovery, standard SQLite locking/concurrency, crash consistency, arbitrary/deeper B-tree operations, and Itonami adapter wiring remain open.
