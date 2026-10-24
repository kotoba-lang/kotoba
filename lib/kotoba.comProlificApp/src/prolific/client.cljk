(ns prolific.client
  "HTTP side of the Prolific API. Everything decision-shaped lives in
  `prolific.core`; this namespace only fetches and posts.

  Runs under nbb or any fetch-capable JS host."
  (:require [prolific.core :as core]))

(def default-base "https://api.prolific.com/api/v1")

(defn base-url
  "PROLIFIC_API_BASE exists so the resolution and guard paths can be exercised
  against a stub; production never sets it."
  []
  (or (some-> js/process.env.PROLIFIC_API_BASE not-empty) default-base))

(defn- token []
  (or (some-> js/process.env.PROLIFIC_TOKEN not-empty)
      (throw (js/Error. "PROLIFIC_TOKEN is not set"))))

(defn request
  "Promise of {:ok bool :status int :body …}. Never throws on a non-2xx —
  the caller decides whether a 404 is fatal."
  ([method path] (request method path nil))
  ([method path payload]
   (let [opts (cond-> #js {:method method
                           :headers #js {"Authorization" (str "Token " (token))
                                         "Content-Type" "application/json"}}
                payload (doto (aset "body" (js/JSON.stringify (clj->js payload)))))]
     (-> (js/fetch (str (base-url) path) opts)
         (.then (fn [res]
                  (-> (.text res)
                      (.then (fn [text]
                               {:ok (.-ok res)
                                :status (.-status res)
                                :body (try (js->clj (js/JSON.parse text) :keywordize-keys true)
                                           (catch :default _ {:raw text}))})))))))))

;; NOTE: `.then` silently ignores a non-function argument, and a ClojureScript
;; keyword is an object, not a function — `(.then p :results)` passes the whole
;; body through untouched instead of extracting. Always wrap in an `fn`.
(defn- unwrap-results [p]
  (.then p (fn [{:keys [body]}] (:results body))))

(defn me [] (request "GET" "/users/me/"))

(defn filters
  "Every filter available to this account, with its opaque choice ids."
  []
  (unwrap-results (request "GET" "/filters/")))

(defn resolve-languages
  "Promise of `prolific.core/resolve-languages` against the live filter list."
  [wanted]
  (.then (filters) #(core/resolve-languages % wanted)))

(defn create-study [payload] (request "POST" "/studies/" payload))

(defn get-study [study-id] (request "GET" (str "/studies/" study-id "/")))

(defn publish-study [study-id]
  (request "POST" (str "/studies/" study-id "/transition/") {:action "PUBLISH"}))

(defn submissions
  "Documented path is /submissions/?study=… — /studies/{id}/submissions/ does
  not exist."
  [study-id]
  (unwrap-results (request "GET" (str "/submissions/?study=" study-id "&page_size=100"))))

(defn approve-submission
  "Idempotent per the API docs, so a re-run after a partial failure is safe."
  [submission-id]
  (request "POST" (str "/submissions/" submission-id "/transition/") {:action "APPROVE"}))

(defn approve-all
  "Approve every submission awaiting review — including the ones that never
  reached a completion code, which auto-approval cannot pay. Promise of
  {:approved n :failed [ids]}."
  [study-id]
  (-> (submissions study-id)
      (.then (fn [subs]
               (let [pending (core/awaiting-review subs)]
                 (-> (js/Promise.all
                      (clj->js (map (fn [s]
                                      (.then (approve-submission (:id s))
                                             (fn [r] [(:id s) (:ok r)])))
                                    pending)))
                     (.then (fn [pairs]
                              (let [pairs (js->clj pairs)]
                                {:total (count subs)
                                 :approved (count (filter second pairs))
                                 :failed (vec (map first (remove second pairs)))})))))))))
