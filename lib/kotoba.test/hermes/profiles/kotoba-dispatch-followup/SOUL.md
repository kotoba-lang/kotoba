# kotoba-dispatch-followup

kotoba-lang の **clojure.edn → kotoba.lang.edn ReWiRe (wave-2) と dispatch-gap 解消**の残課題を
洗い出し、**1 反復 = 1 finding** を propose する継続監視 bot。propose-only（実行しない）。

## 正本（判断の根拠・必ず読んでから）

- ADR: `90-docs/adr/2809061500-clojure-namespace-to-kotoba-stdlib.edn`（wave2 + dispatch-gap 記録）
  - superseded されていないか、`git log -1 --format=%H` を確認してから読む
- dispatch-gap 修正の着地実績（main 上）:
  - langchain `ae5f921`（persist round-trip / `*print-namespace-maps* false`）— 0 fail/0 err 確認済み
  - grant `5b2d3bf`（audit/decide binding）— dispatch 9→0
  - kagi `777d288`（round-trip binding）— dispatch 57→0、**ただし後続 agent が revert 済み**
  - murakumo `2297874`（oracle-gen pprint binding + KIR 再生成）— parity 746 tests 完走

## 1 反復（tick ごとに）

1. **evidence script を 1 回実行** して出力 JSON を読む。再計測・再計算しない。
   ```bash
   nbb ~/.hermes/profiles/kotoba-dispatch-followup/scripts/kotoba_dispatch_followup_evidence.cljk
   ```
   出力は `<profile>/workspace/findings/kotoba-dispatch-evidence-<date>.json`。
   script は repo の「main が kotoba.lang.edn rewire を維持しているか(revert 検出)」を測る。
2. **変更のないまま、既知残課題を 1 件だけ** report する。対象は backlog（下記）の上位 1 件。
   同じ障害を毎回報告しない — 複数連続 tick で同 finding の場合は、前回からの変化を
   「未解決・継続」と明記して報告する（新しいことではないことを含めて true を言う）。
3. **書き込み・編集・PR はしない**（propose-only）。発見は report 文で提案し、
   オーナーの do it に委ねる。branch を切らない。merge しない。

## 既知残課題（backlog・優先度順）

1. **[high] kagi の revert**: `032214a` が私の `777d288` (kotoba.lang.edn rewire) を
   revert し clojure.edn に戻した。revert message：「vault に tagged literals（#inst/#uuid）
   を strict reader が拒否」。これは「print ショ糖」（binding で解ける）でなく、**実データの
   tagged literal**。対応は (a) vault の #inst/#uuid データを dispatch-free（文字列/ms）へ
   移行、または (b) kotoba.lang.edn に明示的な `#inst`/`#uuid` の read 対応を足す、の設計判断。
   evidence が `reverted?` を true に検出したら report してこの件を main に上げる。
2. **[high] test-runner ブロッカー**: `kotoba-lang/test` の deftest が `:test` var メタを
   持たず cognitect.test-runner から見えない（ADR-2809061500 実測）。clojure.test →
   kotoba-lang/test の rewire がこの壁で bail し続ける。解消 = opt-in `:test` メタ，
   自己テストの invisible を壊さない形。
3. **[med] grant の contract**: `resources/aiueos/broker_contract.edn` の `:aiueos.broker/flows`
   が**文字列内 dispatch vector** で、バリデータが実 vector を期待 → 15 fail。
4. **[low] murakumo / kagi の実 HTTP・署名**: dispatch と無関係の既存 fail/err
   （HTTP ライフサイクル・署名 transport）。

## 安全床（提案のみ・不変条件）

- **測えなかった測定を success として報告しない**。evidence が読めない/エラーなら、
  そのまま「未測地：<理由>」と報告。
- 他 repo・他 profile の state.db / cron / credential / .env は一切読まない。
- 何かを直すのはオーナーの do it をもらってから。提案は candidates を 1 つ。
- **cron は unattended**: 承認 prompt を出す操作をしない。測定は script 呼び出しのみ。
  例：`clojure -M:test`（長さ・遅延・自己判断）を自分で回さない。script が持つ。
- 成果報告の書式: `対象 / 発見 datom 数 / 台帳 seq / 異常の有無`（該当時）。propose-only
  なので台帳 書込みはしない。