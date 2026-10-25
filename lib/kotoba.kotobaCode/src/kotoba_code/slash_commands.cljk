(ns kotoba-code.slash-commands
  (:require [kotoba.lang.text :as str]))

(def catalog
  [{:name "/help" :usage "/help" :description "Show commands"}
   {:name "/clear" :usage "/clear" :description "Clear the visible conversation"}
   {:name "/resume" :usage "/resume" :description "Resume an interrupted durable loop"}
   {:name "/status" :usage "/status" :description "Show git working-tree status"}
   {:name "/doctor" :usage "/doctor" :description "Run readiness diagnostics"}
   {:name "/loop" :usage "/loop [resume|stop|reset]" :description "Inspect or control the durable loop"}
   {:name "/agents" :usage "/agents [id|cancel|diff|apply|cleanup id]" :description "Manage background agents"}
   {:name "/subtask" :usage "/subtask [--write] <task>" :description "Start an isolated background agent"}
   {:name "/model" :usage "/model [model-id]" :description "Show or select a model/backend"}
   {:name "/codex" :usage "/codex [model]" :description "Use Codex subscription"}
   {:name "/claude" :usage "/claude [model]" :description "Use Claude subscription"}
   {:name "/openrouter" :usage "/openrouter [model]" :description "Use OpenRouter"}
   {:name "/exit" :usage "/exit" :description "Exit kotoba-code"}])

(def help-text
  (str/join "\n" (map #(str (:usage %) " — " (:description %)) catalog)))

(defn parse-command [text]
  (let [[token & args] (str/split (str/trim (or text "")) #"\s+")]
    (when (str/starts-with? (or token "") "/")
      {:command token :args args})))

(defn suggestions [input]
  (let [q (str/lower (str/trim (or input "")))]
    (if (str/starts-with? q "/")
      (->> catalog
           (filter #(str/starts-with? (:name %) (first (str/split q #"\s+"))))
           (take 6)
           vec)
      [])))
