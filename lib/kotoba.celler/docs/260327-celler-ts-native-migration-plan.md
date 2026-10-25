# 260327 Celler TS Native Pilot

対象: `60-apps/etzhayyim-project-celler/wasm/etzhayyim-wasm-celler-oilt0wta`

## Scope

- `src/app.ts` と `src/worker.ts` を追加して TS Native スキャフォールドを置く。
- コマンド: `celler.list`, `celler.detail`
- `/_heartbeat` を実装して `fetch` の既存ルートに fallback で `sdk.handleRequest`。
- `src/app.ts` を entry として esbuild bundle (wrangler が自動実行)。

## 実装内容（Pilot）

- `celler.list`: `limit` と `q` を受けて `cypherQueryJson` を placeholder 実装で実行し、`Call` ノードの一覧を返却。
- `celler.detail`: `id` で `Call` を1件検索。
- `runHeartbeat`: heartbeat 回数をカウントし、最小アクションを返す。

## 次アクション

1. `main.go` と同等の `List*` / `Get*` コマンドを段階的に置換。
2. `celler.detail` の結果項目を既存 UI/エージェント期待仕様へ合わせる。
