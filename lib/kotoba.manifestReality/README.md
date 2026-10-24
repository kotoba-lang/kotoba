# manifest-reality

**west manifest が宣言することと GitHub の実態の乖離を検出する、純 `.cljc` ライブラリ。**

`90-docs/repo-reality/` が「doc が主張することと code の実態」の乖離を見るのに対し、
ここは **manifest（`west.yml` / `repos.edn`）が主張することと repo の実態**を見る。

## なぜライブラリなのか（実行器ではなく）

同じ不変条件を **GitHub Actions と murakumo fleet-ci の両方**が走らせる。
実装が 2 つあると「片方だけ通る状態」が黙って生まれるので、**ロジックはここ 1 箇所**に置き、
両方の呼び出し側は入力を用意して呼ぶだけの薄いアダプタにする。

そのため **この ns は HTTP も fs も触らない**。実態（GitHub の repo 一覧・redirect
解決結果・repo の file 一覧）は呼び出し側が集めて data で渡す。

```
呼び出し側 (IO)                    manifest-reality (純関数)
  west.yml を読む          ─┐
  repos.edn を読む          ├─→  (audit {...}) ─→ findings [{:check .. :severity ..}]
  GitHub API を叩く        ─┘
```

## 検査

| check | severity | 何を見るか |
|---|---|---|
| `:west/stray-block` | error | `projects:` セクション外に project 形のブロックが混入していないか |
| `:west/remote-org-mismatch` | error | `remote:` が path の org と一致するか |
| `:west/groups-org-mismatch` | error | `groups:` が path の org と一致するか（`[archived]`/`[datalad]` は除く） |
| `:repos-edn/stale-path-key` | warn | `:rad-rids`/`:datalad`/`:archived` に west に無い path のキーが残っていないか |
| `:west/orphan-entry` | error | west にあるが GitHub に存在しない entry（fetch できず `west update` を壊す） |
| `:west/unregistered` | warn | GitHub にあるが west に無い repo |
| `:west/duplicate-entry` | error | 2 つの path が同じ GitHub repo を指していないか |
| `:west/credential-shaped` | error | 鍵束の形をした repo（登録すると全 clone に鍵が撒かれる） |

### それぞれが実在の事故に対応している

- **stray-block** — project ブロックが `remotes:` に挿入され、west が remote として
  誤解釈しうる状態になった（Contents API の single-entry commit が挿入位置を誤った）
- **stale-path-key** — org 移送でキーが取り残され、**287 件の Radicle RID が dead key** に
  なっていた。うち 63 件は west.yml からも RID が落ちていた
- **orphan-entry / duplicate-entry** — rename / transfer 済みの repo を旧 path のまま
  指す entry が残り、GitHub の redirect で fetch が通るため気付けなかった。
  **消す側の pin が先行しているケースがあり**、単純削除は pin を巻き戻す
- **credential-shaped** — `certs/**/*.p12` と `*.mobileprovision` を持つ
  Fastlane match の証明書 repo が、登録候補に混ざっていた

## 使い方

```clojure
(require '[manifest-reality.checks :as c])

(c/audit {:west       west-yml-string        ; 必須
          :keyed-maps {:rad-rids {...}}      ; 任意
          :gh-repos   #{["org" "name"] ...}  ; 任意（無ければ突合系は走らない）
          :resolve    (fn [path] repo-id)    ; 任意
          :repo-files {["org" "name"] [...]} ; 任意
          :ignore?    (fn [[org name]] ...)})
;; => [{:check :west/orphan-entry :severity :error :subject "orgs/.." :detail {..}} ...]

(c/errors findings)   ; error だけ（gate の exit code はこれで決める）
(c/summary findings)  ; {[check severity] count}
```

`:gh-repos` などを渡さなければその検査は走らない。**ファイルだけで完結する検査
（構造 / org 整合 / stale key）と、GitHub API を要する検査（突合系）で
cadence を分けられる**ようにするため — 前者は毎 tick、後者は日次でよい。
フルスイープは 4,000 コール規模になるので 5 分間隔には載せないこと。

## テスト

```bash
kbb --backend sci --classpath src:test run_tests.cljk   # 10 tests / 23 assertions
kbb -M:test                            # JVM 側
```

## ライセンス

親 workspace の方針に従う。
