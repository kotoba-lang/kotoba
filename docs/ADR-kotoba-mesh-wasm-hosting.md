# ADR — KOTOBA Mesh: WASM ベース分散 hosting / network

> Status: Draft (設計提案) ／ Date: 2026-06-22 ／ Scope: kotoba superproject
>
> wasmCloud (lattice + capability provider + wadm) と Fermyon Spin / SpinKube
> (component + trigger + runtime-config) に相当する **WASM ベースの分散ホスティング
> ファブリック** を、いまある `kotoba` のクレート群の上に被せて設計する。
> 結論を先に: **ランタイム・メッシュ・配布・認可はすでに揃っている。足りないのは
> 制御面（lattice control plane）と宣言的アプリ（wadm 相当）と trigger 層だけ** で、
> これらを新規 2 クレート + server 拡張で埋める。

---

## 1. 背景 — なぜ「もう半分できている」のか

`kotoba` は最初から content-addressed 分散 DB として作られているが、その副産物として
wasmCloud / Spin が個別プロダクトとして提供する要素を、汎用プリミティブとしてすでに
内蔵している。

| 必要な要素 | wasmCloud | Spin / SpinKube | **kotoba 既存資産** |
|---|---|---|---|
| WASM 実行単位 | actor / component | component | `kotoba-runtime`（wasmtime 25 Component Model + WASI p2 + wasi-http） |
| Guest SDK / ABI | wasmCloud SDK | Spin SDK | `kotoba-guest` + WIT world `kotoba:kais@0.1.0` |
| ケイパビリティ供給 | capability provider | runtime host components | WIT host-imports: `kqe / kse / auth / llm / evm / btc / egress / chain` |
| メッシュ / 制御バス | **NATS** lattice | (k8s/CRD) | `kotoba-net`（libp2p QUIC/Noise/**gossipsub**/Kademlia + relay/dcutr/autonat） |
| アーティファクト配布 | **OCI registry** | OCI registry | `kotoba-store` + bitswap（**CID = アーティファクト**、registry 不要） |
| ID / 認可 | (なし／外部) | (なし／外部) | `kotoba-auth`（DID + CACAO depth-2 delegation, capability grant） |
| 状態ストア | KV provider | runtime KV/SQLite | `kotoba-vault`(KV/WAL) / `kotoba-datomic`(SQL/Datalog) / `kotoba-store`(blob) |
| メッセージング | messaging provider | Redis/MQTT trigger | `kotoba-kse` LiveBus + gossipsub |
| リアルタイム | (なし) | (なし) | `kotoba-rt`（per-room bus + rollback netcode） |
| 宣言的デプロイ | **wadm** manifest | spin.toml | **未実装（本 ADR の主対象）** |
| スケジューラ / 配置 | **auction** | k8s scheduler | **未実装（本 ADR の主対象）** |
| trigger / ingress | HTTP/messaging | HTTP/Redis/cron | `kotoba-server` XRPC ingress（部分的） |

つまり **L0〜L3 は完成、L4（lattice 制御面）・L5（宣言的アプリ）・L6（trigger）が
gap**。wasmCloud の NATS を libp2p gossipsub に、OCI registry を CID/bitswap に
置き換えた上で、wadm 相当の reconciler を datom-native に作るのが本設計の核。

---

## 2. 設計原則（kotoba 不変条件の継承）

> **Prior art は 3 系統から取る（出自を明示）。** 制御面 = **wasmCloud**（lattice /
> auction / link definition）、component・trigger・DX = **Spin**（WASI 0.2 純コンポーネント
> + 宣言的 trigger + 単一アプリ deploy）、エージェンシ（agent 主権・cap・検証 DHT）=
> **Holochain**。kotoba は元々 Holochain を `kotoba-dht`（Source Chain / Warrant /
> Neighborhood）でデータ層に取り込んでおり、no-central-master という一点で
> **wasmCloud の分散モデルが Holochain と同じ哲学**になる。Spin / SpinKube の分散は
> k8s 制御面に依存する＝中央管理前提で、この不変条件と衝突するため**ネットワーク制御面
> の参照には採らない**（DX 表層のみ借用する）。詳細な選定理由は §14。

1. **No central master.** lattice は self-forming。スケジューラは中央キューではなく
   gossipsub 上の **auction**（各ノードが入札）。CLAUDE.md の no-central-master 不変条件
   と整合（relay も「ピア」、discovery は Kademlia）。
2. **Content-addressed everything.** component artifact・config・manifest はすべて CID。
   「どの component を動かすか」= 「どの CID を実体化するか」。registry も image tag も無い。
3. **Capability-rooted authz.** component が host-import を呼べるかは、宣言した WIT world
   と **CACAO で付与された capability** の積で決まる。link（component↔provider 接続）は
   CACAO chain で署名された datom。ゼロトラストの service mesh がそのまま得られる。
4. **Datom is the source of truth.** desired state（どのアプリをどれだけ動かすか）も
   observed state（どのノードで何が動いているか）も datom。reconciler は両者の Datalog
   差分を取って動く。manifest は EDN、内部表現は datom。
5. **Deterministic / portable.** 実行単位は Component Model。Rust/Python(componentize-py)/
   JS(jco)/Go(TinyGo)/C いずれからでも同じ world にコンパイルできる（既存実績）。

---

## 3. アーキテクチャ — レイヤ図

```
┌─ L6  Trigger / Ingress ───────────────────────────────────────────────┐
│   HTTP(wasi-http/XRPC) · KSE topic(gossipsub) · cron · datom-Δ · room  │
├─ L5  宣言的アプリ + Reconciler  ……………………………… 新規: kotoba-wadm     │
│   kotoba.app.edn → desired datoms ──diff──> AuctionRequest             │
│   observed datoms <── heartbeat                                        │
├─ L4  Lattice 制御面（gossipsub topics） ……………… 新規: kotoba-lattice  │
│   Heartbeat · Inventory · Start/Stop · PutLink · ScaleTo · Auction     │
├─ L3  ノード WASM ホスト  ………………………………………… 既存: kotoba-runtime  │
│   KotobaRuntime(Engine+ProgramStore) · world kotoba:mesh              │
│   host-imports = kqe/kse/auth/llm/evm/btc/egress/chain (+providers)    │
├─ L2  ID & Capability  …………………………………………………… 既存: kotoba-auth    │
│   DID(did:key) · CACAO depth-2 · link = 署名済み grant datom           │
├─ L1  Content 配布  ……………………………………………………… 既存: kotoba-store    │
│   component.wasm = CID · bitswap want-block · Tiered/Distributed store │
├─ L0  Transport / Mesh  ……………………………………………… 既存: kotoba-net      │
│   libp2p QUIC/Noise · gossipsub · Kademlia · relay/dcutr/autonat(NAT)  │
└───────────────────────────────────────────────────────────────────────┘
```

ノード本体 = `kotoba serve`（= wasmCloud host）。1 ノードに L0〜L3 が常駐し、L4 を喋る。
L5 reconciler は専用プロセスでなくてよく、**どのノードでも leader-less に走る**
（複数 reconciler が同じ desired datom を見て同じ auction を出す→冪等）。

---

## 4. 実行単位とコンポーネントモデル

### 4.1 新 WIT world: `kotoba:mesh`

既存 `kotoba-node`（`kotoba:kais@0.1.0`）を component 配備のメタモデルとして拡張する。
変更は **import の追加と export 契約の標準化** のみで、既存 guest は壊さない。

```wit
package kotoba:mesh@0.1.0;
// 既存 host-import をそのまま継承
use kotoba:kais/{kqe, kse, auth, llm, evm, btc, egress, chain};

world kotoba-component {
    // ── ケイパビリティ（host が供給・CACAO で gate） ──
    import kotoba:kais/kqe;        // datom KV/Datalog（= wasmCloud keyvalue）
    import kotoba:kais/kse;        // pub/sub（= messaging provider）
    import kotoba:kais/auth;       // DID / CACAO
    import kotoba:kais/egress;     // 送信 HTTP（= httpclient provider）
    import kotoba:kais/llm;        // 推論
    import kotoba:kais/chain;      // source chain append
    import wasi:http/outgoing-handler@0.2.0;

    // ── trigger ハンドラ（component が export、host が呼ぶ） ──
    export run:    func(ctx-cbor: list<u8>) -> result<list<u8>, string>;   // 汎用 invoke（既存）
    export on-http: func(req-cbor: list<u8>) -> result<list<u8>, string>;  // HTTP trigger
    export on-kse:  func(topic: string, payload: list<u8>) -> result<_, string>; // topic trigger
    export on-tick: func(epoch-ms: u64) -> result<_, string>;             // cron trigger
}
```

> 既存 `kotoba-node` world はそのまま「run のみ」の最小プロファイルとして残し、
> `kotoba-component` を superset とする。component メタデータが宣言した trigger 種別に
> 応じて、host は必要な export だけを呼ぶ（未 export はその trigger に bind 不可）。

### 4.2 component ディスクリプタ（CID で参照される datom 群）

```clojure
;; CID(component.wasm) = bafy...    ← bitswap で配布される実体
{:kotoba.component/cid      "bafy…wasm"      ; アーティファクト CID（= image）
 :kotoba.component/world    "kotoba:mesh/kotoba-component"
 :kotoba.component/requires #{:cap/kqe :cap/kse :cap/egress}  ; 必要 host-import
 :kotoba.component/triggers #{:http :kse}                      ; export している trigger
 :kotoba.component/limits   {:gas 1000000 :mem-mb 64 :epoch-ms 5000}
 :kotoba.component/labels   {:zone "jp" :tier "edge"}}         ; 配置制約のヒント
```

`:requires` が world の import 集合を超えていたら deploy を拒否（静的検証）。host は
`:requires` ∩「CACAO で実際に grant された cap」だけを linker に束ねる（4.4）。

---

## 5. Capability provider と link（service mesh 部分）

wasmCloud の **link definition** に相当するものを CACAO-native に作る。これが「spinnetwork」
的な部分 — component 間 / component↔provider を**能力ベースのゼロトラスト網**で繋ぐ。

### 5.1 2 種の provider
- **in-proc host-import**: `kqe/kse/auth/egress/llm/evm/btc/chain`。すでに `kotoba-runtime`
  の linker に実装済み。gas 課金つき。stateless・低レイテンシ。
- **out-of-proc provider**: 重い／プロセス分離したい IO（専用 KV シャード、外部 SQL、
  GPU 推論ノード）。component からは同じ WIT interface に見えるが、host が裏で **wRPC 相当
  = libp2p request-response（kotoba-vm の Invoke/Result ChainEntry）** で別ノードへ転送する。

### 5.2 link = 署名された grant datom

```clojure
{:kotoba.link/source   "did:key:zComponentA"     ; 呼ぶ側 component の DID
 :kotoba.link/target   :cap/kqe                   ; interface もしくは provider DID
 :kotoba.link/config   "bafy…linkcfg"             ; 接続設定 CID（endpoint, namespace…）
 :kotoba.link/cacao    "bafy…cacao"               ; depth-2 delegation chain（署名）
 :kotoba.link/ability  "datom:read"}              ; 許す ability
```

> **Holochain cap grant/claim との等価性**: この link モデルは Holochain の
> capability grant/claim とほぼ 1:1。`:kotoba.link/cacao`（署名済み delegation）= Holochain の
> **cap grant**、invoke 時の `auth.has-capability` 検証 = **cap claim** の照合に対応する。
> wasmCloud の link definition（actor↔provider の遅延束縛）と Holochain cap が、CACAO という
> 一つの暗号プリミティブで同時に表現できるのが kotoba の利点。

呼び出し時、host は `auth.has-capability(resource, ability)` を CACAO chain で検証してから
host-import を通す。**link が無い import は実行時に拒否**（宣言だけでは通らない）。これにより
「どの component がどの能力に到達できるか」が暗号学的に証明可能な mesh policy になる。
クロスノード release は X-Road 式アカウンタビリティ（署名+受領+anchored audit、
docs/SECURITY-ARCHITECTURE.md）に乗る。

---

## 6. Lattice 制御面（新クレート `kotoba-lattice`）

NATS の代わりに **gossipsub の予約トピック空間** で制御する。すべて CBOR + 署名付き。

| topic | message | 方向 | 用途 |
|---|---|---|---|
| `kotoba/lat/heartbeat` | `Heartbeat{node_did, labels, free_gas, hosted:[cid…], lat_ms}` | node→all | 在庫・生存・配置入札材料 |
| `kotoba/lat/inventory` | `InventoryReq / InventoryAck` | any | 現状観測（observed state 構築） |
| `kotoba/lat/cmd` | `StartComponent{cid, count, link_set} / Stop{instance} / ScaleTo{cid,n}` | ctrl→node | 配備指示 |
| `kotoba/lat/link` | `PutLink{link-datom} / DelLink{id}` | ctrl→node | mesh policy 更新 |
| `kotoba/lat/auction` | `AuctionReq{cid, constraints, n} / Bid{node_did, score} / Award{node_did}` | 双方向 | **配置決定** |

### 6.1 配置 = auction（中央スケジューラを置かない）

1. reconciler が「component X を +3 instance 必要」と判断 → `AuctionReq` を publish。
2. 制約（labels / `:requires` cap を供給可能か / free_gas / mem）を満たすノードだけが
   自分のスコア（余剰資源・近接・spread ペナルティ）を計算して `Bid`。
3. reconciler は上位 N をローカルに決定的に選び `Award` → 当選ノードへ `StartComponent`。
4. 当選ノードは artifact CID を `want-block`（bitswap）→ ProgramStore で compile/cache
   → instance 起動 → 次の `Heartbeat` に反映。

reconciler が複数いても、同じ desired datom + 同じ Bid 集合から **同じ Award** を出す
（決定的タイブレーク = node_did 辞書順）ので、leader 選出なしで収束する。

---

## 7. 宣言的アプリ（wadm 相当・新クレート `kotoba-wadm`）

### 7.1 manifest（`kotoba.app.edn`）

```clojure
{:kotoba.app/name    "kotodama-bot"
 :kotoba.app/version "0.3.0"
 :kotoba.app/components
 [{:name "ingest"  :cid "bafy…ingestwasm"
   :scale 2 :triggers [{:type :kse :topic "kotoba/mail/in"}]
   :requires [:cap/kqe :cap/egress]}
  {:name "reply"   :cid "bafy…replywasm"
   :scale 1 :triggers [{:type :http :route "/reply"}]
   :requires [:cap/kqe :cap/llm]
   :links [{:target :cap/llm :config "bafy…gemma" :cacao "bafy…grant"}]}]
 :kotoba.app/placement {:spread :zone :require {:tier "edge"}}}
```

`kotoba app deploy kotoba.app.edn` で:
1. EDN → desired datom 群へ projection（`kotoba-edn`/`kotoba-datomic` 既存）。
2. control graph（CACAO Private、owner=operator DID）へ commit。
3. reconciler が desired vs observed(heartbeat) を Datalog で diff → 不足分を auction。

### 7.2 reconciliation loop（Datalog で記述）

```
;; 不足インスタンス = desired - observed（component 単位）
need(?cid, ?delta) :- app-component(?cid, ?want),
                      count-observed(?cid, ?have),
                      ?delta = ?want - ?have, ?delta > 0.
```

reconciler はこの `need` の各行に対し `AuctionReq` を出すだけ。観測は heartbeat で常時更新
されるので、ノード障害 → heartbeat 消失 → observed 減 → 自動 re-auction（self-healing）。

---

## 8. Trigger / ingress（`kotoba-server` 拡張）

| trigger | 実装ソース | 流れ |
|---|---|---|
| **HTTP** | `kotoba-server` XRPC + wasi-http | route → 該当 component の `on-http` を invoke |
| **KSE topic** | `kotoba-net` gossipsub subscribe | topic 受信 → 購読 component の `on-kse` |
| **cron** | server 内 tick scheduler | epoch → `on-tick`（drift 補正は datom 記録） |
| **datom-Δ** | `kotoba-query` Delta/MV | 指定パターンの新 datom → reactive invoke（既存 Δ 基盤） |
| **room / realtime** | `kotoba-rt` per-room bus | フレーム → room sim component（既に WasmComponentSim 実績） |

datom-Δ trigger は kotoba 固有の強み: 「グラフに ?s が role=admin で現れたら component を
起動」のような **データ駆動サーバレス** が SPARQL/Datalog パターンで書ける。

---

## 9. セキュリティモデル

- **サンドボックス**: WASI p2 capability ベース + per-invoke gas + epoch interruption + mem 上限。
- **host-import allowlist**: `world.imports ∩ CACAO-granted cap`。宣言だけでは到達不可。
- **link の暗号証明**: depth-2 CACAO chain、anti-replay nonce（`kotoba-auth` 既存）。
- **アーティファクト完全性**: component = CID なので改竄は別 CID = 別 component（混入不可）。
- **クロスノード release**: 目的宣言 + 署名 + 受領 + anchored audit、未受領は slashable
  （SECURITY-ARCHITECTURE.md の X-Road 方式をそのまま継承）。

---

## 10. CLI / DX

```bash
kotoba component build  ./reply         # → wasm32-wasip2 component
kotoba component push   ./reply.wasm    # → store へ put、CID を表示（= push to registry 相当）
kotoba app deploy       kotoba.app.edn  # desired state を control graph に commit
kotoba app status       kotodama-bot    # desired vs observed
kotoba app scale        reply=5
kotoba lattice ps                       # 全ノードの heartbeat/inventory
kotoba lattice inventory <node_did>
kotoba link put  --source <did> --target cap/llm --cacao <b64>
```

`wash`(wasmCloud) / `spin`(Fermyon) の CLI 体験を、CID push + EDN deploy + auction 可視化に
置き換えたもの。`kotoba serve` がそのままノード（host）。

---

## 11. wasmCloud / Spin との対比（要約）

| 観点 | wasmCloud | Spin / SpinKube | **KOTOBA Mesh** |
|---|---|---|---|
| 制御バス | NATS（要運用） | k8s API | libp2p gossipsub（既存・追加運用なし） |
| 配布 | OCI registry | OCI registry | **CID + bitswap**（registry レス） |
| 配置 | auction | k8s scheduler | **gossipsub auction**（leader-less） |
| 宣言モデル | wadm YAML | spin.toml / SpinApp CRD | **EDN → datom**（query 可能な desired/observed） |
| 認可 | 外部 | 外部 | **CACAO capability link**（mesh policy が暗号証明） |
| 状態 | KV/SQL provider | KV/SQLite | datom DB そのもの（kqe/datomic/vault） |
| 中央依存 | NATS leaf/cluster | k8s control plane | **なし**（no-central-master 不変条件） |
| 固有強み | エコシステム | k8s 親和 | **datom-Δ trigger / content-addressed / DID-native** |

---

## 12. ギャップと段階導入

**既存（変更ほぼ不要）**: L0 net, L1 store, L2 auth, L3 runtime, KSE/RT, server ingress 土台。

**新規**:
- `kotoba-lattice`（新クレート）— §6 の gossipsub 制御プロトコル + Heartbeat/Inventory/Auction。
- `kotoba-wadm`（新クレート）— §7 の manifest projection + reconciler（Datalog diff）。
- `kotoba-runtime` 拡張 — `kotoba:mesh` world、trigger export 呼び分け、out-of-proc provider stub。
- `kotoba-server` 拡張 — HTTP/cron/datom-Δ trigger を component invoke へ配線。
- `kotoba-cli` 拡張 — `component / app / lattice / link` サブコマンド。

**ロードマップ（MVP→拡張）**:
1. **M1 単一ノード host**: `kotoba:mesh` world + HTTP trigger + CID から component 起動（auction なし、手動 start）。Spin 相当の最小形。 ✅ 制御面コア実装済(`kotoba-lattice`: protocol/manifest/reconcile)
2. **M2 lattice + auction loop** ✅: ステートフル `LatticeController`（fleet TTL + tick→auction→bid→award→place + 自己修復）+ `kotoba-net::lattice` gossipsub バインディング（`subscribe_lattice`/`decode_lattice`/`impl Transport for KotobaSwarm`）。`Heartbeat/Auction/Bid/Award/StartComponent` を gossipsub に配線。
3. **M3 server 参加 + CLI + ビルド** ✅: (1) `kotoba-server::net_actor` の swarm event loop に lattice 参加（`subscribe_lattice` + 定期 Heartbeat publish + auction 自動入札）。(2) `kotoba component build`（`.clj`→ Clojure 既定で wasm component → 正準 CID）。(3) `kotoba app deploy`（EDN manifest を各 component コンパイルして content-addressed desired state に解決）/ `kotoba lattice ps`。**残り**: `StartComponent → WasmExecutor` の実行配備 + desired-state を control graph から各ノードへ。
4. **M4 wadm** ✅: (A) `kotoba-lattice::control` — desired-state を control-graph **datom** で表現（`app_to_quads`/`desired_from_quads`、wadm SSOT）。(B) `LatticeMessage::PutApp` — desired を lattice にライブ伝播、controller が `set_desired`。(C) `net_actor` で reconcile tick（auction 発行）+ close（award）+ **StartComponent → WasmExecutor 実行 → hosted 反映で収束**（artifact 不在時は bitswap 待ちで再試行）。(D) `kotoba app deploy` が content-addressed な control datoms を出力。**残り**: deploy → 稼働ノードへの datom ingest/PutApp 注入の自動化、artifact の `kotoba component push`（block store への put）。
5. **M5 link/mesh policy + out-of-proc provider** ✅: `kotoba-lattice::policy` — `LinkTable`（CACAO-rooted link = mesh authz policy）+ `authorize(source,target,ability)`（実行時 gate、escalation 拒否）+ `LinkVerifier` フック（CACAO 検証は kotoba-auth 注入、I/O-free core）+ `route_capability`（local host-import vs richest remote provider = wRPC ルーティング）。`PutLink`/`DelLink` で controller が link table 更新、`CapInvoke`/`CapResult` で wRPC（`net_actor` が provider 宛 CapInvoke を policy gate して応答、topic `kotoba/lat/cap`）。**残り**: 実行時の host-import enforcement を kotoba-runtime の `has-capability` に接続、remote capability の実行（wRPC 先での実体実行）。
6. **M6 datom-Δ trigger** ◐: `kotoba-lattice::trigger` — datom パターン(`predicate`+任意`value`)→ 起動 component のマッチャ(`delta_triggers`/`fired_by_datom`/`fired_by_batch`、batch dedup)。manifest の `{:type :datom-delta :predicate … :value …}` をパース。データ駆動サーバレスの中核を純粋・テスト可能に実装(example `mesh_delta`)。**残り**: live Δ ストリーム(kotoba-query Delta)を net_actor の datom-apply に配線し、起動は既存 StartComponent→WasmExecutor 経路を再利用。room trigger(kotoba-rt)は別途。
7. **M7 multi-export codegen** ◐: kotoba-clj の `compile_core` を複数 entry 対応に一般化（`Entry.export_name`）+ `compile_kais_mesh_component_str` が `run` に加え `(defn on-http …)` 定義時に `on-http` も export（world を `kotoba-component`(run+on-http) / `kotoba-node`(run のみ)に自動選択）。新 WIT world `kotoba-component` 追加。run+on-http の component が wasmtime でロード可能を実証(tests/mesh_component)。**残り**: `on-kse`(string,list<u8>) / `on-tick`(u64) は arity/型が異なるため別 ABI wrapper が必要。

---

## 13. 未解決論点

- **gas → 資源会計**: auction の入札スコアに使う「余剰能力」を gas 単位で正規化するか、
  実 CPU/mem を測るか（`kotoba-server::econ` / SOCIAL-CAPITAL-LEDGER と接続余地）。
- **reconciler の冪等性境界**: 同時 auction の決定的タイブレークで十分か、軽量 lease を
  control graph datom に置くか。
- **out-of-proc provider の障害透過**: libp2p request-response のタイムアウト/再試行を
  WIT result にどう写すか（既存 CALL_FOREIGN 5s timeout の流儀を踏襲）。
- **component の hot-swap**: CID 差し替え時の in-flight invoke ドレイン戦略（rt の room
  swap 実績を一般化できるか）。
- **manifest の versioning**: app datom の commit DAG をそのまま履歴/rollback に使えるか。

---

## 14. デフォルト言語 = Clojure / EDN / Datomic（`kotoba-clj`）

KOTOBA Mesh の**第一級（default）コンポーネント言語は Clojure**（`kotoba-clj` で WASM
Component にコンパイル）とする。理由は「一言語族で manifest・logic・data が揃う」こと:

| 層 | 形式 | 既存実装 |
|---|---|---|
| アプリ manifest | **EDN**（`kotoba.app.edn`） | `kotoba-edn` reader |
| component logic | **Clojure** → wasm component（`kotoba-node` world） | `kotoba-clj::component::compile_kais_component_str` |
| データモデル | **Datomic**（datom / Datalog） | `kotoba-datomic` / `kotoba-query` |
| host-import | `kqe`/`kse`/`auth`/`llm`/`chain`（Clojure builtins） | `kotoba-clj` C-5 `kqe-assert!`/`kqe-query`/`llm-infer` 済み |

つまり **manifest を書く言語＝component を書く言語＝クエリ言語が全部 Clojure/EDN/Datalog**。
Spin（Rust/JS）や wasmCloud（Rust/TinyGo）が「設定 YAML + 別言語コード + 別言語クエリ」に
分かれるのに対し、KOTOBA Mesh は **homoiconic に一貫**する。`defgraph`（langgraph DSL）が
既に動いているので、component = `defgraph` エージェント × Datom 書き込み × Pregel BSP が
end-to-end で成立している（CLAUDE.md kotoba-clj 節の実績）。

### 14.1 既定ビルド経路

`kotoba component build` は **拡張子で言語を判定し、`.clj` を既定**とする:

```
*.clj  → kotoba-clj::compile_kais_component_str(src, runtime_wit_dir)   ← default
*.rs   → cargo component build (wasm32-wasip2)                          ← opt-in
*.py   → componentize-py                                                ← opt-in
*.js   → jco componentize                                               ← opt-in
```

manifest の component 宣言は `:lang` 省略時 `:clojure`、`:src` を `.clj` ファイルにできる:

```clojure
{:name "reply" :src "reply.clj"          ; :lang 省略 = :clojure（default）
 :scale 1 :triggers [{:type :http :route "/reply"}]
 :requires [:cap/kqe :cap/llm]}
```

deploy 時に host 側 / CLI 側で `.clj` をコンパイル → 得た wasm の CID を
`:kotoba.component/cid` に確定（content-addressed なので同一 `.clj` → 同一 CID、再現可能）。

### 14.2 既定 component の最小形（Clojure）

```clojure
;; reply.clj — KOTOBA Mesh default-language component
(ns reply)
(defn run [ctx]                          ; ctx = CBOR InvokeContext（host が渡す）
  (kqe-assert! "g" "reply" "status" "ok") ; → kotoba:kais/kqe.assert-quad
  (kqe-query "status(?s) :- reply(?s)."))  ; → kotoba:kais/kqe.query（Datalog）
```

`run` が `kotoba-node` world の export にコンパイルされ、`WasmExecutor` が駆動する
（CLAUDE.md: `tests/kais_invoke.rs` で実証済みの経路）。HTTP/KSE/cron trigger を使う
component は §4.1 の `on-http`/`on-kse`/`on-tick` を追加 export する（kotoba-clj の
component export 機構を `run` 同様に拡張＝M1 のスコープ）。

### 14.3 制約（honest R0）

- kotoba-clj の言語サブセット（loops/bytes/CBOR は実装済み、C-5 で kqe builtins 済み）で
  書ける範囲が default の到達範囲。複雑な component は Rust/Py に opt-out する逃げ道を残す。
- `on-http` などの追加 export は kotoba-clj 側の component-export 拡張が前提（M1 タスク）。

---

## 15. agent-centric vs host-centric の実体化モデル（決定）

wasmCloud（host-centric: ホストは fungible 計算資源）と Holochain（agent-centric:
conductor は agent に紐づく）は実体化モデルが分岐する。kotoba はその中間にあり、
**本 ADR では次のように分離して両立させる（決定事項）**:

- **データ所有 = agent-centric.** source chain / datom は DID に署名され、所有は agent 主権。
  どのノードに置かれても所有は移らない（Holochain 流）。
- **計算ホスト = host-centric / fungible.** component を載せる lattice ノードは交換可能な
  計算資源。auction で誰のノードにでも載る（wasmCloud 流）。
- **橋渡し = CACAO link.** 「fungible なホスト」が「agent 所有のデータ/能力」へ到達するのは、
  §5 の CACAO link が許す範囲だけ。これにより host-centric な配置と agent-centric な
  主権が、暗号証明つきで安全に両立する。

実体化: lattice 上の component instance は **「DID に署名された source chain を持つ
Holochain 風 agent」として起動**する（host-centric な配置 × agent-centric な実体）。
これが本設計の中心的な決定であり、§6 auction と §5 link はこの決定の帰結。

---

*この ADR は設計提案。M1 から実装に着手済み（`kotoba-lattice` クレート = §6 lattice
プロトコル + §7 reconciler の中核）。以降のマイルストンは個別 ADR
（`90-docs/adr/<timestamp>-…`）に分割する。*
