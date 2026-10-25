# Architecture

## Decision

Use a bounded hierarchical inventory rather than recording every filesystem
entry.

`du -x -d N` scans the selected filesystem once. The adapter sorts observations
by allocated bytes and admits at most `K` rows (default 120) to the guest. The
root observation is always retained. This keeps Kotoba execution and Datomic
growth bounded while retaining the paths that explain disk pressure.

```text
/usr/bin/du
    |
    | allocated-byte observations (host capability boundary)
    v
scan://root --fs-read--> diskspace.kotoba
                             |
                             +--> classification / cleanup policy
                             +--> evidence / confidence / risk
                             +--> non-overlapping cleanup proposals
                             +--> report EDN
                             +--> Datomic tx EDN
```

## Trust boundary

The adapter is allowed to observe one canonical root and write beneath this
repository's `data/` directory. The guest receives no ambient process,
filesystem, environment, or Datomic connection.

The adapter may inspect last-modified time, symbolic-link status, and the local
Git index for retained paths. These are facts, not decisions. The `.kotoba`
program is the sole authority that turns them into cleanup classifications.

The Safe Kotoba policy grants only:

- `scan://root`
- `data/latest.edn`
- `data/latest-tx.edn`

Historical filenames are derived by the adapter from the snapshot identity
created during the same scan. They cannot be supplied by guest data.

## Repeated scans

The expensive native observation is cached by canonical root and depth. In
automatic mode the cache is reused for at most 15 minutes. Every report records
`:diskspace.snapshot/scan-mode`, `source-captured-at`, and `cache-age-ms`, so a
cached observation cannot masquerade as a fresh full scan.

`--refresh` always bypasses the cache. TTL reuse intentionally does not claim
filesystem-event-level incrementality: macOS directory mtimes do not reliably
capture in-place file-size changes. A future FSEvents-backed adapter can add
correct changed-subtree rescans without changing the `.kotoba` domain model.

## Data identity

- Snapshot identity: UTC capture timestamp prefixed with `diskspace-`.
- Entry identity: `<snapshot-id>|<canonical-path>`.
- An entry belongs to exactly one snapshot.
- Paths are observations, not stable entities. Comparing two snapshots joins
  on `:diskspace.entry/path`.

This avoids mutating old facts and fits Datomic's append-oriented model.

## Cleanup proposal model

Cleanup is a separate append-only projection:

```text
diskspace.entry
    |
    +-- path category
    +-- Git state
    +-- symlink state
    +-- age evidence
    |
    v
cleanup.candidate
    +-- class / confidence / risk
    +-- proposed action
    +-- recovery method
    +-- evidence codes
    +-- status = proposed
```

The domain fails closed:

- Git-tracked entries are preserved even when their path resembles a build
  artifact.
- Symbolic links are preserved.
- Unknown Git state never receives high confidence.
- Data without a recognized recovery contract is preserved.
- Only the highest directory at a category boundary becomes a candidate. Its
  descendants remain observations but are not separate deletion units.
- No delete capability is granted. Execution requires a separate,
  approval-required capability and must append its own receipt.

This separation allows `local-manimani` to own personal approval and
`cloud-itonami` to supply organization retention overlays without moving the
reusable classifier out of `kotoba-lang`.

## APFS semantics

`:diskspace.entry/bytes` is allocated size reported by `du`, not logical file
length. `du -x` avoids crossing into other mounted filesystems. APFS clones,
snapshots, purgeable space, and protected paths can still make the sum differ
from the container allocation. Volume capacity/used/free are recorded
separately from `FileStore`.

For the logical root `/`, the adapter also applies `du -I Volumes`.
`/System/Volumes/Data` is the physical backing mount for firmlinked paths such
as `/Users`, `/Library`, and `/private`; counting both views would report more
bytes than the physical disk. The logical paths are retained and the physical
mount view is excluded.

## Future capability

When Kotoba gains a typed `fs-walk/stat` host import, replace `scan://root`
with that capability. The `.kotoba` domain and Datomic schema do not change.
