(ns denchu.slot
  "電柱広告の掲出面（slot）モデル。

  日本の電柱広告は主に2形態で、これは代理店各社が自社サイトで公開して
  いる区分そのもの（テルウェル東日本『\"袖広告\"と\"巻広告\"2タイプ』）:

    :wrap       巻付広告（巻広告）— 柱に巻き付ける。2枚1組で、歩行者の
                目線高さに近い位置に付く（東電タウンプランニング記載）。
    :projecting 袖広告（袖看板）— 柱から直角に張り出す。車道側から視認
                しやすい代わりに道路上空へ突き出すため、屋外広告物許可に
                加えて道路占用許可が絡む（`denchu.facts` 参照）。

  **在庫数を計算しない。** 1本の柱に何面掛かっているか、空きがあるか、
  そもそも掲出可能な柱かは、所有者と代理店だけが知っている。この ns は
  『どの面がありうるか』の型と、代理店回答を受け取る器を持つだけで、
  空き数を推定する関数を**意図的に持たない** — 推定した空き数は必ず
  「在庫がある」という嘘になるため。"
  )

(def slot-kinds
  {:wrap {:slot/kind :wrap
          :slot/name-ja "巻付広告（巻広告）"
          :slot/panels 2
          :slot/panels-note "2枚1組で柱に巻き付ける（東電タウンプランニング記載）"
          :slot/typical-audience :pedestrian
          :slot/overhangs-road? false
          :slot/source-url "https://www.ttplan.co.jp/service/ad_pole/"
          :slot/as-of "2026-08-04"}
   :projecting {:slot/kind :projecting
                :slot/name-ja "袖広告（袖看板）"
                :slot/panels 1
                :slot/typical-audience :road
                :slot/overhangs-road? true
                :slot/source-url "https://www.telwel-east.co.jp/denchu-koukoku/fee/"
                :slot/as-of "2026-08-04"}})

(defn slot-kind? [k] (contains? slot-kinds k))

(defn describe [k] (get slot-kinds k))

(defn requires-road-occupancy?
  "道路占用許可の検討が要る面か。`true` は『必ず要る』ではなく
  『要否を所管に確認する必要がある』の意味（要否は道路管理者が決める）。"
  [k]
  (boolean (:slot/overhangs-road? (describe k))))

(defn candidate-slots
  "柱 1 本に**ありうる**面の一覧。実在の空き面ではない。
  代理店回答が無い限り全て `:availability :unknown` で返す。"
  [{:keys [pole/id pole/owner]}]
  (mapv (fn [k]
          (assoc (describe k)
                 :slot/pole-id id
                 :slot/owner owner
                 :slot/availability :unknown
                 :slot/availability-note "空きの有無は所有者/代理店の回答でのみ確定する"))
        (sort (keys slot-kinds))))

(defn apply-agency-answer
  "代理店から返ってきた実際の可否を面に載せる。ここが `:unknown` から
  出られる唯一の経路で、必ず `:answer/source`（誰が答えたか）を要求する。"
  [slot {:keys [availability source answered-at note]}]
  (when-not (contains? #{:available :occupied :not-offered} availability)
    (throw (ex-info "unknown availability" {:availability availability})))
  (when-not (and (string? source) (seq source))
    (throw (ex-info "agency answer requires a source" {:slot slot})))
  (assoc slot
         :slot/availability availability
         :slot/availability-note note
         :slot/answer {:answer/source source
                       :answer/answered-at answered-at}))
