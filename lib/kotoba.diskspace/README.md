# diskspace

`kotoba-lang/diskspace` is a bounded, historical disk-usage inventory for
macOS. The domain program is Safe Kotoba (`.kotoba`); observations and Datomic
transactions are EDN.

The scanner answers four questions:

1. Where is space used now?
2. Which large paths are rebuildable, cache-like, or review-only?
3. What changed between snapshots?
4. Which non-overlapping paths are evidence-backed cleanup proposals?

## Run

The default scan inventories the current user's home directory to depth 3 and
retains the 120 largest observed nodes:

```sh
kbb -M:run
```

Whole logical macOS root (the physical `/System/Volumes` view is excluded to
avoid APFS firmlink double counting):

```sh
kbb -M:run --root / --depth 3 --refresh
```

Explicit options:

```sh
kbb -M:run --root /Users/me --depth 3 --limit 120
```

An observation cache is valid for 15 minutes by default. A repeated command
with the same root and depth reuses the native scan and still creates a new
Kotoba/Datomic snapshot with explicit cache provenance:

```sh
kbb -M:run --root /Users/me --depth 3
kbb -M:run --root /Users/me --depth 3                 # cache hit
kbb -M:run --root /Users/me --depth 3 --refresh       # forced full scan
kbb -M:run --root /Users/me --depth 3 --max-age-seconds 60
```

Outputs:

- `data/latest.edn` — current report
- `data/latest-tx.edn` — Datomic transaction data
- `data/snapshots/<snapshot-id>.edn` — immutable report history
- `data/transactions/<snapshot-id>.edn` — immutable transaction history
- `data/cache/<root+depth>.edn` — bounded-TTL native observation cache

The report contains `:diskspace.report/cleanup-candidates`. Candidates are
proposal-only: this repository does not delete, trash, or mutate the observed
filesystem.

Each candidate records its class, confidence, risk, proposed action, recovery
method, and evidence. Git-tracked paths and symbolic links fail closed to
`:cleanup/preserve`. Only the highest matching directory in a classified tree
is proposed, so parent and child sizes are not double counted.

For a focused cache assessment:

```sh
kbb -M:run --root "$HOME/Library/Caches" --depth 2 --limit 120 --refresh
```

The generated proposal can later be projected to `local-manimani` for human
approval. Organization-wide retention overlays belong in `cloud-itonami`;
neither concern is part of this reusable classification engine.

Install `schema.edn` once, then transact each generated transaction file.
`queries.edn` contains Datalog examples for largest paths and snapshot deltas.

## Boundary

`src/diskspace.kotoba` is the semantic authority. It classifies paths,
assigns cleanup policy, and projects observations to Datomic entities.

Safe Kotoba currently has `fs-read` and `fs-write`, but no directory-list or
file-stat host import. `src-host/kotoba/lang/diskspace/host.cljk` is therefore
a narrow capability adapter:

- it invokes macOS `/usr/bin/du` on one canonical root;
- bounds depth and retained row count;
- reuses a root+depth cache only within an explicit TTL;
- exposes the observation as a pair-chain through the guarded `fs-read`
  resource `scan://root`;
- atomically persists only the EDN value returned by Kotoba.

It contains no cleanup policy or path classification. It only observes
allocated bytes, modification time, symlink status, and Git index membership.
All cleanup decisions remain in `.kotoba`.

See [docs/architecture.md](docs/architecture.md).
