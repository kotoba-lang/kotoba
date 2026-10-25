(ns hata.call
  "cell 間の呼び出し・remote call の形（root ADR-2610082200 §2 の P5、
  kotoba-lang/kotoba-lang docs/adr/ADR-kotoba-lisp-machine-contract-decisions.md D5）。

  D5 が確定した責務のとおり、**call API の owner は 機（hata）**で、:
  - wire 形は境界の形（:kotoba.lisp-machine/boundary-v1）の cell-cell domain
    （署名 action + op）—— ここに載せるのはこの op だけ;
  - 呼び出しは interface DefCID で pin する（ADR-2610082200 §8）;
  - **判定は rule Form（validation）と grant が行う。この API は何も決めない。**
    admit には注入された judge-fn が必要で、明示的な allow 以外は拒否する。

  この repo の形態規約どおり pure な .cljc。署名・CID・judge はすべて注入。
  transport / dispatch（布 P4）は**未実装**で、この ns は形と admission の
  継ぎ目だけを持つ。")

(def call-kinds
  "cell 間は同じ機 の中の cell 相互、remote は他 agent への呼び出し。"
  #{:cell-call :remote-call})

(def call-op-keys
  "op の形。境界の形の cell-cell domain に載る payload。"
  [:hata.call/kind :hata.call/from :hata.call/to
   :hata.call/interface-cid :hata.call/method :hata.call/params])

(defn problems
  "この op が cell-cell domain に載れない理由の一覧。空 = 形として載る。
  問題を throw せず報告する（hata.ito/problems と同じ姿勢）。"
  [op]
  (cond-> []
    (not (map? op))
    (conj {:problem :call-op-not-a-map})

    (map? op)
    (into
     (concat
      (when-not (contains? call-kinds (:hata.call/kind op))
        [{:problem :unknown-call-kind :value (:hata.call/kind op)}])
      (when-not (and (string? (:hata.call/interface-cid op))
                     (pos? (count (:hata.call/interface-cid op))))
        [{:problem :no-interface-pin}])
      (when-not (and (string? (:hata.call/from op))
                     (pos? (count (:hata.call/from op))))
        [{:problem :no-from-cell}])
      (when-not (and (string? (:hata.call/to op))
                     (pos? (count (:hata.call/to op))))
        [{:problem :no-to-cell}])
      (when-not (and (string? (:hata.call/method op))
                     (pos? (count (:hata.call/method op))))
        [{:problem :no-method}])
      (when-not (or (nil? (:hata.call/params op)) (map? (:hata.call/params op)))
        [{:problem :params-not-a-map}])))))

(defn prepare
  "op を形として整える。成功は {:ok :call op}、失敗は {:problems [...]}。
  形を整えるだけで、許可も実行もしない。"
  [op]
  (if-let [probs (seq (problems op))]
    {:problems (vec probs)}
    {:ok :call :call (select-keys op call-op-keys)}))

(defn admit
  "注入された judge-fn（rule Form + grant の判定）に委ねる。**この関数は
  判定しない。** judge が無い、明示的な allow でない、または形が悪い場合は
  すべて拒否（fail closed）。拒否理由を返し、黙って通さない。"
  [call judge-fn]
  (let [probs (problems call)]
    (cond
      (seq probs)
      {:ok? false :reason :bad-shape :problems (vec probs)}

      (not (ifn? judge-fn))
      {:ok? false :reason :no-judgment}

      :else
      (let [decision (judge-fn call)]
        (if (= :allow decision)
          {:ok? true :call call}
          {:ok? false :reason :denied :decision decision})))))

(defn entry
  "admit 済みの call を 糸 に足す entry の形（hata.ito が受ける :commit）。
  署名は注入された sign-fn が作る。prev は caller が 糸 の head から渡す。
  実行・dispatch はしない。"
  [{:keys [sign-fn cid-fn]} call author prev]
  (let [action {:hata.action/kind :commit
                :hata.action/prev prev
                :hata.action/op call}
        signature (sign-fn author action)]
    {:author author
     :signature signature
     :hata.action/action action
     :hata.call/entry-cid (cid-fn action)}))
