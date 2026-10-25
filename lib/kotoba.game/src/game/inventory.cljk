(ns game.inventory
  "Inventory system: items, equip/unequip, pickup.

  Restored from kami-game (kotoba-lang/kami-engine, deleted PR #82),
  per ADR-2607010930. Ported 1:1 from `kami-game/src/inventory.rs`.")

;; ItemDef: {:id :name :item-type :rarity :stackable?}
;; InventorySlot: {:item :quantity :equipped?}
;; Inventory: {:slots [InventorySlot ...] :max-slots}

(def item-types
  "Rust `ItemType` enum values."
  #{:weapon :armor :consumable :material :key})

(def rarities
  "Rust `Rarity` enum values."
  #{:common :uncommon :rare :epic :legendary})

(defn inventory-new
  [max-slots]
  {:slots [] :max-slots max-slots})

(defn add-item
  "Add `item` (quantity `qty`) to `inv`. Stacks onto an existing slot with
  the same item id if `:stackable?` is true. Returns [added? inv']."
  [inv item qty]
  (let [slots (:slots inv)]
    (if (:stackable? item)
      (if-let [idx (some (fn [[i s]] (when (= (:id (:item s)) (:id item)) i))
                          (map-indexed vector slots))]
        [true (update-in inv [:slots idx :quantity] + qty)]
        (if (>= (count slots) (:max-slots inv))
          [false inv]
          [true (update inv :slots conj {:item item :quantity qty :equipped? false})]))
      (if (>= (count slots) (:max-slots inv))
        [false inv]
        [true (update inv :slots conj {:item item :quantity qty :equipped? false})]))))

(defn remove-item
  "Remove up to `qty` of item `item-id` from `inv`. Returns [removed-count inv']."
  [inv item-id qty]
  (let [[slots' removed]
        (reduce
         (fn [[acc removed] slot]
           (if (and (= (:id (:item slot)) item-id) (< removed qty))
             (let [take (min (:quantity slot) (- qty removed))
                   qty' (- (:quantity slot) take)
                   removed' (+ removed take)]
               [(if (pos? qty') (conj acc (assoc slot :quantity qty')) acc) removed'])
             [(conj acc slot) removed]))
         [[] 0]
         (:slots inv))]
    [removed (assoc inv :slots slots')]))

(defn equip
  "Equip item by id. Returns [equipped? inv']."
  [inv item-id]
  (let [slots (:slots inv)
        idx (some (fn [[i s]] (when (= (:id (:item s)) item-id) i))
                  (map-indexed vector slots))]
    (if idx
      [true (assoc-in inv [:slots idx :equipped?] true)]
      [false inv])))

(defn total-items
  [inv]
  (reduce + (map :quantity (:slots inv))))

(defn demo-items
  "Predefined items for demo."
  []
  [{:id "gem-blue" :name "Blue Gem" :item-type :material :rarity :rare :stackable? true}
   {:id "sword-iron" :name "Iron Sword" :item-type :weapon :rarity :common :stackable? false}
   {:id "potion-hp" :name "Health Potion" :item-type :consumable :rarity :common :stackable? true}])
