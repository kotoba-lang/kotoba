# ADR — kotoba 言語の安全性設計まとめ直し: capability-confinement を一次原理にする

Status: **Accepted (設計まとめ直し; S0 実装済み・S1〜S5 段階導入)**
Date: 2026-06-25
Crate: `crates/kotoba-clj`（front-end 拡張）+ `kotoba-runtime` / `kotoba-lattice`（runtime 側 enforcement）
関連: `docs/ADR-clojure-wasm.md`, `docs/ADR-kotoba-word.md`, `docs/ADR-kotoba-mesh-wasm-hosting.md`, `docs/SECURITY-ARCHITECTURE.md`, `docs/ADR-sealed-cold-tier.md`

## 0. 一行で

**最安全は「強い言語」ではなく「攻撃されても何もできない実行環境」である。**
したがって kotoba の言語安全性は *ownership の強さ* ではなく **capability confinement（与えられていない資源には型レベルで手が届かない）** を一次原理に据え、それを言語層と実行層の **二重化**で達成する。

> 順位:
> ```
> 1. 能力ベース sandbox + deny-by-default + 再現可能・検証済みビルド   ← kotoba が狙う到達点(S級)
> 2. Rust 的 ownership/borrow を持つ小さな Wasm 言語                  (A級)
> 3. clj/cljs 風 syntax + safe subset + borrow checker               (B級)
> 4. linter だけで守る Clojure/CLJS                                  (最下位)
> ```
> mythos 級の敵対 agent に対して **linter の赤線は親切な看板にすぎない**。壁ごと来る相手には、そもそも壁の外に資源を置かない設計（confinement）でしか勝てない。

### 実装状況サマリ（2026-06-25）

`compile_safe_clj` は `compile_str`（legacy/ambient 経路）と別の deny-by-default プロファイルとして稼働中。
ゲート層はほぼ完成、型システム層が残務。

| 機能 | 状態 | 定理 | 場所 |
|---|---|---|---|
| Capability gate（policy 由来 import、ambient 廃止） | ✅ | T3 | `policy.rs` |
| per-cid 束縛（graph/model 単位の instance 粒度） | ✅ | T3 | `policy.rs::check_resource_targets` |
| Subset gate（eval/require/set!/defmacro/reflection/ref types 拒否） | ✅ | — | `subset.rs` |
| Effect gate（宣言 ⊇ 推移的 used、interprocedural） | ✅ | T2 | `effects.rs` |
| Effect 推論 `infer_effects` / least-privilege `minimal_policy` / over-grant linter `unused_grants` | ✅ | — | `lib.rs` / `policy.rs` |
| 監査 `embedded_capability_ifaces` / `Policy::to_edn` | ✅ | — | `lib.rs` / `policy.rs` |
| CLI `safe-build` / `safe-policy` | ✅ | — | `cli.rs` |
| literal 型チェック（numeric op に string/keyword literal を拒否） | ✅ | T-lite | `ty.rs` |
| `:memory-pages` を emit module の memory max に適用（engine が物理的に enforce、static data 超過 / wasm32 max 65536 超過は compile error） | ✅ | — | `codegen.rs` / `lib.rs` / `policy.rs` |
| 型付き HIR・`Option`/`Result`・no-nil（S1b 残） | ⬜ | — | — |
| borrow checker（S2） | ⬜ | **T1** | — |
| capability の値渡し（S4b）・signed/reproducible（S5） | ⬜ | — | — |

達成: **T2 Effect Soundness ✅ / T3 Capability Confinement ✅（instance 粒度、バイト列検証済み）**。
残: **T1 Memory Safety**（borrow checker 未）。テスト: safe-mode 約 160（`crates/kotoba-clj/tests/safe_*.rs` + `confinement_property.rs`）+ ast meta-guard + **実在の agent cell（`examples/kotoba-langgraph-echo-clj/agent.clj`）への end-to-end 統合テスト**（`safe_integration.rs`: minimal_policy → confined build → audit → per-cid deny を実コードで検証）、full suite green（39 groups）、clippy clean（default + cli）。

## 1. 背景 — kotoba の現在地

kotoba には **S級に必要な実行層の部品がすでにほぼ揃っている**。にもかかわらず、言語層（`kotoba-clj`）と import モデルが現状 **C級**に留まっており、ここが弱点になっている。

### 1.1 すでに在るもの（実行層は強い）

| 部品 | crate | 現状 | confinement への意味 |
|---|---|---|---|
| Wasm Component Model host | `kotoba-runtime` | ✅ wasmtime 22+、`kotoba:kais` WIT | sandbox 本体 |
| gas metering | `kotoba-runtime` | ✅ assert=10 / query=100 / llm=1000 / limit=10M、`gas_limit=0` 禁止 | resource confinement の一部 |
| epoch interruption | `kotoba-runtime` | ✅ | 無限ループ/CPU 枯渇への上限 |
| CACAO depth-2 委譲 + attenuation | `kotoba-auth` | ✅ leaf.cap ⊆ root.cap, leaf.graph ⊆ root.graph, depth≥3 拒否 | **capability attenuation のランタイム実装そのもの** |
| capability mesh policy (LinkTable / wRPC) | `kotoba-lattice` | ✅ | モジュール間の権限ルーティング |
| word ごとの粗い Cap | `kotoba-word` | ✅ `proc:` / `net:` / `fs:`（Ctx 経由 enforce） | coarse-grained capability の原型 |
| encrypt-at-rest cold tier | `kotoba-store` `SealedBlockStore` | ✅ AES-256-GCM、ネットワークに出るのは暗号文のみ | secret confinement |
| t-of-N custody | `kotoba-custody` | ✅ Shamir GF(2^8) + HPKE、t−1 で何も漏れない | 鍵の単一障害点排除 |
| access receipt / 監査 | `kotoba-server`, `kotoba-datomic` | ✅ who/which/what/why/when datom、署名付き | accountability（confinement が破れた時の検知） |

### 1.2 弱点（言語層と import モデルが C級）

`docs/ADR-clojure-wasm.md` の通り、`kotoba-clj` は現状:

- **値モデルが i64 一本**、静的型なし。`Option`/`Result`/所有権/borrow/effect いずれも未実装。
- host import が **ambient**。`WasmExecutor` は guest をインスタンス化するとき **`kotoba:kais` の全 import（kqe/kse/auth/llm/evm/btc/chain/egress）を無差別に bind** する。つまり `(kqe-assert! …)` や `(llm-infer …)` を書ける guest は、**宣言なしに**任意グラフへの書き込み・推論・チェーン読み取り能力を持つ。
- これは user 指摘の **ambient authority アンチパターン**そのもの。コードがどれだけ賢くても困るのと同様、**コードがどれだけ「正しく」ても、ambient に権限がある限り confinement は成立しない**。

```clojure
;; 現状の悪い設計: 権限が ambient（誰でも呼べる = 持っているのと同じ）
(kqe-assert! "graph-cid" "s" "p" obj)     ; どのグラフにでも書ける
(llm-infer model-cid prompt)              ; どのモデルでも推論できる
```

**結論: kotoba の安全性は `kotoba-clj` 本体ではなく、その前段に置く type/borrow/effect/capability checker と、後段の capability-only runtime で決まる。** 本 ADR はその二重化を定義する。

## 2. 決定 — 二重化（言語層 × 実行層）

```
Untrusted / AI-generated safe-clj
        ↓  reader (kotoba-edn 再利用)
        ↓  restricted macroexpand  … eval/dynamic var/unrestricted macro 禁止
   typed HIR
        ↓  ownership / borrow checker
        ↓  effect + capability checker   … Γ ⊢ e : T ! E  &  要求 cap ⊆ policy
   Wasm component
        ↓  import table は policy から生成（ambient import を一切張らない）
   capability-based runtime (kotoba-runtime + kotoba-lattice)
        ↓
   no graph-write / no inference / no egress / no secret  by default
```

二重化の要点は **「どちらか一方が破れても、もう一方が残る」**こと。

```
言語層 (compile_safe_clj):           実行層 (runtime):
  ownership / borrow                   Wasm sandbox
  effect system                        gas / epoch / memory quota
  capability-passing style             import table = policy 由来（ambient 排除）
  no eval / no dynamic global          CACAO depth-2 attenuation
  no hidden IO                         WASI deny-by-default（preopen のみ）
                                        SealedBlockStore / custody（secret）
                                        signed / reproducible build
```

## 3. capability-only import — kotoba 固有の核心

### 3.1 ambient import の廃止

新しいコンパイル経路 `compile_safe_clj` は、`compile_clj`（既存・互換 i64 経路）とは**別物**として追加する。

```rust
// 既存: ambient import、型なし（C級・互換用に残す）
compile_clj(src) -> Result<WasmModule, Error>

// 新規: policy 駆動、型/borrow/effect/capability checked（S級）
compile_safe_clj(src: &str, policy: &Policy) -> Result<WasmModule, Error>
```

そして **`WasmExecutor` 側の bind を policy 化する**: 現在の「全 `kotoba:kais` import を無差別 bind」をやめ、**module が policy で宣言した import だけを linker に張る**。宣言していない import は **そもそもリンクされない** → guest が `egress` を呼ぶコードを持っていても、import table に egress が無ければ **リンク時/インスタンス化時に失敗**する（実行時チェックではなく、authority が存在しない）。

> これは「ネットワーク capability がない → 外部送信できない」を、ランタイムの linker レベルで物理的に保証することに等しい。

### 3.2 host interface を capability 値に細粒度化

kotoba の既存 host interface（`kqe`/`kse`/`llm`/`evm`/`btc`/`egress`）を、**万能インターフェースの ambient import** から **scope 済み capability 値**へ落とす。原則は user の指摘どおり: **万能なものは攻撃者にも便利**。

| 現状の ambient interface | 細粒度 capability（型） | scope |
|---|---|---|
| `kqe`（全グラフ read+write） | `GraphReadCap{graph_cid}` / `GraphWriteCap{graph_cid}` | **単一グラフ**・read/write 分離 |
| `kse`（全 topic pub/sub） | `TopicPubCap{prefix}` / `TopicSubCap{pattern}` | topic prefix |
| `llm`（任意 model 推論） | `InferCap{model_cid}` | **特定 model-cid のみ** |
| `evm`/`btc`（任意 RPC） | `ChainReadCap{caip2}` | 特定チェーン read-only |
| `egress`（任意 HTTP） | `HttpEgressCap{allowlist}` | endpoint allowlist |
| secret/env | （capability 化、default 無し） | 明示授与のみ |

ここが kotoba の妙: **`GraphWriteCap{graph_cid}` は CACAO の attenuation（leaf.graph ⊆ root.graph）を型に持ち上げたもの**。CACAO は実行時にグラフ scope を絞る既存機構なので、`compile_safe_clj` の capability checker は **「この関数が要求する `GraphWriteCap` の集合 ⊆ 呼び出し元 CACAO が委譲するグラフ集合」**を静的に照合できる。実行時 attenuation と静的 capability checking が同じ束（lattice）の上で一致する。

```clojure
;; 良い設計: 権限は値として渡る。持っていないグラフには書けない。
(defn.wasm tally
  [(g    &mut GraphWriteCap)     ; ホストから明示授与された単一グラフ書き込み権
   (rows & Bytes)
   -> Result]
  {:effects #{:graph-write}}
  (kqe-assert! g "s" "p" (sum rows)))   ; g 無しでは型が付かない

;; net も同様に endpoint 限定 capability にする（万能 HttpClient ではなく）
(defn.wasm push-metric
  [(m      &mut MetricsEgressCap)  ; 特定 metrics endpoint のみ
   (metric & Metric)
   -> Result]
  {:effects #{:network}}
  (egress-post m metric))
```

```
HttpClient       ではなく  MetricsEgressCap{allow: ["https://metrics.internal/…"]}
FileSystem       ではなく  WriteOnlyLogSink
GraphStore(全部) ではなく  GraphWriteCap{graph_cid}
LLM(任意)        ではなく  InferCap{model_cid}
```

## 4. policy スキーマ（EDN）

policy は module ごとに与え、**生成 wasm が要求できる import を制限する**。既存の gas/WASI/CACAO 設定に接続する。パース可能な実例: `crates/kotoba-clj/examples/safe-policy.edn`（`Policy::parse_edn` でロード、`tests/safe_policy.rs::example_policy_edn_parses_and_gates` が doc↔code 整合を検証）。

```edn
{:exports
 [{:name "tally" :params [Bytes] :result Result}]

 ;; capability import。ここに無いものは import table に張られない（ambient 不可）。
 :imports
 {:graph-read   ["bafy…graphA"]          ; 読める graph-cid
  :graph-write  ["bafy…graphA"]          ; 書ける graph-cid（read と分離）
  :infer        []                        ; 推論可能 model-cid（空 = 不可）
  :topic-pub    []
  :egress       []                        ; HTTP allowlist（空 = deny-by-default）
  :chain-read   []
  :clock        false                     ; timing channel 抑止
  :random       false                     ; 非決定性抑止（deterministic mode）
  :secrets      []}

 ;; 実行層の quota（kotoba-runtime に渡る）
 :limits
 {:memory-pages   4
  :fuel           1000000                 ; 既存 gas accounting に接続
  :max-call-depth 128
  :max-output-bytes 65536}

 ;; supply chain
 :build
 {:deterministic true
  :signed        true
  :deps-allowlist [...]}}
```

`:imports` の各 entry が §3.2 の capability 値に 1:1 対応し、`compile_safe_clj` は **コード中で要求される capability ⊆ policy の `:imports`** を検査して落ちる。policy が空集合なら、その module は **deny-by-default**（何もできない純粋関数）になる。

## 5. effect system —— ownership より effect が重要

mythos 級を想定するなら、最重要は ownership ではなく **effect system**。所有権が防ぐのはメモリ系（use-after-free / double-free / data race / invalid aliasing）。一方 effect が防ぐのは **「いつ・どこへ・何を・secret に触れるか・非決定性・unsafe・host capability 要求」**という *権限の所在*。confinement の主役は後者。

判定の形:

```
Γ ⊢ expr : T ! Effects        この式は T を返し、Effects だけを起こす
```

```clojure
(defn.wasm parse [(input & Bytes) -> Ast] {:effects #{}} …)            ; pure
(defn.wasm save! [(g &mut GraphWriteCap) (d & Bytes) -> Result]
  {:effects #{:graph-write}} …)                                        ; write effect
(defn.wasm fetch! [(n &mut HttpEgressCap) (u Url) -> Result]
  {:effects #{:network}} …)                                            ; network effect
```

effect ラベルは単なる注釈ではなく、§3.2 の **capability 値の保持と一致しなければならない**（`:network` を起こす関数は `HttpEgressCap` を引数に持つ）。これにより effect の宣言と capability の授与が二重チェックになる。

**実装済み（S3, `crates/kotoba-clj/src/effects.rs`）**: `(defn f {:effects #{…}} …)` の effect row を **body が（直接・推移的に）実際に起こす effect と照合**し、宣言外の effect を起こす（under-declaration）と **(T2) Effect Soundness 違反**として拒否する。**interprocedural**: call graph を fixpoint で閉じ、helper 経由で effect が隠れるのを防ぐ（相互再帰も収束）。effect 語彙（`:graph-read`/`:graph-write`/`:infer`/`:auth`）外の宣言（typo）も拒否。over-declaration（使わない effect の宣言）は conservative として許可。annotation は opt-in（無宣言関数は capability gate のみ）。effect row（コードの自己申告）⇄ policy grant（caller の認可, §3.2）は同じ束を両側から記述する。`crates/kotoba-clj/tests/safe_effects.rs` 14 tests green（推移伝播・相互再帰の終端を含む）。

## 6. safe-clj の最小仕様セット

`compile_safe_clj` が受理する subset（`compile_clj` の互換 subset とは別プロファイル）。Clojure 構文に **見える**が、意味論は Rust/ML/linear 寄り。

```
言語:
  static type / no nil by default / Option / Result
  ownership / borrow / no implicit clone / no implicit boxing
  no eval / no runtime require / no dynamic var / no reflection
  restricted hygienic macro（allowlist された macro のみ展開）
  effect system / capability-passing style
メモリ:
  safe mode で raw pointer 無し / bounds-checked slice
  unsafe block は隔離 / deterministic drop / allocator quota
並行:
  Send / Sync / 共有可変は同期必須 / spawn は Send + 'static か scoped region
Wasm:
  ambient import 無し / import table は policy 由来のみ
  memory max 固定 / fuel metering / output size limit / deterministic mode
supply chain:
  lockfile / reproducible build / signed module / deps allowlist
```

**Clojure 互換は明示的に捨てる**（`eval`・unrestricted macro・dynamic var・lazy-by-default を持ったままでは confinement が穴だらけになる）。`kotoba-clj` の既存 i64 経路は互換・既存テスト用に温存し、safe profile は別 entry point として共存させる。

## 7. 望む定理（confinement を形式化）

通常の Rust 的安全性は「well-typed program はメモリ安全エラーを起こさない」を狙う。mythos 級対策では **さらに confinement** が要る。kotoba の文脈で 3 つ:

```
(T1) Memory Safety:
     well-typed safe program は use-after-free / double-free /
     data race / invalid aliasing を起こさない。

(T2) Effect Soundness:
     Γ ⊢ P : T ! E ならば、P の実行時に観測される effect は E に含まれる。

(T3) Capability Confinement:
     program P が capability set C の下で型付けされるなら、
     P の実行中に C に含まれない外部資源へアクセスすることはない。
```

kotoba 固有の接続:
- **(T3) は CACAO attenuation のコンパイル時版**。実行層では `DelegationChain::verify`（leaf.cap ⊆ root.cap, leaf.graph ⊆ root.graph）が同じ束を守る。静的(T3) ∧ 実行時 attenuation = 二重化された confinement。
  - **(T3) は emit されたバイト列で検証済み**（`crates/kotoba-clj/tests/confinement_property.rs`, 7 tests）: pure module は `kotoba:kais` import を 1 つも埋め込まない／許諾した interface 以外（`llm`/`auth` 等）は **物理的に import section に存在しない**／policy が過剰許諾でもコードが使う capability だけが emit される、を import 名のバイト走査で確認。runtime は module が宣言した import しか bind できないため「バイト列に無い」＝「その資源に手が届かない」の最強形。
- **resource confinement** は gas/epoch/memory-pages（既存）で量的に閉じる。WASI/WASIX 経由のリソース消費攻撃（arXiv:2509.11242 等）に対し、sandbox だけでなく fuel・memory・output の quota を policy で必須化する。
- **(T2)/(T3) が破れた時の検知**は access receipt + 署名付き監査（既存 R1/R2b）が担保（confinement は完全防御ではなく、破れを slashable にする accountability と二段構え）。

## 8. 安全性ランキング上の kotoba の位置

| 級 | 構成 | kotoba |
|---|---|---|
| **S** | capability Wasm + safe static lang + verified policy + deny-by-default + signed/reproducible + OS sandbox 二重化 | **本 ADR の到達目標** |
| A | Rust/Zig → Wasm（memory-safe だが unsafe/FFI/logic bug/権限ミス残存） | runtime 単体は近い |
| B | clj syntax + safe subset + borrow checker → Wasm（設計が正しければ A に接近） | safe-clj の設計目標 |
| C | Clojure/CLJS + linter + convention | safe-clj 導入前の出発点 |

**現在地（2026-06-25）: C → B/S の間。** ambient import は廃止（policy 由来 import のみ）、
deny-by-default の **capability gate（instance 粒度・T3）／subset gate／effect gate（interprocedural・T2）**
が稼働し、T3 はバイト列で検証済み。残るのは **型システム（S1b 型付き HIR）と borrow checker（S2・T1）**、
および capability の値渡し（S4b）・supply chain（S5）。すなわち「言語層 checker の欠如」と「ambient import」
という当初 2 ギャップのうち後者は解消、前者は capability/effect 軸で達成・**型/所有権軸が残務**。

## 9. 段階導入ロードマップ（既存 phase 1–5 / A–E の続き）

`kotoba-clj` の既存実装（phase 1–5、langgraph A–E、kqe/Pregel live 済み）を壊さず、safe profile を増分で積む。

| phase | 内容 | 依存 |
|---|---|---|
| **S0 ✅** | `compile_safe_clj(src, &Policy)` + policy EDN パーサ（`crates/kotoba-clj/src/policy.rs`）。コード中で使う host import を **policy に照合し、未許諾なら module を一切 emit しない**（deny-by-default）。emit される import section ⊆ 許諾 capability になるため、**module が宣言した import しか bind できない runtime は ambient authority を張れない**＝コンパイル時に confinement が成立。read/write 分離・quota floor（`fuel`/`memory-pages` > 0 必須）・policy-aware prelude（`:graph-read` 許諾時のみ `KQE_PRELUDE` をリンク）込み。**CLI 露出**: `kotoba-clj safe-build <cell.clj> --policy <p.edn>`（`--features cli`）が gate を通して confined module を emit し、埋め込まれた capability surface を報告（実例 policy `examples/safe-policy.edn`）。**監査 API**: `embedded_capability_ifaces(wasm)` が module の capability surface を返す（built module を policy に照合可能）。test: `safe_policy.rs`(25) + `safe_subset.rs`(17) + `confinement_property.rs`(8, **T3 をバイト列で検証**) + doctest green | — |
| **S1** | restricted macroexpand / safe-subset gate **✅**（`crates/kotoba-clj/src/subset.rs`）: `eval`/`read-string`/`require`/`use`/`import`/`in-ns`/`set!`/`binding`/`with-redefs`/`alter-var-root`/`resolve`/`gen-class`/`proxy`/`reify`/ユーザー `defmacro`、、**mutable reference types**（`atom`/`swap!`/`reset!`/`volatile!`/`ref`/`ref-set`/`alter`/`dosync`/`agent`/`send`/`add-watch` 等 = shared mutable state）、**ambient I/O**（`slurp`/`spit`/`print`/`println`/`pr`/`read-line`/`flush` = I/O は capability 経由のみ）、**non-determinism**（`rand`/`rand-int`/`shuffle`/`random-uuid` = `:random` capability 必要）、**ambient concurrency**（`future`/`promise`/`pmap`/`locking`）、**host interop syntax**（`(.method obj)`/`(. obj …)`/`(Class. args)`/`(new …)`/`..` = no host interop）を **deny-by-default で拒否**（legacy path は silently ignore する＝それ自体が confinement hole）。`(ns …)` の `:require`/`:import` clause も拒否、bare `(ns foo)` は許可。built-in macro allowlist（`->`/`cond`/`case`/threading）はそのまま展開。user source のみ gate（prelude は trusted）。`crates/kotoba-clj/tests/safe_subset.rs` 17 tests green。**S1b first slice ✅（literal 型チェック, `ty.rs`）**: 双方向の literal 型不一致を静的検出 —（a）numeric op（`+ - * / mod inc dec pos?…`）と numeric 比較（`< > <= >=`、`=` は除外）に **非数値 literal**（string/keyword/vector/map/set — いずれも heap handle で数値でない）、（b）string op（`str-len`/`byte-at` の string 引数）に **numeric literal**。どちらも i64 model が handle を誤演算/誤比較する silent miscompile の bug class。加えて（c）**literal-zero 除算**（`/ mod rem quot` の divisor が literal 0）は実行時 trap 確定なので静的に拒否。literal のみ判定＝false positive なし（変数は実行時不明なので素通り、inert form の中身も解析しない）。typed HIR の足場。`safe_types.rs` 26 tests green。**残り（S1b 本体）**: i64 一本 → 型付き HIR・`Option`/`Result`・no-nil | kotoba-edn reader |
| **S2** | ownership / borrow checker（safe slice、deterministic drop、no implicit clone）。(T1) を狙う | typed HIR |
| **S3 ✅** | effect system（`{:effects …}` の検査、`Γ ⊢ e:T!E`）。`effects.rs` が effect row ⊇ **推移的** used-effects を強制（call graph fixpoint、under-declaration / unknown effect 拒否、over-declaration 許可、opt-in、相互再帰収束）。**(T2) Effect Soundness の checking 達成**。**S3b（effect 推論）✅**: `infer_effects(src)` が注釈なしで各関数の推移的 effect を推論（公開 API、`safe-build` が `inferred effects:` として report）。残り（S3c）: 注釈の必須化／自動付与・capability 値保持との一致検査 | S1 |
| **S4 ✅(per-cid slice)** | **per-cid capability binding**（`policy.rs::check_resource_targets`）: リテラル resource id を policy allowlist と静的照合 → **T3 を class 粒度から instance 粒度へ**。対象: `kqe-assert!`/`kqe-retract!`(graph-write)・`kqe-get-objects`(graph-read)・`llm-infer`(infer = **model-cid 単位**)。graphA への write 許諾は graphB を許さない／modelA の推論許諾は modelB を許さない。`"*"` で any、dynamic 引数は class-level fallback。CACAO の `leaf.graph ⊆ root.graph` のコンパイル時版。`crates/kotoba-clj/tests/safe_percid.rs` 13 tests green。**least-privilege 合成（gate の逆）✅**: `minimal_policy(src)` ／ `kotoba-clj safe-policy <cell>` が cell に必要な最小 policy を合成して EDN 出力（literal は per-cid pin、dynamic は `"*"`）。不変条件: 合成 policy は必ず compile 通過（sufficiency）かつ任意 grant 除去で失敗（minimality）。`Policy::to_edn` が `parse_edn` と round-trip。`safe_minimal.rs` 8 tests green。残り（S4b）: `GraphWriteCap`/`InferCap` を**値として**引数渡し（capability-passing style）・effect↔capability 一致検査・CACAO chain との動的照合 | S3 + kotoba-auth |
| **S5** | supply chain: signed module、reproducible build、deps allowlist。OS sandbox 二重化（seccomp/gVisor/Firecracker 検討）を runtime 運用に | S0–S4 |

各 phase は「言語層を一段強くする」＋「runtime 側の policy enforcement を一段増やす」の対で進める（片側だけ進めても confinement は完成しないため）。

## 10. host 側運用原則（mythos 級前提）

```
- module ごとに isolate / 可能なら Wasm runtime + OS sandbox 二重化
- network は allowlist / filesystem は preopen のみ
- secrets は raw env に置かない（capability 化・SealedBlockStore/custody 経由）
- token は short-lived + scoped（CACAO）/ output は taint 付き
- logs は append-only（CommitDag）/ build artifact は signed
```

Wasm sandbox は強いが **絶対ではない**（CVE-2025-4609 等の sandbox escape 事例あり）。「Wasm だから安全」を禁物とし、OS sandbox との二重化を運用前提に置く。

## 11. 命名

safe profile の呼称候補（実装上は `kotoba-clj` の `safe` プロファイル / `compile_safe_clj` として導入し、別 crate 化は任意）:

- `kotoba-clj` safe profile（無難・推奨）
- "Kototama Core" / "Kototama Safe"
- "Mythos Cage"（強そうだが厨二。嫌いではない）

目指すのは **「Clojure 互換言語」ではなく「Clojure-shaped capability-safe Wasm language」**。構文は clj に見え、意味論は affine + effect + object-capability。

## 12. 禁止（本 ADR 由来）

- safe profile で **ambient host import を張る**（policy 由来 import table のみ）
- `compile_safe_clj` で **eval / dynamic var / unrestricted macro / reflection** を許す
- 万能 capability（`HttpClient` 全開・`GraphStore` 全グラフ）を guest に渡す（必ず scope 済み値に絞る）
- gas/memory/output quota 未設定での safe module 実行（既存 `gas_limit=0` 禁止を踏襲）
- 「Wasm sandbox だから OS sandbox 不要」と判断する
- 新しい host import（`HostImport` variant）を追加して **`HostImport::ALL` への追加を忘れる**。capability 監査 `embedded_capability_ifaces` は `ALL` から interface 集合を導出するため、漏れると新能力が監査から消える（silent confinement gap）。`CapClass::of` の exhaustive match と `ast::host_import_meta_tests::host_import_all_is_complete` がコンパイル時／テスト時に強制する
- 新しい EDN walker（subset/type/effect/policy 系の解析）を書くとき **inert form（`quote`/`var`/`comment`）の中身を解析する**。これらは data か compile 時に drop され実行されない（`eval` は subset で禁止済みなので code に昇格しない）ため、解析すると false positive（valid code の誤拒否・effect 誤帰属・不要 capability 要求）を生む。判定は `ast::is_inert_form` に single-source 済み — 全 walker がこれを呼ぶ（`tests/safe_quote.rs` が quote/var/comment の回帰を防ぐ）

## 13. まとめ

```
所有権     : メモリを壊させない          (T1)
borrow     : aliasing / data race を防ぐ  (T1)
effect     : 何を起こせるか制限する       (T2)
capability : そもそも攻撃対象へ手を届かせない (T3)  ← 一次原理
Wasm sandbox: 破られても外へ出にくくする
OS sandbox : runtime ごと閉じ込める
```

kotoba は **実行層（S級部品）がすでに強い**。残る仕事は、`kotoba-clj` を *capability-confinement を一次原理とする safe profile* に育て、**ambient import を policy 由来 import に置き換える**こと。それが済めば kotoba は

```
safe-clj → borrow/effect checked Wasm
  + capability-only imports
  + deny-by-default runtime
  + strict resource limits
  + separate OS sandbox
  + signed / reproducible build
```

という S級構成に到達する。`kotoba-clj` は safe-clj→Wasm の良い土台だが、**真の安全性は本体ではなく前段の checker と後段の capability runtime が決める。**

### 参考

- Capabilities-Based Security with WASI — marcokuoni.ch
- Why do AI agents complicate zero trust and NHI controls? — nhimg.org
- Exploring and Exploiting the Resource Isolation Attack Surface of WebAssembly Containers — arXiv:2509.11242
- NSA/CISA CSI: Importance of Memory-Safe Languages — nsa.gov
- CVE-2025-4609 sandbox escape — ox.security
