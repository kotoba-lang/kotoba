# AIUEOS-PARITY.md — 実測台帳（Linux 並 parity）

測定のみを記録する台帳。判断や水増しは含まない。主張は観測値と紐づく。
未測定の項目は `:declared`（宣言のみ）で止め、`:measured` を付けない。

## 測定方法

- スクリプト: `scripts/parity_evidence.py`（本 PR で同梱）。判断を含まない測定のみ。
  失敗時は REFUSED バナーを出して exit 0。
- 実行: `python3 scripts/parity_evidence.py <worktree>`。worktree が dirty の場合は測定拒否。

## 実測値（2026-10-12 JST）

測定対象: amu @ `e0315666` (origin/main), aiueos @ `fe8f6f7` (origin/main)。
worktree dirty=false、REFUSED 無し。

| 項目 | amu | aiueos |
|---|---|---|
| test_files (git ls-files test/ fuzz/) | 441 | 63 |
| has docs/coverage.edn | false | true |
| has docs/performance.md | true | false |
| has qualification | false | true |
| last CI (main) | success | **failure** |
| open issues | 28 | 12 |

aiueos main CI 赤: run headSha `fe8f6f7` 「paging: the transition page tables live
in .high_bss too (low-region headroom) (#421)」 conclusion=failure（CI ワークフロー）。
triage は amu-maint/aiueos-maint の分担。

## ADR-2608153500 残 gap（stage 台帳）

以下の行は本 window で再測定していないため全て `:declared`
（前回測定分の繰越。09-07〜10-03 の反復記録参照）:

- real-boot / NVMe NIC drivers — `:declared`
- DHCP / SLAAC, DNS — `:declared`
- prod TCP wiring, TLS transport — `:declared`
- wall-clock + NTP — `:declared`
- HTTP, enrollment-send, OTA + publisher-trust — `:declared`

これらは kernel/ハードウェア層の設計変更を伴うため、1 反復で閉じられる
gap は現時点で台帳上存在しない（この PR 自体は測定基盤の repo 同梱が目的）。

## 履歴

- 2026-10-12: 初版。parity_evidence.py を repo 内 `scripts/` に同梱
  （profile 外からも再実行可能に）。実測値は上表。opened via bot PR。
