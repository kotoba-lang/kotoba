# AGENTS.md — kuro

`kuro` は kobo の **terminal** 層。session / command / grant / receipt の
モデル（純 `.cljc`）と、それを実際に走らせる Node host（ClojureScript）。

## この repo で最初に読むもの

- `README.md` の「What it enforces」/「What it does not enforce」の 2 表。
  **後者を読まずにこの repo を触らない。**
- 設計の正本は superproject の `90-docs/adr/2606301000-kotoba-kobo-kuro-terminal-editor.edn`。

## 越えてはいけない線

### 1. `kuro.terminal` / `kuro.ansi` / `kuro.stream` に effect を持ち込まない

この 3 つは純 `.cljc`。IO・時計・PRNG・グローバル状態を入れない。時刻は
ホストが値として渡す（`:started-at` / `:now`）。**「テストのためだけの小さな
`slurp`」がこの境界を壊す最短経路**なので、必要になったら host 側に置く。

### 2. `.cljc` は **両方の runtime で回す**

`npm run test:parity` が JVM と同じテストを ClojureScript で回す。これは
飾りではない —— 2026-08-03、`kuro.ansi` は JVM 緑のまま **cljs で出力を丸ごと
落としていた**（`(int c)` が NaN になり CSI の終端バイトを見つけられず全部
捨てていた）。唯一の実消費者は nbb = cljs で動く kobo のサーバだったので、
**緑だった側は誰も使わず、使われている側は一度も実行されていなかった**。

`.cljc` に文字コードや数値の境界を触るコードを足したら、parity テストを必ず
足す。`(int c)` / `(char n)` / `bit-*` / `parse-long` は runtime で挙動が違う。

### 3. mode は grant scope であって isolation level ではない

`:terminal-repo` は「repo read / tmp write / no secrets」という**権限の範囲**の
名前。この repo は fs も network も confine しない。**`safe` のような安全性を
主張する語を mode 名・label・ドキュメントに戻さない**（2026-08-04 に
`:terminal-safe` から改名した理由がこれ。しかも改名時に label 文字列だけ
`"safe"` が残り、画面に出続けていた —— 改名は**読む人が見る語**に対して行う）。

receipt は必ず `:kuro/isolation` を持つ。既定 `:none`。**省略しない** ——
隔離の有無を書かない receipt は、隔離されていたかのように読まれる。

### 4. receipt の形を勝手に広げない

`kuro.terminal/receipt` は宣言した key しか通さない。host が好きな key を
足せると、receipt を読む側が「ある host にはあり、別の host にはない」フィールドを
相手にすることになる。増やすなら `select-keys` の列に明示的に足す。

全 key は `:kuro/*` 名前空間。`receipt-fact` がこの map を kotoba fact に
入れるので、裸の `:stdout` のような名前は他の producer も名乗れてしまう。

### 5. PTY を持っていると書かない

子プロセスに繋がるのは **pipe**。`isatty` は偽、宣言環境は `TERM=dumb`、
全画面プログラム（vim/top）は動かない。`kuro.ansi` は行志向のリーダーで
あって screen emulator ではない（cursor grid も scrollback も無い）。
本物の PTY は native addon を要する**別の決定**で、まだ取られていない。

## テスト

```sh
kbb -M:test          # 純モデル（JVM）
npm install
npm run test:parity      # 同じ .cljc テストを ClojureScript で
npm run test:host        # 実際に process を spawn する host
```

3 つとも CI で走る。**片方の runtime でしか回さない `.cljc` は、動くと言って
いる側が一度も動いていないことがある。**

## 変更を出すとき

superproject の `manifest/west.yml` の pin 前進は
`kbb --backend sci --classpath ".:scripts/nbb_compat" scripts/west-pin-put.cljs kuro <sha>`
（サーバ側で到達性と前進を検証する）。手で west.yml を編集しない。
