(ns kami.mangaka.qa.axes
  "QA 軸レジストリ — 漫画ページ/パネル品質の「何を測るか」の正本
  (ADR-2607165100)。

  3 系統の軸セットを data として持つ:

  - :rubric8    — composeScene3d topology 由来のパネル rubric (0-1)。
                  ai-gftd-mangaka の品質ループ (PanelQuality / Coscientist)
                  が使っている 8 軸 + 知覚軸 :facePresence。
  - :heuristic  — 退役 Python v10 scorer の決定論 heuristic 13 軸 (0-10)。
                  実装 (ピクセル計測) は移植していない — 軸の意味と scale の
                  正本のみ。計測値は consumer が供給する。
  - :jump       — 同 v10 の Jump 誌基準 VLM 審査 8 軸 (0-10、n_samples 平均)。

  v10 score JSON (mangaka-data/ghosthacker/resources/v10/v10-p00-score.json
  が現存する実サンプル) との相互運用は from-v10 / ->v10-key で行う。"
  (:require [kotoba.lang.text :as str]))

(def rubric8
  "パネル単位 rubric (0.0-1.0)。:facePresence は知覚レイヤ (VLM 顔カウント vs
  storyboard 期待 focal 数) が加える軸で、rubric prompt 自体には含まれない。"
  [{:axis :composition            :scale [0.0 1.0]}
   {:axis :silhouette             :scale [0.0 1.0]}
   {:axis :characterRecognizability :scale [0.0 1.0]}
   {:axis :framing                :scale [0.0 1.0]}
   {:axis :mangaShotGrammar       :scale [0.0 1.0]}
   {:axis :lightingDrama          :scale [0.0 1.0]}
   {:axis :actionClarity          :scale [0.0 1.0]}
   {:axis :emotionAlignment       :scale [0.0 1.0]}
   {:axis :facePresence           :scale [0.0 1.0] :source :perception}])

(def heuristic
  "v10 決定論 heuristic 軸 (0-10)。:polarity :lower-better の軸は「低いほど
  良い」実測値 (Python 側では減点材料として扱われた)。"
  [{:axis :character-visible   :v10 "character_visible"}
   {:axis :scene-continuity    :v10 "scene_continuity"}
   {:axis :panel-diversity     :v10 "panel_diversity"}
   {:axis :inking-quality      :v10 "inking_quality"}
   {:axis :composition-bimodal :v10 "composition_bimodal"}
   {:axis :background-white    :v10 "background_white" :polarity :lower-better}
   {:axis :bubble-legibility   :v10 "bubble_legibility"}
   {:axis :emotional-impact    :v10 "emotional_impact"}
   {:axis :artifact-freedom    :v10 "artifact_freedom"}
   {:axis :brightness-avg      :v10 "brightness_avg"}
   {:axis :silhouette-clarity  :v10 "silhouette_clarity"}
   {:axis :panel-coherence     :v10 "panel_coherence"}
   {:axis :wasted-lines        :v10 "wasted_lines" :polarity :lower-better}])

(def jump
  "v10 の Jump 誌基準 VLM 審査軸 (0-10)。"
  [{:axis :jump-character-anatomy      :v10 "jump_character_anatomy"}
   {:axis :jump-multi-character-quality :v10 "jump_multi_character_quality"}
   {:axis :jump-background-detail      :v10 "jump_background_detail"}
   {:axis :jump-composition-pose       :v10 "jump_composition_pose"}
   {:axis :jump-bubble-integration     :v10 "jump_bubble_integration"}
   {:axis :jump-manga-authenticity     :v10 "jump_manga_authenticity"}
   {:axis :jump-sfx-text               :v10 "jump_sfx_text"}
   {:axis :jump-environment-detail     :v10 "jump_environment_detail"}])

(def page18
  "完成ページ単位の VLM/構造レビュー軸 (0-100)。パネル単体の美麗さではなく、
  原作EDNへの忠実性、コマ割り、吹き出し、SFX、身体・小物の整合までを分離して
  測る。各軸を独立させることで、画像再生成が必要な問題と compose だけで直せる
  問題を混同しない。"
  [{:axis :prompt-alignment :repair :panel}
   {:axis :character-identity :repair :panel}
   {:axis :required-object-presence :repair :panel}
   {:axis :spatial-continuity :repair :panel}
   {:axis :object-orientation :repair :panel}
   {:axis :action-continuity :repair :panel}
   {:axis :dialogue-progression :repair :lettering}
   {:axis :page-composition :repair :layout}
   {:axis :panel-rhythm :repair :layout}
   {:axis :reading-flow :repair :layout}
   {:axis :lettering-quality :repair :lettering}
   {:axis :balloon-placement :repair :lettering}
   {:axis :sfx-integration :repair :lettering}
   {:axis :manga-expression :repair :mixed}
   {:axis :pose-physics :repair :panel}
   {:axis :speaker-tail-alignment :repair :lettering}
   {:axis :semantic-line-breaking :repair :lettering}
   {:axis :psychological-lettering :repair :lettering}])

(def all-sets {:rubric8 rubric8 :heuristic heuristic :jump jump :page18 page18})

(defn axis-names [set-key] (mapv :axis (all-sets set-key)))

(def ^:private v10->axis
  (into {} (for [a (concat heuristic jump) :when (:v10 a)] [(:v10 a) (:axis a)])))

(defn ->v10-key
  "kebab axis keyword → v10 JSON の snake_case 文字列 (未登録軸はそのまま
  snake 化)。"
  [axis]
  (or (some (fn [a] (when (= axis (:axis a)) (:v10 a))) (concat heuristic jump))
      (str/replace (name axis) "-" "_")))

(defn from-v10
  "v10 score JSON (keywordize 済み map — :scores/:total/:jump_tier_label/
  :heuristic_total/:jump_qa/:issues/:improvement_hints/:version) → 正規化 EDN:
  {:axes {<kebab-axis> <0-10>} :total <0-100> :heuristic-total <0-100>
   :jump {:total :label :verdict :issues :model :n-samples}
   :issues [...] :improvement-hints [...] :version ...}。
  未知の score キーは kebab 化して素通し (前方互換)。"
  [m]
  (let [scores (:scores m)
        axes (into {}
                   (keep (fn [[k v]]
                           (let [ks (name k)]
                             (when-not (= ks "jump_qa_total")
                               [(or (v10->axis ks)
                                    (keyword (str/replace ks "_" "-")))
                                v]))))
                   scores)
        jq (:jump_qa m)]
    (cond-> {:axes axes
             :total (:total m)
             :heuristic-total (:heuristic_total m)}
      (some? (get scores :jump_qa_total)) (assoc-in [:jump :axes-total] (get scores :jump_qa_total))
      jq (update :jump merge {:total (:total jq) :label (:label jq)
                              :verdict (:verdict jq) :issues (:issues jq)
                              :model (:model jq) :n-samples (:n_samples jq)})
      (:jump_tier_label m) (assoc-in [:jump :tier-label] (:jump_tier_label m))
      (:issues m) (assoc :issues (:issues m))
      (:improvement_hints m) (assoc :improvement-hints (:improvement_hints m))
      (:version m) (assoc :version (:version m)))))
