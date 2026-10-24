(ns persona.relay
  "persona 宛の受信と、persona からの送信の**判断**。

  機構（SMTP・Email Routing・キュー）はここに無い。ここが答えるのは
  『この 1 通をどうするか』だけで、答えは値として返る。

  ## 返信が一番よく壊れる

  受信を alias にするのは簡単で、たいていの実装はそこで終わる。壊れるのは
  返信で、**1 通を本体のアドレスから返した瞬間に全部無効になる**。相手は
  本体を知り、以後の突き合わせが可能になる。しかも壊れたことに誰も気づかない
  —— 相手には普通に届くので。

  だから `outbound` は『どの From で出すか』を**必ず**返す。呼び出し側が
  From を組み立てる自由を残さない。

  ## 相手違いは止めない、が黙らない

  ある persona は 1 社のために作られている。その persona から**別の相手**に
  出すと、2 社が同じアドレスを見て結びつく。これは事故だが、正当な場合も
  ある（サポート窓口が別ドメインに転送されている等）ので `:allow` にしつつ
  `:persona.relay/cross-party` を必ず添える。

  同じことが受信側にも要る。相手のドメイン以外から届くのは、そのアドレスが
  漏れたか売られた証拠になりうる。**これは Apple にはできない** —— 向こうは
  alias をどの相手に渡したかを持っていないので、差出人が想定内かを言えない。

  ## ドメインの比較は接尾辞であって登録可能ドメインではない

  `mail.example.com` は `example.com` の内側と見なすが、`example.co.uk` と
  `co.uk` の関係は**判定していない**。正しくやるには Public Suffix List が
  要り、それはこの library が持つべきデータではない（更新され続ける外部の
  表を、判断だけの純関数 repo に抱えると腐る）。ここが返すのは信号であって
  遮断ではないので、接尾辞比較の粗さは誤警報の側に倒れる。"
  (:require [kotoba.lang.text :as str]
            [persona.core :as persona]))

(def schema "persona.relay.v1")

(defn- domain-of
  "アドレスの `@` 以降。アドレスでなければドメインそのものとして扱う。"
  [value]
  (let [v (some-> value str str/trim str/lower not-empty)]
    (when v (if-let [i (str/last-index-of v "@")] (subs v (inc i)) v))))

(defn within?
  "`domain` が `party` と同じか、その部分ドメインか。接尾辞比較。"
  [domain party]
  (boolean (and domain party
                (or (= domain party)
                    (str/ends-with? domain (str "." party))))))

(defn inbound
  "persona 宛に届いた 1 通をどうするか。

  `destination` は本体の実アドレスで、**呼び出し側が渡す** —— directory は
  本体の識別子しか持たず、その人がどこで受け取るかは知らない。

  返る `:persona.relay/signals` は遮断理由ではない。遮断は
  `:persona.relay/decision` が `:reject` のときだけで、その理由は
  `:persona.relay/reason` 1 つ。"
  [dir {:keys [address sender destination]}]
  (let [p (persona/persona-at dir address)
        state (:persona/state p)
        from (domain-of sender)
        party (:persona/party p)
        signals (cond-> []
                  (and p (= :active state) from party (not (within? from party)))
                  (conj {:persona.relay/signal :persona.relay/unexpected-sender
                         :persona.relay/sender-domain from
                         :persona.relay/party party
                         :persona.relay/basis
                         "この alias は別の相手のために作られている。漏れたか売られた可能性"}))]
    (cond
      (nil? p)
      {:persona.relay/decision :reject
       :persona.relay/reason :persona.relay/unknown-address
       :persona.relay/signals signals}

      (= :burned state)
      {:persona.relay/decision :reject
       :persona.relay/reason :persona.relay/address-burned
       :persona.relay/signals signals}

      (= :disabled state)
      {:persona.relay/decision :reject
       :persona.relay/reason :persona.relay/address-disabled
       :persona.relay/signals signals}

      (str/blank? (str destination))
      {:persona.relay/decision :reject
       :persona.relay/reason :persona.relay/no-destination
       :persona.relay/basis "本体の受け取り先が渡されていない。黙って捨てない"
       :persona.relay/signals signals}

      :else
      {:persona.relay/decision :forward
       :persona.relay/deliver-to destination
       :persona.relay/persona (persona/outward p)
       :persona.relay/signals signals})))

(defn note-sender
  "届いた差出人を persona に記録する。`inbound` と分けているのは、判断が
  状態を書き換えないため —— 同じ 1 通について『どうするか』と『何を覚えるか』
  を別に決められる。"
  [dir address sender]
  (let [address (some-> address str str/trim str/lower)
        root (persona/root-of dir address)
        from (domain-of sender)]
    (if (and root from (persona/persona-at dir address))
      (update-in dir [:persona.directory/by-root root address
                      :persona/observed-senders]
                 (fnil conj #{}) from)
      dir)))

(defn outbound
  "persona として 1 通出す。**From を必ず指定して返す。**

  `:allow` でも `:persona.relay/from` を無視してよいわけではない。呼び出し側が
  自分で From を組み立てられるようにしないために、決定の中に入れてある。"
  [dir {:keys [root address recipient]}]
  (let [p (persona/persona-at dir address)
        owner (persona/root-of dir address)
        to (domain-of recipient)
        party (:persona/party p)]
    (cond
      (nil? p)
      {:persona.relay/decision :refuse
       :persona.relay/reason :persona.relay/unknown-address}

      (not= owner root)
      {:persona.relay/decision :refuse
       :persona.relay/reason :persona.relay/not-yours
       :persona.relay/basis
       "他人の persona からは出せない。ここを通すと、なりすましが alias 経由で成立する"}

      (not= :active (:persona/state p))
      {:persona.relay/decision :refuse
       :persona.relay/reason (if (= :burned (:persona/state p))
                               :persona.relay/address-burned
                               :persona.relay/address-disabled)}

      :else
      {:persona.relay/decision :allow
       :persona.relay/from (:persona/address p)
       :persona.relay/signals
       (cond-> []
         (and to party (not (within? to party)))
         (conj {:persona.relay/signal :persona.relay/cross-party
                :persona.relay/recipient-domain to
                :persona.relay/party party
                :persona.relay/basis
                "この persona は別の相手のためのもの。両者が同じアドレスを見ると結びつく"}))})))
