# ADR-0002: issuer・credential request・lease・policy の形

**Status**: accepted (implemented 2026-10-13) · **Date**: 2026-10-10 · **Deciders**: Jun Kawasaki

kagi ADR-0003（credential broker と MCP）が使うデータの形を、kagitaba の原則
（zero-dep `.cljc`、crypto/store 非依存、データを黙って落とさない）のまま定義する。
振る舞い（発行・封入・承認・MCP）は kagi 側。

## 背景

kagitaba の item は「人が保管する値」（login、API credential、SSH key …）を
1Password と同じ形で表す。2026-10-10、フリートのノードに GitHub の読み取り権限を
渡す必要が出たが、持ち主は最小権限トークンの作り方を知らなかった。kagi は
「人が作った長期トークンを保管する」から「長期の根から短命の資格情報を発行する」へ
広がる（kagi ADR-0003）。その語彙は kagi 固有ではなく、どの消費者
（kagi CLI、MCP サーバ、ブラウザ）でも同じ形で読めるべきなので kagitaba に置く。

## 決定

新しい ns を 4 つ足す。どれも純粋データと検証だけ。

### `kagitaba.issuer` — 発行能力を持つ item

既存 item の category に `:issuer` を加える（1Password に対応 uuid は無いので
kagitaba 固有の正準 keyword。1PUX export では `:category/issuer` として保持）。

```clojure
{:item/category :issuer
 :item/title    "github-app: kotoba-fleet"
 :issuer/kind   :github-app
 :issuer/public {:app-id 123456 :slug "kotoba-fleet"
                 :installations [{:id 789 :account "cloud-itonami"}
                                 {:id 790 :account "kotoba-lang"}]
                 :permissions {:contents :read :metadata :read
                               :pull-requests :write}}
 :item/sections [{:section/fields
                  [{:field/id "private-key" :field/type :concealed :field/value "<PEM>"}]}]}
```

- `:issuer/public` は秘密を含まない（App ID、インストール先、App が持つ権限の上限）。
  policy の検証と MCP の `issuer` 一覧はこれだけで足りる。
- 秘密（秘密鍵）は既存の `:concealed` field に入り、`kagitaba.field/sensitive-types`
  の判定がそのまま効く。
- `kind` ごとの `:issuer/public` の必須キーを `issuer-schemas` に持つ
  （`:github-app` → `#{:app-id :installations :permissions}`）。未知の kind は
  警告つきで保持し、落とさない。

### `kagitaba.capability` — provider 中立の「何をしたいか」

```clojure
{:capability/provider :github
 :capability/access   {:contents :read :metadata :read}   ; 権限 → 水準
 :capability/resources ["cloud-itonami/cloud-itonami-isic-0111"]}
```

- 水準は全順序 `:none < :read < :write < :admin`。`(covers? granted wanted)` は
  権限ごとの水準比較と resource のパターン照合（`org/*`）だけで決まる。
- provider ごとの権限名は provider の語彙をそのまま使う（GitHub の
  `contents` `pull_requests` …）。kagitaba は翻訳しない。

### `kagitaba.credential-request` と `kagitaba.lease`

```clojure
;; agent が頼む形（MCP の credential_request 入力と同形）
{:request/id        "req-…"
 :request/principal "did:key:z6Mk…"          ; 要求者 agent
 :request/capability {…}                      ; 上の capability
 :request/ttl-sec   3600
 :request/purpose   "hermes-cron:physai-isic-0111"}

;; 発行記録（秘密を含まない。台帳と MCP の credential_status が返す形）
{:lease/id         "lease-…"
 :lease/request-id "req-…"
 :lease/issuer     "github-app: kotoba-fleet"
 :lease/principal  "did:key:z6Mk…"
 :lease/capability {…}                        ; 実際に発行した範囲（要求以下）
 :lease/issued-at  1791600000                ; unix 秒(時計を持たない導出のため整数)
 :lease/expires-at 1791603600
 :lease/approval   {:by :policy :rule 0}      ; or {:by :passkey :approver "did:…"}
 :lease/state      :active}                   ; :active | :expired | :revoked
```

- `lease` は **値を持たない**。値は kagi が要求者の公開鍵へ封入して別に返す。
  だから lease 記録は台帳にも MCP の返り値にもそのまま出せる。
- `(lease-state lease now)` は時計を引数に取る純粋関数（`kagitaba.contract` の
  「時計なしの導出」と同じ流儀）。

### `kagitaba.policy` — 自動発行・承認・拒否の判定

```clojure
{:policy/principal "node@joseph"
 :policy/issuer    :github-app
 :policy/allow     [{:capability {…} :max-ttl-sec 3600}]
 :policy/approve   [{:capability {…} :by :passkey}]}

(decide policy request) ;=> {:decision :allow :rule 0}
                        ;   {:decision :approve :rule 0 :by :passkey}
                        ;   {:decision :deny :reasons [...]}
```

- `decide` は純粋関数。allow の規則のどれかが request を `covers?` し TTL が上限内なら
  `:allow`、approve に当たれば `:approve`、どれでもなければ `:deny` と理由
  （どの権限・resource・TTL が超えたか）。理由は agent が範囲を絞り直すのに使う。
- 判定と表現だけを持ち、通知や承認 UI は kagi 側。

## 影響

- kagi・MCP サーバ・ブラウザ UI が同じ形を読み書きでき、判定（`decide` `covers?`）が
  どこでも同じ結果になる。
- 既存の item モデル・1PUX import には変更なし（category が 1 つ増えるだけ）。

## 段階

1. `capability`（水準・`covers?`・パターン照合）とテスト。
2. `credential-request` / `lease`（形・検証・`lease-state`）とテスト。
3. `policy`（`decide` と拒否理由）とテスト。
4. `issuer` category と `issuer-schemas`、`:github-app` の public 部。
