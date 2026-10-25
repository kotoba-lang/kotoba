(ns hata.ito
  "糸（ito）—— 1 つの cell の source chain。署名付き action の連鎖。

  root ADR-2610082200（§5 糸）。私的な entry は糸 にだけ残し、布 には出さない。
  ここには署名も CID も無い：両方とも注入する（verify-fn / cid-fn）。この ns が
  決めるのは連鎖の形と、壊れ方（分岐・逆転・close 後の追記）が fail-closed
  であることで、鍵と digest は各 owner の仕事。")

(def action-kinds
  "open で genesis、commit が通常の追記、close は紋 の移行（新しい紋 CID を指す）。"
  #{:open :commit :close})

(defn entry-cid
  "The action's identity: whatever the injected cid-fn answers for its map."
  [cid-fn entry]
  (cid-fn (:hata.action/action entry)))

(defn- head-cid [cid-fn chain]
  (when (seq chain) (entry-cid cid-fn (peek chain))))

(defn- signature-problems [verify-fn entry]
  (let [{:keys [author signature]} entry]
    (cond
      (not (string? author)) [{:problem :no-author}]
      (not (string? signature)) [{:problem :no-signature}]
      (not (verify-fn author (:hata.action/action entry) signature))
      [{:problem :bad-signature :author author}])))

(defn- link-problems [cid-fn chain action]
  (let [prev (:hata.action/prev action)
        expected (head-cid cid-fn chain)
        kind (:hata.action/kind action)]
    (cond-> []
      (not (contains? action-kinds kind))
      (conj {:problem :unknown-kind :value kind})

      ;; the chain only grows at its head: prev must be exactly the head.
      (not= prev expected)
      (conj {:problem :not-the-head :prev prev :expected expected})

      (and (empty? chain) (not= :open kind))
      (conj {:problem :genesis-is-open})

      (and (seq chain) (= :open kind))
      (conj {:problem :open-after-genesis})

      (and (= :close kind) (not (string? (:hata.action/next-mon action))))
      (conj {:problem :close-without-next-mon}))))

(defn problems
  "Everything wrong with appending `entry` to `chain`. Empty = appendable.

  Reports rather than throws — a chain that cannot grow names why, and a
  caller that ignores the reasons is the caller's bug."
  [{:keys [cid-fn verify-fn]} chain entry]
  (into [] (concat (link-problems cid-fn chain (:hata.action/action entry))
                   (signature-problems verify-fn entry))))

(defn append
  "Return {:ok chain'} or {:problems [...]}. Nothing after a :close ever
  appends — the next chain starts at the new 紋 with its own :open."
  [seams chain entry]
  (if-let [probs (seq (problems seams chain entry))]
    {:problems (vec probs)}
    {:ok (conj (vec chain) entry)}))

(defn diverged?
  "Two chains are diverged when they share a parent and disagree after it —
  the 糸 の分岐 that becomes a warrant on the 布 (P4)."
  [cid-fn chain-a chain-b]
  (boolean
   (and (seq chain-a) (seq chain-b)
        (not= (entry-cid cid-fn (first chain-a))
              (entry-cid cid-fn (first chain-b)))
        (= (:hata.action/prev (:hata.action/action (first chain-a)))
           (:hata.action/prev (:hata.action/action (first chain-b)))))))
