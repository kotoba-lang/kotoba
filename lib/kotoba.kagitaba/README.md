# kagitaba — 1Password 互換キーチェーン(鍵束)データモデル + import

**鍵束(taba)** = category/field/item のタクソノミー。1Password の item モデルと
構造的に互換な EDN shape を、暗号にもストレージにも依存しない `.cljc` として持つ。
kagi(vault actor / PQC crypto / governance)はこの上に乗る消費者の 1 つで、
kagitaba 自体は crypto/store への依存を一切持たない zero-dep ライブラリ。

設計の正は superproject 側 **`90-docs/adr/2607023000-kagitaba-1password-keychain-cljc.md`**
と本リポの `docs/adr/0001-architecture.md`。

## なぜ kagi と別リポか

kagi-clj(`orgs/kotoba-lang/kagi`)は既に **PQC vault actor**(hybrid crypto +
AccessGovernor + 改竄検知台帳)として実装済み。kagitaba はその手前にある
「**1Password と同じ形の item を表現できるか**」という別の関心事——category の
taxonomy、field の型システム、1PUX からの import——を切り出したもの。kagi は
kagitaba を `:local/root` 依存として使い、kagitaba item を `pr-str` してから
kagi の DEK 封緘パイプラインに渡す(kagitaba はどこにも平文を保存しない)。

## レイヤ

| ns | 役割 |
|----|------|
| `kagitaba.category` | `categoryUuid`(1Password 001〜114) ⇄ 正準 keyword |
| `kagitaba.field` | section field の値型タクソノミー + 機微フィールド判定 |
| `kagitaba.item` | 正準 item/section/field shape、コンストラクタ、最小検証 |
| `kagitaba.schema` | カテゴリ別デフォルトテンプレート(新規作成用、best-effort) |
| `kagitaba.contract` | 契約(継続課金)を item の `Contract` section として表す正準形 + 時計なしの導出 |
| `kagitaba.capability` | provider 中立の権限 + resource。水準 `none<read<write<admin`、`covers?` / `excess`(ADR-0002) |
| `kagitaba.lease` | credential request の検証と lease(値を持たない発行記録)。`lease-state` は時計を引数に取る |
| `kagitaba.policy` | `decide` → allow / approve / deny(拒否理由つき)。既定は閉じる |
| `kagitaba.issuer` | 発行能力を持つ item(category `:issuer`)。`ceiling` = 発行できる最大の capability |
| `kagitaba.import.onepux` | 1PUX JSON → kagitaba item の**純粋変換**(IO なし、`.cljc`) |
| `kagitaba.import.onepux-file` | `.1pux` zip を読んで onepux へ渡す JVM 専用 IO 層 |

## item shape

```clojure
{:item/id "uuid"
 :item/category :login          ; kagitaba.category の正準 keyword
 :item/title "GitHub"
 :item/tags ["dev"]
 :item/favorite? false
 :item/url "https://github.com"
 :item/urls [{:label "primary" :url "https://github.com"}]
 :item/state :active            ; :active | :archived
 :item/username "jun"           ; Login category の convenience(sections にも残す)
 :item/notes "..."
 :item/sections
 [{:section/title "Login"
   :section/fields
   [{:field/id "password" :field/title "password"
     :field/type :concealed :field/value "hunter2" :field/sensitive? true}]}]
 :item/password-history [{:value "..." :time 1700000000}]}
```

`kagitaba.field/sensitive-types` = `#{:concealed :totp :credit-card-number :ssh-key}`。
呼び出し側(kagi)はこの集合に属す field を含む item を必ず暗号化して保存する。

## 1Password import(1PUX)

```clojure
(require '[kagitaba.import.onepux-file :as onepux-file])

(def result (onepux-file/load-1pux "/path/to/export.1pux"))
;; => {:attributes {...} :warnings [...] :files {name -> bytes}
;;     :vaults [{:account "jun@example.com" :name "Personal" :items [kagitaba item ...]}]}
```

- 入力は 1Password アプリの **Export > 1Password Unencrypted Export(.1pux)**。
- `categoryUuid`/field 型の対応表(`kagitaba.category`/`kagitaba.field`)は 1Password
  公式ドキュメントには `001`(Login)の例しか無いため、実 export と複数の独立
  1PUX パーサ実装を突き合わせて検証した値(001〜006, 100〜114)。
- **単一不変条件**: import はデータを黙って落とさない。未知 category/field 型は
  フォールバック keyword(`:category/<uuid>` / `:unknown`)で保持し、
  `kagitaba.import.onepux/item-warnings` が目視確認用の警告を返す(エラーにしない)。
- `files/` 配下の添付は best-effort で `{name -> bytes}` に集めるだけ(1PUX の
  ファイルパス構造は非公開のため、正式なドキュメント検証はできていない)。
- **op CLI 経由の import(`op item list/get --format json`)は未実装** — 1PUX を
  第一実装として置き、op CLI 連携は段階導入の TODO として設計だけ残す
  (`docs/adr/0001-architecture.md` 参照)。

kagitaba 自体は import した item を **どこにも永続化しない**。呼び出し側
(例: `kagi import onepassword`)が受け取った item を即座に暗号化してから
保存する責務を持つ。

## 開発

```bash
kbb -M:lint   # clj-kondo(errors fail)
kbb -M:test   # clojure.test
```

## Wi-Fi profiles

`kagitaba.wifi/profile` makes a `:wireless-router` item from an opaque ID,
verified account principal, SSID, password and personal WPA2/WPA3 security.
SSID, password and principal are concealed fields. `network` validates and
extracts a profile; `summary` is for the unlocked local UI and omits password
and principal. SSIDs are bounded by UTF-8 bytes. The current Node transport's
8–63 ASCII passphrase format is enforced; open/enterprise networks are not
supported by this initial provisioning contract. This library does not persist
anything. Send the whole item to the kagi governed sealing path immediately.

Node/SCI test: `kbb --backend sci --config nbb.edn --classpath src test/kagitaba/wifi_runtime.cljk`.
