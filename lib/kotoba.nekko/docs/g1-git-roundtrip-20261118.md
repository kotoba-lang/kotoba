# G1: bonsai と標準の git の往復（2026-11-18）

network-awai-apex ADR 0044 の D3 で決めた段階 G1（Git 互換）の証跡。Tracking: AWAI-3194。

## 実行したもの

- スクリプト: `lib/kotoba.bonsai/test/g1_git_roundtrip.cljk`。新しく作った一時 directory の中だけに書き込む。
- 実行した host: kotoba の nbb fork（`kotoba-lang/org-babashka-nbb`、`1675e6a` 2026-10-07）、Node.js v26.0.0、`git version 2.50.1`（macOS、Homebrew）。
- source: `kotoba-lang/kotoba` の `b3c8545c19ccff5e6943c58cb4aaec5cc7ecbcc6` に、この PR の変更を加えたもの。
- コマンド（`lib/kotoba.bonsai` から）:

```sh
node <org-babashka-nbb>/cli.js --classpath "src:test:$(ls -d ../*/src | tr '\n' ':')" test/g1_git_roundtrip.cljk
```

- 固定した入力: 作成者と commit の日時は `1700000000 +0000`。`GIT_CONFIG_NOSYSTEM=1`、`GIT_CONFIG_GLOBAL=/dev/null` で、手元の git 設定を読まない。

## 結果（全 15 項目が合格、`:pass true`）

| 方向 | 確認 | 結果 |
|---|---|---|
| bonsai → git | bonsai が loose object と ref を書いた repo を `git fsck --strict --no-dangling` で検査 | 合格 |
| bonsai → git | `git rev-parse HEAD` が bonsai の計算した commit OID（`4998079674…`）と一致 | 合格 |
| bonsai → git | `git show HEAD:README` で blob を読める | 合格 |
| bonsai → git | `git clone --no-local`（pack の転送）でき、clone 側も `fsck --strict` に合格 | 合格 |
| bonsai → git | bonsai が 2 つ目の commit（`c006d06bf4…`、親は 1 つ目）を書いた後、`git fetch` で取り込め、親のリンクも一致 | 合格 |
| git → bonsai | git が書いた loose object 5 個すべてを bonsai が復号し、OID を計算し直して path と一致 | 合格 |
| git → bonsai | commit（`fcbc962893…`）の tree と message を復号 | 合格 |
| git → bonsai | tree を復号して符号化し直すと、byte 単位で同じ OID になる | 合格 |
| git → bonsai | `git gc --aggressive` で作った pack を `bonsai.pack/decode` で読み、同じ 5 個の OID が揃う | 合格 |

## この証跡が示さないこと

- 検証した git は 1 つの版（2.50.1）だけ。ほかの版や SHA-256 の repo（`--object-format=sha256`）は確かめていない。
- remote helper（`git-remote-kotoba*`）を通した push と fetch は対象外。ここで扱ったのは、object と ref を直接置くことと、git 同士の clone・fetch。
- Radicle との互換（R1 以降）とは別の話。R1 は `docs/r1-radicle-mapping.md` を参照。
