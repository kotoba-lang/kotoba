---
id: adr-2606291100-kotoba-eda-web-semiconductor-app
title: "ADR-2606291100: kotoba-lang EDA — 半導体開発を web で完結する clj/kami/murakumo/LLM 統合アプリ"
status: proposed
doc_type: adr
topic: kotoba-eda-web-semiconductor
authoritative: true
last_verified: 2026-06-29
authoritative_for:
  - kotoba-lang で EDA/半導体開発アプリを web 完結にする製品アーキテクチャ
  - .kotoba/.cljc を EDA IR、PDK rule、verification workflow の正本にする境界
  - kami engine を schematic/layout/waveform/3D package viewer に使う方針
  - murakumo inference と LLM copilot を EDA toolchain に統合する安全境界
related:
  - 90-docs/adr/2606241700-kotoba-clj-runtime-kotoba-ext.md
  - 90-docs/adr/2606271600-kotoba-stack-equivalences.md
  - 90-docs/adr/2606271700-kotoba-transport-planes.md
  - 90-docs/adr/2606272300-cloud-murakumo-gpu-cloud.md
  - 90-docs/adr/2606272330-gftd-ai-generation-studio.md
  - orgs/kawasakijun/docs/adr/0013-clj-agent-stack.md
  - orgs/kawasakijun/docs/adr/0022-spirit-in-physics-svelte-ts-to-clojure-kami-engine.md
supersedes: []
superseded_by: []
---

# ADR-2606291100: kotoba-lang EDA — 半導体開発を web で完結する app

**Status**: proposed  
**Date**: 2026-06-29  
**Deciders**: Jun Kawasaki

## Context

半導体開発を web で完結するには、単なる「ブラウザ UI + EDA CLI 実行」では足りない。
必要なのは、要求仕様、回路、レイアウト、PDK、検証結果、LLM 提案、承認履歴をすべて
同じ不変ログに置き、Datalog で横断できる開発面である。

既存の kotoba スタックにはこの前提に合う部品が揃っている。

- `.kotoba` / `.clj` / `.cljc` は Clojure/EDN 系ソースとして kotoba-clj で扱える。
- kotoba は CID + Datom + WASM Component の基板で、設計データと実行コンポーネントを
  content-addressed にできる。
- murakumo は kotoba WASM mesh の制御面で、GPU/CPU ジョブ、inference、課金/承認 gate を
  datom 化できる。
- kami engine は Clojure 著作層 + Rust/wgpu render 層を持ち、ブラウザの高密度可視化に
  使える。
- langchain-clj / langgraph-clj は LLM/agent の状態、checkpoint、tool call を datom 化する
  パターンを既に持つ。

## Decision

新しい製品面として **kotoba-eda** を設計する。目的は「小規模 IP、ASIC/SoC ブロック、
analog/mixed-signal macro、FPGA prototype、package/board 境界」までを、ブラウザから
要求定義、設計、検証、レビュー、artifact 生成まで完結させること。

実装正本は `.cljc` と `.kotoba`。UI は ClojureScript。可視化は kami engine。重い実行と
web inference は murakumo。LLM は copilot であり、sign-off tool ではない。

```
Browser app (CLJS)
  schematic / layout / waveform / package viewer
  chat + review + verification dashboard
        |
        | XRPC / HTTP / SSE
        v
kotoba-eda service (.cljc)
  EDA datom schema / Datalog views / workflow FSM / policy gate
        |
        +--> kotoba store: specs, netlists, layouts, reports, artifacts by CID
        |
        +--> murakumo jobs:
              LLM inference / synthesis / place-route / DRC / LVS / STA / SPICE
        |
        +--> kami engine:
              WebGPU layout canvas, graph viewer, waveform, package/thermal scene
```

## Product Surface

### 1. Web IDE

左から右へ流れる実務 UI にする。

| Pane | 役割 |
|---|---|
| Project | PDK、process、target、IP block、constraints、artifact library |
| Source | `.kotoba` / `.cljc` / Verilog/SystemVerilog / SPICE / constraint EDN |
| Canvas | schematic graph、floorplan、layout、waveform、timing path、package view |
| Verify | DRC/LVS/STA/SPICE/formal の run list、差分、waiver、sign-off checklist |
| Copilot | LLM 提案、tool plan、review comments、root-cause analysis |

「説明ページ」ではなく、初期表示は project workspace。新規 project でも、PDK 選択、
top module、constraints、最初の verification target がすぐ編集できる。

### 2. EDA Flow

最初の対応 flow は digital mixed-signal 寄りにする。

1. **Spec**: 要求、interface、clock/reset/power domain、test intent を EDN datom 化。
2. **Design**: `.kotoba` / `.cljc` で generator、glue logic、constraint transform を記述。
3. **RTL / Netlist**: Verilog/SystemVerilog、SPICE netlist、intermediate graph を CID 保存。
4. **Synthesis / P&R**: open toolchain または社内 runner を murakumo job として実行。
5. **Verification**: lint、simulation、formal、DRC、LVS、STA、SPICE を run datom に束ねる。
6. **Review**: LLM が report を要約し、差分、regression、risk、waiver 候補を出す。
7. **Release**: sign-off checklist が緑の artifact set だけを release candidate CID にする。

### 3. Artifact Model

大きい artifact は git に置かない。GDS/OASIS、wave dump、simulation db、model weight、
large report は B2/DataLad または kotoba object store に置き、git には CID/datom だけを残す。

主要 datom 語彙:

| Entity | 例 |
|---|---|
| `:eda.project/*` | project id、owner、process、PDK、top、status |
| `:eda.pdk/*` | PDK id、license、rule deck CID、primitive device、layer map |
| `:eda.design/*` | block、revision、source CID、interface、dependency |
| `:eda.netlist/*` | RTL/gate/SPICE、format、source relation |
| `:eda.layout/*` | GDS/OASIS CID、bbox、layer stats、cell hierarchy |
| `:eda.run/*` | tool、version、input CIDs、output CIDs、status、duration |
| `:eda.report/*` | DRC/LVS/STA/SPICE/formal report、severity、findings |
| `:eda.waiver/*` | rule、region、reason、approver、expiry |
| `:eda.review/*` | LLM proposal、human decision、accepted/rejected reason |
| `:eda.release/*` | sign-off bundle、artifact set、approval chain |

## kotoba-lang / clj Boundary

`.kotoba` は EDA 用 DSL の正準ソースにする。ただし、巨大な EDA 全体を `.kotoba` に押し込まない。
分担は明確にする。

| Layer | 実装 | 責務 |
|---|---|---|
| EDA IR | `.cljc` + EDN schema | design graph、netlist graph、layout graph、run graph |
| Generators | `.kotoba` / `.cljc` | parameterized RTL、PCell、constraint、testbench 生成 |
| Workflow | `.cljc` | run FSM、policy、Datalog view、diff/review |
| Tool host | JVM / native runner | EDA CLI、filesystem sandbox、license check、artifact upload |
| Browser | CLJS | editing、visualization、review、SSE progress |
| Hot compute | murakumo | inference、batch verification、parallel simulation、GPU/CPU placement |

`.kotoba` の用途は「再現可能な小さな生成ロジック」に限定する。PDK rule deck や EDA tool 本体の
再実装を目指さない。既存ツールの出力を datom/CID に正規化し、Datalog で扱うのが価値の中心。

## kami engine Integration

kami engine は EDA viewer の描画 arm として使う。

- schematic graph: net/cell/pin の graph を pan/zoom 可能な canvas で表示。
- physical layout: GDS/OASIS を tile 化し、layer visibility、rule hit overlay、selection を
  WebGPU で描画。
- waveform: VCD/FST 等を downsample して browser 表示。event correlation を report とリンク。
- timing/path: STA critical path を schematic/layout 上に重ねる。
- package/thermal: die/package/board 境界を 2.5D/3D scene として表示。

kami 側に EDA の真実を持たせない。真実は `:eda.*` datom と artifact CID。kami は
render-IR を受けて表示する stateless viewer。

## murakumo Inference / LLM Integration

web 推論は 2 段に分ける。

1. **サーバ/mesh inference**: murakumo の vLLM/LLM serving を使う。large context report
   analysis、RTL generation、constraint explanation、DRC root-cause、timing closure assistant は
   ここで実行。
2. **browser-local assist**: 小さい autocomplete、symbol search、UI ranking だけを将来の
   browser WebGPU inference に逃がせる。sign-off 判断や機密 PDK を必要とする推論は browser に
   閉じ込めず、policy gate 付きの murakumo job にする。

LLM は次の能力を持つ。

| Agent | Input | Output | Gate |
|---|---|---|---|
| `spec-agent` | natural language spec、既存 interface | EDN spec proposal | human approve |
| `rtl-agent` | spec、interfaces、constraints | patch proposal / generator proposal | tests required |
| `verify-agent` | reports、waveform summary、run history | root-cause / next run plan | read-only by default |
| `layout-agent` | DRC/LVS/timing paths | fix candidate / region highlight | human approve |
| `release-agent` | all reports and waivers | sign-off checklist diff | cannot approve itself |

安全境界:

- LLM 出力は直接 commit / release しない。常に `:eda.review/*` として提案に落とす。
- EDA tool の実 report が authoritative。LLM summary は補助情報。
- PDK license、export control、customer NDA、model provider 送信可否を policy datom で判定する。
- 外部 LLM に送る context は redaction / CID indirection / tenant boundary を通す。
- destructive action、paid GPU scale-up、外部 fab/package vendor への送信は approval gate 必須。

## APIs

最小 API は REST + SSE + kotoba XRPC。

| Method / Path | 用途 |
|---|---|
| `GET /v1/projects` | project 一覧 |
| `POST /v1/projects` | project 作成 |
| `GET /v1/projects/{id}/db` | Datalog view snapshot |
| `POST /v1/projects/{id}/transact` | spec/source/review datom 追加 |
| `POST /v1/projects/{id}/runs` | synthesis/sim/drc/lvs/sta/spice job submit |
| `GET /v1/runs/{id}` | run status |
| `GET /v1/runs/{id}/events` | SSE progress |
| `GET /v1/artifacts/{cid}` | Read 面 CID-over-HTTP artifact fetch |
| `POST /v1/copilot` | LLM proposal job |
| `POST /v1/releases` | sign-off bundle proposal |

AT-proto / XRPC namespace は `ai.gftd.eda.*` または `com.junkawasaki.eda.*`。
public SaaS 化する場合は `ai.gftd.eda.*`、core library / self-host を先に切る場合は
`com.junkawasaki.eda.*` を正本にする。

## Toolchain Adapters

tool は adapter 化する。特定ツールを UI に直結しない。

```clojure
{:eda.tool/id :tool/openroad
 :eda.tool/kind :place-route
 :eda.tool/inputs [:rtl :sdc :lef :def :pdk]
 :eda.tool/outputs [:def :gds :sta-report :log]
 :eda.tool/runner :murakumo.cpu
 :eda.tool/policy {:license :open :network :deny-by-default}}
```

初期 adapter 候補:

- RTL/synthesis: Yosys 系、commercial tool host は後段。
- P&R/STA: OpenROAD 系、commercial sign-off は adapter だけ定義。
- Layout/DRC/LVS: KLayout/Magic/Netgen 系、rule deck は PDK policy に従う。
- Simulation: ngspice/Xyce/Verilator/iverilog 系。
- Waveform: VCD/FST parser、browser 表示用 downsample。

各 adapter は `inputs -> command plan -> outputs -> report parser -> datoms` の純データ境界を持つ。
実 command は host capability 注入で、library 本体から shell を直接叩かない。

## Risk Gate

EDA は「計算コスト」だけでなく「知財流出」と「sign-off 誤認」がリスクになる。

| Effect | Risk | Gate |
|---|---|---|
| CPU/GPU 大規模 run | financial | quota + approval |
| PDK / customer data の外部送信 | confidential | policy fail-closed |
| foundry/vendor upload | external-disclosure | explicit approval |
| release candidate 作成 | quality | all required reports green |
| waiver 追加 | quality/legal | approver + expiry required |
| LLM patch 適用 | code-change | tests + human approve |

## Non-goals

- commercial EDA tool を置き換えること。
- PDK rule deck を LLM で生成して sign-off に使うこと。
- LLM に sign-off 承認権限を与えること。
- browser だけで全 verification を実行すること。
- 大容量 artifact を git に直接入れること。

## Implementation Plan

### P0a: docs-hosted executable workbench

- `docs/eda/index.html` を説明ページから flow workbench に変更済み。
- `docs/eda/kotoba_eda_core.cljc` が工程、policy gate、datom、manufacturing packet、
  kami render-IR の正本モデルを持つ。
- `docs/eda/eda_file_formats.edn` が EDA でよく使うファイル形式を registry として定義し、
  `docs/eda/kotoba_eda_formats.cljc` が拡張子、工程、policy、manifest 生成を純関数で扱う。
- registry は `:software`、`:operations`、`:converter-pipelines` も持つ。
  変換は file-to-file 直結ではなく、`external file -> typed EDN -> tool/render/report output` の
  EDN hub 方式にする。
- `docs/eda/kami_render_ir.edn` は kami engine の plain-data render-IR 形状を EDA layout に
  適用した公開サンプル。
- `co-sientist` は品質/UIUX レビュー agent として扱う。sign-off 権限は持たず、
  `:eda.review/co-sientist` datom と proposal に品質、UIUX、policy gate coverage、next action を
  記録する。
- `#manufacturing` は maturity dashboard として、readiness evidence、simulation matrix、
  MRL-like level、blocker、useable-for を出す。設計・シミュレーション・製造 handoff に使える
  品質かを `:eda.maturity/*` data として評価する。
- `Artifact Intake` はブラウザ内で EDA file を読み、形式判定、軽量 parse、CID 風 ID、
  `:eda.artifact/ingest`、`:eda.parser/summary`、`:eda.report/finding` datom を作る。
  これにより `upload -> parse -> datom -> maturity` の一周は GitHub Pages 上で実行できる。
  実 Verilator/Yosys/OpenROAD/KLayout/ngspice 実行は次段の host/murakumo runner adapter に接続する。
- `docs/eda/eda_runner_adapters.edn` と `docs/eda/kotoba_eda_runner.cljc` は
  artifact manifest から Verilator/Yosys/OpenSTA/OpenROAD/KLayout/Netgen/ngspice の EDN job plan を
  生成する。`docs/eda/runner_host.clj` は host 側 dry-run/execution skeleton。
- 現時点では実 foundry 送信や有償 mask order は gate 付き handoff packet 生成まで。
  外部 vendor への destructive / paid action は P2/P4 の policy 実装後に接続する。

### P0: data model and mock web IDE

- `kotoba-eda-clj` を `.cljc` library として作る。
- `:eda.*` schema、in-memory db、Datalog view、artifact CID stub を実装。
- CLJS web IDE で project/source/run/report/review を表示。
- kami viewer はまず schematic graph と report overlay から始める。

### P1: real verification runners

- host capability 注入で Yosys/Verilator/ngspice/KLayout などを adapter 化。
- run submit -> SSE -> artifact CID -> report parser -> datom の閉ループを作る。
- run history と report diff を UI に出す。

### P2: murakumo placement

- CPU/GPU job を murakumo app として `resources/eda.edn` に宣言。
- parallel simulation、LLM report analysis、large waveform summarization を scale-to-zero job にする。
- financial/confidential gate を runtime に入れる。

### P3: LLM copilot

- langgraph-clj で `spec-agent` / `rtl-agent` / `verify-agent` / `layout-agent` を構成。
- すべての proposal を `:eda.review/*` に保存し、accept/reject を human decision として記録。
- model provider ごとの redaction policy を実装。

### P4: sign-off bundle

- required checks、waiver、tool version、input/output CID を束ねた release candidate を作る。
- as-of で過去 release を再構成できるようにする。
- foundry/vendor handoff は explicit approval と export/NDA policy gate を通す。

## Consequences

- 半導体開発の「作業 UI」だけでなく、設計判断と検証結果の provenance が kotoba datom に残る。
- `.kotoba` は EDA generator / constraint / workflow の小さな再現可能単位として効く。
- kami engine により browser で schematic/layout/waveform を一体表示できる。
- murakumo により LLM 推論と重い verification を web から扱えるが、課金・機密・承認 gate を
  同じ仕組みに乗せられる。
- LLM は便利な設計者補助になる一方、authoritative source ではない。この境界を破らないことが
  EDA アプリとしての信頼性の条件になる。

## Open Questions

1. project/repo 名は `kotoba-eda-clj`（library 先行）か `ai-gftd-eda`（product 先行）か。
2. 最初の PDK target は open PDK に限定するか、private PDK を vault/policy 前提で扱うか。
3. 初期 flow は digital RTL から始めるか、analog/SPICE macro から始めるか。
4. UI は既存 `murakumo.cloud` に EDA tab を足すか、独立 `eda.gftd.ai` / `eda.kotoba.dev` にするか。
5. LLM provider は murakumo-hosted model を既定にし、外部 provider は opt-in にするか。
