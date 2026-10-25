(ns comfyui.viz
  "Workflow → Mermaid flowchart string."
  (:require [kotoba.lang.text :as str]
            [comfyui.workflow :as wf]))

(defn- nid [id] (str "n" (str/replace id #"[^A-Za-z0-9_]" "_")))

(defn mermaid [workflow]
  (let [lines
        (concat
         ["flowchart TD"]
         (for [[id {:keys [class_type]}] (sort-by key workflow)]
           (str "  " (nid id) "[\"" id ": " class_type "\"]"))
         (for [[id {:keys [inputs]}] (sort-by key workflow)
               [in-name v] (sort-by key inputs)
               :when (wf/link? v)
               :let [[src idx] v]]
           (str "  " (nid src) " -->|" idx "→" (name in-name) "| " (nid id))))]
    (str/join "\n" lines)))
