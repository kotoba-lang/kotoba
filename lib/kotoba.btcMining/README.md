# btc-mining (CPU proof-of-work エンジン)

Bitcoin の proof-of-work を計算する portable Clojure (`.cljc`) エンジン。
**スコープは CPU/教育・検証用と明示する**（ADR:
`90-docs/adr/2607012200-kotoba-lang-btc-mining-wallet-substrate.md`）。
ASIC 対抗の実運用ハッシュレートは主張しない — 実運用でのハッシュ計算は ASIC/FPGA
ハードウェアが担い、このライブラリは主に
[kotoba-lang/mining-pool](https://github.com/kotoba-lang/mining-pool) 側の
job テンプレート組み立て・share/block 検証で使う。

[kotoba-lang/btc-crypto](https://github.com/kotoba-lang/btc-crypto) の
`sha256d` に依存。genesis block の実ヘッダーで parse/serialize/hash/PoW判定/
difficulty 計算を検証し、人工的に易しい target への実 CPU nonce 探索も
テストしている（`kbb -M:test`）。

## API (`btc-mining.core`)

- `serialize-header` / `parse-header` — 80 バイトのブロックヘッダー ⇄ map
- `header-hash` / `display-hash` — SHA256d、内部順序 ⇄ 慣用表示（big-endian）順序
- `merkle-root` — Bitcoin のマークルルート（奇数葉は最後を複製する既知の仕様）
- `bits->target` / `difficulty` — compact `bits` ⇄ 256-bit target、difficulty-1 比
- `meets-target?` — PoW 合否判定
- `mine` — CPU nonce 探索（32-bit nonce 空間を使い切ったら nil。呼び出し側が
  coinbase/extranonce か `:time` を変えて merkle root を作り直し再試行する）
- `template->header` — `getblocktemplate` 形状の入力から未解決ヘッダーを組み立て

## Test

```
kbb -M:test
```
