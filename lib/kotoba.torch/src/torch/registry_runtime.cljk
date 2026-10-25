(ns torch.registry-runtime
  "Serialized mutable facade around the side-effecting model registry."
  (:require [torch.model-registry :as registry]))

(defn runtime [registry*]
  {:state (atom registry*)
   #?@(:clj [:lock (Object.)])})

(defn- transact! [runtime* operation]
  #?(:clj
     (locking (:lock runtime*)
       (let [result (operation @(:state runtime*))]
         (reset! (:state runtime*) (:registry result))
         (dissoc result :registry)))
     :cljs
     ;; JavaScript callbacks run to completion between event-loop turns. The
     ;; registry loader is deliberately synchronous (GPU dispatch may enqueue
     ;; work but does not await), so no second mutation can interleave here.
     (let [result (operation @(:state runtime*))]
       (reset! (:state runtime*) (:registry result))
       (dissoc result :registry))))

(defn acquire! [runtime* name now-ms]
  (transact! runtime* #(registry/acquire % name now-ms)))

(defn release! [runtime* name now-ms keep-alive-ms]
  (transact! runtime*
             #(hash-map :registry
                        (registry/release % name now-ms keep-alive-ms))))

(defn expire! [runtime* now-ms]
  (transact! runtime*
             #(hash-map :registry (registry/expire % now-ms))))

(defn unload!
  ([runtime* name] (unload! runtime* name false))
  ([runtime* name force?]
   (transact! runtime*
              #(hash-map :registry (registry/unload % name force?)))))

(defn copy-model! [runtime* source destination]
  (transact! runtime*
             #(hash-map :registry
                        (registry/copy-model % source destination))))

(defn delete-model! [runtime* name]
  (transact! runtime*
             #(hash-map :registry (registry/delete-model % name))))

(defn snapshot [runtime*] @(:state runtime*))
(defn tags [runtime*] (registry/tags (snapshot runtime*)))
(defn running-models [runtime*] (registry/running-models (snapshot runtime*)))
(defn describe [runtime* name] (registry/describe (snapshot runtime*) name))
(defn stats [runtime*] (registry/stats (snapshot runtime*)))
