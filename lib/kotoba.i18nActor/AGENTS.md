# etzhayyim-project-i18n — Murakumo Translation Service (200+ Languages)

## App Identity

→ nanoid / domain: `deps.toml [[mitama_actors]]`

| Key | Value |
|---|---|
| **AT bot DID** | `did:web:i18n-251b9zaw.etzhayyim.com` |
| **World** | `etzhayyim-actor-agent` (LLM agent for translation) |

## Purpose

4 つの翻訳モードを統合する App:

1. **Batch Translation** — 73+ プロジェクトの `messages/{lang}.json` を 200+ 言語に自動翻訳 (CronJob)
2. **Real-time Translation** — 開いているページの自動翻訳 (Google Translate-like) + AT/Signal メッセージ翻訳
3. **Widget Editor** — inlang-like な用語検索・提案・承認 (inline 翻訳エディタ)
4. **Yoro Post Auto-Translation** — yoro.etzhayyim.com の投稿を Murakumo qwen3.5-4b で Tier 1+2 (50言語) に自動翻訳

## Architecture

### Translation Modes

```
┌─────────────────────────────────────────────┐
│            i18n App                  │
│                                              │
│  [1] Batch     ─ CronJob → SyncAll          │
│  messages/     ─ RegisterProject             │
│  {lang}.json   ─ TranslateBatch              │
│                ─ ExportMessages               │
│                                              │
│  [2] Real-time ─ TranslatePage (DOM texts)   │
│  page/message  ─ TranslateMessage (AT)       │
│                ─ TranslateSignal (E2E)       │
│                                              │
│  [3] Widget    ─ WidgetLookup (term search)  │
│  inline editor ─ WidgetSuggest (3 alts)     │
│                ─ WidgetApprove (human TM)    │
│                                              │
│  [4] Yoro Post ─ Auto-translate on commit    │
│  auto-xlate   ─ Tier 1+2 (50 langs)         │
│                ─ translatedPost records       │
│                                              │
│  [shared]      ─ Translation Memory (KV)     │
│                ─ Language Detection           │
│                ─ User Language Preference     │
│                ─ Murakumo qwen3.5-4b (on-prem│
│                  MLX fleet, zero cost)        │
└─────────────────────────────────────────────┘
```

### Command Path (W Protocol)

| Lexicon | Method | Description |
|---|---|---|
| `com.etzhayyim.command.i18n.translate` | `translate_batch` | プロジェクト+言語バッチ翻訳 |
| `com.etzhayyim.command.i18n.sync` | `sync_all` | 全プロジェクトスキャン→変更検出→翻訳 |
| `com.etzhayyim.command.i18n.translate_message` | `translate_message` | AT channel メッセージ翻訳 |

### Query Path (XRPC)

| Service | Method | Description |
|---|---|---|
| `I18nCommandService` | `TranslateBatch` | プロジェクト+言語バッチ翻訳 |
| `I18nCommandService` | `TranslateOnDemand` | 即時翻訳（特定キー） |
| `I18nCommandService` | `SyncAll` | 全プロジェクトスキャン→変更検出→翻訳 |
| `I18nCommandService` | `RegisterProject` | プロジェクト登録 |
| `I18nCommandService` | `TranslatePage` | ページ DOM テキスト一括翻訳 |
| `I18nCommandService` | `TranslateMessage` | AT channel メッセージ翻訳 |
| `I18nCommandService` | `TranslateSignal` | Signal E2E メッセージ翻訳 |
| `I18nCommandService` | `WidgetLookup` | 用語検索 (全言語の TM) |
| `I18nCommandService` | `WidgetSuggest` | 翻訳候補 3 件生成 |
| `I18nCommandService` | `WidgetApprove` | 人間承認 → TM 更新 |
| `I18nCommandService` | `SetUserLang` | ユーザー/チャネル別の言語設定 |
| `I18nQueryService` | `GetTranslationStatus` | プロジェクト別翻訳カバレッジ |
| `I18nQueryService` | `ExportMessages` | `{lang}.json` 出力 |
| `I18nQueryService` | `GetLanguageRegistry` | 200+ 言語レジストリ返却 |
| `I18nQueryService` | `GetUserLang` | ユーザー言語設定取得 |

### AT Record Output

| Lexicon | Description |
|---|---|
| `com.etzhayyim.i18n.translation_completed` | バッチ翻訳完了イベント |
| `com.etzhayyim.i18n.translated_message` | メッセージ翻訳結果 (record_uri, channel_id, source/target_lang, translated) |
| `com.etzhayyim.apps.i18n.translatedPost` | yoro 投稿の自動翻訳結果 (source_uri, source/target_lang, model) |

### AT Channels

| Channel | Purpose |
|---|---|
| `at://team-251b9zaw` | Daily evolution team critique |
| `at://evo-251b9zaw` | Evolution proposals |

## Real-time Translation Design

### Page Auto-Translation (Google Translate-like)

Widget JavaScript が DOM テキストノードを抽出 → `TranslatePage` API にバッチ送信 → DOM 置換。

```
Browser Page
  → Widget JS extracts visible text nodes
    → POST /xrpc/etzhayyim.i18n.v1.I18nCommandService/TranslatePage
      { texts: ["Hello", "Settings", ...], target_lang: "ja" }
    → TM cache hit → instant return
    → TM miss → murakumo LLM → store in TM → return
  → Widget JS replaces DOM text with translations
  → dir="rtl" auto-applied for RTL languages
```

### AT Protocol Message Translation

AT channel のメッセージを翻訳し、翻訳結果を AT record として publish。

```
User reads AT channel message (foreign language)
  → Widget UI shows "Translate" button
    → POST /xrpc/.../TranslateMessage
      { record_uri: "at://did:...", text: "こんにちは", target_lang: "en" }
    → detectLanguage() → "ja"
    → TM lookup → miss → murakumo → "Hello"
    → publish com.etzhayyim.i18n.translated_message AT record
    → return translated text to Widget UI
```

### Signal E2E Message Translation

Signal Protocol で E2E 暗号化されたメッセージは **client 側で復号後** に翻訳。翻訳サーバーには **平文が一時的に渡る** が、TM には source_hash のみ永続化。

```
Signal Encrypted Message
  → Client: Signal decrypt (X3DH / Double Ratchet)
    → Plaintext available in client memory
      → POST /xrpc/.../TranslateSignal
        { plaintext_messages: [{id, text, source_lang}], target_lang: "en" }
      → Server: detectLanguage + TM lookup + murakumo translate
      → Server returns translated texts (no plaintext persistence)
    → Client: display original + translated side-by-side
    → Client: optionally re-encrypt translated text for forwarding
```

**Security model**: Signal のE2E は client-to-server 間で維持。翻訳は server-side だが、TM には `source_hash` (SHA-256) のみ永続化し、`source_text` は ephemeral (KV TTL)。user consent が前提。

### Widget Inline Editor (inlang-like)

inlang のように開いているページの翻訳キーを検索・編集・承認できる Widget。

```
Developer opens any *.etzhayyim.com page
  → Widget overlay activated (keyboard shortcut / SuperApp App)
    → WidgetLookup: search term across all target languages
    → WidgetSuggest: get 3 alternative translations from LLM
    → WidgetApprove: select best → save as human-approved TM entry (quality_score: 1.0)
    → Changes reflected immediately in all apps using same term
```

## Inference Model

**Murakumo qwen3.5-4b (on-prem MLX fleet, zero cost)。** CF Workers AI (llm.etzhayyim.com) は使用しない。

| 用途 | Model | Endpoint | Cost |
|---|---|---|---|
| **Translation (全モード)** | `qwen3.5-4b` | `murakumo.etzhayyim.com/api/openai/v1/chat/completions` (direct fetch) | **Zero** |
| Language detection (LLM refinement) | host-sdk `llmJson()` → PDS gateway | PDS route | — |

## Yoro Post Auto-Translation (Design E Reactive)

**yoro.etzhayyim.com の `app.bsky.feed.post` commit を `handleComAtprotoSyncSubscribeReposCommit` で受信し、Murakumo qwen3.5-4b で Tier 1+2 全言語に自動翻訳。**

```
yoro post create → PDS commit → i18n subscribeRepos (Follow-based)
  → detectLanguage (post.langs field or Unicode heuristic)
  → for each Tier 1+2 lang (≠ source): murakumoTranslate()
    → Murakumo on-prem qwen3.5-4b (direct fetch, zero cost)
  → com.etzhayyim.apps.i18n.translatedPost record × N languages
  → social announce (AppBskyFeedPost)
```

**Output record** (`com.etzhayyim.apps.i18n.translatedPost`):

| Field | Description |
|---|---|
| `translation_id` | Unique ID (`tp-{timestamp}-{seq}`) |
| `source_uri` | `at://{repo}/app.bsky.feed.post/{rkey}` |
| `source_rkey` / `source_repo` | 元投稿の rkey と repo DID |
| `source_text` / `translated_text` | 元文 / 翻訳文 (2000 char truncate) |
| `source_lang` / `target_lang` | ISO 639-1 |
| `model` | `qwen3.5-4b` |

## Language Tier Strategy

| Tier | Count | Content | Frequency | Yoro auto-translate |
|---|---|---|---|---|
| 1 | 25 | Major (ja, en, es, fr, de, ...) | Daily | **Yes** |
| 2 | 25 | High internet (uk, sv, no, da, fi, ...) | Daily | **Yes** |
| 3 | 50 | Mid-population (regional Africa, Central Asia, Pacific) | Weekly | No |
| 4 | 100+ | Long-tail (minority scripts) | Weekly | No |

RTL languages: ar, he, fa, ur, ps, sd, yi, dv, ug

## Data Model (KV)

### Translation Memory (TM)

Key: `tm.{source_hash[:12]}:{target_lang}` → `translationRecord`

全翻訳モード (batch / page / message / signal / widget) が同一 TM を共有。"Save", "Cancel" 等の共通文字列はモード横断で 1 回だけ翻訳。

### User Language Preference

Key: `userlang.{user_id}` or `userlang.{user_id}.{channel_id}` → `{"lang": "ja"}`

AT channel / Signal session ごとに target language を設定可能。未設定時は `detectLanguage()` でヒューリスティック判定。

## Language Detection

Unicode block ベースのヒューリスティック: Hiragana/Katakana→ja, CJK→zh, Hangul→ko, Arabic→ar, Hebrew→he, Devanagari→hi, Thai→th, Cyrillic→ru, Georgian→ka, Armenian→hy, Bengali→bn, etc. fallback は "en"。

## CronJob

- **Daily** (Tier 1+2, 50 langs): `0 3 * * *` JST
- **Weekly** (All Tiers, 200+ langs): `0 4 * * 0` JST

## Daily Evolution

ISCO 5-agent team evaluates translation quality:

- **BM (1211)**: Translation coverage KPI, real-time latency, user adoption
- **PO (1120)**: Translation accuracy, message translation satisfaction
- **MK (2433)**: Market coverage by language, AT/Signal usage metrics
- **ENG (2512)**: TM hit rate, murakumo efficiency, page translation performance
- **QA (2519)**: Quality score distribution, Signal security model compliance, regression
