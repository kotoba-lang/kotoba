(ns kotoba.property.eu-intent-score
  "EU の公開シグナル -> intent の点数。I/O ゼロ。

   `kotoba.property.intent-score`（日本 / SKU A）の EU 版。**重みは日本のものを
   そのまま使えない** —— 代理しているものが違う。

     JP / SKU A  『この会社は最近、設備投資の優遇を取りにいった』（認定 → 設備購入）
     EU / SKU B  『この会社は最近、EU の競争的 R&D 資金を取りにいった』（採択 → 計算資源）

   採点の**形**（種別の重み × リセンシー減衰 × スタッキング、base と boost を
   足さない）は日本と同じで、そこは `intent-score` の関数を再利用する。
   変わるのは重みの表と、boost に載るシグナルだけ。

   ## base と boost を足さない（日本と同じ規律。理由も同じ）

   実測 2026-08-25、母集団 8,831 法人に対する被覆:

     topic（call ID）・署名日・役割           100%     -> base
     euroSciVoc の AI/計算機タグ              86.2%    -> boost
     SME 区分                                 98.8%    -> boost
     EC 拠出額                                71.2%    -> boost

   足すと、**測れなかった法人が『シグナルの無い法人』として沈む。**
   euroSciVoc が 86.2% と高いので base に入れたくなるが、100% ではない ——
   入れた瞬間、タグの無い 13.8% が『AI をやっていない』ことになる。

   ## 母数が大きいことはシグナルが強いことではない

   母集団で最大のクラスは **MSCA**（実測 3,327 参加 = 24.6%）だが重みは最小である。
   MSCA は博士課程ネットワークと人材交流で、金は人件費と移動に出る —— 参加企業は
   受入先であって、計算資源を買う主体ではない。日本側で
   『事業継続力強化計画（母数最大）の重みを最小にした』のと同じ判断。

   ## 重みは仮定であって測定値ではない

   返信率で検証していない。順位を作るための単調な関数でしかない。
   ⚠ **この点数は、その企業が推論を買う意思を持つという主張ではない。**"
  (:require [kotoba.property.intent-score :as jp]))

(def dataset "eu-lead-intent-score")

(def topic-class-weights
  "Horizon Europe の call クラス -> 重み。**ホスト推論（SKU B）を買う意思に
   どれだけ近いか**で置いている。距離の目安は『その資金で計算を回すか』。

   `:cl4-digital`（Cluster 4: Digital, Industry and Space。DATA / AI / robotics の
   call を含む）が最大。`:chips-ju` と `:eic` が次点 —— 前者は半導体で設計計算が
   重く、後者は EIC Accelerator / Pathfinder すなわち**ディープテックの中小企業**で、
   自前の計算基盤を持たない SKU B の買い手像そのもの。

   `:msca` と `:widera` が最小。人材育成・能力構築であって計算の購入ではない。

   ⚠ 参考までに、この母集団で euroSciVoc が AI/計算機を付けた率（実測 2026-08-25）:
   chips-ju 60.3% / cl3-security 50.3% / cl4-digital 31.2% / msca 20.8%。
   **重みはこの率に一致させていない** —— 率は『その分野を研究しているか』であって
   『推論を買うか』ではない（security の 50.3% は ML 研究の多さで、EIC の 17.6% は
   起業の多様さである）。率で重みを決めると、測ったものと違うものを測ることになる。"
  {:cl4-digital  3.0
   :chips-ju     2.5
   :eic          2.5
   :cl3-security 2.0
   :other-ju     1.5
   :cl1-health   1.0
   :cl5-climate  1.0
   :cl6-food     1.0
   :cl2-culture  1.0
   :infra        1.0
   :erc          1.0
   :other        1.0
   :msca         0.5
   :widera       0.5})

(def coordinator-multiplier
  "コーディネータであることの倍率。`role` は **100% 埋まっている**ので base に置ける。

   コーディネータはコンソーシアムの予算と調達を仕切る側で、参加者より意思決定に
   近い。実測 2026-08-25、母集団 8,831 のうち 636（7.2%）。
   ⚠ これも仮定。"
  1.15)

(defn base-score
  "被覆 100% のシグナルだけで作る点数。**全社で比較可能。**

   `participations` は `{:topic-class :cl4-digital :event-date \"2026-01-20\"}` の列。
   `as-of` は基準日（ISO）。純関数にするために引数で受ける。

   クラスごとに**最新の 1 件だけ**を数えるのは日本と同じ理由 —— 同じ call に
   何度も出ている法人が、今日採択された法人を古い実績の積み上げで追い越さないため。

   ## ここだけ日本と形が違う: クラスを**足さず、最大を採る**

   日本の `intent-score/base-score` は認定の種別を**合計**する。EU で同じ形にすると、
   自分が書いた『母数が大きいことはシグナルが強いことではない』を裏切る:

     MSCA(0.5) を 8 クラス分積んだ法人  0.5×8 × 1.6 = 6.4
     CL4-digital(3.0) 1 本の法人        3.0   × 1.0 = 3.0

   **博士課程ネットワークの常連が、デジタル分野の採択を 1 本持つ会社を追い越す。**
   実測 2026-08-25、この形で母集団 8,831 を並べたところ 1 位が THALES、2 位が
   F6S NETWORK —— どちらも EU プロジェクトの常連（26 / 20 件）で、自前の計算基盤を
   持つか、そもそも計算を買う主体ではない。**SKU B の買い手像の逆である。**

   合計が日本で妥当なのは、認定が 5 種類しかなく、そのどれもが設備投資に隣接して
   いるから。EU の call クラスは 13 あり、大半は SKU B と無関係なので、
   合計は『無関係な広さ』を積み上げる。

   したがって **base = 最も近いクラスの重み × 減衰 × スタッキング × 役割**。
   広さは `stacking-multiplier`（1.6 で頭打ち）からだけ入る。
   意図は『この法人の一番近い採択がどれだけ近いか』であって『何本持っているか』
   ではない。"
  [participations coordinator? as-of]
  (let [known (filter #(contains? topic-class-weights (:topic-class %)) participations)
        per-class (->> known
                       (group-by :topic-class)
                       (map (fn [[cls ps]]
                              ;; ⚠ `max-key` を使わない（数値しか比較できず、
                              ;; cljs では JS の `>` に落ちて黙って動き JVM で落ちる）。
                              ;; `sort-by` は `compare` なので両 runtime で同じ。
                              (let [latest (last (sort-by #(str (:event-date %)) ps))]
                                (* (get topic-class-weights cls)
                                   (jp/decay (jp/months-between (:event-date latest) as-of)))))))]
    (* (if (seq per-class) (reduce max per-class) 0.0)
       (jp/stacking-multiplier (count (distinct (map :topic-class known))))
       (if coordinator? coordinator-multiplier 1.0))))

(def boost-weights
  "部分被覆のシグナル -> 加点。**減点は無い。**

   `:ai-topic` が最大なのは、これが唯一『その資金で計算を回すか』に直接触れる
   シグナルだから。ただし被覆が 86.2% なので base には置けない。"
  {:ai-topic 2.0
   :sme 1.0
   :ec-contribution 0.5})

(def ec-contribution-floor
  "この額（EUR）を超える EC 拠出があれば加点する。**額に比例させない** ——
   比例させると大型コンソーシアムの 1 社が小さな deep-tech を常に上回るが、
   SKU B の買い手は後者である。閾値は『予算が付いた事業がある』の代理。
   ⚠ 仮定。"
  100000.0)

(defn score
  "1 法人分のシグナル -> 点数と、**どれが測れてどれが測れなかったか**。

   `signals` は
   `{:participations [...] :coordinator? bool :sme bool-or-nil
     :ai-tagged? bool-or-nil :ec-contribution number-or-nil}`。

   **nil は『測れなかった』であって『無い』ではない** —— `:intent/unmeasured` に
   名前が残り、点数には影響しない。"
  [signals as-of]
  (let [{:keys [participations coordinator? sme ai-tagged? ec-contribution]} signals
        base (base-score (or participations []) (boolean coordinator?) as-of)
        measured (cond-> #{:topics :recency :role}
                   (some? ai-tagged?) (conj :ai-topic)
                   (some? sme) (conj :sme)
                   (some? ec-contribution) (conj :ec-contribution))
        unmeasured (cond-> #{}
                     (nil? ai-tagged?) (conj :ai-topic)
                     (nil? sme) (conj :sme)
                     (nil? ec-contribution) (conj :ec-contribution))
        boost (cond-> 0.0
                (true? ai-tagged?) (+ (:ai-topic boost-weights))
                (true? sme) (+ (:sme boost-weights))
                (and (some? ec-contribution) (>= ec-contribution ec-contribution-floor))
                (+ (:ec-contribution boost-weights)))]
    {:source/dataset dataset
     :intent/base (/ (Math/round (* 1000.0 base)) 1000.0)
     :intent/boost (/ (Math/round (* 1000.0 boost)) 1000.0)
     :intent/measured (vec (sort (map name measured)))
     :intent/unmeasured (vec (sort (map name unmeasured)))
     :intent/as-of as-of}))

(def rank
  "`intent-score/rank` と同じ —— base の降順、同点は boost の降順。
   **base + boost で並べない。** 日本側と同じ関数を使う（規律を 2 箇所に
   置かない）。"
  jp/rank)
