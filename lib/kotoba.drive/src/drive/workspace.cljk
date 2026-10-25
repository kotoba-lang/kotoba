(ns drive.workspace
  "Portable tenant Drive metadata: hierarchy, ACL, versions, trash and quota."
  (:refer-clojure :exclude [ancestors descendants])
  (:require [kotoba.lang.text :as str]
            [drive.model :as model]))

(def permission-roles #{:owner :editor :commenter :viewer})

(defn workspace [id owner-id quota-bytes]
  {:drive.workspace/id id
   :drive.workspace/owner-id owner-id
   :drive.workspace/root-id "root"
   :drive.workspace/items
   {"root" (assoc (model/folder "root" {:drive/title "My Drive"})
                  :drive/parent-id nil :drive/trashed? false
                  :drive/permissions {owner-id :owner})}
   :drive.workspace/used-bytes 0
   :drive.workspace/share-links {}
   :drive.workspace/quota-bytes quota-bytes})

(defn item [ws id] (get-in ws [:drive.workspace/items id]))

(defn- ensure-parent [ws parent-id]
  (when-not (= :folder (:drive/kind (item ws parent-id)))
    (throw (ex-info "drive parent folder not found" {:parent-id parent-id}))))

(defn create-folder [ws id parent-id title actor-id]
  (ensure-parent ws parent-id)
  (-> ws
      (assoc-in [:drive.workspace/items id]
                (assoc (model/folder id {:drive/title title})
                       :drive/parent-id parent-id :drive/trashed? false
                       :drive/permissions {actor-id :owner}))
      (update-in [:drive.workspace/items parent-id :drive/children] conj id)))

(defn create-file [ws id parent-id attrs actor-id]
  (ensure-parent ws parent-id)
  (-> ws
      (assoc-in [:drive.workspace/items id]
                (assoc (model/file id attrs)
                       :drive/parent-id parent-id :drive/trashed? false
                       :drive/permissions {actor-id :owner}
                       :drive/versions []))
      (update-in [:drive.workspace/items parent-id :drive/children] conj id)))

(defn grant [ws item-id principal-id role]
  (when-not (contains? permission-roles role)
    (throw (ex-info "invalid drive permission role" {:role role})))
  (assoc-in ws [:drive.workspace/items item-id :drive/permissions principal-id] role))

(defn effective-role [ws item-id principal-id]
  (loop [id item-id seen #{}]
    (when (and id (not (contains? seen id)))
      (or (get-in ws [:drive.workspace/items id :drive/permissions principal-id])
          (recur (:drive/parent-id (item ws id)) (conj seen id))))))

(defn can-read? [ws item-id principal-id]
  (contains? permission-roles (effective-role ws item-id principal-id)))

(defn can-write? [ws item-id principal-id]
  (contains? #{:owner :editor} (effective-role ws item-id principal-id)))

(defn create-share-link [ws token item-id role expires-at]
  (when-not (contains? #{:viewer :commenter} role)
    (throw (ex-info "invalid public link role" {:role role})))
  (when-not (item ws item-id)
    (throw (ex-info "drive item not found" {:item-id item-id})))
  (assoc-in ws [:drive.workspace/share-links token]
            {:drive.share/token token :drive.share/item-id item-id
             :drive.share/role role :drive.share/expires-at expires-at}))

(defn revoke-share-link [ws token]
  (update ws :drive.workspace/share-links dissoc token))

(defn resolve-share-link [ws token now]
  (when-let [link (get-in ws [:drive.workspace/share-links token])]
    (when (or (nil? (:drive.share/expires-at link))
              (< now (:drive.share/expires-at link)))
      link)))

(defn add-version [ws item-id version]
  (let [size (:drive.version/size-bytes version 0)
        next-used (+ (:drive.workspace/used-bytes ws) size)]
    (when (> next-used (:drive.workspace/quota-bytes ws))
      (throw (ex-info "drive quota exceeded" {:used next-used
                                               :quota (:drive.workspace/quota-bytes ws)})))
    (-> ws
        (update-in [:drive.workspace/items item-id :drive/versions] conj version)
        (assoc-in [:drive.workspace/items item-id :drive/object-ref]
                  (:drive.version/object-ref version))
        (assoc :drive.workspace/used-bytes next-used))))

(defn ancestors
  "Every id above `item-id`, nearest first, root last.

  Guarded against a cycle rather than trusting there is none: `move` refuses
  to make one, but a workspace is data and can arrive from anywhere. A loop
  here would hang the process, which is a worse answer than a short list."
  [ws item-id]
  (loop [id (:drive/parent-id (item ws item-id)) seen #{} out []]
    (if (or (nil? id) (contains? seen id))
      out
      (recur (:drive/parent-id (item ws id)) (conj seen id) (conj out id)))))

(defn path
  "The items from the root down to `item-id`, inclusive — a breadcrumb.

  Titles rather than ids are the caller's business; this returns the items so
  it does not have to guess which field is wanted."
  [ws item-id]
  (when (item ws item-id)
    (conj (vec (reverse (map #(item ws %) (ancestors ws item-id))))
          (item ws item-id))))

(defn descendants
  "Every id below `item-id`, at any depth.

  By walking `:drive/children`, which is the structure being maintained,
  rather than by scanning every item for a matching parent — the two agree
  and the walk visits only the subtree."
  [ws item-id]
  (loop [queue (vec (:drive/children (item ws item-id))) seen #{} out []]
    (if-let [id (first queue)]
      (if (contains? seen id)
        (recur (subvec (vec queue) 1) seen out)
        (recur (into (subvec (vec queue) 1) (:drive/children (item ws id)))
               (conj seen id)
               (conj out id)))
      out)))

(defn trashed?
  "Whether `item-id` is in the trash — its own flag, or any ancestor's.

  **Derived rather than cascaded, and that is the whole design.** Trashing a
  folder by writing the flag onto every descendant means restoring it has to
  know which ones it wrote: a file already in the trash before its folder
  went there would come back out, having been restored by a fact about its
  parent. Recording which were cascaded is a second piece of state to keep in
  step with the first.

  Asking instead makes both operations exact. Trashing a folder hides
  everything under it because the answer changes for all of them at once;
  restoring reveals exactly what was visible before, because nothing else was
  ever touched. A file explicitly trashed inside a trashed folder stays
  trashed when the folder comes back — which is right, and is only possible
  because the two flags are independent."
  [ws item-id]
  (boolean
   (or (:drive/trashed? (item ws item-id))
       (some #(:drive/trashed? (item ws %)) (ancestors ws item-id)))))

(defn trash [ws item-id]
  (when (= item-id (:drive.workspace/root-id ws))
    (throw (ex-info "the root folder cannot be trashed" {:item-id item-id})))
  (assoc-in ws [:drive.workspace/items item-id :drive/trashed?] true))

(defn restore [ws item-id]
  (assoc-in ws [:drive.workspace/items item-id :drive/trashed?] false))

(defn move
  "Put `item-id` inside `parent-id`.

  Refuses to move a folder into itself or into its own descendant. That is
  not a strange thing for a user interface to ask for — a drag lands where it
  lands — and the result would be a subtree detached from the root, invisible
  to a listing that walks down and unreachable by a breadcrumb that walks up,
  with nothing marked wrong anywhere."
  [ws item-id parent-id]
  (ensure-parent ws parent-id)
  (when-not (item ws item-id)
    (throw (ex-info "drive item not found" {:item-id item-id})))
  (when (= item-id (:drive.workspace/root-id ws))
    (throw (ex-info "the root folder cannot be moved" {:item-id item-id})))
  (when (or (= item-id parent-id)
            (contains? (set (descendants ws item-id)) parent-id))
    (throw (ex-info "a folder cannot contain itself"
                    {:item-id item-id :parent-id parent-id})))
  (let [from (:drive/parent-id (item ws item-id))]
    (cond-> ws
      from (update-in [:drive.workspace/items from :drive/children]
                      (fn [children] (vec (remove #{item-id} children))))
      true (update-in [:drive.workspace/items parent-id :drive/children]
                      (fnil conj []) item-id)
      true (assoc-in [:drive.workspace/items item-id :drive/parent-id] parent-id))))

(defn children
  "What is directly inside `folder-id` and readable, trash excluded.

  In the order the folder records, which is the order things were put there —
  not sorted, because sorting is a question about a particular listing and
  this is the structure."
  [ws folder-id principal-id]
  (->> (:drive/children (item ws folder-id))
       (map #(item ws %))
       (filter #(and % (not (trashed? ws (:drive/id %)))
                     (can-read? ws (:drive/id %) principal-id)))
       vec))

(defn visible-items [ws principal-id]
  (->> (:drive.workspace/items ws) vals
       (filter #(and (not (trashed? ws (:drive/id %)))
                     (can-read? ws (:drive/id %) principal-id))) vec))

(defn search [ws principal-id query]
  (let [needle (str/lower (str (or query "")))]
    (->> (visible-items ws principal-id)
         (filter #(or (empty? needle)
                      (str/includes? (str/lower (str (:drive/title %))) needle)))
         (sort-by :drive/title) vec)))
