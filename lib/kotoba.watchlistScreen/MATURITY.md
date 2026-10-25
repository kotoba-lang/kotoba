# Maturity

**Level: R1 experimental (real data, narrower-than-commercial match quality)**

Implemented:
- `watchlist.model` — entity/list-manifest records, match-tier vocabulary,
  staleness policy (pure, clock-as-param).
- `watchlist.match` — normalization, Jaro-Winkler (verified against
  Winkler's own published reference vectors), token-set/overlap scoring,
  tiered candidate classification (`:exact`/`:fuzzy-high`/`:fuzzy-low`).
- `watchlist.adapters.xml` — portable zero-dependency XML-string reader
  (same hand-rolled pattern kotoba-lang/org-omg-bpmn, org-oasis-open-xmile,
  org-omg-uml, org-sbml each already carry).
- `watchlist.adapters.ofac-sdn` / `.un-consolidated` / `.jp-mof` — real
  parsers, built and tested against the actual live government files (not
  reconstructed from memory). `resources/watchlist/lists/` ships a real
  snapshot of all three; the committed `*.manifest.edn` files carry the
  authoritative counts, fetch times and source hashes, so this file does not
  restate numbers that go stale the next time anyone runs the refresh.
- `watchlist.adapters.jp-mof` — Japan MOF 資産凍結等対象者一覧 (asset-freeze
  designations under the 外為法), parsed from the consolidated CSV via
  `csv.core` (kotoba-lang/org-ietf-csv, RFC 4180). Includes
  `latest-csv-link`, a pure function over the MOF index page's HTML, because
  MOF encodes the publication date in the filename and keeps no stable
  alias — a hardcoded URL would keep reporting successful refreshes of one
  frozen file. Rows are counted three ways (`:row-count`, `:entity-count`,
  `:skipped-rows`) so a row the adapter could not read shows up as a skip
  rather than as a quietly shorter list.
- `watchlist.match` script folding — halfwidth katakana with its voicing
  marks (ｶﾞ is two codepoints, ガ is one), fullwidth ASCII, hiragana →
  katakana, and CJK ideographs kept. Plus an empty-name floor in
  `score-name`: before it, two names the normalizer could not represent both
  became `""` and Jaro-Winkler scored them `1.0`, i.e. `:fuzzy-high` at
  0.92 on unrelated names. Both halves are regression-tested, and the
  empty-floor test asserts the inputs still normalize to `""` so it cannot
  start passing for a different reason.
- `watchlist.adapters.edn-index` — durable file-backed
  `watchlist.ports/IWatchlistIndex` (JVM-only, `.clj` not `.cljc`, matching
  `ekyc.adapters.edn-provider`'s own precedent for the same reason).
- `watchlist.core/screen` — orchestration: always returns staleness
  alongside candidates, never lets "no match" and "we don't actually know"
  look identical.
- `watchlist.adapters.aml-port` — real `aml.ports/IAmlScreening`
  implementation, fail-closed discipline mirroring
  `aml.adapters.etzhayyim`'s own documented "never :clear on an
  unrecognized/absent signal" rule (an absent name, a stale/absent index,
  and zero candidates are three different states, never collapsed).
- `scripts/refresh_lists.cljk` (nbb) — real fetch/hash/parse/write, run
  against every live source (see commit history / manifest
  `sha256`/`entity-count` fields for proof, not just a claim). A source
  whose data URL is not stable declares a `:discover` step, and a discovery
  that finds no link fails the refresh rather than falling back to a
  remembered URL.
- `scripts/publish_r2.cljk` (nbb) — publishes the committed snapshot to an
  R2 bucket, content-addressed by the sha256 of each entities file, with one
  mutable pointer per source and one index. Every put is read back and
  hashed before the source is reported published. Run for real against the
  `watchlist-snapshots` bucket; the read-back path was checked against a
  missing key (`wrangler r2 object get` exits 1), so the verifier has been
  observed refusing, not only accepting.
- Contract tests: Jaro-Winkler reference vectors, per-source fixture
  parsing (schema-faithful fixtures with fabricated names, verified
  independently against real live data during development — see each
  adapter's test namespace doc comment), staleness-threshold behavior,
  `aml-port` fail-closed mapping, `edn-index` file-I/O round-trip. 38
  tests, 93 assertions, 0 failures. `clj-kondo`: 0 errors, 0 warnings.

- Two-runtime test execution — `kbb -M:test` (55 tests / 147 assertions)
  and `kbb --backend sci -cp "test:$(kbb -Spath)" test/run.cljk` (52 / 141; the
  difference is `edn-index-test`, JVM-only by design). Every adapter is
  `.cljc` and runs under nbb in `scripts/refresh_lists.cljk`, so the JVM
  suite alone covered one of two runtimes. The nbb runner was added after a
  ClojureScript-only defect (`(int c)` on a one-character string is 0) made
  the script folds no-ops under nbb while the JVM suite stayed green;
  reverting `watchlist.match/char-code` fails 8 assertions under nbb and 0 on
  the JVM, so the runner has been observed discriminating.

Not yet R1 (i.e., explicitly absent, not a rounding-down):
- **EU Consolidated Financial Sanctions List** — not implemented at all.
  The EU's machine-readable source requires a registered access token this
  repo doesn't have (`watchlist.adapters.eu-consolidated`'s module doc).
  `watchlist.model/sources` does not include `:eu-consolidated`.
- **Not wired into `aml.core/screen`'s actual routing.**
  `aml.model/routes` (`kotoba-lang/aml`) is a closed `[:yabai :malak]`
  vector this repo does not own — a real, separate, small follow-up PR to
  `aml` is required before `:watchlist` is a real route a caller can select
  through the normal `aml.core/screen` path. Until then,
  `watchlist.adapters.aml-port/screening-port` is only directly/standalone
  callable.
- **Diacritic transliteration** — `watchlist.match/normalize` strips
  accented characters as punctuation rather than transliterating them
  (documented, tested known gap: "José" → "jos", not "jose").
- **Kanji ↔ kana readings** — 山田 and ヤマダ are the same name and
  `normalize` returns different strings for them. A codepoint table cannot
  close this; it needs a reading dictionary.
- **Scripts other than Latin and Japanese** — Hangul, Cyrillic, Arabic,
  Greek, Thai and Devanagari still normalize to `""`. That is a false
  negative, not a wrong answer: the empty floor in `score-name` turns an
  unrepresentable name into "no candidate", never into a self-match. The
  MOF list romanizes every entry (measured: 0 of 2,866 rows lack an English
  name), so its entities stay reachable through their Latin primary name.
- **No scheduled export to the Iceberg tables.** The four
  `cloud_itonami.watchlist_*` tables in `cloud-itonami-datalake` exist and
  hold this snapshot (see README), but the superproject's exporter is run by
  hand, so they age exactly the way `resources/watchlist/lists/` does — and
  `watchlist_manifest.source_commit` is the column that makes that visible
  rather than invisible.
- **No 反社会的勢力 (organised-crime) source of any kind** — and not for
  want of an adapter. No Japanese authority publishes such a list in
  machine-readable form. Commercial providers exist; none is ingested here,
  and nothing in this repo should be described as 反社チェック.
- **Phonetic/transliteration-variant matching** (Soundex, Metaphone, or a
  Cyrillic/Arabic romanization-aware comparator) — not implemented. A name
  variant that scores below 0.80 on both Jaro-Winkler and token overlap is
  never surfaced, full stop.
- **No accuracy benchmark of any kind** (false-positive rate, false-
  negative rate) against a real screening workload. The match algorithm is
  tested for correctness of its own stated logic, not validated against a
  labeled compliance dataset — none exists in this workspace, and none is
  fabricated here.
- **No automated scheduled refresh** — `scripts/refresh_lists.cljk` and
  `scripts/publish_r2.cljk` both exist and both have been run for real
  against live sources, but nothing runs either on a schedule.
  `resources/watchlist/lists/` is a point-in-time snapshot that will
  silently age unless someone re-runs it. This is the largest operational
  gap in the repo: the previous snapshot sat 38 days stale, and
  `watchlist.model/default-stale-after-days` is 14 — every screen against
  it correctly reported `:watchlist/stale? true`, and nobody was reading
  that field. A murakumo fleet gate (this workspace does not use GitHub
  Actions) is the follow-up.
- **Performance** — the shared XML reader is a straightforward char-
  scanning implementation, not optimized for the ~19,000-entity OFAC file's
  ~28MB size (tens of seconds on the JVM). Acceptable for a periodic batch
  job, not a hot path.
- **Entity types beyond individual/entity** — OFAC's real data also
  includes `Vessel`/`Aircraft` designations; this repo's `sdnType` mapping
  folds anything not exactly `"Individual"` to `:entity` (documented in
  `watchlist.adapters.ofac-sdn`'s module doc), so a vessel/aircraft-
  specific screening use case is out of scope.

## Downstream consumers

None yet in production. Designed to sit behind
`kotoba-lang/aml` (once the `:watchlist` route PR lands) and to be reusable
standalone by any caller wanting real sanctions/PEP name screening.
