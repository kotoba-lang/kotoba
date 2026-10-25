# kekkai Actor Design — coord-LLM as a contained intelligence node

ゼロトラスト・メッシュ網（Tailscale 相当の **制御面**）を扱う actor。
robotaxi（AR1⊣SafetyGovernor）/ itonami（ops-LLM⊣CertGovernor）と同型に
**coord-LLM⊣TailnetGovernor** を据え、charter（制御面専用・データ面無作動・
deny-by-default・反監視）を守る。

actor は「ネットワーク地図(netmap)を出版する」だけで、WireGuard トンネルを張る
のは各ノード。actor がパケットを運ぶことは設計上ない（Tailscale の coordination
server とデータ面 WireGuard の分離をそのまま写す）。

## 1. 二つのフロー

```
ingest(record-op):  intake → record → END                ; 観測。常時ON、無作動
assess(assess-op):  intake → advise → govern → decide → commit | hold | 人間承認
```

- **ingest**: node/heartbeat/user/acl/route を EAVT ground datom として記録
  （charter G3）。LLM/governor/phase を通らない事実記録。
- **assess**: `:node/admit` `:access/assess` `:route/approve`。coord-LLM 提案 →
  TailnetGovernor ゼロトラスト検査 → phase gate → 機器参加・exit node は必ず人間
  （`interrupt-before`）。

チャネル: `:request :context(:phase) :proposal :verdict :disposition :record :approval :audit`

## 2. 注入される依存（swap）

- **Store**（`kekkai.store/Store`）: `MemStore` ‖ `DatomicStore`（langchain.db、
  `:db-api` で実 Datomic Local / kotoba pod）。鍵失効は epoch 秒（整数）で判定。
- **Advisor**（`kekkai.coordllm/Advisor`）: `mock-advisor` ‖ `llm-advisor`
  （langchain.model）。破損応答は confidence0 noop → governor が hold/escalate。
- **Phase**（context `:phase 0..3`）: 制御面決定の自律度のみ段階化。機器参加・
  exit は常に人間。

## 3. TailnetGovernor（独立・ゼロトラスト）

LLM は node 鍵の有効性も deny-by-default も tag 所有も知らないので、EAVT 上の
規則として **独立**に提案を *棄却* し HOLD に落とせる別系統である必要がある。

HARD 不変条件（人間でも上書き不可）:

| op | HARD |
|---|---|
| `:node/admit` | **valid-key**（did:key 提示・非 revoked・期限内）/ **tag-ownership**（policy tag-owners が所有者に認可した tag のみ）/ **no-actuation**（effect=:netmap） |
| `:access/assess` | subject と全 peer の **valid-key** / **deny-by-default**（全到達 edge が grant 由来）/ **no-actuation** |
| `:route/approve` | 広告ノードの **valid-key** / **no-hijack**（同一 cidr が別ノードに承認済みでない）/ **no-actuation** |

SOFT: 確信度 floor → escalate。機器参加と exit node 承認は high-stakes → 常に人間。

単一不変条件: **actor は governor が拒否する到達edge/参加/経路承認を決して行わず、
データ面(WireGuard)を作動させない**（netmap を出版し、トンネルはノードが張る）。

## 4. deny-by-default ACL（`kekkai.acl`、純関数）

policy = `{:tag-owners {tag [user...]} :grants [{:src [sel] :dst [sel] :ports [...]}]}`。
ノードは「所有者(user) ＋ 自分の tag 群」を selector として満たす。edge src→dst は
*いずれかの* grant で src が src-selector に、dst が dst-selector に一致するときだけ
許可（暗黙 allow なし）。governor と mock coord-LLM が **同じ純関数** を使い、censor
を proposer から分離したまま同じ規則を評価する。

## 5. SSoT + 系譜台帳

EAVT ground datoms が canonical。append-only の genealogy ledger が
「いつ・どのノードを・誰の権限で参加させ／誰が誰に到達可能にしたか・鍵をいつ
回したか」を不変に残す＝ゼロトラスト監査証跡／データ主権の核。
`:traffic/*` `:user/activity` 名前空間は持たない（charter G4、制御面は到達性を
authorize するが、トンネルを流れる中身は記録しない＝反監視は型で表現）。

## 6. CACAO 自己発行（per-actor node key）

Tailscale の「ノード＝node key」をそのまま写す: actor は自分の Ed25519 鍵を生成・
永続し、その **鍵由来 IPNS 名がその actor の graph**。owner hand-off も
coordination-server 発行の auth-key も要らず、depth-1 自己 mint が構造的に authorized。
詳細は ADR-0002。

## 7. Tailscale 対応表（lexicon 候補 com.junkawasaki.kekkai.*）

| Tailscale | actor op | フロー |
|---|---|---|
| device join request | `:node/register` | ingest |
| keep-alive / endpoint | `:node/heartbeat` | ingest |
| add tailnet member | `:user/register` | ingest |
| publish ACL (HuJSON) | `:acl/publish` | ingest |
| advertise subnet/exit route | `:route/advertise` | ingest |
| machine approval | `:node/admit` | assess（人間承認） |
| receive netmap | `:access/assess` | assess |
| approve route / exit node | `:route/approve` | assess（exit=人間承認） |
