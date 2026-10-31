# ADR-0001: aero-clj — reduced-order Cd ソルバを EDN/CLJ・datom 化し、設計の固定 Cd を実計算で置換する

- Status: Accepted (2026-06-27)
- 文脈: 「Isaac/Cosmos では空力(CFD)は解けない」→ 専用 CAE を kami-engine/*-clj として
  clean-room・EDN/CLJ 化する方針の第1弾（残り: クラッシュ FEA / モーター電磁・熱 / FC 電気化学）
- 連携: vehicle-design-actor（固定 Cd 仮定を置換）, kami-cfd（将来の高忠実度 LBM backend）,
  nvidia_cosmos-compat（同じ kotoba Datom ログ EAVT 形）

## 課題

vehicle-design-actor は航続を路面荷重から計算するが、その空力項の **Cd を固定の prior
（セダン 0.24 等）**で置いていた。実形状の空力を解いて Cd を出し、設計ループに戻したい。
ただし Isaac Sim/Cosmos では空力 CFD は解けない（前者はロボ向け接触物理、後者は生成
ワールドモデル）。フル CFD（OpenFOAM/LS-DYNA級）は数十年規模で過剰。

## 決定

kami-genesis と同じ clean-room パターンで、**reduced-order ソルバを clj/edn 化**する:

1. **手法は component build-up**（概念段階の正攻法）。ポテンシャル流/パネル法は d'Alembert
   で抗力ゼロになるため、Cd は粘性・剥離の**成分和**から積み上げる:
   `Cd = forebody + afterbody + wheels + underbody + cooling + friction + induced`。
   各成分は形状記述子 [0,1] でスケールし、**全カウントが記述子に追跡可能**（分解＝説明可能）。
2. **EDN ケース in / datom out**。ケース（geometry ref・形状記述子・流体）は EDN、結果
   （Cd・CdA・成分分解）は kotoba Datom ログ（`:aero.AeroCase/*` / `:aero.AeroComponent/*`、
   nvidia_cosmos-compat と同形）。係数は `aero.model/default` の単一 edn 表に集約。
3. **設計ループ閉包**（`aero.bridge`）。`F=½ρ·Cd·A·v²`、固定航続では空力エネルギーが Cd に
   線形 → computed-vs-prior の Cd 差が航続(または kWh)差に直結。vehicle-design-actor の路面
   荷重 aero 項と同式をローカルに持ち、リポ間ハード依存なしでループを実証。
4. **backend 差し替え**。`:rom-buildup` と同じ `solve` 契約で、将来 `kami-cfd`（Rust
   lattice-Boltzmann）が解像場を返す高忠実度 backend として同じ EDN/datom 境界に入る。

## 帰結

- 同一セダンで BEV Cd 0.248 / FCEV 0.267 を計算（afterbody が支配）。FCEV は床下粗さ
  ＋冷却開口で +19 カウント → 航続 −4.3%。BEV 0.248 は設計 prior 0.24 を 3% 以内で**検証**。
- 検証は `test/aero/aero_test.cljk`（7 tests / 11 assertions, green）: 現実 Cd 帯・各レバー
  単調性・BEV<FCEV・afterbody 支配・決定論・datom 化・ループ方向。
- 依存ゼロの純 clj（JVM/SCI/CLJS/GraalVM 可搬）。係数 re-fit と kami-cfd 配線が次段。

## 却下案

- **パネル法/ポテンシャル流で Cd**: d'Alembert で抗力ゼロ。剥離・粘性が要るので不可。
- **いきなりフル CFD**: 概念段階で過剰。reduced-order で工学的に十分、高忠実度は後段 backend。
- **Cd を固定 prior のまま**: 設計ループが空力に応答せず、BEV/FCEV の床下・冷却差を取り逃す。
