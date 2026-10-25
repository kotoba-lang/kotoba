# atprotocol

atproto 互換を **[kotoba-protocol](https://github.com/kotoba-lang/kotoba-protocol)
の上に立つ投影層**として定義する boundary/spec repo（pure `.cljc`）。
ADR-2607071500。

atproto の record / lexicon / XRPC / handle / repo-commit wire は
「kotoba graph の別 encoding」。真実（鍵・datom・graph CID・IPNS head・配布）
は常に kotoba-protocol 側にあり、この層は投影と互換だけを所有する。
依存方向も同じ（この repo → kotoba-protocol のみ。逆依存は作らない）。

## Namespaces

- `atprotocol.boundary` — owns / delegates の責務表（as data）+ `delegated?`。
- `atprotocol.projection` — record ⇄ datom **codec 契約**（実装 map を注入）。
  参照実装 = `aozora.pds.encode` / `aozora.appview.scan`（本番稼働中 —
  移植せずポインタとして記録）。未知 collection は generic 保全
  （`:atproto.record/*`）に落ちるのが契約。
- `atprotocol.profile` — `:kotoba.app/*` manifest → profile view への投影
  （`appId` / `appKind` / `embedUrl` / `bundleCid` / `appLatest`）。
  **旧 W-Protocol fields（performerType / contentMode / uiType）は
  deprecated compat alias に降格** — `{:include-legacy? true}` でのみ導出され、
  新規実装は読まない・書かない。

## Kotoba bounded profile

`src/atprotocol/bounded_boundary.kotoba` is a capability-free, sovereign-
source port of `atprotocol.boundary`'s fixed 12-concern ownership table —
a tamper-evident declaration of which system owns which architectural
concern, verified against `atprotocol.atprotocol-test`. `atprotocol.
projection`/`atprotocol.app-record`/`atprotocol.profile` stay CLJC
(function-valued codec contracts and open-ended JSON-record projection
aren't Kotoba-representable today). See
[migration/bounded-boundary-v1.edn](migration/bounded-boundary-v1.edn)
for the full record.

## Dev

```bash
kbb -M:test
```

## Kotoba bounded profile — app-record vocabulary

`src/atprotocol/bounded_app_record.kotoba` is a capability-free port of
`atprotocol.app-record`'s fixed 13-field camelCase-record-key →
`:kotoba.app/*` attribute projection vocabulary, as a canonical bounded
typed-map (`[:map :string :keyword]`, ≤31 entries). The reduce-kv
record↔manifest codec (which walks arbitrary open input maps and preserves
unknown fields under `:atprotocol/unprojected`), the reverse `attr->field`
direction, `valid-record?` (which delegates to
`kotoba.protocol.app/validate-manifest`), and the profile/projection layers
stay the CLJC oracle. See
[migration/bounded-app-record-vocab-v1.edn](migration/bounded-app-record-vocab-v1.edn).
This joins the existing `bounded_boundary.kotoba` profile in this repo.
