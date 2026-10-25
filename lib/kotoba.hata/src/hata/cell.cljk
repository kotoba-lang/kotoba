(ns hata.cell
  "cell —— 紋 CID × agent 鍵。機 が起動し、糸 を 1 本だけ持つ実行単位。

  root ADR-2610082200（§3 membrane、§5 糸）。genesis で membrane 証明を
  検査する。証明の判定は注入（membrane-check-fn）— capability chain か
  kotoba-passport の stamp かはこの repo の仕事ではない。"
  (:require [hata.ito :as ito]))

(defn open
  "Open a cell. {:ok cell} or {:problems [...]}.

  A cell that refuses its membrane never exists — there is no half-open cell
  for anything downstream to trip over."
  [{:keys [mon-cid agent-key membrane-proof membrane-check-fn]}]
  (let [problems (cond-> []
                   (not (string? mon-cid))
                   (conj {:problem :no-mon-cid})

                   (not (string? agent-key))
                   (conj {:problem :no-agent-key})

                   (not (membrane-check-fn membrane-proof))
                   (conj {:problem :membrane-refused :mon-cid mon-cid}))]
    (if (seq problems)
      {:problems problems}
      {:ok {:hata.cell/mon-cid mon-cid
            :hata.cell/agent-key agent-key
            :hata.cell/ito []}})))

(defn append
  "Append a signed action to the cell's 糸. Delegates the shape rules to
  hata.ito; adds the cell-level rule that the action names this cell's 紋.
  Returns the cell with its 糸 grown — a chain is not a cell."
  [seams cell entry]
  (let [action (:hata.action/action entry)]
    (if (not= (:hata.action/mon action) (:hata.cell/mon-cid cell))
      {:problems [{:problem :wrong-mon
                   :expected (:hata.cell/mon-cid cell)
                   :value (:hata.action/mon action)}]}
      (let [result (ito/append seams (:hata.cell/ito cell) entry)]
        (if (:ok result)
          {:ok (assoc cell :hata.cell/ito (:ok result))}
          result)))))
