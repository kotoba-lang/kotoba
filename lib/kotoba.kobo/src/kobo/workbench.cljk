(ns kobo.workbench
  (:require [kobo.editor :as editor]
            [kuro.terminal :as terminal]))

(defn workbench
  ([repo-root-cid] (workbench repo-root-cid {}))
  ([repo-root-cid attrs]
   (merge {:kobo/type :kobo/workbench
           :kobo/repo-root-cid repo-root-cid
           :kobo/buffers {}
           :kobo/terminals {}
           :kobo/receipts []
           :kobo/running {}
           :kobo/denials []
           :kobo/diagnostics []}
          attrs)))

(defn buffer [path text]
  (editor/buffer path text))

(defn open-buffer [wb buf]
  (assoc-in wb [:kobo/buffers (:kobo.buffer/path buf)] buf))

(defn update-buffer [wb path f & args]
  (apply update-in wb [:kobo/buffers path] f args))

(defn apply-patch [wb p]
  (update-buffer wb (:kobo.patch/path p) editor/apply-patch p))

(defn open-terminal
  ([wb id mode] (open-terminal wb id mode {}))
  ([wb id mode attrs]
   (let [sess (terminal/session id (:kobo/repo-root-cid wb) mode attrs)]
     (assoc-in wb [:kobo/terminals id] sess))))

(defn terminal [wb id]
  (get-in wb [:kobo/terminals id]))

(defn command-receipt [wb terminal-id cmd result]
  (let [sess (terminal wb terminal-id)
        rcpt (terminal/receipt sess cmd result)]
    (update wb :kobo/receipts conj rcpt)))

(defn set-running
  "実行中の `kuro.stream` 値を terminal-id の下に置く（nil で外す）。

  receipt の列に混ぜない —— 「まだ終わっていない」と「終わって exit 0」は
  別の事実で、同じ列に積むと読み手が取り違える。"
  [wb terminal-id st]
  (if (nil? st)
    (update wb :kobo/running dissoc terminal-id)
    (assoc-in wb [:kobo/running terminal-id] st)))

(defn record-denial
  "Keep a refused command alongside the ones that ran.

  A denial that leaves no trace is indistinguishable from a command nobody
  typed — the workbench would show an empty receipt list either way. This is
  the ADR's \"inline grant view: why this component can or cannot run\", in
  its smallest form."
  [wb denial]
  (update wb :kobo/denials conj denial))

(defn add-diagnostics [wb diagnostics]
  (update wb :kobo/diagnostics into diagnostics))

(defn diagnose-aiueos-manifest [wb path manifest]
  (add-diagnostics wb (editor/aiueos-manifest-diagnostics path manifest)))

(defn kotoba-facts [wb]
  (concat
   [{:kotoba/type :kobo/workbench
     :kotoba/id [:kobo/workbench (:kobo/repo-root-cid wb)]
     :kobo/repo-root-cid (:kobo/repo-root-cid wb)}]
   (map (fn [[path buf]]
          {:kotoba/type :kobo/buffer
           :kotoba/id [:kobo/buffer (:kobo/repo-root-cid wb) path]
           :kobo/buffer buf})
        (:kobo/buffers wb))
   (map terminal/receipt-fact (:kobo/receipts wb))))
