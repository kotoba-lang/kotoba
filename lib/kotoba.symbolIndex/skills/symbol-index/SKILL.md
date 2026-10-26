---
name: symbol-index
description: コードを Read / cat / grep する前に引く symbol 索引。「X はどこで定義されているか」「この file / ns に何があるか」「定義は変わったか」を 1 call・数百 tok で答える。1 file 全読み (平均 6,580 tok) の代わりに snippet (平均 122 tok)。exit 0 = hit / 1 = 測って 0 件 / 2 = 拒否。
---

# symbol-index — コードを読む前に引く

`.cljk` / `.cljc` / `.cljs` / `.clj` / `.kotoba` の top-level 定義の索引。west / submodule 配下の
子 repo も見える (root の `git grep` は gitlink を 1 件も引かない)。

## 使い方 (subcommand は要らない — 形で解釈し、解釈を 1 行目に出す)

```
symbol-index <sym>            # find: どこに在るか。exact hit ≤3 なら定義の冒頭 (前 1 / 後 6 行) まで出る
symbol-index <ns>/<sym>       # show: その ns の定義の冒頭
symbol-index <file.cljk>      # outline: file の定義一覧 (行番号 + signature + #hash)
symbol-index <ns.name>        # outline: ns の定義一覧
symbol-index find <t> --in <path> | --exact   # 多いときの絞り込み
symbol-index find <sym> --dependents [--depth N|all]   # X を変えたら見直すべき定義 (被依存) を深さ別に (1 call)
symbol-index closure <ns/sym> | <file>  # Merkle closure hash (依存先の本文まで含む identity)。file なら全定義を畳んだ 1 つの hash = compile / test 結果の memo key
symbol-index status           # 索引の素性 (top / built-at / symbols / pruned)
symbol-index build            # 索引生成 (incremental。--full で全読み)
```

## 判断の規則 (これだけ守れば think と call が減る)

0. **最初の 1 回から project root で引く。** `cd <project root> && symbol-index <sym>` か
   `SYMBOL_INDEX_ROOT=<project root>`。cwd に索引が無いとき、build 済みの root が 1 つだけなら
   そこで答えて 1 行目に `(using index root …)` と出す。2 つ以上なら `REFUSE` で候補を列挙する ——
   **その場で `build` しない** (拒否文に従って build した 6/8 が 1 query あたり +1 call だった)。
1. **file を cat / Read する前に outline を引く。** outline は file の 1/5.7 の chars。
2. **exit code で次を決める。** 0 = hit。1 = 測って 0 件 (near の提案を引き直す。0 件は「無い」ではない)。
   2 = 拒否 (`REFUSE\t<理由>`: 索引が無い / top が違う / 旧形式 → `status` を見て `build`)。
3. **hit が 40 件超なら repo 別件数表が出る。** `--in <repo-path>` か `<ns>/<sym>` で 1 手で絞る。
4. **`(+N identical)` の写しは読まない。** 同じ構造 hash = 同じ本文。写しの file:line 自体が要る
   ときは `symbol-index find <sym> --unfold` (1 call)。TSV を自分で grep / awk しない。
5. **変更の有無は hash で確かめる。** outline / find / show の `#xxxxxxxxxx` が前と同じなら本文は同じ。
   `re-located … body unchanged` なら読み直さない。`body changed → #new` のときだけ読む。
   構造 hash は名前・局所変数名・comment・docstring・空白を含まない (本文の form だけ)。
   依存先まで含めた同一性が要るなら `closure <ns/sym>` (依存先の本文が変われば変わる)。
5b. **定義を変える前に `find <sym> --dependents`。** 参照している定義を深さ別に出す (test も含む)。
   grep で被参照を探さない (alias 経由の `a/sym` は grep に映らない)。
6. **索引より新しい file は自動で再走査される** (行番号は合う)。`build` は日次で十分。

## 数値 (実測、正本は repo の measurements.edn)

- full-file read 平均 6,580 tok/query → symbol + snippet 122 tok (54 倍)
- Hermes Agent A/B (8 query): skill 先読みで 8/8 正解・token 2.7 分の 1・API call 2.5 分の 1・壁時計 1/10。
  **置くだけでは agent が選ぶのは 2/8** —— 先読み (`hermes chat -s symbol-index`) まで含めて導入。
- 定義の 45.8% は他の定義と本文 (構造 hash: 名前・局所束縛・comment・docstring を除いた form) が同一 (root corpus、v4)。

## 導入

repo: https://github.com/kotoba-lang/symbol-index
`kbb --backend sci scripts/install.cljk` が `~/.local/bin/symbol-index` の symlink と
`~/.hermes/skills/software-development/symbol-index/` (hermes が在れば) を置き、AGENTS.md /
AGENTS.md 向けの 1 行を印字する。`--check` で導入状態を検査 (未導入は exit 2)。
