# facade の amu 適格化（JUN-133 — amu selfhost への実経路）

appview 差替えの実経路は **amu compile（guest subset）→ wasm32-browser →
browser-host.mjs（kototama-browser-host-v1）**。JS 関数の import 差替えでは
ない。このため facade の kotoba モジュールは **amu の admitted subset** を
満たす必要がある。2026-10-20 に全モジュールで `amu compile` を実測。

## 実測判定表（amu compile src/kotodama/<f>.cljk）

| モジュール | 結果 | 拒否コード |
|---|---|---|
| host_util | 拒否 | `host-regex-literal`（`#"..."` → `kotoba.lang/bounded-regex` に文字列で） |
| host_heartbeat | 拒否 | `map-literal-value`（マップ literal の汎用値） |
| host_types | 拒否 | `row-generic-export`（型無しの汎用 export） |
| host_cadence | 拒否 | `subset-reject`（`js/Math.round` 等の host interop） |
| host_model | 拒否 | `namespace-require-needs-project`（clojure.string require） |
| host_export | 拒否 | `namespace-require-needs-project`（host_util require） |
| host_lexicon | 拒否 | `namespace-require-needs-project`（clojure.string require） |

kbb テスト（9 ランナー・173 assertions）は全て緑 —— **意味の正本としての
正しさは担保済み**。未達は amu の subset 適格性。

## 適格化の方針（guest 規約に追従）

1. **型注釈必須**: `defn` は `[v :vector-i64 i :i64] :i64` 形式の
   KIR タイプ注釈を付ける（typed ホスト = amu selfhost の前提）。
2. **regex**: `#"..."` 禁止 → `kotoba.lang/bounded-regex` にパターン文字列。
3. **host interop 禁止**（js/Date, js/Math, js/JSON 等）。効果（時刻・乱数・
   JSON デコード）は **host capability** として呼び出し側（host 側）に寄せ、
   guest は純粋な判定のみを持つ:
   - 純粋（guest 化できる）: nsid 検証 / mood 表 / stress scaling /
     model resolve / schema validate / 型述語 / registry lookup
   - 効果（host capability）: now-iso / gen-id / decode-json
4. **clojure.string / 要求元モジュールの require** は project 文脈で
   `--source-path` を通すか、リポジトリ内で同一モジュールとして扱う
   （`namespace-require-needs-project` は単体 file 入力でのみの制約か要確認）。
5. 構造化返り値: マップ literal の汎用値は拒否されるため、**ベクタ・
   スカラー・キーワード・文字列（EDN/JSON 文字列化）**の語彙に寄せる。

## 適格化の進捗（2026-10-20 実測）

| モジュール | 結果 | 備考 |
|---|---|---|
| host_util | **適格**（amu test 24/24） | NSID は文字コード歩き。効果 3 つは host_effects へ |
| host_types | **適格**（33/33） | typed map フィールド検証。HostSDK 形は oracle 専用 |
| host_cadence | **適格**（30/30） | mood コード + 整数 round |
| host_model | **適格**（18/18） | レジストリ走査は oracle 残置、判定核のみ guest |
| host_lexicon | **適格**（24/24） | スキーマ走査・JSON デコードは oracle 残置 |
| host_heartbeat | **適格**（6/6） | CadenceState の i64 6 フィールドのみ guest。InboxBuffer / recentPostTypes ベクタは oracle |
| host_export | **guest 対象外**（確定） | レジストリが関数値（handler）を持つため guest ABI で表せない。host が構築し guest は判定核を呼ぶ |

guest で判明した制約（pitfall）: 多引数 and の詰め込みは fuel/trap / `:export` は public のみ /
`[:vec :string]` パラメータは safe profile 外 / `contains?` は canonical typed map のみ /
docstring の引用符はエスケープ必須 / `#"..."` と `{}` 量詞は bounded-regex でも拒否。

## 残スライス（1 run = 1 モジュール）

1. host_util: regex → bounded-regex、効果 2 つを host 側へ分離。
2. host_types: 型注釈 + 返り値をスカラー（1/0）へ。
3. host_cadence: js/Math → 手組みの round、型注釈。
4. host_model / host_lexicon: cstr 依存の除去（trim/lower-case を手組み）。
5. host_export / host_heartbeat: require 経路と map literal の解消。
6. 全モジュール amu compile 緑 → wasm32-browser でビルド →
   appview（app-itonami）から browser-host.mjs 経由で読み込み + bundle 検証。
