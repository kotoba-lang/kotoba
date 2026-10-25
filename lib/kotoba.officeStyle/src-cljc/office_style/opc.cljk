(ns office-style.opc
  "JVM-backed reader for pptx style-oriented XML parts."
  (:require [kotoba.lang.text :as str])
  #?(:clj (:import [java.io ByteArrayInputStream]
                   [java.util.zip ZipInputStream])))

#?(:clj
   (defn- read-entry [^ZipInputStream zip]
     (let [buf (byte-array 8192)
           out (java.io.ByteArrayOutputStream.)]
       (loop []
         (let [n (.read zip buf)]
           (when (pos? n)
             (.write out buf 0 n)
             (recur))))
       (.toString out "UTF-8"))))

(defn open-pptx [bytes]
  #?(:clj
     (with-open [zip (ZipInputStream. (ByteArrayInputStream. bytes))]
       (loop [entries {}]
         (if-let [entry (.getNextEntry zip)]
           (let [name (.getName entry)]
             (recur (if (or (str/ends-with? name ".xml")
                            (str/ends-with? name ".rels"))
                      (assoc entries name (read-entry zip))
                      entries)))
           {:office-style/kind :pptx
            :office-style/entries entries})))
     :cljs
     (throw (ex-info "open-pptx requires a host zip implementation" {:feature :office-style/opc}))))
