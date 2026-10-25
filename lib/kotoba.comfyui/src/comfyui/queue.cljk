(ns comfyui.queue
  "Prompt queue — ComfyUI's /prompt + /queue + /history, minus the
  server. Synchronous, single-threaded (WASM premise): `run-next!`
  pops and executes one prompt; drive it from your host's event loop."
  (:require [comfyui.exec :as exec]))

(defn make-queue []
  (atom {:next-id 1 :pending [] :history []}))

(defn enqueue!
  "Queues a workflow. Returns the prompt id."
  ([q workflow] (enqueue! q workflow {}))
  ([q workflow opts]
   (let [{:keys [next-id]} @q]
     (swap! q (fn [s]
                (-> s
                    (update :next-id inc)
                    (update :pending conj {:id next-id :workflow workflow :opts opts}))))
     next-id)))

(defn pending [q] (mapv :id (:pending @q)))

(defn run-next!
  "Pops and executes the next prompt. Returns the history entry
  {:id .. :status :done|:error :results|:error ..}, or nil when idle."
  [q ctx]
  (when-let [{:keys [id workflow opts]} (first (:pending @q))]
    (swap! q update :pending #(vec (rest %)))
    (let [entry (try
                  (assoc (exec/execute ctx workflow opts) :id id :status :done)
                  (catch #?(:clj Exception :cljs :default) e
                    {:id id :status :error
                     :error (ex-message e) :data (ex-data e)}))]
      (swap! q update :history conj entry)
      entry)))

(defn run-all!
  "Drains the queue. Returns the history entries produced."
  [q ctx]
  (loop [out []]
    (if-let [entry (run-next! q ctx)]
      (recur (conj out entry))
      out)))

(defn history
  ([q] (:history @q))
  ([q id] (some #(when (= id (:id %)) %) (:history @q))))
