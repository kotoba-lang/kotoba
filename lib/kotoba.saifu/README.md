# saifu（財布）— 権限は popup ではなく値

Cosmos / EVM のウォレット。設計の正本は superproject の
**ADR-2608039900**（`90-docs/adr/2608039900-saifu-wallet-authority-is-a-value-not-a-popup.edn`）。

## なぜ Keplr / Leap ではないのか

Keplr も Leap も、権限の問題を **「人間が popup で 1 件ずつ承認する」** ことで解いて
いる。ブラウザで人間が操作する前提では正しい。

しかし murakumo の消費者は Cloudflare Worker・CLI・スケジュールされた routine・
agent であり、**popup を出す相手がいない**。そこで普通に起きるのは「じゃあ鍵を
環境変数に置こう」で、その瞬間に権限は **ambient authority**（持っているだけで
何でもできる）に退化する。**それを起こさないことがこの repo の目的。**

## 層

| ns | 種別 | 状態 |
|---|---|---|
| `saifu.address` | 純粋 | **実装済み**（bech32 / BIP-173） |
| `saifu.policy`  | 純粋 | **実装済み**（attenuate は単調） |
| `saifu.tx`      | 純粋 | **実装済み**（SIGN_MODE_DIRECT 正準化。cosmjs 生成ベクタと **byte 一致**で検査 — `test/saifu/direct_test.cljk`） |
| `saifu.sign`    | `.cljc` + signer seam | **実装済み**（`wallet.signer/Signer` 経由 — **鍵は kagi から出さない**。署名の前に必ず `saifu.policy/gate`、`:commit` 以外はデータで拒否。64 byte 署名も cosmjs と一致） |
| `saifu.broadcast` | `.cljc` + capability | 未実装 |

実装順が address → policy → tx → sign → broadcast なのは、**前半 3 つが資金も鍵も
無しに正しさを証明できる**から。sign は ADR-2608241100 の signer seam
（本番 custody は `kagi.chain-signer` — 全署名が governor 検閲 + append-only 台帳）に載った。

## 実装しないもの

- **暗号プリミティブ**（secp256k1 / ripemd160 / sha256）。自前実装は事故の定番。
  レビュー済み実装（JDK / `@noble/*` / kagi）を呼ぶ。これは判断を含まない
  **機構(mechanism)** であって、`.cljc` 優先の対象外（ADR-2607241100 と同じ線引き）
- **鍵の保管**。kagi が持つ。saifu が持つのは**権限**であって鍵ではない

## 検査

`test/saifu/vectors.edn` は **Akash mainnet の実在口座** から取った
(address, hash160) の対。捏造ベクタで通しても意味がないため。

```bash
kbb -M:test
```

## 状態

**セキュリティクリティカルで、まだ誰もレビューしていない。意味のある額を扱わないこと。**
最初の用途は Akash 検証の最小額（0.5 AKT 級）に限る。
