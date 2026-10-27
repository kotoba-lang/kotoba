(ns browser.desktop-backend
  "Pure contract between the browser desktop shell and a display/input host.

   The guest owns windows, workspaces and retained draw data.  A backend only
   presents versioned frames, reports canonical input and performs explicitly
   brokered ambient operations.  Nothing here assumes DOM, Linux or aiueos."
  (:require [browser.input :as input]
            [browser.surface :as surface]))

(def contract-version 1)

(def capabilities
  #{:frame/present :input/events :clipboard/read :clipboard/write
    :file-picker/open :file-picker/save})

(defn empty-desktop
  ([] (empty-desktop {}))
  ([{:keys [viewport workspace-id]}]
   {:desktop/contract-version contract-version
    :desktop/viewport (or viewport [1280 800])
    :desktop/workspaces [(or workspace-id "main")]
    :desktop/active-workspace (or workspace-id "main")
    :desktop/frame-sequence 0
    :desktop/last-frame nil
    :desktop/input (input/empty-state)
    :desktop/pending {}
    :desktop/next-request-id 1}))

(defn valid-frame?
  "A retained frame replaces the previous display list atomically."
  [frame]
  (and (= contract-version (:frame/contract-version frame))
       (string? (:frame/workspace-id frame))
       (vector? (:frame/viewport frame))
       (= 2 (count (:frame/viewport frame)))
       (vector? (:frame/draw-ops frame))))

(defn surface-frame
  "Snapshot a browser.surface as an OS-neutral retained display list."
  [desktop browser-surface]
  (let [rendered (surface/render-surface browser-surface)]
    {:frame/contract-version contract-version
     :frame/workspace-id (:desktop/active-workspace desktop)
     :frame/viewport (:surface/viewport browser-surface)
     :frame/draw-ops (vec (:draw-ops rendered))
     :frame/focus (:surface/focus browser-surface)}))

(defn present
  [desktop frame]
  (if-not (valid-frame? frame)
    {:desktop desktop :effects [] :error :desktop/invalid-frame}
    (let [sequence (inc (:desktop/frame-sequence desktop))
          frame (assoc frame :frame/sequence sequence)]
      {:desktop (assoc desktop
                       :desktop/frame-sequence sequence
                       :desktop/last-frame frame)
       :effects [{:backend/op :frame/present :frame frame}]})))

(defn consume-input
  "Normalize one backend event and reduce it through the existing shell input
   model.  Returns effects only for the resulting pure surface actions."
  [desktop browser-surface backend-event]
  (let [canonical (input/normalize-event backend-event)
        {:keys [input actions]} (input/actions-for-event
                                 browser-surface
                                 (:desktop/input desktop)
                                 canonical)]
    {:desktop (assoc desktop :desktop/input input)
     :surface (surface/apply-actions browser-surface actions)
     :event canonical
     :actions actions}))

(def privileged-capabilities
  #{:clipboard/read :clipboard/write :file-picker/open :file-picker/save})

(defn request
  "Create a backend request only after a broker decision. Deny is fail-closed
   and produces no host effect. The broker result is data, never a callback."
  [desktop {:keys [capability origin payload]} decision]
  (cond
    (not (contains? privileged-capabilities capability))
    {:desktop desktop :effects [] :error :desktop/unsupported-capability}

    (not= :allow (:permission/decision decision))
    {:desktop desktop :effects [] :error (or (:reason decision)
                                              :permission/not-granted)}

    :else
    (let [id (str "desktop-request-" (:desktop/next-request-id desktop))
          operation {:request/id id
                     :request/capability capability
                     :request/origin origin
                     :request/payload payload}
          desktop (-> desktop
                      (update :desktop/next-request-id inc)
                      (assoc-in [:desktop/pending id]
                                (assoc operation :request/status :pending)))]
      {:desktop desktop
       :effects [{:backend/op capability :request operation}]})))

(defn complete-request
  "Accept a completion exactly once. Unknown/stale ids cannot inject data."
  [desktop {:keys [request/id result error]}]
  (if-let [pending (get-in desktop [:desktop/pending id])]
    {:desktop (update desktop :desktop/pending dissoc id)
     :completion (cond-> {:request/id id
                          :request/capability (:request/capability pending)}
                   result (assoc :result result)
                   error (assoc :error error))}
    {:desktop desktop :error :desktop/unknown-request}))
