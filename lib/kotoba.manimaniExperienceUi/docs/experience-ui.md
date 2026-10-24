# Experience UI — Kinetic Companion

## 役割

まにまに君は「流れを預かり、仕事の運動状態を身体で伝える」随伴者です。ハムスターがwheelを走るように、まにまに君自身がマニ車の内側を走ります。マニ車はagent loop、token投入、検証の循環を表します。常に穏やかに回り、ユーザーの操作や実際の進捗で走りと車輪が加速し、慣性をもって基礎速度へ戻ります。

車輪と身体は別layerです。車輪は回転し、まにまに君は車輪の底で接地を保ちながら小さく上下します。身体を車輪と一緒に回転させたり、車輪の横へ置いたりしません。

## 状態と振る舞い

| system state | companion behavior | 意味 |
|---|---|---|
| idle / ready | ゆっくり一定回転、呼吸 | いつでも預かれる |
| input accepted | 短いsquash、目線を対象へ | 入力を受け取った |
| running | 速度が仕事量で緩やかに変化 | agentが処理中 |
| external wait | 回転を保ち、耳を澄ます | GitHub/人間を待つ |
| blocked | 急停止せず減速、障害物を見る | 原因を発見した |
| user press | impulseを加え一時加速 | 応援。処理能力の偽装はしない |
| device shake | 上限付きimpulse、粒子効果 | 遊びの入力。実行権限は変えない |
| verified receipt | 一周だけ祝福、receiptを掲げる | 外部検証済み |
| failure | 転倒させず、立て直し動作 | 回復可能性を伝える |

## Motion physics

- 基礎角速度を0にしない。ただし静止設定とreduced-motionを尊重する
- 押下は角速度へのimpulse。押している間だけ線形に回す実装を避ける
- 摩擦で指数的に基礎速度へ収束する
- 連打とshakeにはsoft capを設け、発光や音量も飽和させる
- 実際のagent進捗と応援入力を別変数にする。応援でfake progressを増やさない
- motionはtransform/opacityを中心にし、layoutを揺らさない

## Reward grammar

報酬は「tokenを大量消費したこと」ではなく、価値が確認されたことに与えます。

- micro: 入力受付、step完了 — 小さな音、表情、粒子1–3個
- milestone: blocker解除、PR作成、checks成功 — マニ車の色相変化、短い軌跡
- receipt: merge後の検証完了 — 一度だけ明確な祝福、証跡カード

同じ演出を短時間に繰り返さず、既知の成功は静かに扱います。課金、token消費、連打を過度に促す可変報酬は使いません。

## Visual language

- 形: 丸い伴走者と回転体。業務カードは安定した矩形
- 色: companionの感情色とsystem severity色を分離
- 線: 外形は太め、内部情報は細く。小サイズでもsilhouetteを保持
- 素材感: 柔らかな玩具感を演出に限定。diff、log、権限UIには使わない
- コピー: 短く具体的。「がんばっています」ではなく「Actions 2/4を確認中」

## Anti-patterns

- 全カードを玩具にして情報密度を失う
- private repoを可愛い色だけで示す
- spinnerとしてまにまに君を無期限に走らせる
- agent failureでキャラクターを罰する、泣かせ続ける
- animation終了を処理完了と誤認させる
- Nintendoや既存キャラクターの輪郭、配色、効果音を模倣する
