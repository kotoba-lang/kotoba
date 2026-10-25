# ADR-0002: mail IMAP capability — programmatic read via injected IMail

- Status: Accepted (2026-06-29)
- 関連: ADR-0001, kawasakijun ADR-0009 / 0013, kagi-clj ADR-2606272330,
  manimani channels.email

## 課題

computer-use-clj でオペレータの Gmail を読みたい。
2 つの取得経路があった:

1. **OAuth(via gcloud SDK client)** — `403: restricted_client /
   Unregistered scope(s)`。gcloud SDK の OAuth client(`32555940559…`)
   は restricted client で Gmail scope が未登録のため、Gmail scope を
   要求すると Google に弾かれる。回避不能。
2. **デスクトップ画面操作(IComputer で Mail.app / ブラウザ Gmail を
   screenshot+click)** — 文字通り computer use だが、**kawasakijun
   ADR-0009:84-90 が「agent はパスワードサインインを computer use /
   1Password 経由でも行ってはならない」**と禁止。既サインイン状態の
   Mail.app を読むだけなら合憲だが、座標依存で脆く、メール本文の
   スクショが model に送られる(プライバシ)。

## 決定

**第3の経路: app password による programmatic IMAP を、`IComputer` と
同型の host-capability(`IMail`)として computer-use-clj に追加する。**

- `computeruse.mail/IMail`(`-fetch! [m opts]` → `{:uid :from :subject
  :date :message-id :body}`)。`mock-mail`(test 用) + `#?(:clj
  curl-imap-mail)`(JVM host・`curl imaps://`・依存ゼロ)。
- `fetch-mail-tool`(langchain extra-tool): `:fn` 内で `IVault` から app
  password を解決し `mail/-fetch!` の `:password` にだけ渡す。curl の
  `--user` で消費され、**戻り値(解析済み mail)にも model にも log にも
  映らない**。`log-action!` が `pr-str` する input は model が渡した
  `{:limit N}` のみ。
- custody: `computeruse.vault/kagi-vault`(`kagi get` に shell out。kagi は
  `op` 互換 PQC vault)。app password は `kagi add gmail-app-password -c
  mail` で保管。kagi が無い環境では既存 `op-vault` / `bw-vault` でも可。

### なぜこの経路か

- app password はブラウザサインインでなく **IMAP の `--user user:pass`
  プログラム認証**。ADR-0009 の「パスワードサインイン禁止」に触れない
  (manimani `channels.email/curl-imap-fetch` と同模型)。
- 画面非依存・堅牢・mail 本文は構造化 EDN で model に渡る(スクショ不要)。
- ADR-0013 の「I/O は host capability として注入・`.cljc`・依存ゼロ」に
  準拠。curl 実 I/O は `:sh` 注入で fake-able。

### no-leak 不変条件

password は `vault → fetch-mail-tool :fn → mail/-fetch! :password → curl
--user` の経路のみを流れ、いかなる戻り値・log・prompt にも現れない。
`mail_test.cljc` の `fetch-mail-tool-never-leaks-the-password` と
`curl-imap-mail-parses-and-hides-password` がこれを検証する(`vault-test/
type-secret-injects-without-leaking` と同型)。

## 非スコープ(本 ADR では扱わない・follow-up)

- **governed actor 分離**: 秘匿 mail の reveal / send / delete 等の特権
  op を行う場合は、ADR-2606272330(kagi-clj)に従い別 actor repo へ分離
  (propose-only `:advise` + 独立 Governor + append-only ledger +
  `interrupt-before #{:request-approval}`・phase 0→3)。本 capability は
  読み取り専用で Governor 不要。
- **長期 mail watcher**: ADR-2606280001 の durable outer loop(lease /
  tick / budget / `:agent.*` datom)で有界 run を反復する。StateGraph 内
  の無限ループは ADR-0013 addendum が禁止。
- **ADR-0009 CAS + Keychain-token model との統合**: 既存の
  `mail/messages/<cid>.eml` + `index.jsonl`・per-account OAuth (Keychain
  only) という ingest ground truth がある。本 IMAP 経路はその OAuth
  model ではなく app-password model(manymai `gmail_setup.cljc` /
  `curl-imap-fetch`)を採用。両者の統合・EDN fact 層への join は別途。
- **`build-agent` の `:computer` 必須の緩和**: mail-only agent でも
  `mock-computer` を渡して loop を成立させる(画面は使わない)。`IComputer`
  optional 化は別 PR。
