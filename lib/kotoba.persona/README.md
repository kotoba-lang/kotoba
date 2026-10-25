# persona

**1 人が持つ複数の公開の顔。** Apple の Hide My Email と同じ形で、相手ごとに
別のメールアドレスを配り、相手は本体のアドレスも識別子も知らない。止めたければ
その 1 本だけ止める。

違いは 3 つ。**アドレスが読み上げられる**（`word-id` の 4 語）。**相手を記録
する**ので、想定外の差出人が来たら「このアドレスは漏れたか売られた」と言える。
そして**返信の From を決定に含める**ので、1 通を本体から返して全部無効にする
事故が構造的に起きない。

```clojure
(require '[persona.core :as persona]
         '[persona.relay :as relay]
         '[word-id.english :as english])

(def dir (persona/directory))

(def r (persona/issue dir {:root "did:key:z6Mk…"        ; 本体
                           :party "example.com"          ; 誰のために
                           :domain "relay.itonami.cloud"
                           :entropy csprng-bytes
                           :vocabulary english/vocabulary
                           :cap 10                       ; 上限は外から
                           :now "2026-08-06T00:00:00Z"}))

(:persona/address (:persona/persona r))
;; => "meteor-polar-silken-parable@relay.itonami.cloud"

(relay/inbound (:persona/directory r)
               {:address "meteor-polar-silken-parable@relay.itonami.cloud"
                :sender "offers@datamarket.example"
                :destination "jun@example.invalid"})
;; => {:persona.relay/decision :forward
;;     :persona.relay/deliver-to "jun@example.invalid"
;;     :persona.relay/signals [{:persona.relay/signal :persona.relay/unexpected-sender
;;                              :persona.relay/party "example.com" …}]}
```

## 本体は persona の中に無い

この設計で唯一取り返しのつかない失敗は、本体の識別子が外に出ることである。
だから本体は persona の**フィールドではなく directory の鍵**にした。

```clojure
{:persona.directory/by-root    {root -> {address -> persona}}
 :persona.directory/by-address {address -> root}
 :persona.directory/burned     #{address}}
```

persona の値が本体を持たないので、**どんな投影をしても漏れない**。「投影関数で
落とす」設計にしなかったのは、投影関数は増えるからで、増えたどれか 1 つが
落とし忘れれば終わりだから。持たないものは落とせない。

テストは persona・`owner-view`・`outward`・`inventory` の**全ての値を再帰的に
走査して**本体の文字列が出ないことを見る。同じ走査が directory に対しては
陽性になることも確認する（検出器が働いていることの確認）。

## 相手ごとに 1 本

同じアドレスを 2 社に渡した瞬間、2 社は突き合わせで同一人物と判定できる。
だから `issue` は**相手を必須の引数にする**。省略できるようにはしない ——
省略できる引数は必ず省略され、省略された瞬間にこの library の存在理由が消える。

同じ相手への 2 本目は禁じない（同じサービスに 2 アカウントは普通）が、
`:persona/existing` に既存を並べて返すので UI は「もう 1 本ありますが」と言える。

## 返信が一番よく壊れる

受信を alias にするのは簡単で、たいていの実装はそこで終わる。壊れるのは返信で、
**1 通を本体のアドレスから返した瞬間に全部無効になる**。相手には普通に届くので
誰も気づかない。

`relay/outbound` は `:allow` のときに `:persona.relay/from` を**必ず**返す。
呼び出し側が From を組み立てる自由を残さないためで、`:refuse` のときは
`:from` が無いので組み立てようがない。

## 状態は戻れない順

| 状態 | 受信 | 送信 | アドレス |
|---|---|---|---|
| `:active` | 転送 | 可 | 使用中 |
| `:disabled` | 拒否 | 不可 | **押さえたまま** |
| `:burned` | 拒否 | 不可 | 永久に予約、再発行しない |

`:disabled` でアドレスを解放しないのは、解放すると他人に再発行されうるから。
`:burned` から戻せないのは、戻すと昔の相手と新しい相手が同じアドレスを見て
静かに結びつくから。

上限（`:cap`）が数えるのは `:burned` 以外。burn を数え続けると、使い捨てを
繰り返した人が上限に張り付く。

## 上限はここが決めない

何本まで持てるかは信頼の段階が決める（`kotoba-lang/sekisho` の
`sekisho.assurance`）。ここは数として受け取り、超えたら理由を言って断るだけ。
上限の根拠をここに置くと、認証の強さと alias の数という無関係な 2 つの関心が
1 箇所に混ざる。

## 持たないもの

**SMTP・キュー・Email Routing**。`relay` が返すのは 1 通についての判断だけ。

**Public Suffix List**。`within?` は接尾辞比較で、`example.co.uk` と `co.uk` の
関係を判定しない。正しくやるには更新され続ける外部の表が要り、判断だけの純関数
repo に抱えると腐る。返るのは信号であって遮断ではないので、粗さは誤警報の側に
倒れる —— これはテストで明示している。

**乱数**。`issue` は byte 列を受け取る（`word-id` と同じ理由）。

## テスト

```bash
kbb -M:test                                                  # JVM
kbb --backend sci --classpath src:test:../word-id/src run-tests.cljk           # ClojureScript
```

受信の振り分けは Cloudflare Worker（CLJS）で動くので、両方で回す。
