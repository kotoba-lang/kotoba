(ns comfyui.nodes.langchain
  "Node pack bridging to langchain-clj — ComfyUI-style graphs driving
  LLM calls. The model is injected at pack-construction time (same
  host-capability pattern as everything else)."
  (:require [langchain.model :as model]
            [langchain.message :as msg]
            [langchain.tool :as tool]))

(defn chat-node
  "STRING prompt (+ optional system) → STRING completion."
  [chat-model]
  {:type "ChatModel" :category "llm"
   :inputs {:prompt {:type "STRING"}
            :system {:type "STRING" :optional true}}
   :outputs [{:name "text" :type "STRING"}]
   :fn (fn [{:keys [prompt system]}]
         (let [messages (cond-> []
                          system (conj (msg/system system))
                          true (conj (msg/user prompt)))]
           [(:content (model/-generate chat-model messages {}))]))})

(defn tool-node
  "Wraps a langchain tool map as a node type: one input per schema
  property, one STRING output (the tool result)."
  [{:keys [name description schema] :as t}]
  {:type name :category "tool"
   :inputs (into {}
                 (map (fn [[prop spec]]
                        [(keyword prop)
                         {:type (case (:type spec)
                                  "integer" "INT"
                                  "number" "FLOAT"
                                  "boolean" "BOOLEAN"
                                  "string" "STRING"
                                  "*")}]))
                 (:properties schema))
   :outputs [{:name "result" :type "STRING"}]
   :fn (fn [args]
         (let [r (tool/execute [t] {:id "node" :name name :input args})]
           (when (:error? r)
             (throw (ex-info (:content r) {:tool name :args args})))
           [(:content r)]))})

(defn pack
  "Node pack for a model + tools."
  [chat-model tools]
  (into [(chat-node chat-model)] (map tool-node tools)))
