# ADR-0001: godaddy-dns-clj — portable Clojure, dry-run-first DNS agent

- Status: Accepted — 実装済み・root main マージ済み (2026-06-25)
- 関連: langchain-clj / langgraph-clj / computer-use-clj / browser-use-clj ADR-0001
- superproject 記録: `90-docs/adr/2606251621-godaddy-dns-clj-dns-management-agent.md`

## 課題

GoDaddy がホストする DNS を、ターミナルから自然言語で操作できる AI エージェントとして
実装したい。制約は本ファミリーと同じ:

1. **Clojure-on-WASM 前提**（実 DNS API はホスト能力として注入、`.cljc` 純度を保つ）、
2. **Datomic API 前提**（操作履歴を EAV ファクトとして保持）。

加えて DNS 固有の事情として **書き込みが破壊的**（A レコードの誤更新でサイトが落ちる）
であるため、デフォルトは安全側に倒す必要がある。

## 決定

### 1. DNS はホスト能力 (IDns protocol)

`godaddydns.dns/IDns`（`-list-domains` / `-list-records` / `-upsert-records!` /
`-delete-records!`）。実装はホストが注入する:

- `godaddydns.godaddy/godaddy-dns` — `api.godaddy.com` を叩く実装。HTTP と JSON は
  注入された `:http-fn` / `:json-read` / `:json-write` で行い、**第三者依存ゼロ**を維持
  （langchain-clj 全体と同じ seam）。認証は `sso-key KEY:SECRET` ヘッダ。`:base` を
  `https://api.ote-godaddy.com` にすると OTE テスト環境。
- `godaddydns.dns/mock-dns` — インメモリの決定的ゾーン。ネットワークも API キーも不要で、
  テストと「鍵なしデモ」を成立させる（computer-use-clj の `mock-computer` に相当）。

### 2. GoDaddy のセマンティクスを忠実に写す

GoDaddy の `PUT /v1/domains/{domain}/records/{type}/{name}` は、その (type,name) の
**レコード集合を丸ごと置換**する。`-upsert-records!` はこの置換契約をそのまま実装する
ので、mock と実ホストの挙動が一致する（テストで保証）。

| GoDaddy API | godaddy-dns-clj |
|---|---|
| `GET /v1/domains` | `-list-domains` / `list_domains` |
| `GET …/records[/{type}[/{name}]]` | `-list-records` / `list_records` |
| `PUT …/records/{type}/{name}`（集合置換） | `-upsert-records!` / `upsert_record` |
| `DELETE …/records/{type}/{name}` | `-delete-records!` / `delete_record` |
| `sso-key KEY:SECRET` | `godaddy-dns` `:key` / `:secret` |

### 3. 書き込みは dry-run 既定（安全不変条件）

`godaddydns.tool` の write ツール（`upsert_record` / `delete_record`）は `dry-run?` で
ゲートされる。真（既定）のときは **IDns を一切呼ばず**、意図した変更を plan-atom に積んで
`PLANNED: …` を返す。`agent/run` は `:plan` に計画変更一覧を、`:applied? false` を返す。
`:dry-run false` を明示したときだけ実 API に適用し `APPLIED: …` / `:applied? true`。
read ツールは常に実行。これにより「鍵・権限なしでも計画まで安全に試せる」。

### 4. サンプリングループ + 操作履歴は datom

`godaddydns.agent` — langgraph StateGraph（`:agent ⇄ :tools`、`done` tool 終端、
`:recursion-limit`）。`:history-conn` を渡すと全ツール呼び出しが session entity +
dnsaction entity の datom になり（`:dnsaction/{tool,domain,record,input,result,applied?}`）、
Datalog で監査可能（「session s1 で変更したレコード」「example.com に触れた全 session」）。

### 5. 非スコープ

- 他 DNS プロバイダ（Cloudflare / Route53 等）— 必要になれば別の IDns 実装を足す。
  プロトコルはプロバイダ非依存だが、本リポジトリは GoDaddy 実装に集中する。
- ドメイン購入・移管・証明書 — DNS レコード管理に絞る。

## 帰結

- 鍵なし・ネットワークなしで全ループをテスト/デモ可能（mock + dry-run）。
- 実運用では OTE → DRY_RUN=true で計画確認 → DRY_RUN=false で適用、の三段で安全に進める。
- GoDaddy の書き込み API はアカウント条件で制限される場合があるが、設計上それに触れずとも
  開発が完結する。

## 実装状況（closing, 2026-06-25）

- **repo**: `com-junkawasaki/godaddy-dns-clj`（MIT, public, init `e279abf`）。
- **submodule**: `orgs/com-junkawasaki/godaddy-dns-clj` を superproject `root` に登録、
  pin `e279abf`（main fast-forward `4bbfe812`、GitHub Data API server-side commit）。
- **名前空間**: `godaddydns.{dns,godaddy,tool,agent}`（全 `.cljc`）+
  `examples/{jvm_host,dns_agent}.clj`。
- **検証**: `kbb -M:test`（公開 git deps）/ `-M:dev:test`（local checkout）とも
  **8 tests / 38 assertions / 0 failures**。dry-run（計画のみ・ゾーン不変・datom ログ）と
  live（適用・`applied? true`）を end-to-end でアサート。
- **次段**: 他プロバイダ IDns 実装、OTE→prod 実適用の e2e 検証。
