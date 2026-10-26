# hata — 機（conductor）

2026-10-23 の統合状態: **CLJC の移行入力。canonical Kotoba / Amu selfhost による
conductor の native closure は未認定**。
[受付状態機械の Kotoba 実装と残る接続条件](docs/accountable-admission.md)
（AWAI-95）を追加した。署名・責任資格検証の後段に置く内部 component であり、
本人確認、通信、永続化、dispatch の完成とは区別する。
[C0 の Native 署名・責任資格検証と署名付き永続化](docs/authority-and-store.md)
（AWAI-96/97）を後続として追加した。CI は既存 compiler で authority を検証し、
別の固定ソースから生成する capability project 対応候補で永続化も検証する。
[Native broker 接続と固定 4/3 署名 quorum](docs/broker-and-quorum.md)
（AWAI-98）を追加。既存 host FS provider 上の有限 object adapter、永続投票と
provider fencing の実装であり、独立ホストの合意・通信・本番運用は未認定。
[mon / Cell の区別、全 public API と下から通す gate](docs/native-cell-integration.md) を参照。
Awai Network 全体では、hata は Itonami node 上または利用者 device 上の conductor を担う。
mon は網の定義、Cell は mon CID × agent 公開鍵 identity。OCI や配置 node は別の軸。
以下の KBB/Node・過去の loopback 検証コマンドは履歴であり、現在の native 受入経路ではない。

**「機」は機織りの metaphor である。** 織機そのもの —— 紋（DNA）に従って糸（source
chain）を織る、agent の常駐ランタイム。Holochain の **conductor** にあたる。名前は
amu（編む）・osaho（筬）・abi（経）・kototama（言霊）と同じ機織りの語系に並ぶ。

root ADR-2610082200（Kotoba の app 面を agent 中心にする）の P3。1 つの
principal の 1 台の device（または 1 bot）に 1 つ常駐する。

## 持つもの（ADR-2610082200 §2）

| 役割 | 実体 |
|---|---|
| agent 鍵の保管 | device 鍵（did:key、Ed25519）を預かる。署名は注入された sign-fn |
| cell の起動 | cell = 紋 CID × agent 鍵。genesis で membrane 証明を検査 |
| 糸 の記録 | 署名付き action の連鎖（hata.ito）。分岐・逆転は fail-closed |
| 布 への参加 | P4（未実装） |
| UI への局所 API | P3 後続 |
| cell 間の呼び出し・remote call | P5 形と admission の継ぎ目（`hata.call`、ADR-kotoba-lisp-machine-contract-decisions.md D5）。判定は注入した judge（rule Form + grant）。dispatch / transport（布 P4）は未実装 |

## 持たないもの

- **権限の判断（grant）** — しない。admit の判定は注入する（kotoba-lang/grant）。
- **配置（sahai）** — しない（kotoba-lang/sahai）。
- **VM の定義** — しない（kotoba-lang/kototama）。**実行は kototama の 宿
  （kototama-native / kototama-component / wasm-webcomponent）に渡す。** 1 つの
  機 が複数の 宿 を使ってよい。宿 とは別物である。
- engine・loader・provider をこの repo に積まない（kototama の hosts.md と同じ規則）。

## 形態

pure な `.cljc`。暗号・CID・実行はすべて注入（sign-fn / verify-fn / cid-fn /
host-fn / membrane-check-fn）で、この repo は決定の形だけを持つ。

    kbb -M:test

P3 合否条件 (4)「bundle CID から再構築」は実 digest（DAG-CBOR CIDv1）と実
CAR（CARv2）で測る。codec が classpath に無いと読めない別 runner に置いて
ある — CID と CAR のない「再構築できた」は測ってはいけない主張だから:

    kbb --backend sci --classpath \
      src:test:../io-ipld-car/src:../io-ipld/src:../io-multiformats/src:../bytes/src:../coll/src:../edn/src:../error/src:../hash/src:../io/src:../pprint/src:../text/src:../org-nist-sha2/src:../org-ietf-cbor/src \
      test/hata/run_rebuild.cljk

## UI への局所 API

`hata.ui/serve-plan` は bundle の UI entry と型・path を返すだけ。表示・DOM・
ネットは 宿 の仕事で、origin は 機 の loopback（app origin は static 配信のみ、
共通アーキテクチャ契約どおり）。

## loopback 通し（実 HTTP transport）

P3 合否条件 (1)(2)(3) + UI を実 HTTP（loopback）で通す実演:

    kbb --backend sci --classpath src:test:<codec paths> bin/loopback_demo.cljk

2026-10-19 実測で OPENED → RECEIPT → ITO [:open :commit] → UI-SERVED まで
全経路が通る。実 IPFS/IPNS plane だけが DNS 不通で未測定。

## 実ネットワーク harness

app DID だけで bundle を開く経路の実走査:

    kbb --backend sci --classpath src:<codec paths> bin/open_bundle.cljk \
        --app-did did:key:... [--name k51...] [--gateway https://<host>]

`--name` を省けば `hata.didkey` が app DID から IPNS name を導出する
（ed25519 鍵 → tech-ipfs-specs-ipns の pubkey->name。実測ベクタは
didkey-test）。導出できない DID は「測れなかった」で止める。

exit は 3 値（content-address の CLI と同じ規則）: 0 = 開けた、1 = 開けない
（**応答有り**の拒否、HTTP status を印字）、2 = **測れなかった**（名前解決
不通・接続不能）。測れなかったことを合格にしない。

2026-10-19 実測（導出済み name `k51qzi5...7127` で走査）:
- `kotobase.net` → `UNANSWERED ... exit 2`（A レコードが無い。yataverse.com /
  itonami.app も同じ）
- `ipfs.io` → `REFUSED 429 ... exit 1`（応答は有る。rate limit）
- `kotoba.cloud` は応答するが `PUT 405` の static origin（app origin は
  static 配信のみの契約どおり）

bytes 面の名前解決・publish plane が戻るまで実走査は exit 2 のまま。

## itonami-hello（P3 の「小さな app 1 本」）

`examples/itonami-hello/logic.kotoba` が logic の実体。実コンパイル（amu）:

    amu compile examples/itonami-hello/logic.kotoba --target wasm32-browser \
      --output logic.wasm

2026-10-19 実測: `:ok true, :target :wasm32-browser-kotoba-v1`、成果物
**307 bytes、sha256 `6f0741bc…f8a860`**、provenance / publication receipt 付き。

残る (2)「kototama 経由の receipt」の宿 側入口は `kototama-component`
`tender.component/run-effectful!`（JSON-protocol Component host = Wasmtime
micro-TCB または jco-component-host）。kbb 側 driver は
`bin/kototama_host_demo.cljk` として実装済み（下の節）。

## 実 kototama 宿 driver（P3 合否条件 2）

`bin/kototama_host_demo.cljk` が実宿（`kototama-component/native/jco-component-host.mjs`、
JSON-line protocol）を spawn して logic を動かし、receipt-v1 を gate に通して
糸 に残すところまで組んである。2026-10-19 実測の停止点:

1. `amu compile --target wasm32-browser` ✓ core wasm（sha256 `6f0741bc…`）
2. `amu compile --target wasm-component` ✗ **nbb/native route に未実装**
   （「the JVM route was removed on 2026-09-11」、docs/adr `jvm-route-removed`）
3. `wasm-tools component new` で包めはするが **world が空**（`component wit`
   → `world root {}`）。宿 は `{"type":"error","message":"component.main is not
   a function"}` で止まる（実測）

つまり (2) の最後の 1 マスは **amu の wasm-component target の port** が上流の
依存。そこが通ればこの driver の残り（receipt → 糸）はそのまま動く。

## ステータス

P3 の最小形の骨組み（糸・cell・機 の record/execute の分離）。布・UI API・
remote call・bundle 起動は未実装。合否条件（ドメイン無しで app DID だけから
bundle を開く）は後続 PR。
