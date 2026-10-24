(ns denchu.facts
  "電柱広告の法令面。**正本は `okugai.facts`（屋外広告物一般）に移した。**
  この ns はそこへの委譲 + 電柱固有の読み替えだけを持つ。

  なぜ委譲するのか: 屋外広告物法・条例・道路占用・建築基準法は媒体をまたいで
  同じものであり、電柱用とビルボード用に 2 つ持つと必ず片方だけが更新されて
  ずれる。**電柱はこの体系の中の 1 媒体でしかない**（`okugai.medium` の
  `:utility-pole`）。

  電柱固有なのは 1 点だけ: 多くの条例が電柱・街路灯柱への**貼り紙・貼り札・
  広告旗を禁止物件**として列挙する。これは無断の貼付物への規制であり、所有者の
  許諾と条例許可を経た巻付／袖看板とは別扱い —— **『電柱広告は条例で禁止』と
  要約しない。**"
  (:require [okugai.facts :as okugai]
            [okugai.medium :as medium]))

(def ^:const medium :utility-pole)

(defn- placement
  "電柱の掲出条件。`slot-kind` が分かっていれば道路上空の別を確定できる
  （袖看板は道路上空に出る、巻付は出ない）。分からなければ nil のままにして
  `okugai.facts` に undetermined と判定させる —— 推測で埋めない。"
  ([] (placement nil))
  ([slot-kind]
   {:medium medium
    :overhangs-road? (case slot-kind
                       :projecting true
                       :wrap false
                       nil)}))

(defn requirements [iso3] (okugai/requirements iso3))
(defn covered? [iso3] (okugai/covered? iso3))
(defn coverage [] (okugai/coverage))

(def prohibited-note
  "多数の条例が電柱・街路灯柱への貼り紙・貼り札・広告旗を禁止物件として列挙する。
  これは無断の貼付物に対する規制であり、所有者の許諾と条例許可を経た巻付／袖看板
  とは別扱い。")

(defn required-evidence
  "電柱掲出に要る証跡キー。`slot-kind` を渡すと道路占用の要否が確定する。"
  ([iso3] (okugai/required-evidence iso3 (placement)))
  ([iso3 slot-kind] (okugai/required-evidence iso3 (placement slot-kind))))

(defn missing-evidence
  "掲出提案が持つべき証跡のうち、まだ無いもの。管轄が未収録なら `:no-spec-basis`。"
  ([iso3 provided-evidence-keys]
   (okugai/missing-evidence iso3 (placement) provided-evidence-keys))
  ([iso3 slot-kind provided-evidence-keys]
   (okugai/missing-evidence iso3 (placement slot-kind) provided-evidence-keys)))

(defn road-occupancy-relevant?
  "その掲出面が道路占用許可の検討対象になりうるか。`true` は『必ず要る』ではなく
  『要否を所管に確認する必要がある』の意味（要否は道路管理者が決める）。"
  [iso3 slot-kind]
  (and (covered? iso3)
       (contains? (medium/triggers medium) :road-space)
       (= slot-kind :projecting)))
