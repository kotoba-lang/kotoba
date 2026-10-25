# 機・mon・Cell の native 統合 gate

Status: implementation inventory / acceptance contract。2026-10-23 の main source 照合。
**hata の native component は未実装・未認定**。過去の CLJC/KBB 実測は履歴であり、
canonical Kotoba + Amu selfhost の build / 実行の代わりにはしない。
追跡: [AWAI-22](https://linear.app/kotobalabs/issue/AWAI-22)、[AWAI-30](https://linear.app/kotobalabs/issue/AWAI-30)。

## 全体への接続

[Awai Network ADR 0011](https://github.com/network-awai/network-awai-apex/blob/main/docs/adr/0011-awai-network-as-a-kotoba-lisp-machine-network.md)
の全体構造では、hata は **conductor** を担う。Itonami node の OCI launcher、
tsukasa の node 状態、Murakumo/sahai の placement、kototama の宿とは別の契約で接続する。

- **mon = DNA に近い網の定義**。owner は abi `spec/mon-v1.edn`。
  rule Form、schema、properties、network seed、membrane が mon CID を決め、logic Form は入らない。
- **Cell = mon CID × agent 公開鍵 identity**。一つの machine と署名履歴の単位。
  node ID、runtime class、OCI digest、role 名を代わりにしない。秘密鍵は identity 値ではない。
- **ito = Cell の source chain、nuno = per-mon の検証・複製網**。
  private entry は公開 op に含めず、unresolved を invalid/valid と混ぜない。
- 配置先が変わっても同じ mon + agent は同じ Cell。writer fence と検証済み head が要る。
  同じ mon の別 agent は別 Cell、mon の変更は明示 migration。
- L5 `:kotoba.app/cells` / install-lock `:cells` は role → DNA/mon 参照の宣言。
  現行 hata bundle が読む `:kotoba.app/roles`（`:mon` / `:logic`）との正規化 seam は未接続。
  二つを別々の権威 manifest として増設せず、所有 schema/codec で照合する。
  DNA bundle CID と mon CID の意味が違う場合は推測で置換しない。

## 移す component の全範囲

次を各 public export と transitive dependencies ごと canonical `.kotoba` へ移す。
純粋な二値判定を追加するだけでは、この component の port 完了ではない。

| source namespace | 現行 public API / 値 | 閉じる接続 |
|---|---|---|
| `hata.ito` | action-kinds、entry-cid、problems、append、diverged? | canonical action bytes、署名・CID、head、close、fork証拠 |
| `hata.cell` | open、append | abi mon schema、agent binding、membrane、ito |
| `hata.receipt` | receipt-v1-required/forbidden、authority-decision-keys、problems、acceptable? | 現行kototama receipt spec、型・値・権限の検査 |
| `hata.bundle` | problems、read-bundle | L5/roles正規化、CAR、全role/mon/logic/UIのCID検証 |
| `hata.conductor` | resident、start-cell!、record!、execute、open-bundle!、run-logic! | 明示state遷移、grant、宿の実行、receipt、履歴。atom/swap!を移植しない |
| `hata.call` | call-kinds、call-op-keys、problems、prepare、admit、entry | Cell identityのcodec、interface DefCID、rule+grant、署名action、dispatch |
| `hata.didkey` | did-key-bytes、did-key-pubkey、did-key->ipns-name、pubkey->did-key | strict did:key/multicodec、multiformats、IPNS、Ed25519 |
| `hata.ui` | content-types、ui-entry、serve-plan | 検証済み静的UI、origin分離、共有browser broker。request-time app logicなし |

現行 `src/hata/*.cljc`、`bin/*.cljk`、tests は移行入力。唯一の
`examples/itonami-hello/logic.kotoba` は app logic であって conductor ではない。
暗号/CID/membrane/authority/VM は各 owner が提供し、app caller が「検証済み」と自己申告した
bool や callback だけで信頼境界を越えない。native linker/codec/provider が不足すれば実診断と
source lock を AWAI-22 に記録し、hosted fallback を作らない。

## 下の土台から通す順序

1. **ABI / codec / native closure**: mon-v1 と action/Cell/receipt の正確な canonical bytes、
   strict CID/did:key、署名、全 namespace の native check / project-link / build。
   複数 role と一つの schema 正本の接続を確定する（AWAI-22、AWAI-30 D1）。
2. **Cell lifecycle**: mon + agent の binding、membrane/genesis、同じ Cell の再openで履歴を失わない。
   開始に失敗した Cell を machine state に残さず、既存 Cell も壊さない。
3. **execution / history**: authority の明示 allow → 宿で実 code → 検証した receipt →
   同じ Cell の署名 append。未許可なら宿・署名・記録を一切呼ばない。
4. **network / storage**: native TCP（JUN-292）と署名（JUN-326）を接続し、nunoで検証・op同期・
   warrantを独立peerに伝える。commitとbytesの復元はJUN-296、鍵/headはJUN-299/300を待つ。
   特定Yataverse app / domainではなくbytes protocolに依存する。
5. **service composition**: Itonami node の class/grant/OCI admission（JUN-287/288）と
   Cell identityを結び、Murakumo inference / Yataverse提供Cellをinterface pinで呼ぶ。
   writer lease/fenceで別hostへの移動と二重確定を検査。remote-callは単なるop shapeで完了としない。
6. **release qualification**: domainを使わずapp DIDからbundleを検証し、複数roleを起動、logic実行、
   receiptと履歴を確認。別operator/WANで同期・fork拒否・node喪失復元まで通す（KOTOBA-15）。

## 移植先で必須の反例

下記は**未実行の受入条件**。現行 CLJC が全て拒否するという主張ではない。

| 入力・操作 | 必要な結果 |
|---|---|
| 同じmon + Alice / Bob | 別Cell・別履歴。Bobの真正な署名でもAliceの履歴には追記不可 |
| mon-A + Alice / mon-B + Alice | 別Cell・別網。旧履歴を暗黙に流用不可 |
| 同じCellをnode-Xからnode-Yへ移す | identityは不変。署名headの復元とfenceなしではwriterを有効化しない |
| roleを同じCellに二重にbind / 同じCellの再open | 履歴を消さず重複genesisを作らない |
| 未知mon、空agent、membrane拒否、mon bytes不一致 | 実行Cellを作らず理由を記録 |
| 別agent / 別mon / 古いprev / 分岐 / close後のappend | 拒否、元state維持。必要なfork証拠を保持 |
| bundleの第2roleだけdigest不一致 | 一部成功を装わずinstallを拒否。first roleだけの検査にしない |
| admissionなし・deny・callerによるjudge/membrane差替え | 宿を呼ばず、署名/履歴/状態に副作用なし |
| 未解決の検証依存 | unresolved。取得後に再検証し、valid/永久invalidに短絡しない |
| 未宣言interface / remote target / capability拡大 | dispatchなし。新しい承認を要求する経路へ |
| logic-only更新 | monとCell identityを維持、旧continuationは旧DefCID、interfaceとreceiptを検査 |
| mon更新 | 明示migration。新monのgenesis/membraneと旧履歴への参照を検証 |

実施証拠には source/lock/compiler/artifact のdigest、実host/profile、positive結果、
各負の対照、行われなかったeffect、失敗理由を含める。rebuild/parity/独立peerは別gateとして記録する。
Native product entry は AWAI-64、TCP/spawn は JUN-292。これらの進行を待つ部分と
先行できる純粋なschema/状態遷移の移植を区別し、issue全体をDoneにしない。
