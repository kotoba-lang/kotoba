# symbol-index

シンボル索引: `.cljk` / `.cljc` / `.cljs` / `.clj` / `.kotoba` を走査し、top-level
`(def...)` / `(ns...)` form に現れるシンボルから「シンボル → file:line」の索引を
作る。agent がコードを探すとき、full-file read の代わりに snippet を引くための道具。

## agent はこう使う (思考を減らす順)

コードを読む前に、この 3 つで済むか試す。全部 1 s 以内・数百 tok。

```
<query>              # subcommand 不要: *.cljk / a.b → outline、a.b/c → show、他 → find (解釈を 1 行目に出す)
find <term>          # どこに在るか。hit ≤3 なら定義の冒頭まで出る (往復 1 回)
find <ns>/<term> | --in <path> | --exact   # 多いときの絞り込み (出力が次の 1 手を示す)
outline <file|ns>    # file を Read する前の地図: 行番号 + signature + #hash (変更確認は hash 比較で、cat しない)
show <ns/sym>        # 定義の前後 3 行。ns で曖昧性を解く
```

exit code で判断する: **0 = hit / 1 = 測って 0 件 / 2 = 拒否** (理由は `REFUSE\t…` 行)。
2 が出たら索引の問題 (top 違い・空・旧形式) —— `status` で素性を見て `build`。
`find` が 40 件超なら repo 別の件数表が出るので `--in <repo-path>` で絞る。0 件なら
near の提案を引き直す (0 件は「無い」ではない)。`~` 付きは reader-cond / indent 内の nested 定義。

## 実測 (append-only、正本は `measurements.edn`)

### iteration 1 (2026-09-15)

- full-file read: 平均 **~6,580 tok/query** (p50 2,212 tok)
- symbol + 前後 3 行 snippet: 平均 **~122 tok/query** → **54 倍削減**
- 最悪ケース: `catalog.cljk` 1.28M tok の full read は context を破綻させる

### iteration 2 (2026-09-15)

superproject root (orgs/ 含む、51,594 file / 612,791 symbol) で:

| 仮説 | before | after |
|---|---|---|
| find / show の wall time | 5.85 s / 5.18 s (108 MB JSON + js->clj) | **0.76 s / 0.64 s** (TSV + native RegExp、kbb 起動 0.49 s 込み) |
| 正本 path が索引から消える | `apply-pin-advance` が `worktrees/…` 側 1 件のみ | `orgs/kotoba-lang/kagami/src/kagami/db.cljk:81` |
| metadata を名前に取る | `^:private` 等 38,894 件 (5%) | 0 件 |
| linked worktree / 生成物 dir の重複 | worktrees/ 305,436 + runs/ 32,025 symbol | skip 34 worktree + 22 gitignored dir |
| file の地図 | Read 7,611 chars | `outline kagami.db` 423 chars (**18 倍**) |
| 空索引 / 空 tree | exit 0 で「0 hits」 | REFUSE exit 2 |
| test | 無し | 32 check、壊したコピー 3 種で赤を確認 |

build は 105 s (sys 37 s = stat × 5 万)。→ iteration 3 で対処。

### iteration 3 (2026-09-15)

| 仮説 | before | after |
|---|---|---|
| 読めない dir 1 つで build が落ちる (ENAMETOOLONG / EACCES) | crash | `UNREADABLE-DIRS\tn` に数えて続行 |
| walk が entry ごとに stat + realpath | 67.2 s (walk のみ) | **46.1 s** (dirent、stat は symlink だけ) |
| scan が SCI の per-line loop | 1,712 ms / 5,000 file | **387 ms** (native `gm` RegExp) |
| 複数行 `^{:doc …}` の def | 取れない | 5,018 件を新たに索引 (ns 形式も) |
| build 全体 (root corpus、A B A B 交互) | 134.1 s / 149.2 s (load 50 / 25) | **107.7 s / 121.1 s** (load 24 / 28、各周 −20%) |

### iteration 4 (2026-09-15)

観測: 136,302 dir のうち **85% (116,269) は source を 1 つも持たない subtree**
(takeout / news content / onedrive archive / .venv)。名前では分けられない。

| 仮説 | before | after |
|---|---|---|
| 連続 fileless dir 数で data subtree を prune (budget 1000、校正: source を持つ group の最長 run 737) | 全 dir を歩く | 11 group を prune、**失った file 0** (row 集合が同一) |
| build 全体 (no-prune / prune 交互、load 33–99) | 200.5 s / 179.4 s | **161.9 s / 132.4 s** (−19% / −26%) |
| walk が実は DFS だった (`(rest dirs)` への conj) | 校正と実装が不一致 | BFS に固定 |
| virtualenv | 2,776 dir を歩く | `pyvenv.cfg` で skip (8 個) |

prune した group は `status` の `pruned-group` 行に必ず出る。そこにある code を探すなら
`build --no-prune`。

### iteration 6 (2026-09-15) — 「kotoba-lang の find / grep で速くなるか」

phase 内訳 (prune 後 74,419 dir、load 54): **walk 121.7 s** / scan 40.3 s / write 5.9 s。

| 仮説 | 結果 |
|---|---|
| `org-ieee-find` (amu native) を walk に使う | **今は不可、理由は 1 つに減った** (2026-09-15 再評価、iteration 13): 式 (`-prune`) が無い。arena の trap と速度は消えた — 857,322 entry を 1 thread で user 1.64 / sys 18.5 s (`/usr/bin/find -s` 1.41 / 36.5、`fd -HI` 1.90 / 22.7、wall は 49 / 76 / 7.4 s)。再評価条件は `-prune` 相当が入ったとき。正本 root ADR-2609152113 |
| `/usr/bin/find -L` を fast path に | **不採用**: load 90–130 の共有機では I/O bound。全 tree の find 93.7 / 88.0 s ≒ prune 後の SCI walk 131.5 / 95.2 s。SCI overhead は上限でも 3 割 |
| 子 dir ごとの `.git` statSync (74K 回) を dirent 判定に | A B A B: 156.7 / 172.0 s → **141.2 / 150.7 s** (−10% / −12%) |

build は I/O bound で、この機械の load 次第で 2 倍ぶれる。以後 build の最適化は
「syscall を減らす」以外に lever が無いので、次は query 側の実測 (agent が実際に
何 tok 使ったか) に戻る。

### iteration 7 (2026-09-15) — 目標を「agent の 1 task」に置き直す

| 仮説 | before | after |
|---|---|---|
| incremental build (dir は mtime、file は mtime+size で cache) | full 191.1 / 179.6 s | **warm 85.1 / 104.5 s**、結果は次の full と同一。file 書換 / 追加 / 削除 / `--full` を test で pin |
| top 自身が linked worktree | iteration 6 の regression: SCANNED 0 で REFUSE | top は worktree 判定の対象外 (test) |
| `find` が 1 call で答える | Hermes arm C は 8/8 が find → show の 2 call | hit ≤3 なら全 hit の冒頭 (前 1 / 後 6 行) を出す。agent 側の実測は hermes のある機で `bench/hermes_ab.cljk` |

cache は `.kotoba-cache/symbol-index.cache.json`。同一 ms・同一 size の書き換えは
見えないので、疑わしいときは `build --full`。

### iteration 8 (2026-09-15) — 出力形で think を減らす

| 仮説 | before | after |
|---|---|---|
| hit が多いとき | 40 行 + 「narrow the term」(`find walk`: 42 行 / 2,526 chars) | repo 別件数 top 12 + rank 上位 8 + narrow 3 形 (**24 行 / 1,018 chars**) |
| 0 hit | 「0 hits」だけ (agent は『無い』と読む) | 断片 / prefix で近い symbol を最大 8 個提案。`--in` / ns の filter を守る |
| `find` の絞り込み | 無し | `find <ns>/term` / `--in <path-substr>` / `--exact` |
| prompt cache 向けの出力並び替え | — | 理屈で落ちるので不採用 (cache は会話 prefix 単位) |

### iteration 9 (2026-09-15) — 代理指標 `bench/one_call.cljk`

hermes の無い機でも測れるように、同じ 8 query で「`find` 1 call の出力だけで答えられるか」
(correct) と「定義の冒頭が出ているか」(opening = 2 call 目不要) を取る。

| | correct | opening | chars 平均 |
|---|---|---|---|
| iteration 8 | 8/8 | 5/8 | 1,022 |
| iteration 9 | 8/8 | **8/8** | 1,147 |

直したこと: exact hit が 1–3 件なら substring hit が混ざっても exact の snippet を出す /
同じ定義の写し (verify-run・clone、`.clj` と `.cljk`) を 1 行に畳んで `(+N copies)`。

### iteration 10 (2026-09-15) — outline に signature

defn 600 件の実測: arglist が def 行にあるのは 55%、docstring が先なのが 40%。outline の
各行に「名前より後ろ」(arglist + 本体の頭) か docstring 1 行目を 80 字で添える。
`outline kagami.db`: 404 → 1,333 chars (file Read 7,611 の 1/5.7)。`--bare` で従来形。

### iteration 11 (2026-09-15) — subcommand を選ばせない

`symbol-index <query>` だけで形から dispatch する (`*.cljk` / `a.b` → outline、`a.b/c` → show、
他 → find)。解釈は 1 行目に出る。agent が 3 つの使い分けを覚える必要が無くなる分、skill
本文を縮められる (agent 側の実測は hermes のある機で)。

### iteration 12 (2026-09-15) — 索引より新しい file は、その file だけ直す

build 1.6 h 後の root corpus で変更済み file は 0.10% (49/47,353) だが、agent が今編集
している file こそ次に引く file。`find` / `show` / `outline` は hit の file の mtime が
built-at より新しければその file だけ再走査して行番号を直し、`(re-located: … was line N)`
/ `(re-scanned)` と印字する。symbol が消えていれば snippet を出さず build を促す。

### iteration 14 (2026-09-15) — 定義の content hash (Unison 型)

索引 v3 は定義ごとに content hash (#10 hex) を持つ。span はその def から次の top-level def の
直前まで、空白を畳んで sha256。**名前でなく本文で同一**: 写しは同じ hash、空白だけの変更は
同じ hash、本文の変更は違う hash。

root corpus の実測: **定義の 41.2% (233,858 / 567,719) は他と本文が同一**。旧 iteration 9 の
推定畳み (sym/kind/line/stem) は 10,322 group で本文の違う定義を同一視していた → hash で消えた。

agent はこう使う: 変更の有無は `cat` でなく `outline` の hash 比較 (file の 1/5.7)。`find` の
`(+N identical)` の写しは読まない。stale file の `re-located … body unchanged` なら読み直さない。

### iteration 21 (2026-09-18) — 導入の実測と費用の内訳、出力に証拠を同梱

朝の superproject 本体は root 写し v5 / 索引 v2 で `find` が 10/10 REFUSE、hermes は skill が 09-15 の写しで
先読み無し、plugin-hermes 未導入だった。直してから測った (腕 G3 = Claude Code、腕 I = hermes `auto_load` のみ):

| 腕 | 正解 | tool/q | API/q | tok/q | file read |
|---|---|---|---|---|---|
| G (09-17、写しが索引を REFUSE = 朝と同じ形) | 9/10 | 6.1 | 7.1 | 438k | 11 |
| **G3 (v5 rebuild 後)** | **10/10** | 3.5 | 4.5 | 278k | 1 |
| I (hermes、`-s` 無し・`skills.auto_load` だけ、q1–q3) | 3/3 | 1.0 | 2.0 | 38k | 0 |

I は `-s` 先読み腕 H (35k / 1 tool) と同じ形 —— `auto_load` は効いている (q4 以降は上流 api.kotoba.cloud の
503/504 嵐で session 無しの TIMEOUT、5 分あたり 94 件。回復後に再走)。

**費用の内訳 (G3、Opus 5、$6.71 / 10 query)**: cache write 74% / cache read 17% / output 9%。
ctx0 = 58k tok のうち **44.6k を毎 session 書き直している** —— 同一 prompt を続けて 2 回でも、`--resume` でも
write 44.6k / read 12k。hook 出力 7 本の diff と `git status` は 1 分間同一なので、変動要因は harness の
prompt 組み立ての中 (外からは特定不能、product feedback 下書き)。symbol-index の出力は call あたり 1–3k で
支配項ではない。hermes 側は 1 call 18.5k tok、`cache_read_tokens` は 0 だが edge が
`prompt_tokens_details.cached_tokens` を通していないので **未測定** (0 ではない)。

**h44: 裏取り call は『出力に確かめる材料が無い』から起きる。** G3 は 10/10 で最初の call が索引で答えを出し、
残りは裏取りだった (q9: `--dependents` 7 件の後 rg/sed 10 call、q8: exact 3 件の後 tree 全体に rg 2 回、
q1–q7: snippet を sed で読み直し)。着地: `--dependents` に各定義の call site 行 (≤3、今 file から読む、
`--no-sites`)、`find` に網羅性の 1 行 (exact/substring・scanned・built) と「snippet は今 file から読んだ」、
AGENTS.md に「sed / grep / rg で読み直さない」の 1 文。

| q | G3 → G4 tool | API | tok | wall |
|---|---|---|---|---|
| q1 | 4 → **1** | 5 → 2 | 299k → 119k | 165 s → 38 s |
| q9 | 11 → **4** | 12 → 5 | 795k → 313k | 151 s → 96 s |
| q8 | 6 → **2** | 7 → 3 | 442k → 184k | 107 s → 69 s |

3 query 合計: tool 21 → 7 (−67%)、tok 1.54M → 0.62M (−60%)、$2.76 → $1.91 (−31%。床は session ごとの
cache write 44.6k ≈ $0.45)。test 130/0、壊した写し 2 通りで対応する check だけ赤。

### iteration 20 (2026-09-18) — 同 ns 別 file の参照、`closure <file>`、plugin-hermes の memo

- 参照列の穴を塞いだ: bare 参照は「同 file の定義名」でなく「core (sci の `clojure.core` public 674 個 +
  special form) でも局所でもない unqualified symbol」を持つ。同 ns の別 file にある定義への被依存が引ける。
  full build user CPU 245 → 254 s (+3.4%)、索引 109 → 113 MB、参照 1.42M → 1.92M 本
- `closure <file>`: file の全定義の closure を sort して 1 つの hash に。`plugin-hermes` の `kotoba_check` が
  これを memo key にした (hit 0.39 s / miss 26.7 s、comment 編集は hit・本文編集は miss、index 無しは『keyed
  していない』と言って走る)。**`amu check` 自身が定義ごとの CID (`kotoba.definition-identity/v1`、dependencies
  付き) を出している** —— compiler 側と索引側で同じ Merkle を 2 回計算している。揃えるのは open
- test 126/0、壊し方 2 通り (core 除外を殺す / file closure が定義を見ない) で赤

### iteration 19 (2026-09-17) — Claude Code の腕、task 形 2 つ、版ずれの誤導

| 腕 | 正解 | tool call | API call | token | file read |
|---|---|---|---|---|---|
| H: hermes + iteration 18 (q1–q10、被依存 / closure 込み) | **10/10** | **1.5** | **2.5** | 46,604 | 0 |
| G: Claude Code headless (AGENTS.md の 1 行のみ、root 写しは v4) | 9/10 | 6.1 | 7.1 | 438,416 | 11 |
| G2: 同、root 写しと AGENTS.md を揃えた翌日 (09-18) | **10/10** | 3.1 | 4.1 | 259,634 | 9 |

G の費用は索引ではなく 2 つの穴: ① superproject 本体の root 写し `scripts/symbol-index.cljk` が v4 のまま
v5 索引を REFUSE し、10/10 で agent が上流を探して復旧した (+3〜5 call)。拒否文が「run build」だと古い版で
索引を作り直して潰すので、**索引の方が新しいときは『新しい script を使え、この写しで build するな』**に変えた。
② `--dependents` を知らず (AGENTS.md にも写しにも無い) `rg` で探して turn 上限 → `find` の出力末尾に
被依存と closure の口を 1 行出す。**新しい口は出力と入口文書に書かないと使われない。**
bench には q9 (被依存 7 件)、q10 (closure、期待は実行直前に取る)、`--agent claude` を足した。

### iteration 18 (2026-09-17) — 参照列 (v5)、`find --dependents`、`closure`

iteration 17 の closure hash を索引の列にはせず、**参照だけを 8 列目に持ち、解決は query 時**にした。
参照は 3 種だけ (同 file の定義名 / `:require` の alias・refer 経由の `ns/sym` / 完全修飾)。core・interop・
索引外の lib は名前を持たない。同 ns の別 file にある定義への bare 参照は落ちる (設計上の穴)。

- `find <sym> --dependents [--depth N|all]` — 参照している定義を深さ別に (BFS、写しは hash で畳む)。
  「X を変えたら見直すべき定義」を 1 call で。root corpus で 2.9 s (109 MB を正規表現で 2 本走査 / 段)
- `closure <ns/sym>` — その場で Merkle closure hash (到達可能な subgraph を集め、SCC は 1 単位)。0.9 s。
  compile / test 結果の memo key に使う (依存先の本文が変われば変わる、無関係は変わらない)
- build cost: full build user CPU 238 s → 245 s (+3%)、索引 80 MB → 109 MB (384,556 行が参照を持ち 1.42M 本)
- test 116/0、壊し方 3 通り (参照列を空に / BFS を 1 段に / closure が依存先を入れない) で名指しの test が赤

### iteration 17 (2026-09-17) — closure hash (Merkle、測定のみ)

構造 hash は参照先が変わっても変わらない。`bench/closure_hash.cljk` で参照 symbol を参照先の hash に
置換した closure hash を全件 (546,482 定義) 計算した。参照の解決率 22.5% (残りは core / interop /
索引外の lib で、名前のまま identity に入る)。相互再帰 (declare、362 SCC、最大 43) は SCC 単位で hash
しないと伝播が止まる —— 最初の全件で 5/20 が落ちて分かった。直したあと 30/30 両方向 (推移的被依存は
全部変わり、他は 1 つも変わらない)。blast radius は中央値 1・p90 22・最大 60,957 (最下層の helper)。
**本文は同じだが依存先が違う写しが 49,254** —— text / struct hash では見えなかった差。
索引には入れていない (bench で 20 min = build の 4 倍。incremental な SCC 更新が要る)。数値と再現手順は
`measurements.edn` の `:h39-closure-hash`。

### iteration 16 (2026-09-17) — agent 側の実測 (Hermes 腕 D / E / F) と、そこで見えた 2 つの穴

iteration 7〜15 の効果を初めて agent 側で測った (`bench/hermes_ab.cljk`、8 query、同日 3 腕):

| 腕 | 正解 | timeout | tool call | API call | token | file read |
|---|---|---|---|---|---|---|
| D: v4 索引 + 09-15 の skill | 7/8 | 1 | 3.1 | 4.0 | 72,798 | 0 |
| E: + skill 規則 0 (project root で引く) | 7/8 | 1 | 1.8 | 2.5 | 46,269 | 0 |
| F: + iteration 16 (登録簿 fallback / --unfold) | **8/8** | **0** | **1.5** | **2.5** | **46,060** | 0 |

D で見えた穴: ①hermes の terminal は `$HOME` から始まり、7/8 が `REFUSE no index` を受け、6/8 が拒否文の
「run `symbol-index build`」に従って build を走らせた (+1.1 call / query)。②multi-hit の q8 は
「(N identical folded)」の写しの file:line を TSV の grep で出そうとして 600 s 時間切れ。
直し: `build` が root を `~/.kotoba-cache/symbol-index-roots` に記録し、cwd に索引が無いとき登録簿の
root が 1 つだけならそれで答える (読むだけ、build しない。2 つ以上なら列挙して REFUSE)。REFUSE 文は
cd が先頭。`find --unfold` で写しを列挙 (誘いは定義が 2 つ以上のときだけ)。skill に規則 0。
bench 側の欠陥も 2 つ (期待 file:line が 2 日で 4/10 古びた → `--regrade`、si の計数 regex が
subcommand 無しを 0 と数えた)。file read は 3 腕とも 0 —— iteration 7 の snippet が agent 側で効いている。
壁時計は日を跨いで比べない (API 1 call が 09-15 の 9 s → 70–120 s)。

### iteration 15 (2026-09-17) — 構造 hash (TSV v4 として着地)

v3 の text hash は「写しの検出」には効くが「名前だけ違う同じ定義」は畳めず、rename / comment で
変わる。`bench/structural_hash.cljk` で reader を通した構造 hash (def 名 → `%name`、局所束縛 →
`%0 %1 …`、docstring と位置 meta を落とし、set / map は印字 sort、`*print-meta*` で pr-str →
sha256) を text hash の隣で全件計算した (599,439 定義、4 min):

- 他と同一の定義: text **39.0%** → 構造 **45.8%** (+41,135。自明な `(def x 32)` を除くと +17,409)
- 1 つの構造 hash に 2 つ以上の名前: 10,000 group 超 (最大 73 名)。`(defn disposition-commit [d]
  (eq-flag d 2))` と `(defn reason-phase-approval [r] (eq-flag r 2))` は同じ hash に 23 名 ——
  naming 面と identity 面を分ける根拠
- 両方向: ws / comment / rename は構造 hash 同、末尾に `nil` を足すと異 (各 ~100 定義、全部期待どおり)
- **text hash の欠陥が 1 つ見つかった**: 文字列リテラル内の改行+空白を畳んで「同じ」と答える
  (構造 hash は正しく「違う」)

着地 (TSV **v4**): 7 列目が構造 hash になった。reader を通らない定義 (root corpus で 280 / 616,218)
は text hash に落として flags に `t` を立てる —— 「測れなかった」を「同じ」に混ぜない。A/B (同一
checkout): full build の user CPU は 58 s → 238 s (parse の分。incremental は cache で 44 s、query は
0.7–0.95 s で不変)。`find` の畳みは名前が同じものの中だけなので増分は小さい (exec-op +2、now +126)。
効くのは `outline` / `show` の変更検知: rename・comment・docstring で「body changed」を出さない。
壊し方 3 通り (set の sort / `%name` / flag `t`) で名指しの test が赤、無改変で 94/0。

未測定: 参照先 hash への置換 (Merkle。依存が変わっても自分は変わらない)、macro 展開後の同一性、
agent 側の効果。数値と再現手順は `measurements.edn` の `:h35-structural-hash` / `:h36-struct-hash-landed`。

### iteration 13 (2026-09-15) — 固定点

この機で測れる指標は固定: test 76/0、`one_call` 8/8 · 8/8 (chars 平均 1,147)、root 索引
51,602 file / 613,286 symbol。**agent 側で未測定のまま残る 5 件** (H24 / H26 / H30 / H31 /
H32) は hermes のある機で `bench/hermes_ab.cljk` を腕 D として回して腕 C と比べる。
`measurements.edn` の `:fixpoint` に一覧。捏造した仮説で反復を埋めないためにここで止める。

## 使い方 (kbb / nbb / babashka どれでも)

```bash
# 索引生成 (1 回。superproject 全体で ~105 s、単 repo なら 1 s)
bin/symbol-index build [--include-worktrees] [--no-prune] [--full]

# シンボル部分一致検索 (大小無視) → file:line 一覧、exact > prefix > substring
bin/symbol-index find reconcile

# 定義の snippet 表示 (前後 3 行)。ns/ で曖昧性を解く
bin/symbol-index show kagami.db/apply-pin-advance

# file (path 末尾一致) か ns の定義一覧
bin/symbol-index outline kagami/db.cljk
bin/symbol-index outline kagami.db

# 索引の素性 (top / built-at / scanned / symbols / age)
bin/symbol-index status
```

`build` は `.kotoba-cache/symbol-index.tsv` (v5、gitignore 推奨) に落とす。
`find` / `show` / `outline` は**索引が無ければ REFUSE する** (exit 2、自動 build
しない —— iteration 3 で Hermes Agent に導入したとき、agent の terminal が `$HOME`
に居る状態で呼ばれ、home 全体を build しに行って tool の 120s timeout に当たった
実測がある)。build は明示の `build` だけ。

top の決め方 (優先順): `SYMBOL_INDEX_ROOT` > `CLAUDE_PROJECT_DIR` > cwd から上へ
辿って `.kotoba-cache/symbol-index.tsv` を持つ最寄りの dir > cwd。project の
subdir から呼んでも root の索引を引く。root の外 (例: `$HOME`) から呼ぶときは
`SYMBOL_INDEX_ROOT=/path/to/root` を付ける。いずれも realpath に揃えてから
索引 header の top と比べる (macOS の `/var` → `/private/var` で不一致になった)。
索引の top と違う場所から引くと REFUSE する (別 tree の答えを返さない)。

`bin/symbol-index` は symlink 越し (`ln -s .../bin/symbol-index ~/.local/bin/`)
でも自分の実体を辿って `scripts/` を見つける (`BASH_SOURCE[0]` は link 側なので、
辿らないと `~/.local/scripts/` を探して ENOENT になった)。

## 他の agent / CLI への導入

```bash
kbb --backend sci scripts/install.cljk           # ~/.local/bin/symbol-index の symlink + hermes skill (在れば)
kbb --backend sci scripts/install.cljk --check   # 導入状態の検査。未導入 / ずれは exit 2
```

- **skill の正本は `skills/symbol-index/SKILL.md`** (agent 非依存: 使い方・判断の規則・数値)。
  Hermes は `~/.hermes/skills/software-development/symbol-index/` に写し、Claude Code は
  superproject の AGENTS.md に 1 行 (install が印字する)、Codex は AGENTS.md (AGENTS.md から生成)。
- **Hermes は先読みまでが導入** (`hermes chat -s symbol-index` / cron の `skills:`)。A/B
  (`bench/hermes_ab.cljk`、`measurements.edn` :iteration 5): 先読みで 8/8 正解・token 2.7 分の
  1・API call 2.5 分の 1・壁時計 1/10。置くだけでは agent が選ぶのは 2/8。
- KPI の正本は superproject の ADR-2609152300 (K1 cost-eq / K2 api-calls / K3 ctx0 / K4 ctx-mean
  / K5 correct / K6 wall)。この repo の代理指標: `bench/one_call.cljk` (K2 / K5)、
  `scripts/agent-usage-report.cljk` (superproject 側、K1-K4・再読みの無駄)。

## 自己検査

```bash
kbb --backend sci test/symbol_index_test.cljk    # CHECKS<TAB>n / FAILED<TAB>n
```

fixture tree を tmp に作り、script を子プロセスで実行して exit code と `REFUSE`
の文言を pin する。8 問 (verification-discipline) の Q1/Q2/Q4/Q5/Q6/Q7 に対応。

## 挙動

- 走査対象: `.cljk` `.cljc` `.cljs` `.clj` `.kotoba` (4 MB 未満の file)
- symlink な checkout (west の子 repo 等) も statSync で指先を辿る。
  visited set (realpath) で symlink loop を断つ。
- Node Stats の `isFile`/`isDirectory` は method — `(.-isFile stat)` は cljs では
  関数が返るだけで真偽にならない。この罠の実装例は src の walk を参照。
- 走査しないもの: linked worktree (`.git` file が `/worktrees/` を指す dir)、
  top 直下で gitignore され `.git` を持たない dir (生成物)。名前でなく構造で判定。
  symlink は realpath で 1 回だけ数え、path も realpath 相対で報告する。
- 索引する形: 行頭の def form + 名前の前の metadata 読み飛ばし (複数行の
  `^{:doc …}` も) + 行頭 `#?(:clj (defn` + indent ≤3 (nested、`~` 印)。indent 4+ は
  取らない。行番号は `(def` のある行。
- 読めない dir (権限 / 異常な名前) は crash せず `UNREADABLE-DIRS` に数える。
- 走査は BFS。group (repo 直下 2 段 / repo 外は 4 段) 内で source を持たない dir が
  1,000 個続いたらその group の残りを歩かず、`PRUNED` と header `pruned-groups` に
  名前を残す (`status` で見える)。`pyvenv.cfg` を持つ dir は virtualenv として歩かない。
- 拒否は fail-closed: 無引数 / 未知 subcommand / 欠 term / 不在 symbol / 索引の
  top 不一致 / 空索引 / 旧 JSON 形式は `REFUSE\t<理由>` を印字して **exit 2**。
  hit は exit 0、測って 0 件は exit 1。

## 前提

- 実行 host: `kbb --backend sci` (本命) / `nbb` / babashka。Node の `fs`/`path`
  を require する。JVM 不要。
- superproject (west / submodule) 配下でも、root の `git grep` が子 repo を
  引けない (gitlink) ことの代替として機能する。

## Co-Scientist 手法 (この数値の取り方)

この repo の数値は 2026-09-15 の Co-Scientist iteration (観測 → 仮説 → 実測 →
着地 → 反証) で出した。再現手順:

1. **観測**: agent log (767 API call) を 1 call ごとに token / cache hit /
   upstream latency で集計。file read を伴う query の token 分布を取る。
2. **仮説**: 「code 理解の cost は file 全文 read に支配されている」
3. **実測 (A/B)**:
   - A: 実運用で起きた full-file read の token 数を 1 query ごとに平均
   - B: 同じ symbol を `find` + 前後 3 行 snippet で引いたときの token 数
   - 同一 corpus・同一 query 意図で比較 (p50 も併記)
4. **着地**: 差が測定値として確定してから tool を着地する。推定値は書かない。
5. **反証**: 「入力が無いとき 0 を返す」「実行できないとき pass を返す」
   自己検査を fail-closed で挟む (無引数 / 未知 cmd / 不在 symbol → exit 2)。

実測は iteration ごとに上書きではなく**追記**する。数値の横に測定日を置く。
正本は `measurements.edn` (1 entry = 1 仮説、`:before` / `:after` / `:verdict`)。

iteration 2 で足した反証の型: **壊したコピーで test が落ちることを確かめてから
landed とする**。落ちない test は劇場。壊した経路の check だけが落ちることまで見る。

## 関連

- kotoba-lang/amu — `.kotoba` compiler
- orgs/kotoba-lang/org-babashka-nbb (kbb engine)
