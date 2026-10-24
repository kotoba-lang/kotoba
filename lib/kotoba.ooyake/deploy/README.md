# ooyake 公 — gov-atlas toolchain

Scripts that build, ingest, promote, serve, consume and verify the world government
atlas (`gov-atlas-v1`). Per ADR-2606021600. All are **read-side / operator-local**
(G9): they catalog and query; they never file/submit/mutate a government record.

Run the full offline test suite:

```bash
bash deploy/run_tests.sh      # 8 suites, no network/deploy → ALL GREEN
```

## Scripts

| Script | Role | Gate / notes |
|---|---|---|
| `ingest_records.py` | Ingest the registry seeds (`gov-units*.seed.edn`) — units / 住所 / 窓口 / 書式 / 手続き / BPMN + the `actor.ooyake` profile — into the live kotoba `gov-atlas-v1` graph. | Bearer token (operator-local); DRY RUN without one. Never `kotoba commit`. |
| `ingest_jp_local.py` | Ingest the bundled JP local-government dataset (47 都道府県 + 71 市区町村, 全国地方公共団体コード). | 〃 |
| `ingest_states_global.py` | Ingest the **real-named** municipality tier across ~176 countries + ISO3 country units (synthetic district/ministry/office/lea tiers explicitly skipped, G5). Country units carry the real English name from lea NCB records when available. | 〃 |
| `promote_authoritative.py` | Promote the JP official-code backbone (118 units) `:representative → :authoritative` under the bootstrap attestation. | Token; **provisional** — re-ratify at Council 3-of-5 (`BOOTSTRAP-ATTESTATION-reconcile-live.md`). |
| `../cells/reconcile/cell.py` | `ReconcileCell`: `mode="bundled"` (offline promotion vs `authority-reference.edn`) / `mode="live"` (external fetch — **G4 + Council 3-of-5 gated**, raises). | `scripts/reconcile.py` is the CLI. |
| `gov_atlas_client.py` | `GovAtlas` — the shared READ API every consumer uses: `get_unit` / `resolve_path` / `children` / `by_level` / `by_jurisdiction` / `search` / `resolve_procedure` / `find_service`. | offline. |
| `resolve_for_toritsugi.py` | Resolve a toritsugi procedureId → 所管 + 窓口 + 住所 + 書式 + 根拠法令 (the ooyake-catalogs / toritsugi-delivers boundary). | offline. |
| `consumers_example.py` | Concrete read patterns for all 5 consumers (toritsugi / danjo / kanae / himotoki / tsumugi). | offline. |
| `validate_atlas.py` | Integrity + coverage validator for `gov-units.json` (unique ids, parent-refs resolve, level/sourcing enums, authoritative scope == bootstrap attestation, summary match). | local file or `--url` live; sets a UA. |
| `run_tests.sh` | Runs all of the above self-tests + dry-run projections. | offline. |

## Public read surface (served by `50-infra/etzhayyim-did-web`)

- `etzhayyim.com/actor/ooyake/did.json` — the actor DID (KV).
- `etzhayyim.com/.well-known/gov-units.json` — the machine-readable atlas index
  (generated offline by `scripts/gen-gov-atlas-index.mjs`).
- `etzhayyim.com/gov` — human civic-wayfinding search page.

## Constitutional gates (ADR-2606021600 §4)

G3 observational mirror · G4 public-data-only · G5 non-fabrication (sourcing
`:authoritative`/`:representative`; synthetic tiers never counted) · G6 no personal
data · G7 Murakumo-only · G8 non-commercial · G9 read-side only · G10 never a
target-list · G11 neutral · G12 freshness-gated. Live external fetch + full
authoritative promotion are Council 3-of-5 gated (bootstrap attestation covers only
the already-bundled official-code tiers).
