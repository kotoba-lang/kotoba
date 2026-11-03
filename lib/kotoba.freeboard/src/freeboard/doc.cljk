(ns freeboard.doc
  "Cross-tool canvas-document envelope, mirroring the **Genko (原稿) document
   structure** used by mangaka (`kami-engine-sdk/.../genko-embed.ts`):

     {:name … :pages [{:id … :name … :nodes [{:id … :type … :visible … :data …}]}]
      :activePageIdx 0}

   Genko itself is authored in TypeScript and is manga-specific (its node types
   are stroke/panel/tone/text/fukidashi/ai-image); freeboard reuses the SAME
   envelope (pages → nodes with id/type/visible/data) but keeps its own generic
   board node types in `:type` (sticky/shape/text/connector/ink/frame/image) and
   the item payload in `:data`. So a freeboard board and a Genko page share one
   document shape — they interoperate at the envelope level while each keeps its
   domain types. Pure, round-trippable. See ADR-2606280200.

   This is the *document* counterpart to `freeboard.render-ir` (the shared
   *render* surface): board ⇄ doc here, board → render-IR there."
  (:require [freeboard.board :as b]))

(defn item->node
  "A board item → a Genko-style node {:id :type :visible :data}. The item's
   geometry+payload (minus id/kind) lives in :data; kind → :type (string)."
  [it]
  {:id      (:item/id it)
   :type    (name (:item/kind it))
   :visible (not (:item/hidden? it false))
   :data    (dissoc it :item/id :item/kind :item/hidden?)})

(defn node->item
  "Inverse of item->node."
  [n]
  (cond-> (merge (:data n) {:item/id (:id n) :item/kind (keyword (:type n))})
    (false? (:visible n)) (assoc :item/hidden? true)))

(defn board->doc
  "freeboard board → the shared canvas-document EDN (Genko envelope). The
   viewport rides on the page so a doc fully reconstructs the board."
  [board]
  {:name          (:freeboard/title board "Board")
   :pages         [{:id       "page-1"
                    :name     "Board"
                    :viewport (:freeboard/viewport board)
                    :nodes    (mapv item->node (:freeboard/items board))}]
   :activePageIdx 0})

(defn doc->board
  "Shared canvas-document EDN → freeboard board (reads the active page)."
  [doc]
  (let [page (nth (:pages doc) (:activePageIdx doc 0))]
    (cond-> (assoc (b/new-board (:name doc "Board"))
                   :freeboard/items (mapv node->item (:nodes page)))
      (:viewport page) (assoc :freeboard/viewport (:viewport page)))))
