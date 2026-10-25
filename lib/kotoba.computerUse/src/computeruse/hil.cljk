(ns computeruse.hil
  "computer-use adapter for the shared hil approval contract."
  (:require [hil.core :as hil]))

(defn approval-tool
  "Expose a human confirmation as a model-callable tool. Only the compact
  request fields are accepted, so screenshots and browser content cannot be
  copied into the alert by accident."
  [prompt]
  {:name "request_human_approval"
   :description (str "Ask the account holder for approval only when an external or "
                     "legally binding action is immediately required. Never include "
                     "credentials, MFA codes, API keys, or page contents.")
   :schema {:type "object"
            :properties {:id {:type "string"}
                         :title {:type "string"}
                         :summary {:type "string"}
                         :action {:type "string"}
                         :impact {:type "string"}
                         :input_label {:type "string"}}
            :required ["id" "title" "summary" "action"]}
   :fn (fn [{:keys [input_label] :as request}]
         (let [result (hil/request-with-input!
                       prompt
                       (cond-> (dissoc request :input_label)
                         input_label (assoc :input-label input_label)))]
           (cond-> {:decision (name (:decision result))
                    :approved (= :approved (:decision result))}
             (:input result) (assoc :input (:input result)))))})
