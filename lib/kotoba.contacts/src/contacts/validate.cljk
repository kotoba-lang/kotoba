(ns contacts.validate
  (:require [kotoba.lang.text :as str]))

(defn problem [severity code id msg]
  {:contacts/severity severity :contacts/code code :contacts/id id :contacts/msg msg})

(defn email? [s]
  (boolean (re-matches #"[^@\s]+@[^@\s]+\.[^@\s]+" (str s))))

(defn problems [book]
  (vec
   (concat
    (for [[id c] (:contacts/entries book)
          :when (str/blank? (:contacts/name c))]
      (problem :warning :contact/missing-name id "contact has no display name"))
    (for [[id c] (:contacts/entries book)
          email (:contacts/emails c)
          :when (not (email? email))]
      (problem :error :email/invalid id "invalid email address")))))

(defn valid? [book]
  (not-any? #(= :error (:contacts/severity %)) (problems book)))
