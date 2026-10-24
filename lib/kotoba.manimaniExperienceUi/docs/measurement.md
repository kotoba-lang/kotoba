# Computational measurement of UI/UX

UI/UXを単一の美的点数へ潰すことはできません。測る対象を **物理量・行動量・認知量・信頼量・成果量** に分け、観測可能な値だけをscore化します。主観評価は別系列で残します。

## 1. Physical and perceptual fitness

### Target acquisition — Fitts' law

`MT = a + b log2(D/W + 1)`

`D` はpointerからtargetまでの距離、`W` は進行方向のtarget幅です。主要操作の予測時間と実測時間を比較します。44pt未満のtarget率、誤タップ率も併記します。

### Choice complexity — Hick–Hyman law

`RT = a + b log2(n + 1)`

同時に競合する選択肢 `n` を数えます。ただしprimary actionが視覚的に優先される場合は、各選択確率 `pᵢ` を用いて `H = -Σ pᵢ log2 pᵢ` とし、`RT = a + bH` で評価します。

### Keyboard and chat ergonomics

software keyboard表示時の実効viewportを `Vusable`、表示前を `Vtotal` とします。

`usable viewport ratio = Vusable / Vtotal`

composerと直近messageがkeyboardに隠れたframe率を `keyboard occlusion rate` として測り、0をgateにします。Chatではtab barを退避し、composerへfocusして送信するまでのtask time、tabへのaccidental activation rate、keyboard dismiss成功率、Chatから戻る経路の発見率、layout shiftを比較します。

tab常時表示案と自動退避案を同じ端末・同じtaskでA/B比較します。画面が広く見えるかではなく、入力完遂、誤操作、戻りやすさで判断します。

### Contrast and legibility

WCAGのrelative luminanceからcontrast ratioを計算し、本文4.5:1、大きな文字3:1を最低線にします。文字サイズ、行長、zoom時overflowも機械監査します。

## 2. State observability

重要state集合を `S`、画面から正しく同定できたstateを `Ŝ` とします。

`observability = Σ wₛ · correct(s) / Σ wₛ`

visibility、capability、run state、blocker、receiptを重くします。5秒テストで「現在地・次の行動・危険度」を回答してもらい、accuracyと回答時間を測ります。

情報理論的には、画面を見る前後の状態不確実性の減少を測れます。

`information gain = H(S before) - H(S after UI)`

情報を増やすことではなく、意思決定に必要な不確実性を減らすことが目的です。

## 3. Agent trust and calibration

agentが成功確率 `p` を提示し、結果 `o ∈ {0,1}` が得られる場合：

`Brier = mean((p - o)²)`

低いほど確率が較正されています。UIの信頼性は「信用された割合」ではなく、適切に承認・拒否できた割合で測ります。

`appropriate reliance = (correct approvals + correct rejections) / decisions`

automation surprise、scope誤認、取り消し不能操作を別途near-missとして数えます。

## 4. Loop dynamics

Walkを離散時間systemとして扱います。

- `WIP(t)`: 未完了work
- `λ(t)`: 新規流入率
- `μ(t)`: verification済み完了率
- `B(t)`: blocker数または重み付きblocker pressure
- `R(t)`: rework率

`WIP(t+1) = WIP(t) + λ(t) - μ(t)`

`blocker pressure = Σ severityᵢ × ageᵢ × dependencyᵢ`

Little's Law `L = λW` を安定期間で用い、WIP、throughput、cycle timeの整合を見ます。改善loopには以下を使います。

`learning gain = verified hypotheses / loop cycles`

`spiral efficiency = verified value / (cycle time × rework factor)`

速度だけを最大化せず、receiptの質と再作業を含めます。

## 5. Companion motion model

マニ車の角速度 `ω` は、入力impulseと摩擦を持つ一次系として実装・測定できます。

`ωₜ₊₁ = ω₀ + (ωₜ - ω₀)e^(-kΔt) + Ipress + Ishake`

`ω ← softCap · tanh(ω / softCap)`

`ω₀` は常時回転の基礎速度です。agent progress `Pagent` と応援energy `Eplay` は別変数にし、相関を表示しても同一視しません。frame time、input acknowledgement latency、overshoot、settling time、reduced-motion parityを測ります。

## 6. Composite score

release gate用には0–100の `MEUI score` を使えます。

`score = 100 × Σ wᵢ qᵢ / Σ wᵢ`

各 `qᵢ ∈ [0,1]`。初期weightはEDNに定義します。ただし安全項目は平均で相殺しません。critical gateが0なら総合点に関係なくfailです。

### Critical gates

- external receiptなしのDone表示: 0件
- visibility/capability誤認: 0件
- unpreviewed external write: 0件
- keyboard/assistive technologyで完遂不能: 0件
- reduced-motionでstate欠落: 0件
- keyboardがcomposerまたは実行確認を隠す: 0件

## Experiment design

1. taskと成功条件を事前登録する
2. novice / experienced、mobile / desktopを層別化する
3. baselineとcandidateを同じtaskで比較する
4. completion、time、error、NASA-TLX簡易値、信頼較正を取る
5. effect sizeと95% confidence intervalを報告する
6. telemetryだけで理由を推測せず、観察と短いinterviewを組み合わせる

美しさや愛着は5–7段階のsemantic differential（calm–restless、clear–confusing、warm–cold、trustworthy–unpredictable）で測り、行動指標とは混ぜずに併記します。
