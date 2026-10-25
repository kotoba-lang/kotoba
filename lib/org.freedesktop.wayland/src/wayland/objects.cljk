;; Object table and id allocation. wayland core protocol §2.4:
;; object ids are unique per connection; server-generated ids are at or
;; above 0xff000000; ids are not reused after destruction.
(ns wayland.objects)

(def server-id-min 0xff000000)

(def empty-table
  {:objects {}              ; id -> {:interface/name n :state state :version v}
   :next-client-id 1
   :dead-ids #{}})

(defn alloc-state [id]
  (if (>= id server-id-min) :server-assigned :client-assigned))

(defn create
  "Put a new object in the table. Fails closed on id reuse — §2.4 says ids
   are unique; a reuse is a caller bug, not a silent overwrite."
  [table id iface-name version]
  (cond
    (contains? (:objects table) id)
    (throw (ex-info "object id already live" {:phase :wayland/create :id id}))
    (contains? (:dead-ids table) id)
    (throw (ex-info "object id reuse after destruction — not allowed" {:phase :wayland/create :id id}))
    :else
    (-> table
        (assoc-in [:objects id] {:interface/name iface-name
                                 :state :live
                                 :version version
                                 :origin (alloc-state id)})
        (assoc :next-client-id (if (>= id server-id-min)
                                 (:next-client-id table)
                                 (max id (inc id)))))))

(defn destroy
  "Mark an object dead. §2.5: a destroyed object id is invalid; using it is
   a protocol error. Double-destroy is likewise an error, never a no-op."
  [table id]
  (let [obj (get-in table [:objects id])]
    (cond
      (nil? obj)
      (throw (ex-info "destroy of unknown object" {:phase :wayland/destroy :id id}))
      (not= :live (:state obj))
      (throw (ex-info "destroy of already-dead object" {:phase :wayland/destroy :id id}))
      :else
      (-> table
          (assoc-in [:objects id :state] :dead)
          (update :dead-ids conj id)))))

(defn live? [table id]
  (= :live (get-in table [:objects id :state])))

(defn object-of [table id]
  (get-in table [:objects id]))
