# etzhayyim-project-sys-tms — Translation Management System

Paraglide 連携前提の翻訳管理システム。OpenRouter (Opus) LLM で自動翻訳。

## Architecture

```
Consumer App (Paraglide)
  ├─ messages/{lang}.json  ← TMS が生成・管理
  └─ project.inlang/settings.json  ← TMS が言語タグ管理
        ↓
  TMS App (etzhayyim:tms)
    ├─ tms.translate()      → OpenRouter/Opus で翻訳
    ├─ catalogs.import()    → Paraglide JSON カタログ取り込み
    ├─ catalogs.export()    → 翻訳済みカタログ出力
    ├─ memory.lookup()      → 翻訳メモリ (KV)
    └─ glossary.set/get()   → 用語統一
```

`Consumer App (Paraglide)` は TMS が翻訳カタログを生成・管理する対象の
任意の Paraglide 利用プロジェクトを指し、この repo 自身の admin UI とは別物。
この repo 自身の frontend（`appview/etzhayyim-wasm-tms-tm5x7k9q/cljs`）は
ClojureScript（reagent + re-frame + jp-go-dds）— 旧 Svelte scaffold
（`svelte/`）は移行に伴い削除済み。

## Gaming Population Languages (Priority)

| Rank | Code | Language | Tier |
|------|------|----------|------|
| 1 | en | English | tier1 |
| 2 | zh | Chinese (Mandarin) | tier1 |
| 3 | es | Spanish | tier1 |
| 4 | hi | Hindi | tier2 |
| 5 | ar | Arabic | tier2 |
| 6 | pt | Portuguese | tier2 |
| 7 | bn | Bengali | tier3 |
| 8 | ru | Russian | tier3 |
| 9 | ja | Japanese | tier3 |
| 10 | ko | Korean | tier3 |

## Components

| Component | nanoid | Port | Description |
|-----------|--------|------|-------------|
| tms-component | tm5x7k9q | 80 | TMS App (XRPC + MCP) |

## WIT Interfaces

- `etzhayyim:tms/tms@0.1.0` — 翻訳コア (translate, translate-batch, get-job)
- `etzhayyim:tms/catalogs@0.1.0` — Paraglide カタログ管理 (import, export, diff)
- `etzhayyim:tms/memory@0.1.0` — 翻訳メモリ (lookup, upsert, count)
- `etzhayyim:tms/glossary@0.1.0` — 用語集 (set-term, get-term, list-terms)

## LLM Configuration

- **Provider**: OpenRouter
- **Model**: `anthropic/claude-opus-4-20250514` (Opus)
- **Temperature**: 0.3 (低め — 翻訳一貫性重視)
- **Max Tokens**: 4096

## Paraglide Integration Flow

1. `catalogs.import()` — source language の messages/*.json を取り込み
2. `catalogs.diff_untranslated()` — 未翻訳キーを検出
3. `tms.translate_batch()` — 未翻訳を OpenRouter/Opus で一括翻訳
4. `catalogs.export()` — target language の messages/*.json を出力
5. `memory.upsert()` — 翻訳メモリに保存 (次回再利用)

## Consumer Integration (他プロジェクトから利用)

```wit
// 他プロジェクトの wit/world.wit
package etzhayyim:my-component;

world component {
  include etzhayyim:platform/etzhayyim-tms-consumer@0.1.0;
}
```

TMS App is called via XRPC (HTTP/2) from other Apps:
```
http://tms-kotodama.kotodama-runtime:80/xrpc/etzhayyim.tms.v1.TmsService/<Method>
```
