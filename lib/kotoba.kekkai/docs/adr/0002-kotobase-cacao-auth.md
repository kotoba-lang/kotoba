# ADR-0002: kotobase.net への認証は actor 自身が CACAO を発行する（node key = graph）

- Status: Accepted (2026-06-27)
- 関連: ADR-0001（kekkai actor）, ai-gftd-itonami ADR-0002（同型の自己発行設計・手本実装 `itonami.cacao`）, kotoba `kotoba.cacao` / kotoba-auth / kotoba-wasm（CACAO mint + DelegationChain::verify）, langchain-clj `langchain.kotoba-db`（datomic XRPC client）

## 課題

kekkai の SSoT を実 kotoba-server pod（kotobase.net、XRPC
`ai.gftd.apps.kotobase.datomic.*`）に置きたい。kotobase の datomic 端点は **CACAO**
（SIWE/EIP-4361 を Ed25519 did:key で署名し、kotoba-auth `DelegationChain::verify`
が検証）で認証する。「coordination server が auth-key を配って渡す」前提は誤りで、
**CACAO は actor 自身が発行する**。

これは kekkai のドメインと美しく一致する: Tailscale ではノードの正体は **node key**
であって、サーバ発行のアカウントではない。「鍵こそが網内の身元」というモデルを、
認証そのものに写す。

## 決定

**actor ごとに鍵を発行し、自分の did:key で CACAO を自己発行する**（`kekkai.cacao`、
JVM 実装。手本は `itonami.cacao` の byte-exact 移植）。`kotoba/write.cljs` の通り
*AUTHORITY は鍵由来 IPNS 名に対する Ed25519 署名であってサーバではない* — **各
actor の graph はその鍵そのもの**（鍵由来の IPNS 名 `k51qzi5uqu5d…`）。よって actor
は鍵を持つことで自分の graph の owner であり、depth-1 の自己 mint（iss = actor 自身
の DID = graph owner）が**構造的に authorized**。owner からの hand-off も共有 token
も coordination-server 発行の auth-key も不要。

- 鍵は **actor ごとに生成・永続**（`load-or-create-identity!`、初回生成→保存→
  再読込。秘密鍵は `.kekkai/identity.edn` で gitignore、git に絶対コミットしない）。
- `kekkai.cacao`: did:key(0xED01+base58btc → `z6Mk…`)、鍵由来 IPNS(`ipns-name` →
  `k51qzi5uqu5d…`)、SIWE/wire は `kotoba.cacao` の byte-exact 純関数を移植、署名は
  JDK Ed25519、最小 CBOR。
- `kekkai.kotoba/kotoba-store {:identity me}`: graph 既定 = me の鍵由来 IPNS、
  read grant を自己 mint。`DatomicStore` は無改造（`:db-api` map 越しにしか喋らない）。

## 帰結

- **token 配布が要らない**。actor は鍵さえ持てば自分の graph に書ける。Tailscale の
  「node key が網内 ID」と同型 — 認証レイヤまで「鍵 = 身元」で貫通。
- オフライン検証済み（`cacao_test`）: did:key `z6Mk…`・graph `k51qzi5uqu5d…`・
  SIWE 署名 verify・CBOR map(3) = {h,p,s}・永続 round-trip。
- **live は未確認**: kotobase.net の datomic origin が現在 **522（Cloudflare
  upstream timeout＝origin 不達）**でサーバ側検証が走らない（itonami ADR-0002 と
  同じ既知状況）。owner 認可は不要（actor が自分の graph の owner）— origin 復帰
  だけで通る状態。
- 破損・不正な LLM 応答が認証や参加に化ける経路は無い（confidence0 → governor が
  hold/escalate）。CACAO は認証であって authorization gate ではない — ゼロトラスト
  不変条件は TailnetGovernor が別途強制する（ADR-0001）。
