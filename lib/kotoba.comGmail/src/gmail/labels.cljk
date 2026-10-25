(ns gmail.labels
  "Gmail label listing/creation. REST v1, JVM-only."
  (:require [gmail.client :as client]))

#?(:clj
(defn list-labels
  ([] (list-labels {}))
  ([http-opts] (:labels (client/request! "/labels" http-opts)))))

#?(:clj
(defn create-label!
  ([label-name] (create-label! label-name {}))
  ([label-name http-opts]
   (client/request! "/labels" (assoc http-opts :method :post :body {:name label-name})))))

#?(:clj
(defn find-label
  "The label map for `label-name` (exact match), or nil if it doesn't exist
  yet."
  ([label-name] (find-label label-name {}))
  ([label-name http-opts]
   (first (filter #(= label-name (:name %)) (list-labels http-opts))))))

#?(:clj
(defn find-or-create-label!
  "The label id for `label-name`, creating it first if it doesn't exist
  yet."
  ([label-name] (find-or-create-label! label-name {}))
  ([label-name http-opts]
   (:id (or (find-label label-name http-opts) (create-label! label-name http-opts))))))

#?(:clj
(defn delete-label!
  "Delete a user label by id (Gmail's users.labels.delete, DELETE
  /labels/{id}) -- it's removed from every thread/message that carried it.
  Only user-created labels can be deleted; Gmail rejects a delete of a
  system label (INBOX/SENT/SPAM/...). The label id, not its display name --
  resolve one via find-label first if you only have the name. Gmail returns
  an empty success body, which client/request! surfaces as nil."
  ([label-id] (delete-label! label-id {}))
  ([label-id http-opts]
   (client/request! (str "/labels/" label-id) (assoc http-opts :method :delete)))))
