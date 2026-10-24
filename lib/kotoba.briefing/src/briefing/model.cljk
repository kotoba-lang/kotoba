(ns briefing.model)

(def item-kinds #{:headline :summary :decision :action :risk :metric})

(defn briefing
  ([id] (briefing id {}))
  ([id attrs]
   (merge {:briefing/id id
           :briefing/type :briefing
           :briefing/title id
           :briefing/items []}
          attrs)))

(defn item [id kind attrs]
  (merge {:briefing/id id
          :briefing/kind kind
          :briefing/text ""}
         attrs))

(defn add-item [b it]
  (update b :briefing/items conj it))

(defn items-by-kind [b kind]
  (->> (:briefing/items b)
       (filter #(= kind (:briefing/kind %)))
       (sort-by :briefing/id)
       vec))

(defn decisions [b]
  (items-by-kind b :decision))

(defn actions [b]
  (items-by-kind b :action))

(defn seed-briefing []
  (-> (briefing "weekly" {:briefing/title "Weekly briefing"})
      (add-item (item "h1" :headline {:briefing/text "Workspace apps are split into CLJC repos"}))
      (add-item (item "d1" :decision {:briefing/text "Use GitHub Pages default domains for preview"}))
      (add-item (item "a1" :action {:briefing/text "Keep kotoba-lang Pages local"}))))
