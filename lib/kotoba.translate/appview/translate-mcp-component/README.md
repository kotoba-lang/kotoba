# etzhayyim-project-translate App migration

このディレクトリは `etzhayyim-project-translate/legacy-runtime/llm-translate-9wfmlzhs` の App 実装です。

## 変更点

- App runtime 依存 (`App HTTP API`) を除去。
- MCP JSON-RPC `tools/list` と `tools/call` を `POST /api/mcp` で提供。
- `GET /health` / `GET /healthz` で稼働確認。

## ツール

- `translate` / `detect_language` / `list_languages`

## 環境変数

- `TRANSLATE_LLM_ENDPOINT`: OpenAI 互換 chat/completions エンドポイント。
  - 既定: `https://api.openai.com/v1/chat/completions`
- `TRANSLATE_LLM_MODEL`: 使用モデル名。
  - 既定: `gpt-4o-mini`
- `OPENAI_API_KEY`: OpenAI 互換 API key。
- `TRANSLATE_LLM_TIMEOUT_SECONDS`: HTTP タイムアウト。既定 `90s`。
