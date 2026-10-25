# screen

**kotoba-lang/screen — 画面を「読み、判断する」ための guest 側ライブラリ。**
画面認識・操作・状況把握の判断核 (judgment core) を Kotoba 言語で書き、
`kotoba compile` (amu native) で x86_64 / aarch64 のネイティブコードまで落とす。
ホスト (cloud-itonami resident、chronicle、コンピュータ操作 actor) が authority を持ち、
このライブラリは capability 経由で渡された観測に対する**純粋な判断**を所有する。

対応: `lang/capability-catalog.edn` の `:screen/observe` (wire id 31) と
`:screen/act` (wire id 32)。ADR-2609031100。

## モジュール

| モジュール | 純粋/能力 | 責務 |
|---|---|---|
| `screen.rect` | PURE | 境界付き座標空間 [0, 100000) の矩形。record 1 引数で ABI 5 param 上限を守る |
| `screen.tree` | PURE | accessibility tree の行 (ref-id × role-code の pair chain) の検索・計数・位置指定 |
| `screen.diff` | PURE | 2 frame の digest 比較。chronicle 風 rolling feed の重複除去判定 |
| `screen.intent` | PURE | act 前の shape 検査。ref-id ≥ 1 かつ expect digest 非空。text 4 KiB 上限 |
| `screen.guest` | `:screen/observe` | capability に面する表面。observe + shape gate (judge-press 等) |

`screen/act` (wire id 32) は**ホストが再検証する** authority であって guest が呼ぶ
API ではない。guest は intent 検査で shape を落とし、act の実行はホストが
digest currency を再確認した上で行う。参照しない capability を
`(:capabilities ...)` に書くとコンパイラが拒否する (declare-what-you-use)。

## ビルド (amu)

```bash
amu check src/screen/rect.kotoba --jvm-free          # 単体
amu check <entry> --source-path src                  # multi-file link
amu compile <entry> --source-path src --policy <pol.edn> \
  --target aarch64 --output screen.kexe --jvm-free   # native
```

policy は guest が宣言した capability を許可する:

```edn
{:allow #{[:cap/call 31]}}   ;; :screen/observe
```

## 検証済み (2026-09-03, M4 aarch64)

- 5 モジュール全部 `amu check --jvm-free` 通過 (sema 219f14f, wire id 31/32)
- kototama-native 経由の署名付き実行で再帰 pair-chain walk が
  `:status :ok :result 2` (fuel 508/512 残)
- `amu extract-native` は amu main 現行 pin で「native export table rejected」
  (upstream ADR 0288 と同型の pin regression、screen 固有の問題ではない —
  verify はkototama-native 経由で通る)

## Host seam

ホストが守るべき約束 (`host/SEAM.md`):

1. observe は tree digest と行 (ref-id/role-code の pair chain) を返す。
   digest 0 は「読めなかった」の意味で、0 は ref-id にならない。
2. act は guest の渡した expect digest を**実行前に**再検証する。
   画面が変わっていれば currency 拒否 (guest はそれを知らない)。
3. role-code はホスト語彙の小整数 [1, 64]。guest の quota 検査を通すため。
4. 座標は i64。screen 外の値は rect 側で境界拒否される。

## License

Apache-2.0 (workspace standard, matching amu/kotoba-sema)
