(ns murakumo-studio.ui
  "murakumo-studio's view tree. Structural chrome (panel/list-view/tab-bar/
  badge/divider) comes from appkit.core (desktop binding) / kotoba-ui.core
  (kotoba-lang default design system, ADR-2607022800). Interactive controls
  that need a live reagent handler (button/text-field/menu-select/toggle) use
  kotoba-ui's `:on-*` escape hatches directly — two components don't support
  the interactivity this app needs, so we work around them with small
  hand-rolled equivalents styled via kotoba-ui's exposed `class-name`
  (mirroring gftdcojp/manimani/src/manimani/ui.cljc's `sbutton`):
    - `button` only supports shitsuke's :act SSR contract, no on-click at all.
    - `text-area` (shitsuke.components/textarea) renders `value` as DOM
      children instead of a `value` prop, so React treats it as effectively
      uncontrolled — typing works (native DOM mutation), but programmatic
      resets (e.g. clearing the chat input after send) never reach the DOM.
      Confirmed via a live browser session: after `swap!`-ing :input back to
      \"\", the atom read back \"\" but the visible <textarea> kept showing the
      old text even across an unmount/remount. `text-field` (<input>) does
      NOT have this bug — shitsuke.components/input sets :value as a real
      prop — so only textarea needs the workaround.
    - `model-select` (shitsuke.components/select) has the same class of bug:
      the `<select>` itself carries no `:value` prop (uncontrolled), each
      `<option>` instead gets a `:selected (= v value)` attribute, and the
      `<option>`s have no React `:key` — confirmed live: real, reproducible
      React warnings (\"Each child in a list should have a unique key prop\",
      \"Use the defaultValue or value props on <select> instead of setting
      selected on <option>\") on every render, not just a one-off."
  (:require [kotoba.lang.text] [appkit.core :as shape]
            [kotoba-ui.core :as ui]
            [murakumo-studio.state :as state]
            [murakumo-studio.client :as client]))

;; ---------------------------------------------------------------------------
;; small local helpers

(defn- btn
  ([label on-click] (btn label on-click {}))
  ([label on-click {:keys [disabled? class]}]
   [:button {:class (str (ui/class-name :button) (when class (str " " class)))
             :type "button"
             :disabled (boolean disabled?)
             :on-click on-click}
    label]))

(defn- text-area
  "Properly controlled replacement for kotoba-ui's text-area (see ns
  docstring) — same DOM shape (outer div wrapper the CSS targets via a
  descendant selector, `.liquid-glass__text-area textarea`), but the
  <textarea>'s value is a real React prop so programmatic resets work."
  [{:keys [value rows placeholder on-input]}]
  [:div {:class (ui/class-name :text-area)}
   [:textarea {:value (or value "") :rows (or rows 6) :placeholder placeholder
               :on-change on-input}]])

(defn- model-select
  "Properly controlled replacement for kotoba-ui's menu-select (see ns
  docstring) — same DOM shape (`.liquid-glass__menu-select` wrapper + a
  specular decoration span the CSS already targets), but the <select>
  carries a real `value` prop and each <option> has a React :key."
  [options {:keys [value on-change]}]
  [:div {:class (ui/class-name :menu-select)}
   [:select {:value (or value "") :on-change on-change}
    (for [[v l] options] ^{:key v} [:option {:value v} l])]
   [:span {:aria-hidden true :class (ui/class-name :specular)}]])

(defn- fmt-bytes [n]
  (cond
    (nil? n) "?"
    (>= n (* 1024 1024 1024)) (str (.toFixed (/ n 1024 1024 1024) 1) " GiB")
    (>= n (* 1024 1024)) (str (.toFixed (/ n 1024 1024) 1) " MiB")
    :else (str n " B")))

(defn- on-tab-bar-click
  "kotoba-ui tab-bar's act contract (data-act=tab id) → tab switch. Same
  delegation pattern as manimani.ui/on-tab-click."
  [on-select]
  (fn [e]
    (when-let [el (some-> (.-target e) (.closest "[data-act]"))]
      (when-let [act (.getAttribute el "data-act")]
        (on-select (keyword act))))))

;; ---------------------------------------------------------------------------
;; header + tabs

(def tabs [[:models "Models"] [:chat "Chat"] [:download "Download"]
           [:settings "Settings"] [:fleet "Fleet"]])

(defn- engine-badge []
  (let [{:keys [status error]} (:engine @state/state)]
    [ui/badge (case status
                :ready "engine: ready"
                :starting "engine: starting…"
                :error (str "engine: error" (when error (str " — " error)))
                "engine: unknown")]))

(defn- header []
  [:div {:style {:display "flex" :align-items "center" :justify-content "space-between"
                 :padding "10px 16px"}}
   [:div {:style {:display "flex" :align-items "center" :gap "10px"}}
    [:span {:style {:font-weight 600}} "murakumo-studio"]
    [engine-badge]]
   [ui/tab-bar tabs (:tab @state/state) {}]])

;; ---------------------------------------------------------------------------
;; Models tab

(defn- load-models! []
  (swap! state/state assoc-in [:models :loading?] true)
  (-> (client/list-models)
      (.then (fn [res]
               (swap! state/state update :models merge
                      {:items (:data res) :loading? false :error nil})))
      (.catch (fn [e]
                (swap! state/state update :models merge
                       {:loading? false :error (str e)})))))

(defn- rescan-models! []
  (swap! state/state assoc-in [:models :loading?] true)
  (-> (client/scan-local-models)
      (.then (fn [_] (load-models!)))
      (.catch (fn [e]
                (swap! state/state update :models merge
                       {:loading? false :error (str e)})))))

(defn- model-row [{:keys [id size_bytes context_length backend] :as m}]
  [ui/list-row
   [:div
    [:div {:style {:font-weight 600}} id]
    [:div {:style {:opacity 0.7 :font-size "12px"}}
     (fmt-bytes size_bytes) " · ctx " (or context_length "?") " · " (or backend "cpu")]]
   {:trailing (btn "Use in Chat"
                    #(swap! state/state assoc-in [:chat :model] id))}])

(defn- models-tab []
  (let [{:keys [items loading? error]} (:models @state/state)]
    [shape/panel
     [:div
      [:div {:style {:display "flex" :justify-content "space-between" :margin-bottom "8px"}}
       [:span "Local models (~/.murakumo-studio/models + ~/.ollama/models)"]
       [btn (if loading? "Scanning…" "Rescan") rescan-models! {:disabled? loading?}]]
      (when error [:div {:style {:color "#ff8a8a"}} (str error)])
      (if (empty? items)
        [:div {:style {:opacity 0.6}} "No models found yet. Try Rescan, or use the Download tab."]
        [ui/list-view (mapv (fn [m] ^{:key (:id m)} [model-row m]) items)])]]))

;; ---------------------------------------------------------------------------
;; Chat tab

(defn- send-message! []
  (let [{:keys [model input messages]} (:chat @state/state)]
    (when (and model (seq (kotoba.lang.text/trim input)))
      (let [user-msg {:role "user" :content input}
            history (conj messages user-msg)
            ;; empty assistant placeholder, filled in progressively as real
            ;; SSE token chunks arrive (kotoba-lang/inference#5 wired up)
            assistant-idx (count history)]
        (swap! state/state update :chat merge
               {:messages (conj history {:role "assistant" :content ""})
                :input "" :busy? true :error nil})
        (client/chat-completion-stream
         {:model model
          :messages history
          :temperature (get-in @state/state [:settings :temperature])
          :max-tokens (get-in @state/state [:settings :max-tokens])}
         {:on-note (fn [note] (swap! state/state assoc-in [:chat :note] note))
          :on-chunk (fn [content]
                      (swap! state/state update-in [:chat :messages assistant-idx :content] str content))
          :on-done (fn [] (swap! state/state assoc-in [:chat :busy?] false))
          :on-error (fn [msg] (swap! state/state update :chat merge {:busy? false :error msg}))})))))

(defn- message-bubble [{:keys [role content]}]
  [:div {:class "ms-chat-log"
         :style {:margin "6px 0" :padding "8px 12px" :border-radius "10px"
                 :background (if (= role "user") "rgba(255,255,255,.08)" "rgba(120,170,255,.10)")}}
   [:div {:style {:opacity 0.6 :font-size "11px" :margin-bottom "2px"}} role]
   [:div content]])

(defn- chat-tab []
  (let [{:keys [model messages input busy? error note]} (:chat @state/state)
        model-ids (mapv :id (get-in @state/state [:models :items]))]
    [shape/panel
     [:div
      [model-select (mapv (fn [id] [id id]) model-ids)
       {:value (or model "") :on-change #(swap! state/state assoc-in [:chat :model] (.. % -target -value))}]
      (when (empty? model-ids)
        [:div {:style {:opacity 0.6 :margin-top "6px"}} "No models loaded — pick one from the Models tab first."])
      (when note [:div {:style {:opacity 0.7 :font-size "12px" :margin-top "6px"}} "⚠ " note])
      [:div {:style {:margin "10px 0" :max-height "340px" :overflow-y "auto"}}
       (for [[i m] (map-indexed vector messages)]
         ^{:key i} [message-bubble m])]
      (when error [:div {:style {:color "#ff8a8a"}} (str error)])
      [text-area {:value input :rows 3 :placeholder "Ask something…"
                  :on-input #(swap! state/state assoc-in [:chat :input] (.. % -target -value))}]
      [:div {:style {:margin-top "8px"}}
       [btn (if busy? "Generating…" "Send") send-message! {:disabled? (or busy? (not model))}]]]]))

;; ---------------------------------------------------------------------------
;; Download tab

(defn- download! [repo-id file]
  (swap! state/state update :download merge {:busy? true :error nil :done nil})
  (-> (client/download-model {:repo-id repo-id :file file})
      (.then (fn [res]
               (swap! state/state update :download merge {:busy? false :done res})
               (load-models!)))
      (.catch (fn [e]
                (swap! state/state update :download merge {:busy? false :error (str e)})))))

(defn- search-hf! []
  (let [query (get-in @state/state [:download :query])]
    (when (seq (kotoba.lang.text/trim query))
      (swap! state/state update :download merge {:searching? true :error nil})
      (-> (client/search-hf query)
          (.then (fn [res]
                   (swap! state/state update :download merge
                          {:results (:data res) :searching? false})))
          (.catch (fn [e]
                    (swap! state/state update :download merge
                           {:searching? false :error (str e)})))))))

(defn- browse-hf-repo! [repo-id]
  (swap! state/state update :download merge
         {:selected-repo repo-id :hf-files [] :listing? true :error nil})
  (-> (client/list-hf-gguf-files repo-id)
      (.then (fn [res]
               (swap! state/state update :download merge
                      {:hf-files (:data res) :listing? false})))
      (.catch (fn [e]
                (swap! state/state update :download merge
                       {:listing? false :error (str e)})))))

(defn- hf-search-result-row [{:keys [id downloads likes]}]
  [ui/list-row
   [:div
    [:div {:style {:font-weight 600}} id]
    [:div {:style {:opacity 0.7 :font-size "12px"}}
     (or downloads 0) " downloads · " (or likes 0) " likes"]]
   {:trailing (btn "Browse files" #(browse-hf-repo! id))}])

(defn- hf-file-row [repo-id {:keys [filename]}]
  [ui/list-row filename
   {:trailing (btn "Download" #(download! repo-id filename)
                    {:disabled? (:busy? (:download @state/state))})}])

(defn- download-tab []
  (let [{:keys [repo-id file busy? error done query results searching?
                selected-repo hf-files listing?]} (:download @state/state)]
    [shape/panel
     [:div
      [:div {:style {:opacity 0.7 :margin-bottom "8px"}}
       "Search Hugging Face Hub, browse a repo's GGUF files, and download —
       or paste an exact repo-id/filename below."]
      [ui/text-field {:value query :placeholder "search models (e.g. \"gemma gguf\")"
                       :on-input #(swap! state/state assoc-in [:download :query] (.. % -target -value))}]
      [:div {:style {:margin "8px 0"}}
       [btn (if searching? "Searching…" "Search") search-hf! {:disabled? searching?}]]
      (when (seq results)
        [ui/list-view (mapv (fn [r] ^{:key (:id r)} [hf-search-result-row r]) results)])
      (when selected-repo
        [:div {:style {:margin-top "10px"}}
         [:div {:style {:font-weight 600 :margin-bottom "6px"}}
          (if listing? (str "Loading files for " selected-repo "…") (str "Files in " selected-repo))]
         (when (seq hf-files)
           [ui/list-view (mapv (fn [f] ^{:key (:filename f)} [hf-file-row selected-repo f]) hf-files)])])
      [ui/divider]
      [:div {:style {:opacity 0.7 :margin "8px 0"}} "Or paste an exact repo-id + filename:"]
      [ui/text-field {:value repo-id :placeholder "e.g. bartowski/gemma-4-e4b-it-GGUF"
                       :on-input #(swap! state/state assoc-in [:download :repo-id] (.. % -target -value))}]
      [ui/text-field {:value file :placeholder "e.g. gemma-4-e4b-it-Q4_K_M.gguf"
                       :on-input #(swap! state/state assoc-in [:download :file] (.. % -target -value))}]
      [:div {:style {:margin-top "8px"}}
       [btn (if busy? "Downloading…" "Download") #(download! repo-id file)
        {:disabled? (or busy? (empty? repo-id) (empty? file))}]]
      (when error [:div {:style {:color "#ff8a8a" :margin-top "6px"}} (str error)])
      (when done [:div {:style {:margin-top "6px"}} (str "Saved: " (:path done))])]]))

;; ---------------------------------------------------------------------------
;; Settings tab

(defn- num-field [path label]
  [:div {:style {:margin "6px 0"}}
   [:label {:style {:display "block" :opacity 0.7 :font-size "12px"}} label]
   [ui/text-field {:value (str (get-in @state/state path)) :type "number"
                    :on-input #(swap! state/state assoc-in path
                                       (js/parseFloat (.. % -target -value)))}]])

(defn- settings-tab []
  [shape/panel
   [:div
    [num-field [:settings :threads] "CPU threads"]
    [num-field [:settings :context-length] "Context length"]
    [num-field [:settings :temperature] "Temperature"]
    [num-field [:settings :max-tokens] "Max tokens per reply"]
    [ui/divider]
    [:div {:style {:opacity 0.7 :font-size "12px"}}
     "Compute backend: CPU (num.cpu, via kotoba-lang/inference). WebGPU/GPU "
     "offload is roadmapped (ADR-2607032700 Phase 2) — not selectable yet."]]])

;; ---------------------------------------------------------------------------
;; Fleet tab

(defn- load-fleet-status! []
  (-> (client/fleet-status)
      (.then (fn [res] (swap! state/state update :fleet merge {:status res :error nil})))
      (.catch (fn [e] (swap! state/state update :fleet assoc :error (str e))))))

(defn- toggle-fleet! []
  (let [enabled? (get-in @state/state [:fleet :enabled?])]
    (swap! state/state assoc-in [:fleet :busy?] true)
    (-> (if enabled? (client/fleet-leave) (client/fleet-join))
        (.then (fn [_]
                 (swap! state/state update :fleet merge {:enabled? (not enabled?) :busy? false})
                 (load-fleet-status!)))
        (.catch (fn [e] (swap! state/state update :fleet merge {:busy? false :error (str e)}))))))

(defn- fleet-tab []
  (let [{:keys [enabled? status busy? error]} (:fleet @state/state)]
    [shape/panel
     [:div
      [:div {:style {:opacity 0.7 :margin-bottom "8px"}}
       "Announce this node's local models to the murakumo fleet "
       "(gftdcojp/cloud-murakumo-fleet /infer/*). v1 is announce-only — "
       "compute participation is a follow-up (ADR-2607032700 Phase 3)."]
      [ui/toggle {:checked (boolean enabled?) :disabled busy?
                   :on-change toggle-fleet!}]
      [:span {:style {:margin-left "8px"}} (if enabled? "Joined" "Not joined")]
      (when error [:div {:style {:color "#ff8a8a" :margin-top "6px"}} (str error)])
      (when status [:pre {:style {:opacity 0.7 :font-size "11px" :margin-top "8px"}}
                     (pr-str status)])]]))

;; ---------------------------------------------------------------------------
;; root

(defn root []
  [:div {:on-click (on-tab-bar-click state/set-tab!)}
   [header]
   (case (:tab @state/state)
     :models [models-tab]
     :chat [chat-tab]
     :download [download-tab]
     :settings [settings-tab]
     :fleet [fleet-tab]
     [models-tab])])
