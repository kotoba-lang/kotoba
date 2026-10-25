(ns hata.conductor
  "機（hata）—— conductor。紋 に従って 糸 を織る常駐のランタイム。

  root ADR-2610082200（§2）。1 つの principal の 1 台の device（または 1
  bot）に 1 つ。持つもの: 鍵の預かり（署名は注入 sign-fn）、cell の起動、
  糸 の記録、UI への局所 API（P3 後続）、cell 間・remote call（P5）。

  持たないもの: 権限の判断（grant = 注入 admit-fn）、配置（sahai）、VM の
  定義（kototama）。実行は 宿 に渡す — host-fn が 宿
  （kototama-native / kototama-component / wasm-webcomponent）への入口。"
  (:require [hata.bundle :as bundle]
            [hata.cell :as cell]
            [hata.receipt :as receipt]))

(defn resident
  "One 機 per device. Every seam is injected; this repo owns no crypto,
  no engine and no placement."
  [{:keys [cid-fn sign-fn verify-fn membrane-check-fn host-fn admit-fn]
    :as seams}]
  (assoc seams :cells (atom {})))

(defn start-cell!
  "Open a cell under this 機. Refused membranes leave no state behind. The
  membrane check comes from the 機's seams, not from the caller's pocket."
  [machine {:keys [mon-cid agent-key] :as opts}]
  (let [result (cell/open (merge machine opts))]
    (if (:ok result)
      (do (swap! (:cells machine) assoc [mon-cid agent-key] (:ok result))
          {:ok [mon-cid agent-key]})
      result)))

(defn record!
  "Record a signed action on a cell's 糸. Nothing is recorded when the chain
  refuses it — the return names why."
  [machine cell-id entry]
  (let [cell (get @(:cells machine) cell-id)]
    (if (nil? cell)
      {:problems [{:problem :no-such-cell :cell cell-id}]}
      (let [result (cell/append machine cell entry)]
        (if (:ok result)
          (do (swap! (:cells machine) assoc cell-id (:ok result))
              {:ok cell-id})
          result)))))

(defn execute
  "Delegate execution to the 宿. The 機 does not decide permission: when an
  admit-fn is present it is consulted first and a refusal sends nothing to
  the host — but the decision itself belongs to grant."
  [machine cell-id call]
  (let [cell (get @(:cells machine) cell-id)]
    (cond
      (nil? cell) {:problems [{:problem :no-such-cell :cell cell-id}]}

      (and (:admit-fn machine)
           (not ((:admit-fn machine) cell call)))
      {:problems [{:problem :admit-refused :call call}]}

      :else {:ok ((:host-fn machine) cell call)})))

;; ------------------------------------------------------------- P3: bundle

(defn- sign-entry [machine action]
  {:hata.action/action action
   :author (:device-key machine)
   :signature ((:sign-fn machine) (:device-key machine) action)})

(defn- action-cid [machine entry]
  ;; The action's identity is the injected cid-fn over its map — the same
  ;; seam hata.ito uses for chain links.
  ((:cid-fn machine) (:hata.action/action entry)))

(defn open-bundle!
  "Open an app from its app DID alone — no domain, ADR-2610082200 §14 (1)(2).

  The seams carry the world: fetch-fn resolves app-did → bundle bytes (the
  IPNS name derivation from the app DID is identity's work, not this repo's),
  parse-bundle-fn turns bytes into the logical bundle (CAR parsing is
  io-ipld-car's work), digest-fn is the content address. What the 機 adds is
  the fail-closed order: the bundle's CIDs must hold before any cell exists,
  and the first 糸 action names what was opened."
  [machine app-did]
  (let [bytes ((:fetch-fn machine) app-did)
        parsed (when bytes ((:parse-bundle-fn machine) bytes))
        read (if parsed
               (bundle/read-bundle machine parsed)
               {:problems [{:problem :unfetched :app-did app-did}]})]
    (if-let [probs (:problems read)]
      {:problems probs}
      (let [{:keys [manifest mon-cid]} (:ok read)
            cell-id [mon-cid (:device-key machine)]
            opened (cell/open (merge machine
                                     {:mon-cid mon-cid
                                      :agent-key (:device-key machine)
                                      :membrane-proof {:app-did app-did
                                                       :mon-cid mon-cid
                                                       :manifest manifest}}))]
        (if-let [probs (:problems opened)]
          {:problems probs}
          (let [genesis (sign-entry machine
                                    {:hata.action/kind :open
                                     :hata.action/mon mon-cid
                                     :hata.action/prev nil
                                     :hata.action/body {:app-did app-did
                                                        :bundle-cid (:bundle-cid (:ok read))}})
                recorded (do (swap! (:cells machine) assoc cell-id (:ok opened))
                             (record! machine cell-id genesis))]
            (if (:ok recorded)
              {:ok cell-id :bundle (:ok read)}
              recorded)))))))

(defn run-logic!
  "Run one logic call on the opened bundle and write the receipt to the 糸.
  P3 合否条件 (2)(3): the execution leaves a kototama receipt and a signed
  action, and an admit refusal writes nothing and runs nothing. A receipt
  kototama's VM spec would refuse is not recorded either — the 機 never
  launders a receipt the VM would not accept (hata.receipt)."
  [machine cell-id call]
  (let [ran (execute machine cell-id call)]
    (if-let [probs (:problems ran)]
      {:problems probs}
      (let [receipt (:ok ran)]
        (if-let [rprobs (seq (receipt/problems receipt))]
          {:problems (vec rprobs) :receipt-refused true}
          (let [action {:hata.action/kind :commit
                        :hata.action/mon (first cell-id)
                        :hata.action/prev nil
                        :hata.action/body {:call call :receipt receipt}}
                cell (get @(:cells machine) cell-id)
                head (peek (:hata.cell/ito cell))
                prev (when head (action-cid machine head))
                action (assoc action :hata.action/prev prev)
                recorded (record! machine cell-id (sign-entry machine action))]
            (if (:ok recorded)
              {:ok receipt :recorded cell-id}
              recorded)))))))
