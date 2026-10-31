(ns freeboard.schema
  "malli schema = SSoT for the freeboard document. Validation/generation only
   (requires metosin/malli; not on the bb test path). See ADR-2606280200."
  (:require [malli.core :as m]))

(def Item
  [:map
   [:item/id :string]
   [:item/kind [:enum :sticky :text :shape :connector :frame :image :ink]]
   [:item/x number?] [:item/y number?]
   [:item/w number?] [:item/h number?]
   [:item/z int?]
   [:item/rotation {:optional true} number?]
   [:item/fill {:optional true} [:maybe :string]]
   [:item/stroke {:optional true} [:maybe :string]]
   [:text/runs {:optional true} [:vector [:map [:text :string]]]]
   [:shape/type {:optional true} :keyword]
   [:connector/from {:optional true} :string]
   [:connector/to {:optional true} :string]
   [:ink/points {:optional true} [:vector [:vector number?]]]
   [:image/blob {:optional true} [:maybe :map]]
   [:frame/title {:optional true} :string]
   [:vector/points {:optional true} [:vector [:vector number?]]]])

(def Board
  [:map
   [:freeboard/version int?]
   [:freeboard/title :string]
   [:freeboard/viewport [:map [:x number?] [:y number?] [:zoom number?]]]
   [:freeboard/items [:vector Item]]
   [:freeboard/next-z int?]])

(defn validate [board] (m/validate Board board))
(defn explain  [board] (m/explain  Board board))
