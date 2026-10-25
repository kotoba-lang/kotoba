(ns num.deno-arrow-upload-verify
  (:require [arrow.source :as arrow]
            [arrow.write :as aw]
            [columnar.bytes :as bytes]
            [columnar.vector :as cvec]
            [num.array :as arr]
            [num.arrow-gpu :as arrow-gpu]
            [num.core :as num]
            [num.deno-gpu :as gpu]))

(def values [1.25 -2.5 3.75 0.125])

(defn- fail! [message data]
  (throw (ex-info message data)))

(defn- arrow-source [type nullable? xs]
  (-> (aw/file {:fields [{:name "value" :type type :nullable? nullable?}]
                :batches [[(cvec/column type xs)]]})
      clj->js
      js/Uint8Array.from
      bytes/of-view
      arrow/open))

(defn- expect-refused! [f boundary]
  (try
    (f)
    (fail! "Arrow integration did not fail closed" {:boundary boundary})
    (catch :default error
      (when-not (= :num/arrow-upload-refused (:type (ex-data error)))
        (throw error)))))

(defn- verify-request [request source file-bytes]
  (let [backend (gpu/backend request)
        _ (expect-refused!
           #(arrow-gpu/borrow-f32-column
             (arrow/column-buffer-views
              (arrow-source :double false [1.0 2.0]) 0 "value"))
           :dtype)
        _ (expect-refused!
           #(arrow-gpu/borrow-f32-column
             (arrow/column-buffer-views
              (arrow-source :float true [1.0 nil]) 0 "value"))
           :validity)
        _ (expect-refused!
           #(arrow-gpu/upload-column backend source 0 "value" [3])
           :shape)
        baseline (gpu/backend-stats backend)
        {:keys [array column-view cpu-view]}
        (arrow-gpu/upload-column backend source 0 "value")
        native-values (bytes/native-view
                       (get-in column-view [:buffers 1 :view]))
        scaled (num/scal! 2.0 array)]
    (when-not (and (identical? (.-buffer file-bytes)
                                (.-buffer native-values))
                   (identical? (.-buffer file-bytes)
                               (.-buffer cpu-view))
                   (= values (vec (js/Array.from cpu-view))))
      (fail! "Arrow CPU view did not retain the file backing"
             {:cpu (vec (js/Array.from cpu-view))}))
    (-> (num/sum scaled)
        (.then
         (fn [sum]
           (arr/release! array)
           (let [after (gpu/backend-stats backend)
                 delta (fn [k] (- (get after k 0)
                                  (get baseline k 0)))]
             (when-not (and (< (Math/abs (- sum 5.25)) 1.0e-6)
                            (= 1 (delta :raw-uploads))
                            (= 16 (delta :raw-upload-bytes))
                            (= 0 (delta :raw-upload-padding-bytes))
                            (= 1 (delta :readbacks))
                            (= 4 (delta :readback-bytes))
                            (= (:live-buffers baseline)
                               (:live-buffers after))
                            (= (:live-bytes baseline)
                               (:live-bytes after)))
               (fail! "Arrow-to-GPU transfer contract failed"
                      {:sum sum :baseline baseline :after after}))
             (println "OK Arrow borrowed CPU view -> one WebGPU upload ->"
                      "device reduction -> 4-byte readback on"
                      (gpu/adapter-description request))))))))

(defn -main [& _]
  (let [encoded (aw/file
                 {:fields [{:name "value" :type :float :nullable? false}]
                  :batches [[(cvec/column :float values)]]})
        ;; One owned ingress buffer, corresponding to an HTTP/file host result.
        file-bytes (js/Uint8Array.from (clj->js encoded))
        source (arrow/open (bytes/of-view file-bytes))]
    (-> (gpu/request-device)
        (.then #(verify-request % source file-bytes))
        (.catch (fn [error]
                  (println "ERROR:" (or (.-stack error) (str error)))
                  (js/Deno.exit 1))))))

(set! *main-cli-fn* -main)
