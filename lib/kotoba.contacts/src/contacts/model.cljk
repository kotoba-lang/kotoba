(ns contacts.model
  (:require [kotoba.lang.text :as str]))

(defn book
  ([id] (book id {}))
  ([id attrs]
   (merge {:contacts/id id
           :contacts/type :book
           :contacts/entries {}}
          attrs)))

(defn contact [id attrs]
  (merge {:contacts/id id
          :contacts/kind :person
          :contacts/name id
          :contacts/emails []
          :contacts/handles {}
          :contacts/tags #{}}
         attrs))

(defn add-contact [book c]
  (assoc-in book [:contacts/entries (:contacts/id c)] c))

(defn contact-by-id [book id]
  (get-in book [:contacts/entries id]))

(defn add-email [book id email]
  (update-in book [:contacts/entries id :contacts/emails] (fnil conj []) (str/lower email)))

(defn add-handle [book id network handle]
  (assoc-in book [:contacts/entries id :contacts/handles network] handle))

(defn search-name [book q]
  (let [needle (str/lower q)]
    (->> (vals (:contacts/entries book))
         (filter #(str/includes? (str/lower (:contacts/name %)) needle))
         (sort-by :contacts/id)
         vec)))

(defn seed-book []
  (-> (book "gftd-contacts")
      (add-contact (contact "jun" {:contacts/name "Jun Kawasaki"
                                   :contacts/emails ["jun@example.invalid"]
                                   :contacts/tags #{"owner"}}))))
