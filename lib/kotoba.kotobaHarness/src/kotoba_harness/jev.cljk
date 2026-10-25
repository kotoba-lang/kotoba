(ns kotoba-harness.jev
  "OpenRouter Decisions API client for TypeSafe Jev. The key is passed in
  explicitly and never written to receipts."
  (:require [clojure.string :as str]))

(def endpoint "https://openrouter.ai/api/alpha/decisions")
(def model "typesafe/jev-1.13")

(defn decide-fn
  ([api-key] (decide-fn api-key js/fetch))
  ([api-key fetch-fn]
   (when (str/blank? (str api-key)) (throw (ex-info "OPENROUTER_API_KEY is unavailable" {:reason :missing-credential})))
   (fn [{:keys [state instructions criteria]}]
     (let [controller (js/AbortController.) timer (js/setTimeout #(.abort controller) 30000)]
       (-> (fetch-fn endpoint #js {:method "POST" :signal (.-signal controller)
                                   :headers #js {"authorization" (str "Bearer " api-key) "content-type" "application/json"
                                                 "X-OpenRouter-Title" "kotoba-harness"}
                                   :body (.stringify js/JSON (clj->js {:model model :state state
                                                                       :questions {"next_action" {:type "choice" :instructions instructions
                                                                                                  :criteria criteria}}}))})
           (.then (fn [r] (if (.-ok r) (.json r)
                              (throw (ex-info "Jev HTTP error" {:reason :provider-http-error :status (.-status r)})))))
           (.then (fn [raw]
                    (let [r (js->clj raw :keywordize-keys true) a (get-in r [:answers :next_action])]
                      (when-not (and (string? (:model r)) (re-matches #"typesafe/jev-1\.13(?:-[A-Za-z0-9._-]+)?" (:model r))
                                     (= "choice" (:type a)) (string? (:choice a)) (map? (:probabilities a)))
                        (throw (ex-info "Jev response refused" {:reason :provider-shape :model (:model r)})))
                      {:choice (:choice a) :confidence (:confidence a) :model (:model r) :request-id (:id r)
                       :usage (select-keys (:usage r) [:input_tokens :output_tokens :cost])
                       :probabilities (into {} (map (fn [[k v]] [(name k) v]) (:probabilities a)))})))
           (.finally #(js/clearTimeout timer)))))))
