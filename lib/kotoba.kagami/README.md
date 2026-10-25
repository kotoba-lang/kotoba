# kagami

Agent Change/Revision/Snapshot contracts, fixed-Snapshot workspaces and the
opt-in grouped publication CLI are documented in [source control](docs/source-control.md).
The existing fleet commands and west-manifest authority remain the operational
integration boundary (ADR-2610151430).

`kagami` is the **mirror** that projects **原本 (genpon)** — the pin registry
for this west-managed workspace — onto `manifest/west.yml`. If you are looking
for the `{repo → pin SHA}` book, that original is `manifest/fleet-db.edn` in
the superproject (plus append-only `fleet-db.ledger.edn`). This repository is
the projector, not the book. The filename `fleet-db.edn` is on-disk legacy;
the spoken name is genpon (ADR-2608147300).

*(旧 kotoba-fleet-vcs — 2026-07-16 rename。west.yml は原本の写し＝鏡像)*

west 後継の AI-agent フリート向け VCS レイヤ（ADR-2607160005）。この repo は
**Phase 0 — 読み取りモデル**: `manifest/west.yml`（生成物）を原本（EDN の
repo entity 集合 + append-only ledger）に import し、byte-exact な projection
round-trip と、pin SHA 直接 fetch による**並列 sync** を提供する。

west 体制の正本はまだ変えない（Phase 0 の設計制約）。pin の前進は
`fleet pin-advance`（ledger event + db 更新）→ 既存の検証済み経路
`kbb --backend sci scripts/gen-west-manifest.cljk --entry <name>` への委譲、の 2 相。

## Runtime

第一の実行経路は **nbb**（repo 運用 tooling の正、AGENTS.md 準拠）。core は
pure `.cljc`（`kagami.west` / `kagami.db` / `kagami.sync`）で、IO は
`bin/fleet.cljs` に隔離（pure planner + injected runner、`kotoba/git_adapter.cljc`
と同じ流儀）。

## Usage

```bash
# import: west.yml -> fleet-db
kbb --backend sci --classpath src bin/fleet.cljs import --west ../../manifest/west.yml --out fleet-db.edn

# check: fleet-db の projection が west.yml と byte 一致するか（Phase 0 受け入れ基準）
kbb --backend sci --classpath src bin/fleet.cljs check --west ../../manifest/west.yml --db fleet-db.edn

# 並列 sync: working set を pin で workspace に実体化（dirty は skip、west 意味論）
kbb --backend sci --classpath src bin/fleet.cljs sync --db fleet-db.edn --workspace /tmp/ws \
    --names kotoba,kotobase --jobs 8

# クエリ / 統計
kbb --backend sci --classpath src bin/fleet.cljs stats --db fleet-db.edn
kbb --backend sci --classpath src bin/fleet.cljs list --db fleet-db.edn --org kotoba-lang

# pin 前進（2 相: ledger + db 更新 → 既存 --entry 経路へ委譲）
kbb --backend sci --classpath src bin/fleet.cljs pin-advance --db fleet-db.edn --repo kotoba --new <sha>
```

`reconcile --only-repos <name,...>` absorbs pin changes or removals for the
named existing repositories and leaves unrelated projection drift untouched.
It rejects repository additions and selected repository metadata edits; use
the registration or grouped publication writer for those changes.

## Tests

（agent 提案の実例: この節見出し直下の一行は governed land-back の dogfood で追加された）


```bash
kbb --backend sci --classpath src:test run-tests.cljk
```

## Design invariants (Phase 0)

- `west/parse` → `west/emit` は generator 方言上の**全単射**（byte-exact）。
- sync planner は **pin SHA を直接 fetch** する（`fetch --depth 1 origin <sha>`）
  — tip との関係を推測しないため、shallow×pin の不整合クラスと local ancestry
  誤判定クラスがこの層に存在しない。
- dirty checkout は **skip し、決して上書きしない**（west 意味論の維持）。
- ledger は append-only（1 行 1 EDN map、monotonic `:event/seq`、
  canvas-ledger.edn と同型）。admission gate（署名・単調 sequence・上流到達性）
  は Phase 1。

## Phase 2 — identity + governed land-back

- `fleet keygen` は did:key も出力（`kagami.did`、base58btc/multicodec）。
- `fleet grant` — owner root から agent への委譲鎖（attenuation・expiry・
  linkage を `kagami.grant/verify-chain` が検証。cacao-clj と同意味論、
  CAIP-122 wire format 化は follow-up）。
- `fleet propose` — grant 保持を検証して land 提案を ledger に記録。
- `fleet govern` — quorum pre-check（不足なら merge せず abort）→ サーバ側
  マージ → k-of-n Governor 署名の canonical pin advance（`admit-quorum`:
  quorum / sequence / parent / reachability / value-advance）。
- 残: workspace manager（GC / checkpoint / best-of-N）と鍵の 1Password 移設。

## delta provenance を fleet head に折り込む（③, ADR-2607160005）

`fleet head --delta-log <ops.edn>` で **op-log head を signed fleet head に
折り込む**。head の value = H(db-hash | delta:H(op-log)) となり、**一つの署名が
manifest（fleet-db）と編集 provenance（kotoba-delta op-log）を同時に証明**する。
実測: op-log を改竄すると head verify が MISMATCH（head が provenance を証明）。
capture 常用化: PostToolUse hook（`.claude/hooks/delta-capture-post-tool.cljs`、
fail-open・opt-in）を `DELTA_CAPTURE=1 DELTA_KEY=<pem> DELTA_LOG=.claude/delta-ops.edn`
で有効化すると Edit/Write が署名 op として記録され、その `.claude/delta-ops.edn` を
`fleet head --delta-log` が折り込む。

## live backend — kotobase commit chain 永続化（ADR-2607160005）

fleet-db を EDN blob でなく **実 kotobase-peer commit chain（content-addressed・
検証可能）**に永続化。`bin/kdb.cljk persist` が fleet-db を datom 化して
`kb/commit!` で耐久 file-backed block store に append、chain head CID を pointer
に記録。`hydrate` が block store だけから fleet-db を復元、`verify` が
tamper/gapless chain 検証。実測: 1745 repos を persist→hydrate ラウンドトリップで
name+rev set 完全一致、`verify-chain` OK。block store 本体は production では
B2/R2（DataLad/B2 経路）。EDN の fleet-db は作業/cache 形として残り、chain が
durable な backing になる。

## governor 統合（既存 ops-runner と相互運用、ADR-2607141700）

fleet の quorum land-back（propose→govern→canonical 前進）を、cloud-itonami
ops-runner の audit ledger 形式に写す `kagami.governor-bridge/land->ops-receipt`。
**実測: fleet の land-back outcome を ops-runner receipt にすると、本物の
cloud-itonami.ops-runner/sign-receipt + verify-receipt が nbb 上で TRUE 検証、
status 改竄は reject**。2つの governance ループ（fleet quorum / ops-runner
verify→handler→receipt）が同型の署名 receipt で合流。ops-runner を hard
require せず plain-map receipt shape で疎結合（VCS-stack decoupling と同原則）。

## CACAO 完全整合（本物の CAIP-122、ADR-2607160005）

**cacao.core（org-chainagnostic-cacao）は既に portable .cljc で nbb 完動**
（「JVM-only」注記は古い）。移植不要で、`bin/cacao.cljk` が **本物の CAIP-122
CACAO** を mint/verify/verify-chain する（署名 seed は kagi PEM から抽出）。
fleet-native lookalike（kagami.grant）でなく実 CACAO を使える。実測: owner が
enrolled agent did に pin+land grant を mint → agent が kagami に attenuate して
sub-delegate → **CHAIN VALID（depth 2、resources 減衰、expiry 強制）**。
`grant->cacao-payload`（前述）で fleet grant と CACAO payload を橋渡し。
（さらに kotoba wasm compiler での CACAO 実行は将来の選択肢。今は nbb で完動。）

## p2p 実 HTTP transport + clone-free reachability（ADR-2607160005 P3b）

到達性を各ノードが clone で確認する代わりに、**一度確認したノードが署名した
reachability receipt を p2p で配り他ノードが信頼する**（kagami.ci receipt 型を
到達性に適用）。`fleet reach-emit` が local-git 検証後に署名 receipt を発行、
`fleet serve`（node http）が `GET /reach?repo=&pin=` / `GET /head` で配信、
`--reach peer:<url>` が receipt を HTTP 取得して署名・trust・鮮度を検証。
**実測: Node B が private club-shinshi を、壊れた GH_TOKEN かつ clone なしで
peer receipt 経由で検証 OK**、receipt 無しは WARN（偽 OK でない）。これで
「reachability の clone すら不要化」が実ネットワークで達成。

## sovereign reachability（PAT を消す、ADR-2607160005）

pin 検証で GitHub に触るのは到達性チェックだけだった。それを **fleet 自身の
materialize した commit graph（treeless clone via git/SSH）**への問い合わせに
差し替えた（`--reach local-git`、既定）。gh API も PAT も使わず、**private repo も
owner の git 権限で strict 検証**できる（実証: 壊れた GH_TOKEN でも private
club-shinshi が OK、bogus SHA は CONFIRMED unreachable）。署名・sequence・parent・
権限は既に nekko/kagami で主権的なので、これで pin 検証全体が GitHub 非依存になる
（GitHub は object transport の mirror に降格）。`--reach github` は公開 repo 用の
fallback。**item「FLEET_PIN_TOKEN 発行」は不要になった**。

## native CI（execution-receipt 型、ADR-2607160005）

- `kagami.ci`: fleet の pin 検証を **content-addressed・署名付き verification
  receipt** にする。kotobase code_graph の `put-execution-receipt!` と同型
  （verdict = **required ⊆ passed**、あちらの required-effects ⊆ granted-effects
  に対応）。cloud-itonami ops-runner パターン（verify → 署名 receipt、
  ADR-2607141700）の fleet 版。GitHub Actions の揮発ログを durable な
  attestation に置換。
- `fleet ci-verify --db --repos a,b --kagi <name> [--required a,b]`: pin 到達性
  チェックを走らせ署名 receipt を append-only ログに記録、verdict :fail で
  exit 1。receipt は IStore stream（`kagami/ci-receipts`）にも載せられる
  （delta.store と同じ substrate）。private repo も owner 認証で検証済み。
- `fleet ci-verify --gate ''name=cmd'' [--gate-timeout ms]`: 品質ゲートを
  **capability-bound（timeout budget = kototama HostCaps の analog）**で実行し、
  hinshitsu-evidence 互換の check（`{:hinshitsu/status :hinshitsu/checks}`、
  ops-runner の plain-map 疎結合原則）を署名 receipt に食わせる。実測: repo の
  テストスイートを gate に走らせ pass、`exit 3` の gate は receipt :fail + exit 1。
- 残: kototama Chicory tender での **literal WASM 封じ**（現状は timeout-bound
  subprocess）と hinshitsu.mokushi（visual diff）ゲート。（旧: pin 到達性
  チェックのみ。hinshitsu evidence schema と互換の {:name :outcome} 形）。

## 日常ドライバ化（reverse-topo: C→B→A→D）

- **C — live query backend**: `bin/query.cljk`（実 datom plane に任意 Datalog +
  canned）。多節 join（例「heavy かつ datalad」→ m365-archive）が回る。
- **B — p2p private visibility**: `kagami.objects/pack` 5-arity が private repo の
  object を **allow-set 外の peer に配らない**（Radicle visibility model）。
- **A — CI strict pin verify**: `fleet verify-pins`（CONFIRMED unreachable で
  exit 1、private が見えない :unknown は WARN）。CI は `FLEET_PIN_TOKEN`
  （org-read PAT、owner 提供）があれば private も strict、無ければ fail-open。
- **D — staged hard flip**: `fleet reconcile --enforce-orgs kotoba-lang` で
  **kotoba-lang(public) だけ legacy 書き込みを REJECT**、混在/private org は
  吸収モードのまま。全 enroll + CI strict 後に段階拡大。

## ⑯ kotobase persistence (datom plane + Datalog)

- `kagami.kdb`: fleet-db EDN read-model を **実 datom plane**（kotobase-peer
  over arrangement/chain/prolly-tree）に射影。plain-fn クエリを **Datalog**
  （`kb/query`）に置換、~500KB EDN blob を **content-addressed commit chain**
  （`kb/commit!` → CID）で永続化。EDN は ingest/transport 形として残す。
- contract test（`kdb-contract.cljk`）が datom-plane クエリ == EDN-model
  クエリを実証（kotoba-lang 1389 / cloud-itonami 58 / heavy 17 / datalad 10 /
  revision / count 全一致）+ 永続化ラウンドトリップ（transact→commit!→hydrate）。
- 実行 classpath（kotobase stack、全て pure cljc + @noble/hashes）:
  `kotobase-peer/src:arrangement/src:chain/src:datom/src:prolly-tree/src:
  io-ipld/src:io-multiformats/src:org-ietf-cbor/src`。cljs では commit!/
  hydrate が Promise を返す（caller が await）。

## Phase ⑥ — per-agent identity (hard-flip prerequisite)

- `fleet enroll --agent NAME --grant PATH --registry fleet-agents.edn` —
  各 agent セッションに専用 did:key を mint し kagi に格納、append-only の
  agent registry に scoped grant 付きで登録。共有 owner 鍵でなく**自分の鍵**で
  署名する。governance keyring（fleet-keys.edn、roots/canonical）は人間が管理、
  registry は機械管理（base-datoms/ledger 分離と同型）。
- `--registry` を渡すと pin-advance が registry の grant を keyring に merge
  （governance が衝突時に勝つ）。GitHub 側は全 agent が同一 owner token で
  push するため per-agent 区別は原理的に不可 — 署名レイヤの per-agent auth が
  hard flip の前提。実 flip（legacy 書き込み拒否）は全 session enroll 後。

## ⑰ object-plane block transfer (kotoba-git)

- `kagami.objects`: P3b の head-cid gossip に **実 object graph 転送**を追加。
  `pack db head-cid have` が `kotoba-git.log/missing-since`（プル
  ネゴシエーション primitive）で受信側が欠く object だけを算出、`unpack` が
  受信側 db に書き戻す（content-addressed なので CID 検証付き・冪等）。
- demo（`objects-demo.cljk`）: 増分 fetch A→B — B は v1 の 3 objects を保持、
  A は delta 3 objects（新 blob+tree+commit、v1 の blob は送らない）だけ送信、
  **B は v2 を再構成でき新ファイルを読める**、forged block（CID 詐称）は
  `cid mismatch` で REJECT。git-fetch の「delta だけ動く」を content-address で。
- classpath: `kotoba-git/src` + arrangement/prolly-tree/io-ipld/
  io-multiformats/org-ietf-cbor（全 pure cljc）。

## Phase 3b — fleet head gossip (p2p)

- `fleet announce --head fleet-head.edn` — P3a signed head を
  kotoba-lang/p2p ワイヤ互換の head-announce メッセージ（`{:type
  :head-announce :graph "fleet-db" :head-cid :seq :fleet-head}`）に。
- `fleet receive --msg announce.edn --keys fleet-keys.edn --state s.edn`
  — trust set（keyring roots + canonical allow）で署名検証し、seq が前進
  する時だけ adopt（monotonic、pin と同規則）。改竄・untrusted signer・
  downgrade は拒否。フリート機は GitHub を polling せず互いの fleet head を
  この gossip で学ぶ（GitHub は mirror に降格）。block-chasing（kotoba-git
  object graph 転送）は後続スライス。

## Phase 1.5 + 3a — flip staging & signed fleet head

- `fleet reconcile [--check]` — legacy 経路（gen --entry / API single-entry）の
  west.yml 書き込みを fleet-db に **attributed ledger events** として吸収。
  CI（superproject の `fleet-projection-verify.yml`）が main 上の drift を
  自動吸収し、fleet-db は lossless に保たれる（hard flip までの dual-write 吸収）。
- `fleet head [--verify]` — fleet-db 内容全体への **自己証明 signed head**
  （sha256 content hash + monotonic sequence + parent-covering、ipns.head 型）。
  これが Phase 3 の p2p head-announce（kotoba-lang/p2p、E2E 検証済み）が
  フリート機間で運ぶ record になる。P3b（実 p2p 配線・複数機 seeding）は
  JVM 側 follow-up。

## Naming

`kotoba-lang/kotoba-fleet`（lease + governor-drain + fleet-view の agent
並行実行コーディネーション基盤、ADR-2606302000）とは**別レイヤの兄弟 repo**。
あちらは「複数 agent の実行をぶつけない」係、この repo は「repo 群の
manifest / pin / sync（west 後継 VCS プレーン）」係。短名が取られているため
role suffix `-vcs` を付けた（repo naming 規約 ADR-2607102200 addendum 14）。

## Roadmap

ADR-2607160005 の Phase 1（signed pins / admission gate）→ Phase 2（agent
identity + governed land-back、既存 kotoba-fleet の governor との統合検討）
→ Phase 3（kotoba-git object plane + p2p）。
