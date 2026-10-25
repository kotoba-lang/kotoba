(ns computeruse.tool
  "The computer tool — Anthropic computer-use action vocabulary
  (screenshot / key / type / type_secret / mouse_move / left_click /
  right_click / middle_click / double_click / left_click_drag* /
  scroll / cursor_position) dispatched onto an IComputer.

  Defined as an ordinary custom tool with an explicit input_schema, so
  it works through langchain.model's Anthropic adapter as-is. Hosts
  that prefer Anthropic's server-defined tool type
  ({:type \"computer_20250124\" …}) can send that wire format
  themselves and still dispatch results through `dispatch`.

  Credentials: there is intentionally NO action that types a literal
  password. `type_secret` takes a vault *reference* ({:item .. :field ..}
  or \"op://..\"), resolved through computeruse.vault/IVault and typed at
  the IComputer layer — the secret never enters the model, the message
  history, or the Datomic action log.

  (* drag is mapped to mouse-move + click for v0.1.)"
  (:require [computeruse.computer :as c]
            [computeruse.vault :as vault]))

(def actions
  ["screenshot" "key" "type" "type_secret" "mouse_move"
   "left_click" "right_click" "middle_click" "double_click"
   "scroll" "cursor_position"])

(defn dispatch
  "Executes one computer action on the computer. For `type_secret` a
  vault must be supplied (3-arity); the secret is resolved from
  `secret_ref` and typed without ever being returned.

  Returns the tool-result content (string, or whatever the host's
  screenshot returns)."
  ([computer action] (dispatch computer nil action))
  ([computer vault* {:keys [action coordinate text secret_ref
                            scroll_direction scroll_amount]}]
   (let [[x y] coordinate]
     (case action
       "screenshot" (c/-screenshot computer)
       "key" (c/-key! computer text)
       "type" (c/-type! computer text)
       "type_secret"
       (do
         (when-not vault*
           (throw (ex-info "type_secret needs a vault (pass :vault to the agent)" {})))
         (when-not secret_ref
           (throw (ex-info "type_secret needs secret_ref" {})))
         (let [secret (vault/-resolve vault* secret_ref)]
           (c/-type! computer secret)
           ;; never echo the value
           (str "Typed secret from " (pr-str secret_ref) " (" (count secret) " chars)")))
       "mouse_move" (c/-mouse-move! computer x y)
       "left_click" (c/-click! computer :left x y)
       "right_click" (c/-click! computer :right x y)
       "middle_click" (c/-click! computer :middle x y)
       "double_click" (c/-click! computer :double x y)
       "scroll" (c/-scroll! computer x y
                            (keyword (or scroll_direction "down"))
                            (or scroll_amount 3))
       "cursor_position" (str (c/-cursor-position computer))
       (throw (ex-info "Unknown computer action" {:action action}))))))

(defn computer-tool
  "langchain tool map over an IComputer.
  opts: {:width px :height px :vault IVault}
    :vault enables the `type_secret` action (credential injection from
    1Password/Bitwarden); omit it and type_secret errors out."
  [computer & [{:keys [width height vault] :or {width 1280 height 800}}]]
  {:name "computer"
   :description
   (str "Control a computer with a " width "x" height " display. "
        "Take a screenshot to see the screen; click/type/scroll/press keys. "
        "Coordinates are [x, y] pixels from the top-left. "
        "To fill a password/credential field, use action `type_secret` with a "
        "vault `secret_ref` (e.g. {\"item\":\"Vultr\",\"field\":\"password\"}) — "
        "never type a literal secret.")
   :schema {:type "object"
            :properties
            {:action {:type "string" :enum actions
                      :description "The action to perform."}
             :coordinate {:type "array" :items {:type "integer"}
                          :description "[x, y] for mouse actions."}
             :text {:type "string"
                    :description "Text to type, or key combo for `key` (e.g. ctrl+s, Return). Must NOT be a credential."}
             :secret_ref {:type "object"
                          :description
                          (str "Vault reference for `type_secret`. Either "
                               "{\"ref\":\"op://Vault/Item/field\"} or "
                               "{\"item\":\"..\",\"field\":\"password|username|totp\",\"vault\":\"..\"}. "
                               "The host resolves it from the vault; you never see the value.")
                          ;; `properties` is required: a bare object-typed param
                          ;; makes some tool-schema validators (Ollama) reject the
                          ;; whole request with a misleading 404 model-not-found.
                          :properties {:ref {:type "string"}
                                       :item {:type "string"}
                                       :field {:type "string"}
                                       :vault {:type "string"}}}
             :scroll_direction {:type "string" :enum ["up" "down" "left" "right"]}
             :scroll_amount {:type "integer"}}
            :required ["action"]}
   :fn (fn [args] (dispatch computer vault args))})
