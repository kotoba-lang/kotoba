(ns persona.core
  "1 人が持つ**複数の公開の顔**と、その裏にある 1 つの本体との関係。

  Apple の Hide My Email と同じ形: 相手ごとに別のメールアドレスを配り、
  相手は本体のアドレスも識別子も知らない。止めたければその 1 本だけ止める。

  ## 本体は persona の中に無い

  この設計で唯一取り返しのつかない失敗は、本体の識別子が外に出ることである。
  だから本体は persona の**フィールドではなく directory の鍵**にした。

      {:persona.directory/by-root    {root -> {address -> persona}}
       :persona.directory/by-address {address -> root}
       :persona.directory/burned     #{address}}

  persona の値そのものが本体を持たないので、**どんな投影をしても漏れない**。
  『投影関数で落とす』設計にしなかったのは、投影関数は増えるからで、
  増えたどれか 1 つが落とし忘れれば終わりだから。持たないものは落とせない。

  逆引き（`by-address`）は受信の振り分けに要るので directory の中に在る。
  これは信頼境界の内側で、persona の値を持ち回ることでは漏れない。

  ## 相手ごとに 1 本、というのが値のすべて

  同じアドレスを 2 社に渡した瞬間、2 社は突き合わせで同一人物と判定できる。
  だから `issue` は**相手（party）を必須の引数にする**。省略できるようには
  しない —— 省略できる引数は必ず省略され、省略された瞬間にこの library の
  存在理由が消える。

  同じ相手に 2 本目を出すこと自体は禁じない（同じサービスに 2 アカウント
  持つのは普通）。ただし `:persona/existing` に既存を並べて返すので、
  UI は『もう 1 本ありますが』と言える。

  ## handle は word-id

  アドレスの local part は `word-id` の 4 語（`meteor-polar-silken-parable`）。
  ランダムなので相関しないが、**電話で読み上げられる**。Apple の
  `k7x9m2p4@privaterelay.appleid.com` にはできないことで、口頭で本人確認を
  する窓口を持つ事業ではこれが効く。

  ## 上限はここが決めない

  何本まで持てるかは信頼の段階が決める（`sekisho.assurance`）。ここは
  `:persona/cap` を数として受け取り、超えたら理由を言って断るだけ。
  上限の根拠をこの ns が持つと、認証の強さと alias の数という無関係な 2 つの
  関心が 1 箇所に混ざる。"
  (:require [kotoba.lang.text :as str]
            [word-id.core :as word-id]))

(def schema "persona.core.v1")

(def states
  "弱い順ではなく、**戻れない順**。`:burned` からはどこへも戻らない。"
  #{:active :disabled :burned})

(defn directory
  "空の directory。"
  []
  {:persona.directory/schema schema
   :persona.directory/by-root {}
   :persona.directory/by-address {}
   :persona.directory/burned #{}})

(defn- normalize-address [a]
  (some-> a str str/trim str/lower not-empty))

(defn- normalize-party
  "相手の識別子。ドメインを想定するが、この ns は形を検査しない —— 何を
  『1 社』と数えるかは呼び出し側の判断（`example.com` と `shop.example.com`
  を同じと見るかは、この library には決められない）。"
  [p]
  (some-> p str str/trim str/lower not-empty))

(defn personas
  "この本体が持つ persona 全部（`:burned` を含む）。"
  [dir root]
  (vals (get-in dir [:persona.directory/by-root root] {})))

(defn live
  "生きている persona —— `:burned` でないもの。上限はこれを数える。

  `:burned` を数え続けると、使い捨てを繰り返した人が上限に張り付く。
  一方でアドレス自体は永久に予約されたまま（`:persona.directory/burned`）で、
  これは別の関心 —— 再発行すると、昔の相手と新しい相手が同じアドレスを見て
  静かに結びつくため。"
  [dir root]
  (remove #(= :burned (:persona/state %)) (personas dir root)))

(defn persona-at
  "アドレスから persona を引く。本体は返さない。"
  [dir address]
  (let [address (normalize-address address)
        root (get-in dir [:persona.directory/by-address address])]
    (get-in dir [:persona.directory/by-root root address])))

(defn root-of
  "アドレスから本体を引く。**信頼境界の内側でだけ呼ぶこと** —— 転送先を
  決めるのと、本人が自分の一覧を見るのに要る。外向きの応答に混ぜない。"
  [dir address]
  (get-in dir [:persona.directory/by-address (normalize-address address)]))

;; ---------------------------------------------------------------------------
;; 発行
;; ---------------------------------------------------------------------------

(defn issue
  "本体に、この相手のための persona を 1 本足す。

  entropy は byte 列で受け取る（`word-id/mint` と同じ理由 —— 固定入力で
  結果が決まるので、発行の正しさをテストで固定できる）。

  アドレスが既に使われていたら `:persona/address-taken` を返す。ここで
  勝手に引き直さないのは、何回引いたかを呼び出し側が知るべきだから
  （毎回衝突するなら空間が枯れかけている）。"
  [dir {:keys [root party domain entropy vocabulary cap label now]}]
  (let [root (some-> root str not-empty)
        party (normalize-party party)
        domain (normalize-address domain)
        existing (vec (live dir root))
        minted (when (and root party domain) (word-id/mint vocabulary entropy))]
    (cond
      (nil? root)
      {:persona/issues [{:persona/issue :persona/root-required}]}

      (nil? party)
      {:persona/issues
       [{:persona/issue :persona/party-required
         :persona/basis
         "相手を記録しない persona は、同じアドレスを 2 社に渡す事故を防げない"}]}

      (nil? domain)
      {:persona/issues [{:persona/issue :persona/domain-required}]}

      (:word-id/issues minted)
      {:persona/issues [{:persona/issue :persona/handle-not-minted
                         :persona/cause (:word-id/issues minted)}]}

      (and (integer? cap) (>= (count existing) cap))
      {:persona/issues [{:persona/issue :persona/cap-reached
                         :persona/cap cap
                         :persona/live (count existing)
                         :persona/basis
                         "上限は信頼の段階が決める。段階を上げるか、使っていない persona を burn する"}]}

      :else
      (let [handle (:word-id/text minted)
            address (str handle "@" domain)]
        (if (or (contains? (:persona.directory/burned dir) address)
                (contains? (:persona.directory/by-address dir) address))
          {:persona/issues
           [{:persona/issue :persona/address-taken
             :persona/address address
             :persona/basis
             "別のエントロピーで引き直す。burn 済みのアドレスは永久に再発行しない"}]}
          (let [p {:persona/schema schema
                   :persona/handle handle
                   :persona/address address
                   :persona/party party
                   :persona/label (some-> label str not-empty)
                   :persona/state :active
                   :persona/created-at now
                   :persona/state-changed-at now
                   :persona/observed-senders #{}}]
            {:persona/persona p
             :persona/existing (filterv #(= party (:persona/party %)) existing)
             :persona/directory
             (-> dir
                 (assoc-in [:persona.directory/by-root root address] p)
                 (assoc-in [:persona.directory/by-address address] root))}))))))

;; ---------------------------------------------------------------------------
;; 状態
;; ---------------------------------------------------------------------------

(defn- transition [dir address to now]
  (let [address (normalize-address address)
        root (root-of dir address)
        current (persona-at dir address)]
    (cond
      (nil? current)
      {:persona/issues [{:persona/issue :persona/unknown-address
                         :persona/address address}]}

      (= :burned (:persona/state current))
      {:persona/issues
       [{:persona/issue :persona/already-burned
         :persona/address address
         :persona/basis "burn は戻せない。戻せると、昔の相手と新しい相手が同じアドレスを見る"}]}

      (= to (:persona/state current))
      {:persona/persona current :persona/directory dir}

      :else
      (let [p (assoc current :persona/state to :persona/state-changed-at now)]
        {:persona/persona p
         :persona/directory
         (cond-> (assoc-in dir [:persona.directory/by-root root address] p)
           (= :burned to)
           (update :persona.directory/burned conj address))}))))

(defn disable
  "転送を止める。アドレスは押さえたまま —— 押さえないと他人に再発行されうる。"
  [dir address now]
  (transition dir address :disabled now))

(defn enable
  "転送を再開する。`:burned` からは戻らない。"
  [dir address now]
  (transition dir address :active now))

(defn burn
  "永久に捨てる。アドレスは directory の `burned` に残り、二度と発行されない。"
  [dir address now]
  (transition dir address :burned now))

;; ---------------------------------------------------------------------------
;; 投影
;; ---------------------------------------------------------------------------

(defn outward
  "相手に見せてよいもの。アドレス 1 つだけ。

  相手が知る必要があるのは『どこに送るか』だけで、状態も相手名もラベルも
  作成日も要らない。作成日は他の persona との相関に使えるので、特に出さない。"
  [p]
  (when p {:persona/address (:persona/address p)}))

(defn owner-view
  "本人に見せるもの。本体の識別子は**元から入っていない**（この ns の
  docstring）。ラベルと相手と状態は本人のためのもの。"
  [p]
  (when p
    (select-keys p [:persona/handle :persona/address :persona/party
                    :persona/label :persona/state :persona/created-at
                    :persona/state-changed-at :persona/observed-senders])))

(defn inventory
  "本人の一覧。どの相手に何を渡したかが 1 画面で読めること。"
  [dir root cap]
  (let [all (vec (personas dir root))
        live' (remove #(= :burned (:persona/state %)) all)]
    {:persona/root-known? (boolean (seq all))
     :persona/cap cap
     :persona/live (count live')
     :persona/remaining (when (integer? cap) (max 0 (- cap (count live'))))
     :persona/parties (into (sorted-set) (map :persona/party live'))
     :persona/personas (mapv owner-view (sort-by :persona/created-at all))}))
