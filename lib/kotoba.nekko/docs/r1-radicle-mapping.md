# R1: nekko と Radicle の対応表（2026-11-18）

network-awai-apex ADR 0044 の D3 で決めた段階 R1（Radicle の形との対応）の記録。Tracking: AWAI-3194。

- Radicle 側の出所は [Radicle Protocol Guide](https://radicle.dev/guides/protocol)（2026-11-18 に取得）。Guide に書かれていない細部は「未確認」と書き、推測で埋めない。
- `rad` CLI や heartwood の実装は、この記録では動かしていない。R2（相互変換）に進むときに、使う版を記録したうえで確かめる（ADR 0044 O2）。
- **結論：nekko と Radicle は、概念はほぼ 1 対 1 で対応するが、識別子・署名の形式・保存の形式はどれも一致しない。** そのため R1 は名乗れるが、R2 と R3 はまだ名乗れない。

## 識別子とリポジトリ

| 項目 | Radicle | nekko / bonsai | 一致 |
|---|---|---|---|
| RID の作り方 | 最初の identity document を Git の `hash-object` にかけた SHA-1。multibase の base58btc で `rad:z…` と書く | genesis block `{kind "rad-identity", did, created}` を DAG-CBOR にした CIDv1（sha2-256）。`nekko.identity/genesis!` | しない。元の文書もハッシュ関数も表記も違う |
| RID は文書が変わっても同じか | 同じ（最初の文書から決まる） | 同じ（genesis から決まる） | する（性質として） |
| identity document | Canonical JSON。`refs/rad/id` にあり、`xyz.radicle.id` COB で管理する | genesis block と identity journal（`nekko.journal`、`kotoba.chain` の上の hash chain） | 概念は対応する。形式は違う |
| delegates | identity document の `delegates`（DID の一覧） | journal の `delegate-add` / `delegate-remove`（署名つき）を畳み込んだ集合。genesis の did は常に含まれる。`nekko.delegate/delegates` | 概念は対応する。表し方は違う（一覧と、イベントの畳み込み） |
| threshold | identity document の `threshold`（既定ブランチの変更に要る署名の数） | `nekko.canonical/canonical-ref` の引数 `threshold`。identity に保存しない | 部分的。nekko は呼び出し側が渡す |
| payload（name、description、defaultBranch） | `xyz.radicle.project` | なし | しない（nekko にない） |
| visibility | `private` と `allow` の一覧。保存時に暗号化しない | `nekko.recipient-grant` と `private-object`。object を受信者ごとに暗号化する | 目的は対応する。nekko の方が強い（保存時も暗号化） |
| 鍵と署名者の表し方 | Node ID（Ed25519）。DID で表す | `did:key`（Ed25519）。`ed25519.core/did-key-from-seed` | 鍵の種類は一致する。`did:key` の表記が Radicle の DID と同じになるかは未確認 |

## 参照と署名

| 項目 | Radicle | nekko / bonsai | 一致 |
|---|---|---|---|
| peer の名前空間 | `refs/namespaces/<nid>/refs/...`。object database を共有する | `nekko.ref-event` が `rad.peer-ref/[rid signer ref]` を arrangement の datom として持つ | 概念は対応する。保存の形は違う |
| sigrefs | peer の参照の集合全体を、変わるたびに署名する。`refs/rad/sigrefs` の blob に、`git show-ref` 形式の一覧と署名を置く | 参照 1 つずつの署名つき証明 `{rid ref commit ts signer sig}`（`nekko.sigref`）。因果を持つ `nekko.ref-event`（old・new・prev・seq・manifest） | しない。Radicle は集合全体、nekko は参照ごと |
| 正本の参照 | threshold 以上の delegate が署名した状態 | `canonical-ref`。threshold 以上の別々の delegate が同じ commit を署名したもの。割れたら例外 | 規則は対応する |
| Git object | Git の object database | `bonsai.git-object`。Git の SHA-1 OID と CID を橋渡しし、byte 単位で一致させる。G1 で確認した（`docs/g1-git-roundtrip-20261118.md`） | object の byte は一致する |

## 協働 object（COB）

| 項目 | Radicle | nekko（`nekko.cob`、AWAI-3194 で追加） | 一致 |
|---|---|---|---|
| 置き場所 | `refs/cobs/<type>/<object-id>` | `nekko.cob/cob-ref` が同じ形 `refs/cobs/<type>/<object-id>` の名前を作り、peer は tip を sigref で公開する | 名前の形は一致する。中身（Git commit か CBOR block か）は違う |
| 型の名前 | `xyz.radicle.issue`、`xyz.radicle.patch`、`xyz.radicle.id` | `awai.cob.issue/1`、`awai.cob.patch/1`。identity は COB ではなく journal | しない |
| 変更の単位 | Git commit の DAG。親子の辺が因果を表す | 署名つき change（DAG-CBOR block）の DAG。`parents` に change の CID を持つ | 構造は対応する。符号化は違う |
| object id | Guide には書かれていない（未確認） | root change の CID | 未確認 |
| 変更の中身の符号化 | Guide には書かれていない（未確認） | `{v type rid cob parents actions ts signer sig}`。actions は `{"type" …}` の一覧で、1 つの change の中ではすべて適用されるか、どれも適用されない | 未確認 |
| 状態の作り方 | root から tip へ topological order で畳み込む。順序が決まらないところは merge 関数（例：commit hash で並べる）か、衝突として利用者に返す | topological order で畳み込み、同じ段では CID の文字列順に並べる。署名・権限・形が不正な change と、その子孫は棄却して理由を返す | 方式は対応する。並べ方の規則が同じかは未確認 |
| issue の操作 | コメント、ラベル、担当者 | open、comment（返信可）、edit、label、state。担当者（assignee）はまだない | 部分的 |
| patch の操作 | レビュー、版（revision）、議論 | open、revise、comment、edit、review（accept・reject・comment）、merge、state | 概念は対応する |
| 権限 | Guide には細かく書かれていない（未確認） | comment と review は誰でもできる。edit・label・state は作成者か delegate。revise は作成者だけ。merge は delegate だけ | 未確認 |

## R2 に進む前に要ること

1. 使う `rad` CLI と heartwood の版を固定し、COB の commit の中身（object id の作り方と、change の符号化）を実物で確かめる。
2. RID と COB の型の名前が一致しないので、相互変換は対応表による付け替えになる。往復して内容が変わらないことを、fixture で示す。
3. Radicle の sigrefs は参照の集合全体を 1 つの署名で覆う。nekko の参照ごとの sigref からそれを作るには、同じ鍵で集合に署名し直す必要がある。どの鍵で署名するかは利用者の承認による（ADR 0044 D4・D5）。
