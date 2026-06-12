"""
ADR-0049 Phase B4 — news translation UDF.

Replaces the RunPod `gemma4:26b` round-trip in
`60-apps/etzhayyim-project-news/appview/news-core-component/src/app.ts`
`translateText()` with a direct call to Vultr Serverless Inference
through the shared `kotodama.llm` tier abstraction.

Input / output are plain VARCHAR so the UDF reads like a native SQL
scalar and can drop into streaming MVs:

    SELECT news_translate(title, lang, 'ja') AS title_ja
    FROM vertex_news_article
    WHERE lang <> 'ja';

This keeps the news Worker thin (just RSS parse + INSERT) and lets
RisingWave handle fan-out across languages without the Worker doing N
sequential HTTPS calls per article.

Failure policy: on any upstream error (auth, timeout, parse), the UDF
returns the **original source text** unchanged. Callers that want to
distinguish "translated" from "passed through on error" should look at
the row's source vs target language — if they match, translation was
skipped. The UDF does not raise because arrow-udf rejects exceptions
at the batch boundary and we'd lose the whole row batch.

Keep prompt short + deterministic (`temperature=0.0`) — news titles
are short enough that Devstral returns a clean single-line
translation in 20-40 completion tokens, so the 250-tok budget below
is generous.
"""

from __future__ import annotations

from kotodama import udf
from kotodama import llm

_SYSTEM_PROMPT = (
    "You are a professional translator. Translate the user's text from "
    "the source language to the target language. Preserve named entities, "
    "URLs, and numeric values verbatim. Output ONLY the translated text. "
    "No preamble, no explanations, no quotation marks, no code fences."
)
_MAX_TOKENS = 250


@udf(
    nsid="com.etzhayyim.apps.news.translate",
    io_threads=100,
    input_types=["VARCHAR", "VARCHAR", "VARCHAR"],
    result_type="VARCHAR",
    capability_tags=("news", "translate", "llm"),
    agent_tool="Translate text between languages via Vultr Serverless Devstral.",
)
def translate(text: str, source_lang: str, target_lang: str) -> str:
    if not text:
        return ""
    src = (source_lang or "").strip() or "auto"
    dst = (target_lang or "").strip()
    if not dst or src == dst:
        # Nothing to do — return input verbatim so the MV pipeline keeps
        # moving. No LLM call, no spend.
        return text
    if len(text) < 2:
        return text

    # Cap to protect the token budget — matches the TS translateText
    # 800-char truncation. Devstral breezes past 800 cleanly.
    truncated = text if len(text) <= 800 else text[:800] + "…"

    user_prompt = (
        f"Source language: {src}\n"
        f"Target language: {dst}\n"
        f"Text:\n{truncated}"
    )

    try:
        resp = llm.call_tier(
            "fast",
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=_MAX_TOKENS,
            temperature=0.0,
        )
    except llm.LlmError:
        return text  # graceful degrade

    content = (resp.get("content") or "").strip()
    if not content:
        return text
    # Strip matched surrounding quotes — some models still add them
    # despite the system-prompt ban.
    if (content.startswith('"') and content.endswith('"')) or (
        content.startswith("「") and content.endswith("」")
    ):
        content = content[1:-1].strip() or text
    return content
