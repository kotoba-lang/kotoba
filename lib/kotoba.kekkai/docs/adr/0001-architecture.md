# ADR-0001: kekkai-actor — coord-LLM を TailnetGovernor で封じたゼロトラスト・メッシュ制御面（Tailscale 相当）

- Status: Accepted (2026-06-27)
- 関連: langgraph-clj ADR-0001 (Pregel superstep + interrupt + Datomic checkpoint), robotaxi-actor ADR-0001 (研究 VLA を SafetyGovernor で封じた知能ノード設計), ai-gftd-itonami ADR-0001 (ops-LLM⊣CertGovernor)
- 鏡像: 本 ADR は robotaxi-actor / itonami の **ネットワーク制御面版ミラー**。あちらは「研究 VLA を SafetyGovernor で封じる」「ops-LLM を CertGovernor で封じる」、こちらは「coord-LLM を TailnetGovernor で封じる」。

## 課題

Tailscale のような**私設メッシュ網（tailnet）の制御面**が欲しい — 機器を網に参加
させ、誰が誰に到達できるかの **netmap** を配り、subnet/exit 経路を承認する。だが
ここに知能（LLM/最適化器）を素朴に据えると、**ゼロトラスト不変条件を守らない**：
失効した鍵のノードを参加させ、ACL に無い到達 edge を「便利だから」と開け、所有者が
認可していない tag を主張するノードを通してしまう。モデルの目的関数に「deny-by-
default」「鍵の有効性」「tag 所有」は入っていない。

しかも制御面が**データ面まで作動**（WireGuard 設定を push）すると、誤りが即座に
トンネルとして実体化する。Tailscale が coordination server と WireGuard を分けて
いるのは偶然ではない。

したがって課題は「LLM でネットワークを運用する」ことではなく、**「提案器を信頼
境界の内側に封じ込め、大胆な調整は探索しつつ、*ゼロトラスト的に閉じた* netmap
だけを出版し、トンネルはノードに張らせる」**こと。robotaxi / itonami と同じ構図。

## 決定

### 1. coord-LLM は最下層・最低信頼の1ノードに封じ込め、直接 commit しない

coord-LLM は *proposal*（参加可否・到達 peer 集合・経路承認）のみを返す**助言者**。
出力は必ず独立した `TailnetGovernor` を通す。**単一の不変条件**:

> **coord-LLM は、TailnetGovernor が拒否する到達 edge / 参加 / 経路承認を決して
> 行わず、データ面(WireGuard)を作動させない。** actor は netmap を *出版* し、
> トンネルは各ノードが自分で張る。

### 2. TailnetGovernor がゼロトラストを強制する（独立した検閲器）

EAVT ground datoms 上の規則として、提案を独立に棄却し HOLD に落とす:

- **valid-key**: ノードは did:key を提示し、非 revoked、期限内（key-expiry > now）。
- **tag-ownership**: ノードが主張する tag は policy `tag-owners` が所有者に認可した
  ものだけ（自己 tag による特権昇格を禁止）。
- **deny-by-default**: 提案される全到達 edge は ACL grant に裏打ちされていること。
  暗黙 allow は無い。到達先も認可済み・鍵有効でなければならない。
- **no-hijack**: 経路承認は、同一 cidr が別ノードに既承認でないこと（経路乗っ取り
  禁止）。
- **no-actuation**: 提案の effect は `:netmap` 固定。データ面 push は構造的に不可。

HARD 違反は人間でも上書き不可。**機器参加（machine approval）と exit node 承認は
high-stakes** → clean でも常に人間 admin（`interrupt-before :request-approval`）。

### 3. deny-by-default ACL は純関数（`kekkai.acl`）で governor と coord-LLM が共有

policy 評価（tag 所有・edge grant・到達 peer 集合）は I/O 無しの純関数。governor が
独立に censor しつつ、mock coord-LLM も同じ規則で提案を組むので、両者が乖離しない
（itonami で mock が CertGovernor を鏡映するのと同型）。

### 4. 注入境界（swap）でコアを不変に保つ

- **Store**: `MemStore` ‖ `DatomicStore`（langchain.db `:db-api`、実 Datomic /
  kotoba pod）。`store_contract_test` が `MemStore ≡ DatomicStore` を保証。
- **Advisor**: `mock-advisor` ‖ `llm-advisor`（langchain.model）。破損応答は
  confidence0 noop → governor が必ず hold/escalate（LLM 不調が参加・到達になる
  経路は無い）。
- **Phase 0→3**: 制御面決定の自律度のみ段階化。参加・exit は常に人間。

### 5. SSoT + 系譜台帳 = ゼロトラスト監査証跡

EAVT ground datoms が canonical。append-only ledger が「誰の権限で誰を参加させ／
誰が誰に到達可能になり／鍵をいつ回したか」を不変に残す。`:traffic/*`
`:user/activity` 名前空間は**持たない** — 制御面は到達性を authorize するが、
トンネルの中身は記録しない（反監視、Wellbecoming §1.13）。

## 帰結

- **robotaxi / itonami と同じ runtime（langgraph-clj）・同じ封じ込め構図**で、別
  ドメイン（ネットワーク制御面）が載ることを実証。新ドメイン = もう一つの
  StateGraph。
- **19 tests / 66 assertions / 0 failures**、lint clean、runnable。zero-trust
  契約・store parity・CACAO crypto を executable に固定。
- WireGuard データ面（トンネルを実際に張るエージェント）は charter 外の別
  コンポーネント。本 actor との境界は「netmap の受け渡し」一点。
- kotoba-server backend と CACAO 自己発行は ADR-0002。
