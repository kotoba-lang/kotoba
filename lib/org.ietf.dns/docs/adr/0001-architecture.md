# ADR-0001: nameserver — a real RFC 1035 authoritative DNS server + IPNS alt-root bridge

- Status: Accepted — implemented, tested (27 tests / 54 assertions incl.
  genuine socket-level tests), `dig`-verified against a running instance.
- superproject 記録: `90-docs/adr/2607083100-kotoba-lang-nameserver-domain-hosting.md`
  （リポジトリは初期実装後に `nameserver` → `org-ietf-dns` へ改名。理由は
  `90-docs/adr/` の rename ADR を参照 — RFC 1035 が IETF RFC であることに
  基づく reverse-domain 命名、`org-ietf-turn`/`org-ietf-ical` 等と同型）

## 課題

このリポジトリ群には DNS 関連ライブラリが既に2つある: `zone`(ゾーンファイルを
EDN として扱うモデル/検証/diff)と `godaddy-dns`(GoDaddy レジストラ API クライアント)。
だがどちらも**実際に DNS クエリへワイヤプロトコルで応答する権威ネームサーバー**では
ない — `zone` はデータ表現、`godaddy-dns` はレジストラ側のレコード管理に留まる。
「.com 等の実 TLD を自前ネームサーバーでホスティングしたい」「`.hogehoge` のような
独自ネームスペースをホスティングしたい」という要求に対し、両者を繋いで実際に
`dig`/`nslookup` から引ける権威応答を返す層が存在しなかった。

## 決定

### 1. ワイヤプロトコル (`nameserver.wire`) は zone.model の `:zone/*` 形状をそのまま再利用

RR (resource record) は `zone.model`/`zone.zone` が使うレコード形状 —
`{:zone/name :zone/ttl :zone/class :zone/type :zone/rdata {...}}` — と
**完全に同一**（`:zone/name` だけ zone-relative でなく絶対 FQDN）。ゾーンファイル
⇄ EDN ⇄ ワイヤバイト間に変換レイヤーを追加しない。

エンコーダは名前圧縮（メッセージ内で一度出現した名前サフィックスへの
ポインタ参照、RFC 1035 §4.1.4）を実装。デコーダは圧縮ポインタを解決するが、
悪意あるポインタ循環に対して jump-count guard（128 回で例外）を持つ —
未検証入力（生の UDP パケット）を安全に捌く必須の防御。

### 2. ストア (`nameserver.store`) は単一マスター・権威データプレーンに限定

`{origin -> zone.model zone}` の map から最長サフィックス一致でゾーンを選び、
exact / wildcard / CNAME chase / NODATA / NXDOMAIN を判定。AXFR/IXFR・DNSSEC・
委任境界の NS リファラルは非スコープ（親子ゾーン両方を持つ場合、レコードは
単にそれぞれの zone map に存在するだけで、リファラルの別ステップは無い）。

### 3. リゾルバは `IResolver` protocol による注入可能な capability（`IDns`/`mock-computer` と同型）

`zone-store-resolver`(実ゾーン) と `custom-tld-resolver`(alt-root) を
`chain-resolver` で束ね、先頭から試して `:refused` 以外が出たら採用。
実 TLD ゾーンを優先し、alt-root カスタム TLD をフォールバックにする構成が典型。

### 4. カスタム TLD (`nameserver.custom-tld`) は IPNS 鍵由来名への dnslink ブリッジであり、グローバル解決の主張ではない

`.hogehoge` のような架空 TLD は誰にもグローバルな解決権を付与できない
（ICANN root の外）。本ライブラリが提供するのは **alt-root**: このネームサーバーに
向けたクライアント（stub resolver / ブラウザ拡張 / 自前クライアント）に対して、
`ipns.core/name->pubkey` で構文検証できる鍵由来ラベルを [dnslink](https://dnslink.io)
規約の TXT レコード（`dnslink=/ipns/<name>`）として返す。所有権移譲や共有 token は
不要 — 秘密鍵を保持すること自体がその名前への authority だから（`ipns.core` の
docstring と同じ設計思想）。IPNS のネットワーク解決自体(libp2p/publish/resolve)は
`ipns.core` 自身の非スコープと同じく本ライブラリの非スコープ。

### 5. ソケット層 (`nameserver.server`) だけ `.clj`（JVM 限定）

本リポジトリの `.cljc`/`.kotoba` ランタイム優先順位（kotoba wasm >
clojurewasm > ClojureScript > nbb > JVM、AGENTS.md 2026-07-07 改訂）に従うと、
生ソケット bind は他ランタイムに移植先が無い: kotoba wasm の `actor:host` ABI は
閉じた host-import 表に raw socket capability を持たず（ADR-2607062330）、
ブラウザも UDP:53 を bind できない。よって JVM は「最後の手段」として意図的に
選択（既定ではない）。リゾルバ注入により、ソケット層自体は薄い wire-up
（decode → resolve → encode → reply）に留め、512 バイト UDP 上限超過時は
TC ビットを立てて TCP フォールバック（RFC 1035 §4.2.1）。

### 6. 実 TLD の委任は `nameserver.delegate` の純データ変換 + `godaddy-dns` の `IDns`

サブドメインを本ネームサーバーへ NS 委任するための NS + glue-A レコード
編集セットを純関数で計算し、`godaddy-dns` の `IDns`(dry-run 既定)へ渡す。
ドメイン全体の apex ネームサーバー変更（レジストラアカウント側の操作）は
`godaddy-dns` の `IDns` 自体が実装していないので、ここでも非スコープとして
明記する（過剰主張しない）。

## Rationale

- **データ第一・変換レイヤーを増やさない**: `zone.model` の `:zone/*` 形状を
  ワイヤ RR にもそのまま採用したことで、ゾーンファイル・EDN・ワイヤバイトの
  三者が同じスキーマを共有し、`zone.zone/parse-str` の出力がそのまま
  `nameserver.store`/`nameserver.wire` に渡せる。
- **注入可能な capability seam**: `IResolver` は `godaddydns.dns/IDns` /
  `computer-use-clj` の `mock-computer` と同じ設計原則 — 実装を差し替えられる
  ことでテスト・デモがネットワーク/権限なしで完結する。
- **正直なスコープ境界**: 「グローバルな `.hogehoge` 解決」のような過大な主張を
  しない。zone-clj の「well-formed subset」・godaddy-dns-clj の「非スコープ」
  節と同じ誠実さの流儀を踏襲。
- **実ソケットでの検証**: ユニットテストだけでなく、実際に `DatagramSocket` を
  bind してワイヤバイトを送受信するテスト、および `dig` による手動検証を実施
  —この過程で `:zone/name` が "@" のまま(絶対 FQDN 化されていない)というバグを
  ユニットテストは検出できず、`dig` の出力を目視して発見・修正した
  (`nameserver.store`)。ユニットテストにも `:zone/name` の回帰防止アサーションを
  追加済み。

## Consequences

- ASCII ラベルのみ(IDN は punycode で ASCII 化されるため実用上の制約ではない)、
  TXT/CAA は 255 オクテット以下(単一 character-string)、EDNS0/DNSSEC/AXFR
  非対応 — README に明記。
- レート制限/接続スロットリングは圧縮ポインタ loop guard 以外実装していない。
  公開デプロイは別途 DoS 対策が必要。
- カスタム TLD ブリッジは alt-root であり、クライアント側がこのネームサーバーを
  指すよう設定しない限り解決されない(Handshake/ENS-via-gateway/OpenNIC と同じ
  現実)。

## Verification

`kbb -M:dev:test`: **27 tests / 54 assertions / 0 failures**
(wire round-trip全型・名前圧縮・悪意ポインタ循環・truncation、store の
exact/wildcard/CNAME/NODATA/NXDOMAIN/ANY、resolver chain、custom-tld の
dnslink/CNAME/NXDOMAIN/REFUSED、delegate の純関数、server の実ソケット UDP
統合テスト4本)。加えて `examples/run_server.cljk` を起動し実 `dig` で
A/CNAME/NXDOMAIN/ANY/TCP フォールバック/カスタム TLD TXT・CNAME を目視確認。

## 7. 実運用エントリポイント (`nameserver.main`) + systemd/Docker（2026-07-08 追記）

「実際にネームサーバーとして動かすには」という問いを受け、REPL/`run_server.clj`
の demo と実運用の間を埋める CLI エントリポイントを追加した:

- **`nameserver.main`** — `kbb -M -m nameserver.main [config.edn]`。
  config は `:host`/`:port`/`:zones-dir`(ディレクトリ内の全 `*.zone` を
  `zone.zone/parse-str` でロード、キーは各ファイルの `$ORIGIN`)/`:custom-tld`
  (任意)。`chain-resolver` で hosted zones → custom-tld alt-root の順に組み、
  `nameserver.server` を起動、JVM shutdown hook で `SIGTERM`/`SIGINT` 時に
  `stop-server!` を呼びソケットを正常終了する。この形（env-var config +
  shutdown hook + `@(promise)` blocking）は本 org 内の既存パターン
  （`murakumo/relay_server.clj`、`ai-gftd-syosetsuka/server.cljc`）と同型 —
  新規に発明していない。
- **`deploy/org-ietf-dns.service`** — systemd unit。`AmbientCapabilities=
  CAP_NET_BIND_SERVICE` で 53 番ポートを root 無しに bind できるようにする
  （本 org に既存の JVM 向け systemd unit 前例は無く、唯一の前例
  `kotodama-py/.../ameno-daemon.service` は Python daemon だったため、
  `Type=simple`/`Restart=on-failure`/journal ログといった**形**だけ流用し、
  `ExecStart`/capability 部分は新規に書いた）。
- **`Dockerfile`** — uberjar を作らず、この org の他サービス
  （`ai-gftd-syosetsuka` 等）と同じ「ソースを Clojure CLI で直接動かす」形。
  本 org 全体を調査したが `tools.build`/uberjar の前例は皆無だったため、
  それを新規導入せずこの org の既定パターンに合わせた。**Docker build 自体は
  未検証**（作業環境に Docker daemon が起動していなかったため）——README に
  「未検証」と明記し、動作確認済みと偽らない。
- README に「Running for real」節を追加: port 53 bind の3方法
  （setcap / systemd AmbientCapabilities / Docker）、実トラフィックの
  獲得（NS委任、既存の delegate 節を参照）、そして
  **カスタム TLD のクライアント側設定**（`.hogehoge` は誰のデフォルト
  resolver にも載っていないため、`systemd-resolved`/`dnsmasq` での
  split-horizon 転送設定を具体例つきで追記——これが ADR-2607083100 の
  「次段」に残していた「custom-tld ブリッジの実クライアント側resolver
  設定手順のドキュメント化」の実施にあたる）。

### Verification（追記分）

`kbb -M -m nameserver.main examples/config.edn` を実際に起動し、
実 `dig` で A / CNAME / カスタム TLD dnslink TXT を再確認、`kill` による
`SIGTERM` で shutdown hook が正しく発火しソケットが閉じることを確認
（ログに "shutting down..." → プロセス終了）。`clj-kondo` (`kbb -M:lint`)
0 errors/0 warnings。
