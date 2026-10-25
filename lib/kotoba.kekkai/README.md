# kekkai-actor

結界 — a **zero-trust mesh-overlay coordination actor**: a Tailscale-equivalent
**control plane** built as a sealed-intelligence ⊣ independent-governor
StateGraph. It coordinates a private mesh ("tailnet") of machines — admitting
devices, publishing a deny-by-default **netmap** (who-can-reach-whom), approving
subnet/exit routes — but it is the *control plane only*: it **never carries a
packet and never pushes WireGuard config**. The nodes pull the netmap and open
their own tunnels; the append-only ledger is the tailnet's immutable zero-trust
genealogy.

Built on this workspace's
[`langgraph-clj`](https://github.com/com-junkawasaki/langgraph-clj) StateGraph
runtime — the same pattern as
[`robotaxi-actor`](../robotaxi-actor) (AR1 ⊣ SafetyGovernor),
[`vehicle-design-actor`](../vehicle-design-actor) and
[`ai-gftd-itonami`](../../gftdcojp/ai-gftd-itonami) (ops-LLM ⊣ CertGovernor).
Here it is **coord-LLM ⊣ TailnetGovernor**.

> Charter: **(G1)** coordinate → publish-netmap only, no data-plane actuation —
> the actor proposes reachability, the nodes apply it; **(G2)** machine
> approval, exit-node approval and **funnel exposure** are **always a human
> call** (high-stakes);
> **(G3)** kotoba-native — node/key/ACL/route facts are durable EAVT ground
> datoms, decisions are transient until committed; **(G4)** anti-surveillance —
> there is **no `:traffic/*` or `:user/activity` namespace**: the control plane
> authorizes *reachability*, it never logs what flows through the tunnels.

## The core contract

```
tailnet facts (node/heartbeat/user/ACL/route)
        │  ingest = durable EAVT ground datoms (observe; always on)
        ▼
   ┌──────────┐  proposal: admit /  ┌─────────────────┐
   │ coord-LLM │  netmap / approve   │ TailnetGovernor │  (independent system)
   │ (sealed)  │ ─────────────────▶ │  zero-trust      │
   └──────────┘  + cited facts       └────────┬────────┘
                            commit ◀──────────┼──────▶ hold (invalid key /
                                │                  │      unowned tag / deny-by-
                          netmap/membership    escalate    default / route hijack;
                          + genealogy              │        un-overridable)
                                                   ▼
                                          人間 admin 承認
                                     (machine & exit approval は常に人間)
```

**The actor never installs a reachability edge / admits a device / approves a
route the TailnetGovernor would reject, and never actuates the data plane.**
HARD zero-trust invariants force **hold** (a human cannot approve past an
expired/revoked node key, a self-claimed unowned tag, an un-permitted edge, or a
route hijack); a clean admission / exit node still routes to a human admin.

The Tailscale parallel runs all the way down to identity: a Tailscale node *is*
its node key. Here the actor *is* its Ed25519 key — the key-derived IPNS name is
its kotoba graph, so it **self-mints its own CACAO** (no coordination-server
auth-key, no human-handed token). See ADR-0002.

## 組織境界 — one control plane, many organizations

**一つの制御面が複数の組織を収容する。組織の境界は ACL の規約ではなく構造で守る**
（ADR-2608040100）。ACL selector は裸のトークン（`"alice"`, `"tag:server"`）なので、
2つの組織がそれぞれ独立に `tag:server` と名付けたら、単一の flat policy では
**互いの grant が一致してしまう**。これは誰かが書き忘れた rule ではなく policy 言語
そのものの形なので、grant を足しても直らない。

だから境界は grant の**外側**に置く。各ノードはちょうど1つの **tailnet**（= 1組織の
オーバーレイ）に属し、tailnet ごとに独立した policy を持ち、`acl/edge-decision` は
**grant を見る前に**組織境界を判定する。ACL が境界を越える grant を書くことはできない
——境界は policy が所有しない field の上で先に判定されるから。

```
edge-decision(plane, src, dst)
  ├ 同一 tailnet → その組織の policy の grant で判定  → :deny-by-default
  └ 異なる tailnet
      ├ 相互承認済み peering がある → その peering の :from 方向 grant で判定
      │                                                  → :peering-grant-missing
      └ 無い                                             → :cross-tailnet
```

- **`:tailnet` 未設定は wildcard ではない。** 特定の tailnet（`acl/default-tailnet`）
  に解決される。tenant plane 以前のノードは全員そこに揃うので既存の到達性は
  1ミリも変わらず、明示的に `"gftd"` に置かれたノードからは到達できない。
  「未設定＝何にでも一致」がまさにこの機構が防ぐ失敗。
- **越境には rule ではなく object が要る。** `peering` は両組織の tailnet を名指し、
  自分の directional grant を持ち、**両方が承認して初めて**有効になる
  （`acl/peering-active?`）。片方が単独で相手への経路を開くことはできず、越境 grant は
  どちらの内部 policy にも埋もれない。承認は常に人間（`:peering/approve` は
  high-stakes）。
- **route hijack 判定は tailnet 単位。** `10.0.0.0/24` は globally unique な名前では
  ないので、2組織が同じ prefix を広告するのは異常ではなく通常。global に走査すると
  2組織目の普通の RFC1918 subnet を「乗っ取り」と報告し、しかも拒否理由で1組織目に
  相手の内部アドレッシングを教えてしまう。

| op | 何をするか |
|---|---|
| `:tailnet/register` | 組織の tailnet を登録（observe） |
| `:acl/publish` | **その tailnet の** ACL を発行（`:tailnet` 省略時は default） |
| `:peering/propose` | 越境 peering を提案（`:approved-by` は空で記録される——提案者が相手の同意を書けない） |
| `:peering/approve` | **1組織分**の同意を追加。常に人間承認、両者揃って初めて有効 |

## kekkai funnel — 公開 ingress（Tailscale Funnel 相当）

NAT 内の fleet ノード上のサービスを、Cloudflare も Tailscale も使わずに**インター
ネットへ公開する**ための制御面。初用途は fleet ノード `gad` の Biscuit-gated block
service を公開ホスト名で出すこと。

```
internet ──TLS/TCP──▶ edge-1 (tag:funnel-edge, 公開 listener)
                          │  overlay (Noise), capability :funnel, port 8080 のみ
                          ▼
                        gad : block-node:8080   (NAT 内、inbound 不要)
```

funnel は**トンネルではなく grant**。「公開 DNS 名 `host` には `edge` が応答してよく、
`edge` はその接続を overlay 越しに `node` の `service`:`port` へ運んでよい」という
承認済みレコードで、制御面はそれを記録し netmap に載せるだけ。

| op | 何をするか |
|---|---|
| `:funnel/expose` | `{:node :edge :host :service :port}` を公開する。**常に人間承認**（exit node と同じ class — tailnet の片側が「インターネット全体」になる唯一の grant）。phase 0 では無効 |
| `:funnel/withdraw` | `{:host}` の公開を取り下げる。high-stakes ではない（到達性を狭めるだけ）。**鍵チェックをしない** — 鍵が漏れた/失効したノードの公開こそ即座に閉じたいので。全 phase で有効、phase 2+ で auto-commit |

TailnetGovernor の HARD 不変条件（人間でも越えられない hold）:

- target / edge ともに有効な鍵・`authorized`・active な tailnet 所属
- edge は `tag:funnel-edge` を持ち、**edge 自身の tailnet の `:tag-owners` がその所有者に認可している**
  （所有されない自己主張 tag は hold — 既存の tag-ownership モデルそのまま）
- edge と target が同じ tailnet（`:cross-tailnet`。peering は「他組織の edge にインターネットを
  転送されること」への同意ではない）
- host は正規の小文字 DNS 名（IP リテラル・wildcard・port・末尾ドット・大文字は拒否）
- host が**別の** active funnel に束縛済みでない（公開 DNS 名は global に一意なので、
  route hijack と違い plane 全体で判定。拒否理由に保持者は出さない）
- port 1–65535、service 名あり、advisor が funnel を書き換えていない、effect は `:funnel-record`

**local funnel と remote funnel**（owner 決定 2026-09-29「エッジ自身のサービスは直接配信にして」）:

| | remote funnel（edge ≠ node） | local funnel（edge = node） |
|---|---|---|
| 配信 | edge の公開 listener → overlay → NAT 内 target | ノード自身の公開 listener から直接配信、overlay を通らない |
| netmap | edge と target の両方に `:netmap/funnels` + `:funnel` edge + 相互 peer | そのノードの netmap にだけ `:netmap/funnels`（edge = node = self）。**edge も peer も足さない** — 誰にも到達性を与えない |
| governor | 上記すべて | 同じ（常に人間承認、`tag:funnel-edge` の所有も必要 — そのノードが edge だから）。組織境界は自明に満たす |

`gad` の配備がちょうど両方: `gad` は IPv6 で公開到達可能なので自分の `block-node` を
local funnel として直接配信し、同時に NAT 内の fleet ノードに対する remote funnel の edge
になる。

承認は提案時だけでなく**人間の sign-off 時にも再検閲**する（同じ host への 2 つの要求が
両方 clean で escalate され、2 つ目の承認が公開名を黙って付け替える経路を塞ぐ）。

**wire netmap（kekkai-node との契約）**: `kekkai.netmap/publish` は、その funnel の
`:funnel/edge` または `:funnel/node` であるノードの netmap にだけ、空でない場合に限り
`:netmap/funnels`（`:funnel/host` 順）を最後のキーとして載せ、`{:edge/from edge
:edge/to node :edge/capabilities [:funnel] :edge/ports [port]}` を `:netmap/edges` に
**別エントリとして**加える（ACL edge に畳み込むと port が capability 間で混ざるため）。
edge と target は互いの peer として載る。funnel に関係しないノードの netmap は
**バイト単位で以前と同一**（署名 fixture でテスト固定）。`:funnel` は `:private-http`
とは別の capability。

**charter との関係**:
- **G1** — 依然として制御面のみ。actor は listener を開かず、DNS も書かず、パケットも
  運ばない。edge ノード（`kekkai-node`）が netmap を読んで listener を開く。
- **G2** — 公開は常に人間の判断。
- **G4** — funnel grant は**到達性を認可するだけで、リクエストを一切記録しない**。
  レコードと台帳にあるのは host/edge/node/service/port と承認者だけで、クライアント
  アドレス・リクエストログ・ヒット数を入れる field がそもそも存在しない。

## Run

```bash
kbb -M:dev:run     # drive a tailnet: admit / netmap / route through the actor
kbb -M:dev:test    # the zero-trust contract + store parity + CACAO crypto
kbb -M:lint        # clj-kondo (errors fail)
```

### Signed heartbeat ingress

`kekkai.heartbeat-http` accepts only signed `:node/heartbeat` writes for nodes
already enrolled as `authorized`. The signer DID is bound to the node ID;
replayed sequences, revoked nodes, stale timestamps, malformed candidate sets,
and invalid signatures are rejected by the same actor path used by the store
tests. The server refuses non-loopback binds. Remote nodes must reach it through
a TLS-terminating reverse proxy; the service itself never accepts public HTTP.

Prepare an operator-owned EDN snapshot with an enrolled `:nodes` map and the
existing policy/tailnet data, then run:

```bash
cd /opt/kekkai
CLJ_CONFIG=/var/lib/kekkai/clj-config kbb --backend sci --classpath src \
  -m kekkai.heartbeat-http /etc/kekkai/control-plane.edn 127.0.0.1 17892
```

Each accepted heartbeat is atomically persisted to that file. The route is
`POST /v1/nodes/{node-id}/heartbeat` with `Content-Type: application/edn` and
the signed heartbeat map as EDN. The request body is capped at 16 KiB. Run the
KBB Node reconciler beside the ingress to turn each new persisted snapshot into
changed per-node signed netmaps. It publishes only for authorized nodes and
publishes a narrowed map when a node is revoked. Heartbeats never change ACLs,
admission, or routes.

#### Tailscale を使わない初回 netmap 取得

初回起動時に SSH mirror 自体へ接続できないノード向けに、登録済み DID で署名した
read-only HTTPS bootstrap を提供する。API は loopback のみで待ち受け、既存の TLS
reverse proxy から公開する。heartbeat の state snapshot と同じ authority / mirrors を
使うため、返す netmap は authority が署名した envelope と CID / epoch を node 側でも
再検証する。`authorized` node には現在の map、`revoked` node には絞り込まれた map を返す。

```clojure
;; /etc/kekkai/netmap-http.edn
{:state-file "/etc/kekkai/control-plane.edn"
 :roots ["/var/lib/kekkai/mirror-a" "ssh://naphtali/var/lib/kekkai/mirror-b"]
 :authority-spki-b64 "<pinned-authority-SPKI-base64>"
 :host "127.0.0.1"
 :port 17893}
```

```bash
CLJ_CONFIG=/var/lib/kekkai/clj-config kbb --backend sci --classpath src \
  -m kekkai.netmap-http /etc/kekkai/netmap-http.edn
```

TLS proxy は `GET /v1/nodes/{node-id}/netmap` と
`x-kekkai-issued-at` / `x-kekkai-signature` headers を loopback service に中継する。
signature は `kekkai.netmap-read.v1`, node ID, Unix timestamp を node の登録済み
Ed25519 DID seed で署名する。API は時刻幅と DID / node status を照合し、state を変更しない。
node の watcher は `:api-url` を設定するとこの経路を使い、HTTPS origin 以外では送信しない
（localhost の HTTP は開発用）。公開 HTTPS endpoint が用意されていれば、bootstrap relay や
Tailscale に依存せず最初の signed netmap を取得できる。

```clojure
;; /etc/kekkai/netmap-reconciler.edn
{:state-file "/etc/kekkai/control-plane.edn"
 :identity-file "/etc/kekkai/authority.edn" ; generated once, mode 600
 :roots ["/var/lib/kekkai/mirror-a" "ssh://naphtali/var/lib/kekkai/mirror-b"]
 :min-copies 2
 :poll-ms 1000
 :relays [{:name "jp-tyo-1" :region "jp" :host "relay.example.net"
           :port 41642 :key "<64-hex-character-public-key>"}]}
```

Run it as a long-lived service after the heartbeat snapshot exists:

```bash
CLJ_CONFIG=/var/lib/kekkai/clj-config kbb --backend sci --classpath src \
  -m kekkai.netmap-reconciler \
  /etc/kekkai/netmap-reconciler.edn --watch
```

The reconciler polls the atomically replaced snapshot, isolates mirror failures
per node, and retries until every eligible map is published. Stable snapshots
are idempotent: heartbeat timestamps alone do not advance netmap versions.
Each node then runs the `kekkai-node` Node watcher for subject
`tailnet/node-id`, pinned to the same authority SPKI, and points its resident
agent at the watched file. At least one signed relay is required so a direct
path failure has a configured fallback.

Generate the authority identity once before configuring the reconciler. The
command refuses to overwrite an existing identity, writes the private key with
mode 0600, and prints only the public authority name and SPKI pin. Keep the
identity file on the control-plane host; configure the printed SPKI value in
the netmap HTTP service and pin that same value on every node.

```bash
./run-control-plane.sh authority-keygen /etc/kekkai/authority.edn
```

### Cloudflare を使わない netmap 配布

netmap は単一 URL へ push せず、署名済み desired state として複数の独立 root に
publish できる。root はローカルディスク、共有ボリューム、object-store mount、または
`ssh://node/absolute/path` の別ホストを指定でき、いずれも信頼対象ではない。SSH root
は検証済みの host/path だけを受け入れ、block と head を remote temp file から atomic
rename する。node が固定するのは Ed25519 authority
だけで、本文は CIDv1、順序は単調増加 epoch、履歴は previous CID で識別する。同じ
epoch に異なる CID が見えた場合は多数決せず split brain として停止する。

```bash
# 2 mirror の両方へ発行。初回は identity を生成し、authority SPKI も結果に表示する
kbb -M -m kekkai.cli netmap-publish netmap.edn .kekkai/authority.edn \
  /mnt/mirror-a,/mnt/mirror-b tailnet/node-a 1

# node 側: mirror を pull し、authority/CID/signature/epoch を検証してから読む
kbb -M -m kekkai.cli netmap-pull \
  /mnt/mirror-a,/mnt/mirror-b tailnet/node-a "$KEKKAI_AUTHORITY_SPKI" 1 "" \
  /run/kekkai/netmap.signed.edn

# 常駐 node: verified mirror head を監視して同じ node-readable file を更新
kbb -M -m kekkai.cli netmap-watch \
  /mnt/mirror-a,/mnt/mirror-b tailnet/node-a "$KEKKAI_AUTHORITY_SPKI" \
  /run/kekkai/netmap.signed.edn 5000

# Murakumo fleet admission: one KBB process for all selected node IDs
kbb -M -m kekkai.status-cli status-batch kekkai-tailnet.edn node-a node-b
# => {"node-a" "authorized", "node-b" "pending"}
```

`status-batch` is a read-only membership query. It does not publish a netmap or
change admission, and a returned `"authorized"` status does not itself grant
network traffic; the signed netmap and `kekkai-node` still enforce data-plane
permissions. `netmap-publish` stores a node-verifiable Ed25519 envelope inside
the CID-addressed desired-state record. `netmap-pull` and `netmap-watch` verify
both signatures before atomically writing that envelope. Point the resident
node's `:netmap-file` at the output path and pin the same
`KEKKAI_AUTHORITY_SPKI`; its reload loop applies each higher signed version.

mutable head は discovery hint にすぎず、内容の identity ではない。ある mirror が
停止しても他方から取得でき、古い head への巻き戻しと同 epoch の上書きは発行側でも
拒否する。この経路は kotobase.net / Cloudflare を必要としない。IPNS 名は authority
key から導出して envelope に束縛されるが、この slice 自体は public DHT への publish
を要求しないため、閉域網でも同じ検証契約を使える。

Demo: register a device + heartbeat (observe → datoms) → admit a clean device
(machine approval → admin approves) → **hold** a rogue device on `:tag-not-owned
:expired-key` → publish a deny-by-default **netmap** for a laptop → exit-node
route → human sign-off → phase-0 disables decisions → prints the genealogy
ledger → swaps to DatomicStore with identical results.

## Layout

| File | Role |
|---|---|
| `src/kekkai/store.cljk` | **Store** protocol — `MemStore` ‖ `DatomicStore` (`langchain.db`, swappable to Datomic Local / kotoba-server) + append-only **tailnet genealogy ledger** |
| `src/kekkai/acl.cljk` | pure **deny-by-default ACL** evaluation (tag ownership · edge grants · reachable peers) + the **organization boundary** (`tailnet-of` · `edge-decision` · peering) — shared by governor & coord-LLM, no I/O |
| `src/kekkai/coordllm.cljk` | **coord-LLM Advisor** — `mock-advisor` ‖ `llm-advisor` (`langchain.model`); admit / netmap / route proposals |
| `src/kekkai/governor.cljk` | **TailnetGovernor** — node-key validity · tenancy (owner/tailnet coherence) · tag ownership · deny-by-default · **cross-tailnet** · route-no-hijack (per-tailnet) · peering party-check · **funnel invariants** · no-actuation · high-stakes |
| `src/kekkai/funnel.cljk` | **kekkai funnel** の純粋定義 — `tag:funnel-edge` · `:funnel` capability · 公開ホスト名の検証 · request からの spec 抽出 |
| `src/kekkai/phase.cljk` | **Phase 0→3** — observe-only → assisted → supervised (admission & exit always human) |
| `src/kekkai/operation.cljk` | **CoordinationActor** — langgraph-clj StateGraph; ingest vs assess flows |
| `src/kekkai/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR; per-actor node key) |
| `src/kekkai/desired_state.cljk` | authority 署名 + CIDv1 + epoch/previous CID + multi-mirror head + split-brain/rollback 検出 + node receipt |
| `src/kekkai/netmap_distribution.cljk` | wire netmap を共通 desired-state 契約で publish/pull |
| `src/kekkai/heartbeat_http.cljk` | loopback-only signed heartbeat API and atomic state snapshots |
| `src/kekkai/netmap_http.cljk` | loopback-only, node-DID-authenticated read-only netmap bootstrap API |
| `src/kekkai/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/kekkai/sim.cljk` | demo driver |
| `src/kekkai/query.cljk` | actor 不要の読み取り — `authorized?`（在籍）と `reachable?`（**組織境界込みの**到達可否）は別の問い |
| `test/kekkai/*_test.cljk` | zero-trust contract · **組織境界**（`tenant_test`）· **funnel**（`funnel_test`）· store parity (Mem≡Datomic) · CACAO · signed heartbeat ingress · desired-state reconciliation and HTTPS bootstrap（`desired_state_test` は JVM 専用: `ProcessBuilder`/`java.nio` を使うため kbb engine では読み込めない） |

## Tailscale → kekkai mapping

| Tailscale | kekkai |
|---|---|
| coordination server (control plane) | the `CoordinationActor` (sealed coord-LLM) |
| node key (WireGuard / machine identity) | the node's `did:key`; the actor's own key = its kotoba graph |
| machine approval | `:node/admit` → high-stakes → human admin (`interrupt-before`) |
| ACL policy (HuJSON, deny-by-default) | `kekkai.acl` over each tailnet's published `:policy` datom |
| tailnet (one org's network) | `:tailnet` — **first-class**、複数組織が1つの制御面に同居する |
| node sharing between tailnets | `:peering` — 両組織の承認が要る directional grant（Tailscale の共有より明示的） |
| netmap (peer map a node receives) | `:access/assess` → committed netmap assessment |
| subnet routes / exit nodes | `:route/advertise` (observe) → `:route/approve` (exit = human) |
| Funnel (public ingress) | `:funnel/expose` (always human) / `:funnel/withdraw` → `:netmap/funnels` + `:funnel` edge, edge ノードは `tag:funnel-edge` |
| `tailscale up` actuating WireGuard | **out of scope by charter** — the node does this, not the actor: [`kekkai-node`](https://github.com/kotoba-lang/kekkai-node) |
| auth keys / SSO-issued tokens | **none** — the actor self-mints CACAO from its own key |

## 本番バックエンド（injection）

`DatomicStore` は `langchain.db` の `:db-api` マップ（`{:q :transact! :db :pull
:entid}`）越しにしか喋らない。`langchain.db/api`（in-process）と
`langchain.kotoba-db/kotoba-api`（kotoba-server XRPC）は同じマップを実装するので、
**同じ record が backend を選ばず動く**（`store_contract_test` で保証）。

```clojure
;; actor ごとに鍵を発行し、自分の鍵由来 graph を所有 → CACAO 自己発行（ADR-0002）
(require '[kekkai.kotoba :as k] '[kekkai.cacao :as cacao] '[clojure.data.json :as json])
(def me    (cacao/load-or-create-identity! ".kekkai/identity.edn"))  ; 初回生成→永続
;; me => {:did "did:key:z6Mk…" :graph "k51qzi5uqu5d…" …}  graph = 鍵由来 IPNS = node key
(def store (k/kotoba-store {:url "https://kotobase.net"
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)
                            :identity me}))   ; graph 既定=me の鍵由来 IPNS、自己 mint

;; coord-LLM → 実LLM
(require '[langchain.model :as model] '[kekkai.operation :as op] '[kekkai.coordllm :as c])
(op/build store {:advisor (c/llm-advisor
                            (model/anthropic-model {:api-key … :http-fn … :json-write … :json-read …}))})
;; phase は context の :phase 0..3 で注入
```

不正・破損 LLM 応答は confidence 0 / noop に落ち、**TailnetGovernor が必ず
hold/escalate** する（LLM 不調が「ノード参加」「到達edge」になる経路は構造的に無い）。

## Status

設計実装 + **kotoba-server(kotobase.net) backend 配線**まで完了。runnable +
全テスト / lint clean。Store は `:db-api` 駆動で
`MemStore ≡ DatomicStore(langchain.db) ≡ kotoba-store(kotobase.net)` が同一契約。
CACAO 自己発行はオフライン検証済み（did:key `z6Mk…`・graph `k51qzi5uqu5d…`・SIWE
署名 verify・CBOR map(3)・永続 round-trip）。**live は未確認**: kotobase.net の
datomic origin が 522（Cloudflare upstream timeout）の間はサーバ側検証が走らない
（ai-gftd-itonami ADR-0002 と同じ既知状況、owner 認可は不要）。

データ面エージェントは実装された（2026-07-26、ADR-2607266500）:
[`kotoba-lang/kekkai-node`](https://github.com/kotoba-lang/kekkai-node) が
netmap を消費して peer 間の Noise IK session（[`kotoba-lang/noise`](https://github.com/kotoba-lang/noise)）
を張り、NAT hole punching と relay（DERP 相当）で経路を作り、MagicDNS を出す。
**charter は変わらない** — actor は依然パケットを運ばず、node 側があのコンポーネントで
actuate する。受け渡し形式は `:netmap/{version,tailnet,self,peers,edges,relays}` の EDN。

**netmap 発行（2026-08-06、着地）**: `kekkai.netmap` が制御面を
`:netmap/{version,tailnet,self,peers,edges,relays}` の wire netmap に射影し、
`kekkai.envelope` が Ed25519 で封をする。README はこの受け渡し形式を以前から
書いていたが、**それを産出するコードは存在しなかった** — actor は `:netmap`
制御面レコードを書き、node はファイルを読み、2 つの repo は散文だけで繋がって
いた。`kekkai-node` 側の `publisher-parity-test` が、ここで作った実 envelope を
**バイト単位で**検証している（独立に書かれた 2 実装が黙って乖離しないため）。

- **peer/edge は id 順に整列する。** netmap はバイト列として署名されるので順序は
  署名の一部。入力順を保つ射影は、同じ論理 netmap に 2 つの署名を与える
  （store 経由と手組みを突き合わせるテストが実際にこれを検出した）。
- **cross-tailnet peer は active peering があっても発行しない。** `prologue-string`
  が*発行側の* tailnet を Noise prologue に束縛するので、peering された別
  tailnet の 2 ノードは異なる prologue を導出して handshake が失敗する。
  握手できないと分かっている peer を載せるより、除外して理由を言う方がよい
  （`netmap/excluded` の `:cross-tailnet-not-carriable`）。越境を運ぶには
  prologue が peering を束縛する必要があり、それはデータ面のプロトコル変更。
- **relay はまだ制御面レコードではない**（発行時の設定値）。

残り: kotobase.net origin 復帰時の live 結合 1 回・実 LLM（一般 API key）・
AT-Protocol XRPC（lexicon）境界の配線。CI workflow は superproject 実行。
