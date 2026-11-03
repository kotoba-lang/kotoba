# ADR-0001: vehicle-design-actor — 概念生成器を物理境界に封じ込めた clean-sheet 車両設計アクター（BEV / FCEV）

- Status: Accepted (2026-06-27)
- 関連: langgraph-clj ADR-0001 (Pregel superstep + interrupt + Datomic checkpoint), robotaxi-actor ADR-0001 (AR1 を SafetyGovernor で封じた知能ノード設計)
- 鏡像: 本 ADR は robotaxi-actor の **設計版ミラー**。あちらは「研究 VLA を SafetyGovernor で封じる」、こちらは「概念生成器を PhysicsGovernor で封じる」。

## 課題

要件（クラス・航続・積載・最高速）から車を**ゼロから設計**し、**電気自動車(BEV)
と水素燃料電池(FCEV)それぞれ**でエネルギー系まで sizing するアクターが欲しい。

設計の「脳」を生成モデル（LLM / 生成 CAD）にすると、概念空間は広く探れるが、
**保存則を守らない**。1500 km の市街車を 1100 kg で平気で提案する。エネルギー
ストアが質量・体積収支に収まる保証がモデルの目的関数に無いからだ。

したがって設計課題は「モデルで車を設計する」ことではなく、**「提案器を信頼境界の
内側に封じ込め、大胆な概念は探索しつつ、*物理的に閉じた*設計だけを spec として
出す」**こと。これは robotaxi-actor と同じ構図である。

## 決定

### 1. DesignProposer は最下層・最低信頼の1ノードに封じ込め、直接 spec を出さない

提案器は *concept*（目標質量・出力・パッケージ）のみを返す**助言者**。出力は必ず
独立した `PhysicsGovernor` を通す。**単一の不変条件**:

> **DesignProposer は、PhysicsGovernor が閉じていない設計を決して release しない。**

### 2. PhysicsGovernor が保存則を強制する（独立した検閲器）

- **質量閉包（mass spiral）**: 重い車ほど大きなストアが要り、さらに重くなる。
  feasible なら不動点に収束、過大要求なら発散 → **発散が reject 信号**（設計版 MRC）。
- **エネルギー収支**: 路面荷重（転がり+空力, サイクル係数で代表化）→ パワートレイン
  別の経路効率でストア容量へ。
- **パッケージング**: ストア体積 ≤ 包絡体積。
- **GVWR / ストア質量率**ゲート。

全反復は1ノード呼び出し内に有界に encapsulate（≤60 iter）。よって robotaxi と
同じく **1 graph run = 1 設計パス**で監査可能、無限内ループにしない。

### 3. VehicleDesignActor = langgraph-clj StateGraph

```
require → propose → govern → decide ─┬─ (closes) ─▶ design-review ─▶ emit
                                     │             [interrupt-before]  (released)
                                     └─ (infeasible) ───────────────▶ emit
                                                       (rejected spec + 違反ゲート)
```

`interrupt-before #{:design-review}` は実際のエンジニア sign-off（robotaxi の
teleop handoff と同型）。全ステップを checkpoint（prod=Datomic / dev=in-mem）し、
「なぜ 1480 kg か」を proposal→spiral 履歴→verdict→emit の監査台帳で説明できる。

### 4. BEV / FCEV はエネルギー系モデルだけが分岐する

glider・路面荷重・包絡は powertrain 非依存。`vdesign.powertrain` のみが分岐:

- **BEV**: `nominal_kWh = range·consumption/DoD` → pack 質量(175 Wh/kg)・体積。
  傾向は**質量律速**。
- **FCEV**: `H2_kg = range·consumption_LHV/LHV`、FC で電力需要を昇圧(η≈0.53)、
  タンク系質量=`H2_kg/0.055`(700 bar typeIV)+スタック+バッファ。傾向は**体積律速**。

同一要件から「重いがコンパクトな BEV」「軽いが体積逼迫の FCEV」が落ちてくる。
トレードは構造的で、governor は具体的マージン（GVWR まで kg、包絡まで L、ストア率）
として提示する。

## 帰結

- 大胆な提案器（将来 LLM/生成 CAD に差し替え可。信頼境界は `:propose→:govern`
  エッジのみ）と、物理的に正直な spec を両立。
- 定数は `vdesign.powertrain/tech` と `vdesign.proposer/classes` に集約（~2026
  量産技術）。セル/タンク進歩はここを retune するだけ。
- 検証は `test/vdesign/closure_contract_test.cljk`（閉包収束・両 powertrain 差・
  過大要求 reject・エネルギー単調性・「未閉包は release しない」不変条件）。

## 却下案

- **提案器に物理を直接やらせる**: 目的関数に保存則を内在化できず、もっともらしいが
  破綻した設計を出す（robotaxi で AR1 に安全を委ねないのと同じ理由）。
- **質量を閉形式で1発計算**: 質量スパイラルは不動点問題。発散＝過大要求の検出という
  最も有用な信号を失う。
