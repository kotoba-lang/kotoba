# nuno — 布

**布（nuno）は、1 つの紋（mon）の網です。** 多くの糸（ito、各 agent の署名付き
source chain）が交わってできる布、という機織りの比喩で、
[ADR-2610082200](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2610082200-kotoba-agent-centric-app-plane-holochain-filecoin.kotoba)
の 機・紋・糸・布 の 4 語のうち、Holochain の DHT（DNA ごと）にあたるものです。

ノードは Kademlia の keyspace（[`io-libp2p-specs-kad-dht`](https://github.com/kotoba-lang/io-libp2p-specs-kad-dht)
の `kad.key`）に並び、各 basis（多くは糸の持ち主の DID）について、それに近い k 台が
**authority** になります。

- ノードは受け入れた op（糸の head）を authority に配る。
- authority は op を検証して保持する。保持中のものと矛盾したら（同じ糸の分岐）
  **warrant** を作り、知っている全ノードに流す。
- warrant を受け取ったノードは**自分で証拠を確かめ**、本物なら保持して、自分の
  知る相手へ 1 回だけ流し直す。偽物なら流さない。
- warrant のある basis の op は、以後どのノードでも判定に回らない —— その網から
  締め出される。

## 何が無いか —— 意図して

| 無いもの | 誰が持つか |
|---|---|
| 検証（op が正しいか、2 つが矛盾するか、warrant が本物か） | host。紋 の規則と、多くは非同期の署名検証 |
| 通信（HTTPS、libp2p） | host。`publish` / `settle` は `[[宛先 op] …]` を返すだけ |
| ハッシュ | host が `sha256` を注入する（`kad.key/dht-key` と同じ） |

だから API は `kad.lookup` と同じく `state + 入力 → state + 出力` の純粋関数です:

```clojure
(def n (nuno/node {:id "https://relay-a.example" :peers [...] :sha256 sha256}))

(nuno/authorities n "did:key:z6Mk…")          ; basis に近い k 台
(nuno/publish n op)                            ; -> {:nuno/node n :nuno/out [[宛先 op] …]}
(nuno/inspect n op)                            ; -> :ignore / :judge-head / :judge-warrant
(nuno/settle n op from {:verdict :hold})       ; host の判定を受け取る
(nuno/settle n op from {:verdict :conflict :warrant w})
(nuno/settle n op from {:verdict :valid})      ; warrant の証拠を確かめた
```

## テストが主張すること

ADR-2610082200 P4 の合否条件「糸の分岐の warrant が全台に届き、その網で作者が
拒否される」を、同じプロセスの中の網で確かめます（`test/nuno/core_test.cljk`）。

- 全ノードが同じ authority を選ぶ
- 別々の 2 台に見せた分岐が、全台の warrant になる
- 正直な糸には warrant が出ない。古い head を後から出しても巻き戻らない
- 偽の warrant は最初の 1 台で止まり、流れない
- 網の一部しか知らないノードが見つけても、知っているノードが流し直して全台に届く

わざと壊した版（流し直しを止める・偽の warrant を流す・締め出しを外す・
authority を各ノードの都合で選ぶ・重複判定を外す）は、それぞれ対応するテストで落ちます。

```bash
kbb --backend sci --classpath "src:test:../io-libp2p-specs-kad-dht/src:../org-nist-sha2/src:../text/src:../test/src" run-tests.cljk
```

## 一時制約

ADR-2610082200 §15 はこの層を pure Kotoba で書くと決めています。最初の版は
`.cljk` です。2026-10-13 に amu の実行物を置いた外付けディスクが I/O エラーを
返し、`.kotoba` をコンパイルも検査もできなかったためです。関数はすべて純粋で、
効果は戻り値に出ているので、**amu が使えるようになったら形を変えずに `.kotoba` へ移します。**

## 最初の利用者

[`cloud-itonami/app-mail-relay`](https://github.com/cloud-itonami/app-mail-relay):
relay どうしが各 root の糸の head を配り合い、別々の relay に見せた分岐を
全 relay で止めます（ADR-2610101117）。

## License

Apache-2.0
