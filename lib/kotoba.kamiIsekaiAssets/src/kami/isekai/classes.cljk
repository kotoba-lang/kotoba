(ns kami.isekai.classes
  "Class/role accessories for kami.isekai.chargen — the small silhouette read
   (a helm, a crown, a satchel) that makes an adventurer, a king, and a
   merchant recognisable from the same base humanoid body plan.")

;; :accessory  :helm | :hood | :crown | :satchel | :emblem | :tiara |
;;             :holy-symbol | nil
;; :cloak      true → a back-mounted rect (knight tabard / mage robe / royal cape)
(def classes
  {:adventurer   {:label "Adventurer"   :accessory nil          :cloak false}
   :knight       {:label "Knight"       :accessory :helm        :cloak true}
   :mage         {:label "Mage"         :accessory :hood        :cloak true}
   :merchant     {:label "Merchant"     :accessory :satchel     :cloak false}
   :guild-master {:label "Guild Master" :accessory :emblem      :cloak false}
   :king         {:label "King"         :accessory :crown       :cloak true}
   :princess     {:label "Princess"     :accessory :tiara       :cloak true}
   ;; the dedicated healer — every isekai party has one distinct from the
   ;; offensive mage. No weapon in kami.isekai.equipment/class->weapons
   ;; (a priest's tool is holy magic, not a blade); pairs thematically with
   ;; kami.isekai.skills/:holy-heal.
   :priest       {:label "Priest"       :accessory :holy-symbol :cloak true}})

(defn class
  "id → the class's accessory map, or throws with the full list of known
   classes. See kami.isekai.races/race — same silent-fallback footgun,
   same fix."
  [id]
  (or (get classes id)
      (throw (ex-info (str "kami.isekai.classes: unknown class " (pr-str id)
                            " — known: " (sort (keys classes)))
                       {:class id :known (set (keys classes))}))))
