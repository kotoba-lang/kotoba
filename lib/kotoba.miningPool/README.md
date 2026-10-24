# mining-pool (Stratum v1 プール・ロジック)

Bitcoin mining pool の **プロトコル/ロジック層**を portable Clojure (`.cljc`) で。
v1 は本番運用向けのネットワークデーモン強化までは対象外（ADR:
`90-docs/adr/2607012200-kotoba-lang-btc-mining-wallet-substrate.md` の
out-of-scope 参照）——Stratum v1 メッセージの encode/decode、share 検証、
vardiff、支払いスキーム（PPLNS 参照実装）に集中する。

[kotoba-lang/btc-mining](https://github.com/kotoba-lang/btc-mining)（ヘッダー/
PoW判定）、[kotoba-lang/btc-crypto](https://github.com/kotoba-lang/btc-crypto)
（SHA256d）、[kotoba-lang/json](https://github.com/kotoba-lang/json)
（JSON encode/decode）に依存。

## Namespaces

- `mining-pool.protocol` — Stratum v1 (JSON-RPC, 改行区切り) の
  `mining.subscribe`/`authorize`/`notify`/`submit`/`set_difficulty` の
  encode/decode。ソケット I/O は含まない
- `mining-pool.share` — `mining.notify` の `coinb1`/`coinb2`/`extranonce1`/
  `extranonce2`/`merkle_branch` から実際に coinbase tx とマークルルートを
  再構築し、ヘッダーを組んで pool share target と network block target の
  **両方**を独立に判定する（share 採否 と 「実はブロックを見つけたか」を分離）
- `mining-pool.vardiff` — 直近の share 提出間隔から難易度を調整
  （速すぎれば上げる・遅すぎれば下げる、`max-adjust-factor` でクランプ）
- `mining-pool.ledger` — 追記専用の accepted-share 台帳 + 支払いスキーム
  （PPLNS を既定の参照実装として同梱、PPS も追加）

## Test

```
kbb -M:test
```

`src/mining_pool/bounded_vardiff.kotoba` は `mining-pool.vardiff/adjust-difficulty`
の capability-free Kotoba プロファイル（`current`/`observed-seconds-per-share`/
`target-seconds-per-share`/`max-adjust-factor` の4引数、f64 clamp 演算のみ）。
`min-difficulty` は Stratum 標準の下限 1.0 に固定しており一般引数としては
持たない — 詳細と、5引数以上の `:f64` 関数が Wasm へ誤コンパイルされる
コンパイラ側の既知の制約は [migration/bounded-vardiff-v1.edn](migration/bounded-vardiff-v1.edn)
を参照。`vardiff.cljc` はプロトコル/共有ledger連携を含む一般オラクルとして
そのまま残る。
