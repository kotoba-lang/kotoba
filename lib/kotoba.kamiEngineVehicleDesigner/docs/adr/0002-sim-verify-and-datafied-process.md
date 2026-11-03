# ADR-0002: 設計 spec を (a) Isaac/CAE 互換シムで検証し、(b) BOM→CAM→4D 組立順まで全 datom 化する

- Status: Accepted (2026-06-27)
- 前提: ADR-0001（concept proposer を PhysicsGovernor で封じた clean-sheet 設計アクター）
- 連携先: kami-engine `kami-genesis`(isaacsim.core.api 互換) / `kami-cae` / `kami-shugyo`(isaaclab RL+DR) / `kami-cam`(CAM) / giemon-factory(4D 組立順), etzhayyim `nvidia_isaac-compat` / `nvidia_cosmos-compat`(kotoba Datom ログ)
- 関連: kami-engine ADR-0034（Isaac-compat スタック成熟）

## 課題

ADR-0001 は「物理的に閉じた設計（質量閉包・エネルギー収支・パッケージング）」までを
出した。しかし**閉じた spec は完成設計ではない**。(a) 構造・衝突がもつか、(b) その車を
どう作る（部品・加工・組立順）かが欠けていた。ワークスペースには既に Isaac/Cosmos
互換シム（kami-genesis/kami-shugyo/nvidia_*-compat）と CAM（kami-cam）・4D 組立順
（giemon-factory）があるのに、設計アクターから未接続だった。

## 決定

released spec の後段に2ステージを追加し、StateGraph を伸ばす:

```
… decide ─closes→ design-review[interrupt] ─▶ (a) verify ─survives→ (b) process ─▶ emit
                                                    └─fail→ rejected(第2の MRC)─▶ emit
```

### (a) SimGovernor（`vdesign.simverify`）— PhysicsGovernor に続く第2の独立検閲器

- **kami-genesis(`isaacsim.core.api`) / kami-cae の語彙**でシーン化し、20g クラッシュ
  荷重に対する床レール構造 SF・パッケージ干渉(clash)・車軸荷重を閉形式で評価。
- **kami-shugyo 流の per-env ドメインランダム化**（質量±8% / 構造強度±6% / クラッシュ
  パルス±10% を 16 env）で worst-case SF を取り、**sim-to-real マージン**を保証。
  乱数は seeded LCG（`Math/random` 不使用）で**再現可能**（G6 継承）。
- 構造不合格なら、物理的に閉じていても spec を `:rejected` に降格（第2の MRC）。
- 不変条件: **閉じた(exists)だけでなく、もつ(survives)を通った設計だけが (b) に進む。**

clean-room（NVIDIA コード非リンク、public API の名前/形だけミラー）は kami-engine
Isaac-compat スタック（ADR-0034）と同じ不変条件を維持。本アクター側は自前の閉形式
構造モデルで計算する。

### (b) ProcessPlanner（`vdesign.process`）— 組立工程まで全 datom 化

- **BOM**: mass-budget から主要アセンブリを数量・質量按分で展開（BEV=電池モジュール
  ×N+pack-tray / FCEV=H2 タンク×N+FC スタック+バッファ）。
- **CAM**: 機械加工部品に kami-cam 語彙（`ToolType` EndMill/FaceMill/Drill,
  `StockShape` Block, `MachineType` Mill3Axis, `G00/G01`）で工程を生成し、実際の
  **G-code**（`G21 G90` … `M30`）とサイクルタイムを出す。
- **4D 組立順**: giemon-factory の `construction.order.json :seq` パターンで段階順を
  生成。**BEV と FCEV はエネルギー系のところだけ分岐**（`battery-pack-install` /
  `charge-to-soc` ↔ `h2-tank-install` / `h2-leak-test` / `h2-fill`）。各ステップに
  station・takt・予定順を持つ真の 4D 順。

### datom 表現（`vdesign.datom`）

検証も製造も **kotoba Datom ログ**（EAVT, Datomic 同型, `nvidia_*-compat` と同じ形）に
書く。entity tx-map（`:vdesign.<Kind>/<attr>`）と EAVT タプルの2ビュー。「station 4 が
なぜボトルネックか」「工具 T-03 を共有する部品は」が Datalog クエリになる。

## 帰結

- 「車をゼロから設計→シム検証→組立工程まで全データ化」が1アクター1グラフで通る。
  デモ: 同一 500km セダンが BEV/FCEV とも close→sign-off→(a)PASS→(b)plan を通り、
  FCEV はパッケージが tight（clash SF≈1.1）に出るなど物理的に正直。
- 検証は `closure_contract_test.clj`（11 tests / 47 assertions, green）。(a) 再現性・
  feasible 合格、(b) BOM/CAM/G-code・組立順の powertrain 分岐・datom 化を網羅。
- **本アクターは self-contained な閉形式モデルで (a)(b) を実装**。実 kami-genesis/
  kami-cam（Rust）や `nvidia_*-compat`（Datom ログ実体）への配線は次段（datom を
  `DatomPort`=kotoba-kqe に transact、シーンを kami-genesis に渡す）で、信頼境界
  （`:verify`/`:process` ノード）は不変。

## 却下案

- **物理閉包と構造検証を1ゲートに統合**: 「存在」と「耐久」は別問題。分けることで
  構造不合格＝第2の MRC を独立に表現でき、監査台帳も clean。
- **工程を非構造の添付（PDF/CAD バイナリ）で持つ**: clone を重くし（AGENTS.md の
  大容量バイナリ方針に反する）、クエリ不能。datom 化が source of truth。
