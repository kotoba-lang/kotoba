"""Yoro actor social primitives.

These helpers keep the graph-visible `vertex_repo_record` fallback used by
the Murakumo cron job available to BPMN/Zeebe workers. The ATProto PDS write
path can be layered on top, but this primitive is intentionally the verified
minimum: one service task produces the same record shape the live cron already
proved visible through atproto.etzhayyim.com.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import time
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


DEFAULT_REPO = "did:web:yoro.etzhayyim.com"
DEFAULT_COLLECTION = "app.bsky.feed.post"
DEFAULT_PREFIX = "Murakumo actor pulse"
PROFILE_COLLECTION = "app.bsky.actor.profile"
TRANSLATION_LINK_COLLECTION = "com.etzhayyim.apps.media_gamers.record.translationLink"
DEFAULT_TRANSLATION_TARGET_LANGS = (
    "en,ja,zh-Hans,ko,es,fr,de,pt,hi,bn,ta,te,mr,ur,gu,kn,ml,pa,ar,fa,he,ku,ckb,zgh,kab,ps,sd,am,ti,id,vi,th,it,nl,tr,pl,uk"
)
TRANSLATION_LANG_LABELS = {
    "am": "Amharic",
    "ar": "Arabic",
    "bn": "Bengali",
    "ckb": "Central Kurdish / Sorani",
    "es": "Spanish",
    "fa": "Persian / Farsi",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "ja": "Japanese",
    "kab": "Kabyle",
    "kn": "Kannada",
    "ko": "Korean",
    "ku": "Kurdish / Kurmanji",
    "ml": "Malayalam",
    "mr": "Marathi",
    "pa": "Punjabi",
    "ps": "Pashto",
    "sd": "Sindhi",
    "ta": "Tamil",
    "te": "Telugu",
    "ti": "Tigrinya",
    "ur": "Urdu",
    "zgh": "Standard Moroccan Tamazight",
    "zh-Hans": "Simplified Chinese",
}
LLM_PROFILE_ENABLED = os.environ.get("YORO_ACTOR_QUALITY_LLM_PROFILE", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}


def utc_now_iso() -> str:
    return _dt.datetime.now(tz=_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _rkey(actor_path: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"murakumo-{actor_path}-{stamp}-{os.getpid()}"


def build_social_post_record(
    *,
    repo: str = DEFAULT_REPO,
    collection: str = DEFAULT_COLLECTION,
    prefix: str = DEFAULT_PREFIX,
    text: str = "",
    created_at: str = "",
    rkey: str = "",
    actor_path: str = "zeebe",
    record_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a `vertex_repo_record` row matching the live cron fallback."""
    repo = repo or DEFAULT_REPO
    collection = collection or DEFAULT_COLLECTION
    created_at = created_at or utc_now_iso()
    ts_ms = int(time.time() * 1000)
    rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{collection}/{rkey}"
    text = text or (
        # ETZHAYYIM: vendor-only
        f"{prefix}: Karmada hub and murakumo-k3s actor worker path alive at {created_at}."
    )
    record = {"$type": collection, "text": text, "createdAt": created_at}
    if record_extra:
        record.update(record_extra)
    value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    return {
        "uri": uri,
        "cid": rkey,
        "collection": collection,
        "rkey": rkey,
        "repo": repo,
        "repo_rev": rkey,
        "value_json": value_json,
        "indexed_at": created_at,
        "takedown_ref": None,
        "ts_ms": ts_ms,
        "created_at": created_at,
        "text": text,
    }


def build_repo_record(
    *,
    repo: str,
    collection: str,
    record: dict[str, Any],
    created_at: str = "",
    rkey: str = "",
    actor_path: str = "zeebe",
) -> dict[str, Any]:
    repo = repo or DEFAULT_REPO
    created_at = created_at or str(record.get("createdAt") or utc_now_iso())
    rkey = rkey or _rkey(actor_path)
    uri = f"at://{repo}/{collection}/{rkey}"
    value_json = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
    return {
        "uri": uri,
        "cid": rkey,
        "collection": collection,
        "rkey": rkey,
        "repo": repo,
        "repo_rev": rkey,
        "value_json": value_json,
        "indexed_at": created_at,
        "takedown_ref": None,
        "ts_ms": int(time.time() * 1000),
        "created_at": created_at,
        "text": str(record.get("text") or ""),
    }


def insert_social_post_record(row: dict[str, Any], *, flush: bool = True) -> dict[str, Any]:
    if row.get("collection") != DEFAULT_COLLECTION:
        raise ValueError("insert_social_post_record only accepts app.bsky.feed.post")
    _insert_feed_post_row(row)
    return {
        "ok": True,
        "uri": row["uri"],
        "repo": row["repo"],
        "collection": row["collection"],
        "rkey": row["rkey"],
        "text": row["text"],
    }


def insert_repo_records(rows: list[dict[str, Any]], *, flush: bool = True) -> list[dict[str, Any]]:
    client = get_kotoba_client()
    for row in rows:
        collection = str(row.get("collection") or "")
        if collection == DEFAULT_COLLECTION:
            _insert_feed_post_row(row)
        elif collection == "app.bsky.graph.follow":
            record = json.loads(str(row.get("value_json") or "{}"))
            client.insert_row(
                "edge_follows",
                {
                    "edge_id": row["uri"],
                    "src_vid": row["repo"],
                    "dst_vid": str(record.get("subject") or ""),
                    "_seq": 0,
                    "created_date": str(row["created_at"])[:10],
                    "sensitivity_ord": 1,
                    "owner_did": row["repo"],
                    "rkey": row["rkey"],
                    "repo": row["repo"],
                    "created_at": row["created_at"],
                },
            )
        elif collection == PROFILE_COLLECTION:
            record = json.loads(str(row.get("value_json") or "{}"))

            # R0: read-modify-write collapsed to single insert_row upsert
            existing = client.select_first_where("vertex_profile", "vertex_id", row["uri"])

            merged = {
                "vertex_id": row["uri"],
                "_seq": 0,
                "created_date": str(row["created_at"])[:10],
                "sensitivity_ord": 1,
                "owner_did": row["repo"],
                "did": row["repo"],
                "repo": row["repo"],
                "display_name": str(record.get("displayName") or ""),
                "description": str(record.get("description") or ""),
                "collection": collection,
                "rkey": row["rkey"],
                "created_at": row["created_at"],
            }
            if existing:
                for k, v in existing.items():
                    if k not in merged:
                        merged[k] = v
                # EXCLUDED logic in SQL: display_name and description are updated, created_at is updated.
                # So we keep the new values for these.
            client.insert_row("vertex_profile", merged)
        else:
            raise ValueError(f"unsupported non-post repo record collection: {collection}")
    return rows


def _post_projection_params(row: dict[str, Any]) -> dict[str, Any]:
    record = json.loads(str(row.get("value_json") or "{}"))
    created_at = str(row.get("created_at") or record.get("createdAt") or utc_now_iso())
    return {
        "vertex_id": row["uri"],
        "created_date": created_at[:10],
        "owner_did": row["repo"],
        "rkey": row["rkey"],
        "repo": row["repo"],
        "text": str(record.get("text") or row.get("text") or ""),
        "embed": json.dumps(record.get("embed"), separators=(",", ":"), ensure_ascii=False)
        if record.get("embed") is not None
        else None,
        "facets": json.dumps(record.get("facets") or [], separators=(",", ":"), ensure_ascii=False),
        "langs": json.dumps(record.get("langs") or ["ja"], separators=(",", ":"), ensure_ascii=False),
        "reply_root": str(((record.get("reply") or {}).get("root") or {}).get("uri") or ""),
        "reply_parent": str(((record.get("reply") or {}).get("parent") or {}).get("uri") or ""),
        "tags": json.dumps(record.get("tags") or [], separators=(",", ":"), ensure_ascii=False),
        "created_at": created_at,
    }


def _insert_feed_post_row(row: dict[str, Any]) -> None:
    projection = _post_projection_params(row)
    client = get_kotoba_client()
    client.insert_row("vertex_repo_record", row)
    client.insert_row("vertex_post", projection)


def _display_actor(did: str, handle: str = "") -> str:
    value = (handle or did or "friend").strip()
    if value.startswith("did:web:"):
        value = value[len("did:web:"):]
    return value


def _profile_vertex_id(actor_did: str) -> str:
    return f"at://{actor_did}/{PROFILE_COLLECTION}/self"


def _safe_display_name(actor_did: str, handle: str = "") -> str:
    candidate = (handle or "").strip()
    if candidate and candidate != "handle.invalid" and not candidate.startswith("did:"):
        return candidate
    short = actor_did.rsplit(":", 1)[-1][:12] if actor_did else "actor"
    return f"YORO actor {short}"


def _safe_description(actor_did: str, source_hint: str = "") -> str:
    suffix = f" Source: {source_hint.strip()}" if source_hint.strip() else ""
    return (
        "Public YORO actor profile. This page is being incrementally enriched "
        "from graph records, provenance sources, and public activity signals."
        f"{suffix}"
    )


def _actor_kind(actor_did: str, handle: str = "") -> str:
    value = f"{actor_did} {handle}".lower()
    if ":iata-airport:" in value:
        return "iata airport"
    if ":icao-airport:" in value:
        return "icao airport"
    if ":iso3166-1:" in value:
        return "country or territory"
    if ":iso3166-2:" in value or ":jis-x0401:" in value:
        return "regional administrative area"
    if ":unlocode:" in value:
        return "UN/LOCODE place or country grouping"
    return "public YORO actor"


def _compact_text(value: Any, *, max_chars: int = 180) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 1)].rstrip() + "…"


def _diet_speaker_actor(speaker_name: str) -> dict[str, str]:
    name = re.sub(r"\s+", "", str(speaker_name or "").strip()) or "unknown"
    digest = hashlib.sha256(name.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return {
        "name": name,
        "handle": f"speaker-{digest}.kokkai.etzhayyim.com",
        "did": f"did:web:yoro.etzhayyim.com:kokkai:speaker:{digest}",
    }


def _diet_speech_excerpt(speech_text: str, speaker_name: str = "", *, max_chars: int = 140) -> str:
    text = re.sub(r"\s+", " ", str(speech_text or "")).strip()
    if speaker_name:
        text = re.sub(rf"^○?{re.escape(speaker_name)}(?:君|さん|議員|大臣|委員)?\s*", "", text)
    text = re.sub(r"^○[^　\s]{1,24}(?:君|さん|議員|大臣|委員)?\s*", "", text)
    return _compact_text(text, max_chars=max_chars)


def _utf8_facet(text: str, marker: str, feature: dict[str, Any]) -> dict[str, Any] | None:
    start = text.find(marker)
    if start < 0:
        return None
    byte_start = len(text[:start].encode("utf-8"))
    byte_end = byte_start + len(marker.encode("utf-8"))
    return {
        "index": {"byteStart": byte_start, "byteEnd": byte_end},
        "features": [feature],
    }


def _post_tags(*values: Any) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, (list, tuple, set)):
            candidates = value
        else:
            candidates = [value]
        for candidate in candidates:
            tag = re.sub(r"^[#＃]+", "", str(candidate or "").strip())
            tag = re.sub(r"\s+", "-", tag)
            if not tag or tag in seen:
                continue
            tags.append(tag[:64])
            seen.add(tag)
            if len(tags) >= 8:
                return tags
    return tags


def _lang_list(value: Any = None) -> list[str]:
    raw = value
    if raw is None:
        raw = os.environ.get("YORO_TRANSLATION_TARGET_LANGS", DEFAULT_TRANSLATION_TARGET_LANGS)
    if isinstance(raw, str):
        candidates = re.split(r"[, \n\t]+", raw)
    elif isinstance(raw, (list, tuple, set)):
        candidates = [str(item) for item in raw]
    else:
        candidates = []
    langs: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        lang = str(candidate or "").strip()
        if not lang or lang in seen:
            continue
        langs.append(lang)
        seen.add(lang)
    return langs


def _fetch_source_post(post_uri: str) -> dict[str, Any]:
    client = get_kotoba_client()
    row = client.select_first_where("vertex_repo_record", "uri", post_uri)
    # R0: in-Python filter for collection='app.bsky.feed.post'
    if not row or row.get("collection") != 'app.bsky.feed.post':
        return {}
    try:
        record = json.loads(str(row.get("value_json") or "{}"))
    except json.JSONDecodeError:
        record = {}
    return {
        "repo": row.get("repo"),
        "rkey": row.get("rkey"),
        "record": record,
        "createdAt": row.get("created_at"),
        "text": str(record.get("text") or ""),
        "langs": record.get("langs") if isinstance(record.get("langs"), list) else [],
    }


def _detect_source_lang(source_post: dict[str, Any], fallback: str = "") -> str:
    langs = source_post.get("langs")
    if isinstance(langs, list) and langs:
        lang = str(langs[0] or "").strip()
        if lang:
            return lang
    return (fallback or "ja").strip()


def _translation_lang_label(lang: str) -> str:
    code = str(lang or "").strip()
    label = TRANSLATION_LANG_LABELS.get(code)
    return f"{label} ({code})" if label else code


def _translation_timeout_sec() -> float:
    raw = os.environ.get("YORO_TRANSLATION_LLM_TIMEOUT_SEC", "300").strip()
    try:
        return max(20.0, min(float(raw), 300.0))
    except ValueError:
        return 300.0


def _translate_social_text(text: str, source_lang: str, target_lang: str) -> dict[str, Any]:
    source_text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not source_text:
        return {"ok": False, "error": "source post text is empty"}
    if source_lang and source_lang == target_lang:
        return {
            "ok": True,
            "translatedText": source_text,
            "source": "same-lang",
            "model": "none",
            "latencyMs": 0,
        }
    try:
        from kotodama import llm
    except Exception as exc:
        return {"ok": False, "error": f"llm import failed: {exc}"}

    system = (
        f"Translate the user's text into {_translation_lang_label(target_lang)}. "
        "Output only the translated text. Do not explain."
    )
    user = (
        f"Source language: {_translation_lang_label(source_lang) if source_lang else 'auto'}\n"
        "Text to translate:\n"
        f"{source_text[:2000]}"
    )
    try:
        result = llm.call_tier(
            "fast",
            system=system,
            user=user,
            max_tokens=1200,
            temperature=0.0,
            timeout_sec=_translation_timeout_sec(),
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:500]}
    raw_text = result.get("content") or ""
    translated = re.sub(r"^```(?:text)?\s*|\s*```$", "", str(raw_text)).strip()
    if not translated:
        return {
            "ok": False,
            "error": "llm returned empty translation",
            "model": result.get("model"),
        }
    return {
        "ok": True,
        "translatedText": translated[:3000],
        "source": "llm-other",
        "model": result.get("model"),
        "latencyMs": result.get("latencyMs"),
    }


def build_translation_link_record(
    *,
    repo: str,
    source_uri: str,
    source_lang: str,
    translated_uri: str,
    target_lang: str,
    source: str = "llm-other",
    quality_score: int = 0,
    created_at: str = "",
    rkey: str = "",
) -> dict[str, Any]:
    created_at = created_at or utc_now_iso()
    rkey = rkey or _rkey(f"translation-link-{target_lang}")
    uri = f"at://{repo}/{TRANSLATION_LINK_COLLECTION}/{rkey}"
    return {
        "vertex_id": uri,
        "_seq": 0,
        "created_date": created_at[:10],
        "sensitivity_ord": 1,
        "owner_did": repo,
        "rkey": rkey,
        "repo": repo,
        "source_uri": source_uri,
        "source_lang": source_lang,
        "translated_uri": translated_uri,
        "lang": target_lang,
        "source": source,
        "quality_score": float(quality_score or 0),
        "created_at": created_at,
        "org_id": "did:web:yoro.etzhayyim.com",
        "user_id": "system",
        "actor_id": repo,
    }


def insert_translation_link_record(row: dict[str, Any]) -> dict[str, Any]:
    client = get_kotoba_client()
    client.insert_row("vertex_translation_link", row)
    return {
        "ok": True,
        "uri": row["vertex_id"],
        "sourceUri": row["source_uri"],
        "translatedUri": row["translated_uri"],
        "lang": row["lang"],
    }


def build_diet_speech_social_post_record(
    speech: dict[str, Any],
    *,
    repo: str = DEFAULT_REPO,
    created_at: str = "",
    rkey: str = "",
) -> dict[str, Any]:
    """Project a Diet speech row into an app.bsky.feed.post-shaped graph record."""
    created_at = created_at or utc_now_iso()
    speaker = _diet_speaker_actor(str(speech.get("speaker_name") or ""))
    chamber = str(speech.get("chamber") or "国会").strip() or "国会"
    committee = str(speech.get("committee_name") or "会議").strip() or "会議"
    meeting_date = str(speech.get("meeting_date") or "").strip()
    where = f"{chamber} {committee}".strip()
    when = f" ({meeting_date})" if meeting_date else ""
    excerpt = _diet_speech_excerpt(
        str(speech.get("speech_text") or ""),
        str(speech.get("speaker_name") or ""),
        max_chars=140,
    )
    if not excerpt:
        excerpt = "発言本文は未抽出です。"
    mention = f"@{speaker['handle']}"
    text = f"{mention} / {where}{when}: 「{excerpt}」 #国会 #発言 #kokkai"
    facets = [
        facet
        for facet in [
            _utf8_facet(
                text,
                mention,
                {"$type": "app.bsky.richtext.facet#mention", "did": speaker["did"]},
            ),
            _utf8_facet(text, "#国会", {"$type": "app.bsky.richtext.facet#tag", "tag": "国会"}),
            _utf8_facet(text, "#発言", {"$type": "app.bsky.richtext.facet#tag", "tag": "発言"}),
            _utf8_facet(text, "#kokkai", {"$type": "app.bsky.richtext.facet#tag", "tag": "kokkai"}),
        ]
        if facet is not None
    ]
    tags = _post_tags("国会", "発言", "kokkai", chamber, committee, speech.get("topic_tag"))
    source = {
        "speechId": speech.get("speech_id"),
        "meetingUrl": speech.get("meeting_url"),
        "session": speech.get("session"),
        "chamber": chamber,
        "committeeName": committee,
        "meetingDate": meeting_date,
        "speakerName": speech.get("speaker_name"),
        "speakerGroup": speech.get("speaker_group"),
        "speakerPosition": speech.get("speaker_position"),
        "speakerRole": speech.get("speaker_role"),
    }
    return build_social_post_record(
        repo=repo,
        text=text,
        created_at=created_at,
        rkey=rkey,
        actor_path="diet-speech",
        record_extra={
            "langs": ["ja"],
            "facets": facets,
            "tags": tags,
            "source": {"$type": "com.etzhayyim.apps.fukkou.dietSpeechRef", **source},
        },
    )


def _fetch_actor_generation_context(actor_did: str, handle: str = "") -> dict[str, Any]:
    context: dict[str, Any] = {
        "actorDid": actor_did,
        "handle": handle or actor_did,
        "actorKind": _actor_kind(actor_did, handle),
        "existingProfile": {},
        "recentPosts": [],
        "repoRecordCollections": [],
    }
    try:
        client = get_kotoba_client()
        # R0: fetch broader single-equality set and sort in python
        profiles = []
        profiles.extend(client.select_where("vertex_profile", "did", actor_did))
        if handle and handle != actor_did:
            profiles.extend(client.select_where("vertex_profile", "handle", handle))

        seen = set()
        unique_profiles = []
        for p in profiles:
            vid = p.get("vertex_id")
            if vid not in seen:
                seen.add(vid)
                unique_profiles.append(p)

        def profile_sort_key(p):
            is_did = 0 if p.get("did") == actor_did else 1
            has_desc = 0 if p.get("description") else 1
            return (is_did, has_desc)

        unique_profiles.sort(key=profile_sort_key)
        if unique_profiles:
            row = unique_profiles[0]
            context["existingProfile"] = {
                "did": row.get("did"),
                "handle": row.get("handle"),
                "displayName": row.get("display_name"),
                "description": row.get("description"),
                "avatar": row.get("avatar_cid"),
                "banner": row.get("banner_cid"),
                "props": row.get("props"),
                "createdAt": row.get("created_at"),
            }

        # R0: in-Python filter for collection, sorting by indexed_at DESC, limit 5
        records = client.select_where("vertex_repo_record", "repo", actor_did, limit=2000)
        filtered_records = [
            r for r in records
            if r.get("collection") != 'app.bsky.actor.profile'
        ]
        filtered_records.sort(key=lambda r: str(r.get("indexed_at") or ""), reverse=True)
        top_records = filtered_records[:5]
        context["recentPosts"] = [
            {
                "collection": rec.get("collection"),
                "rkey": rec.get("rkey"),
                "value": str(rec.get("value_json") or "")[:500],
                "indexedAt": rec.get("indexed_at"),
            }
            for rec in top_records
        ]
        context["repoRecordCollections"] = sorted({str(rec.get("collection")) for rec in filtered_records if rec.get("collection")})
    except Exception as exc:
        context["contextFetchError"] = str(exc)[:300]
    return context


def _llm_profile_draft(
    *,
    actor_did: str,
    handle: str = "",
    source_hint: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not LLM_PROFILE_ENABLED:
        return {"ok": False, "skipped": True, "reason": "YORO_ACTOR_QUALITY_LLM_PROFILE disabled"}
    try:
        from kotodama import llm
    except Exception as exc:
        return {"ok": False, "error": f"llm import failed: {exc}"}

    generation_context = context or _fetch_actor_generation_context(actor_did, handle)
    system = (
        "You generate concise public YORO actor profile copy. "
        "Return one JSON object only. Do not invent unverifiable claims. "
        "Use the provided actor kind, existing profile, DID, handle, and recent records. "
        "If facts are sparse, say it is an incrementally enriched public actor profile. "
        "Write in neutral third person, never first person. "
        "For airports, countries, regions, and codes, describe the actor as a graph node or public actor page, not as a person. "
        "Do not say the actor is official, authoritative, verified, government-run, or an operator unless that is explicit in context. "
        "Do not claim expertise, services, support, operations, employment, or real-world authority. "
        "Keep displayName <= 64 chars, description <= 240 chars, seedPostText <= 260 chars. "
        "profileBasis must name concrete input fields used, not repeat the schema instructions."
    )
    existing_profile = generation_context.get("existingProfile") if isinstance(generation_context, dict) else {}
    recent_posts = generation_context.get("recentPosts") if isinstance(generation_context, dict) else []
    recent_summaries = []
    substantive_recent_summaries = []
    if isinstance(recent_posts, list):
        for post in recent_posts[:2]:
            if isinstance(post, dict):
                value = str(post.get("value") or "")
                recent_summaries.append(value[:180])
                collection = str(post.get("collection") or "")
                if collection == "app.bsky.feed.post" and '"text"' in value:
                    substantive_recent_summaries.append(value[:180])
                elif '"description"' in value and '""' not in value:
                    substantive_recent_summaries.append(value[:180])
    existing_description = str((existing_profile or {}).get("description") or "").strip()
    has_source_facts = bool(existing_description or substantive_recent_summaries)
    sparse_instruction = ""
    if not has_source_facts:
        sparse_instruction = (
            "No source facts are available beyond DID, handle, actor kind, and displayName. "
            "Use only those fields. Do not add geography, language, airport function, hub status, "
            "operator, location, population, service, or authority claims."
        )
    user = (
        f"Actor DID: {actor_did}\n"
        f"Handle: {handle or actor_did}\n"
        f"Actor kind: {generation_context.get('actorKind', 'public YORO actor') if isinstance(generation_context, dict) else 'public YORO actor'}\n"
        f"Existing displayName: {str((existing_profile or {}).get('displayName') or '')[:100]}\n"
        f"Existing description: {existing_description[:240]}\n"
        f"Recent records: {' | '.join(recent_summaries)[:360]}\n"
        f"Source facts present: {'yes' if has_source_facts else 'no'}\n"
        f"Sparse-context rule: {sparse_instruction}\n"
        f"Source hint: {source_hint}\n"
        "Return exactly this JSON shape with no markdown fences: "
        '{"displayName":"...","description":"...","seedPostText":"...","profileBasis":"..."}'
    )
    result = llm.call_tier_json(
        "structured",
        system=system,
        user=user,
        max_tokens=180,
        temperature=0.1,
        timeout_sec=20.0,
    )
    if not result.get("ok"):
        return result
    data = result.get("data") if isinstance(result.get("data"), dict) else {}
    display_name = str(data.get("displayName") or "").strip()[:80]
    description = str(data.get("description") or "").strip()[:280]
    seed_post_text = str(data.get("seedPostText") or "").strip()[:320]
    if not display_name or not description:
        return {"ok": False, "error": "llm profile draft missing displayName or description", "data": data}
    combined = f"{display_name}\n{description}\n{seed_post_text}".lower()
    forbidden_terms = (
        "i'm ",
        "i am ",
        " my ",
        " official",
        "verified",
        "authoritative",
        "professional",
        "expertise",
        "services",
        "support",
        "assistance",
        "operations",
        "based in",
        "known for",
    )
    if any(term in combined for term in forbidden_terms):
        return {"ok": False, "error": "llm profile draft contained unsupported authority or first-person wording", "data": data}
    sparse_forbidden_terms = (
        " located ",
        "located in",
        " serving ",
        " hub",
        "country in",
        "speaking",
        "operator",
        "population",
        "capital",
        "airport located",
        "transportation",
        "government",
    )
    if not has_source_facts and any(term in combined for term in sparse_forbidden_terms):
        return {"ok": False, "error": "llm profile draft added unsupported sparse-context facts", "data": data}
    return {
        "ok": True,
        "displayName": display_name,
        "description": description,
        "seedPostText": seed_post_text or f"{display_name}: {description[:220]}",
        "profileBasis": str(data.get("profileBasis") or "")[:500],
        "model": result.get("model"),
        "latencyMs": result.get("latencyMs"),
    }


def _actor_quality_case_id(actor_did: str, source_hint: str = "") -> str:
    key = f"{actor_did}|{source_hint}".encode("utf-8", errors="ignore")
    return f"yoro-actor-quality-{hashlib.sha256(key).hexdigest()[:24]}"


def _emit_actor_quality_activity_event(
    *,
    task_type: str,
    lifecycle: str,
    actor_did: str,
    handle: str = "",
    source_hint: str = "",
    dry_run: bool = False,
    status: str = "",
    elapsed_ms: int | None = None,
    error: str = "",
    result: dict[str, Any] | None = None,
) -> None:
    now = utc_now_iso()
    ts_ms = int(time.time() * 1000)
    activity_slug = task_type.replace(".", "-")
    event_type = f"{task_type}.{lifecycle}"
    event_hash = hashlib.sha256(
        f"{task_type}|{lifecycle}|{actor_did}|{source_hint}|{ts_ms}|{os.getpid()}".encode("utf-8", errors="ignore")
    ).hexdigest()[:16]
    rkey = f"actor-quality-{activity_slug}-{lifecycle}-{ts_ms}-{event_hash}"
    event_id = f"yoro.actorQuality:{event_hash}"
    case_id = _actor_quality_case_id(actor_did, source_hint)
    payload = {
        "caseId": case_id,
        "taskType": task_type,
        "lifecycle": lifecycle,
        "actorDid": actor_did,
        "handle": handle,
        "sourceHint": source_hint,
        "dryRun": bool(dry_run),
        "status": status,
    }
    if elapsed_ms is not None:
        payload["elapsedMs"] = elapsed_ms
    if error:
        payload["error"] = error[:1000]
    if result:
        payload["result"] = {
            key: value
            for key, value in result.items()
            if key in {"ok", "dryRun", "profileChanged", "seedPostCreated", "qualityScore", "postsCount", "reason"}
        }
    row = {
        "vertex_id": f"at://did:web:yoro.etzhayyim.com/com.etzhayyim.bpmn.activityEvent/{rkey}",
        "owner_did": "did:web:yoro.etzhayyim.com",
        "rkey": rkey,
        "repo": "did:web:yoro.etzhayyim.com",
        "event_id": event_id,
        "instance_id": case_id,
        "activity_id": task_type,
        "event_type": event_type,
        "payload_json": json.dumps(payload, separators=(",", ":"), ensure_ascii=False),
        "occurred_at": now,
        "created_at": now,
        "actor_did": actor_did,
        "org_did": "did:web:yoro.etzhayyim.com",
    }
    try:
        client = get_kotoba_client()
        client.insert_row("vertex_bpmn_activity_event", row)
    except Exception:
        # Telemetry must never fail the enrichment path.
        return


async def _run_actor_quality_task(
    *,
    task_type: str,
    actor_did: str,
    handle: str = "",
    source_hint: str = "",
    dry_run: bool = False,
    fn: Any,
) -> dict[str, Any]:
    started = time.monotonic()
    _emit_actor_quality_activity_event(
        task_type=task_type,
        lifecycle="started",
        actor_did=actor_did,
        handle=handle,
        source_hint=source_hint,
        dry_run=dry_run,
        status="started",
    )
    try:
        result = fn()
    except Exception as exc:
        _emit_actor_quality_activity_event(
            task_type=task_type,
            lifecycle="failed",
            actor_did=actor_did,
            handle=handle,
            source_hint=source_hint,
            dry_run=dry_run,
            status="failed",
            elapsed_ms=int((time.monotonic() - started) * 1000),
            error=str(exc),
        )
        raise
    status = "completed" if bool(result.get("ok")) else "failed"
    _emit_actor_quality_activity_event(
        task_type=task_type,
        lifecycle=status,
        actor_did=actor_did,
        handle=handle,
        source_hint=source_hint,
        dry_run=dry_run,
        status=status,
        elapsed_ms=int((time.monotonic() - started) * 1000),
        result=result,
    )
    return result


def _fetch_profile_quality(actor_did: str, handle: str = "") -> dict[str, Any]:
    profile: dict[str, Any] = {}
    posts_count = 0
    client = get_kotoba_client()

    # R0: in-Python merge/sort for profile lookup by did/handle
    profiles = client.select_where("vertex_profile", "did", actor_did)
    if handle and handle != actor_did:
        profiles.extend(client.select_where("vertex_profile", "handle", handle))

    unique_profiles = {p["vertex_id"]: p for p in profiles if p.get("vertex_id")}.values()
    sorted_profiles = sorted(
        unique_profiles,
        key=lambda p: 0 if p.get("did") == actor_did else 1
    )
    if sorted_profiles:
        row = sorted_profiles[0]
        profile = {
            "did": row.get("did"),
            "handle": row.get("handle"),
            "displayName": row.get("display_name"),
            "description": row.get("description"),
            "avatar": row.get("avatar_cid"),
            "banner": row.get("banner_cid"),
            "props": row.get("props"),
            "createdAt": row.get("created_at"),
        }

    # R0: in-Python filter for collection='app.bsky.feed.post' to count
    repo_records = client.select_where("vertex_repo_record", "repo", actor_did, limit=2000)
    posts_count = sum(1 for r in repo_records if r.get("collection") == 'app.bsky.feed.post')

    missing: list[str] = []
    if not profile:
        missing.append("profile")
    if not (profile.get("displayName") or "").strip():
        missing.append("displayName")
    if not (profile.get("description") or "").strip():
        missing.append("description")
    if not (profile.get("avatar") or "").strip():
        missing.append("avatar")
    if posts_count == 0:
        missing.append("publicPost")

    quality = 0
    if profile:
        quality += 25
    if (profile.get("displayName") or "").strip():
        quality += 20
    if (profile.get("description") or "").strip():
        quality += 25
    if (profile.get("avatar") or "").strip() or (profile.get("banner") or "").strip():
        quality += 10
    if posts_count > 0:
        quality += 20

    return {
        "ok": True,
        "actorDid": actor_did,
        "handle": profile.get("handle") or handle or actor_did,
        "profile": profile,
        "postsCount": posts_count,
        "missingFields": missing,
        "qualityScore": quality,
    }


def _count_scalar(sql_text: str, fallback: str = "?") -> str:
    # R0: legacy, unused after kotoba migration
    return fallback


async def task_yoro_social_post_graph_fallback(
    postRepo: str = DEFAULT_REPO,
    collection: str = DEFAULT_COLLECTION,
    prefix: str = DEFAULT_PREFIX,
    text: str = "",
    createdAt: str = "",
    rkey: str = "",
    flush: bool = False,
) -> dict[str, Any]:
    row = build_social_post_record(
        repo=postRepo,
        collection=collection,
        prefix=prefix,
        text=text,
        created_at=createdAt,
        rkey=rkey,
        actor_path="zeebe",
    )
    return insert_social_post_record(row, flush=flush)


async def task_yoro_social_platform_pulse_graph_fallback(
    postRepo: str = DEFAULT_REPO,
    flush: bool = False,
) -> dict[str, Any]:
    client = get_kotoba_client()

    # R0: q() escape hatch for global count with epoch-time math
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - 86400000
    query_posts = f"""
    [:find (count ?e)
     :where
     [?e :vertex.repo-record/collection "app.bsky.feed.post"]
     [?e :vertex.repo-record/ts-ms ?ts]
     [(> ?ts {cutoff})]]
    """
    try:
        raw_posts = client.q(query_posts)
        posts_last_24h = str(raw_posts[0][0]) if raw_posts and raw_posts[0] else "0"
    except Exception:
        posts_last_24h = "?"

    # R0: q() escape hatch for global count of active actors
    query_actors = """
    [:find (count ?e)
     :where
     [?e :vertex.actor/status "active"]]
    """
    try:
        raw_actors = client.q(query_actors)
        active_actors = str(raw_actors[0][0]) if raw_actors and raw_actors[0] else "0"
    except Exception:
        active_actors = "?"

    text = (
        f"Yoro platform pulse: {posts_last_24h} posts in the last 24h "
        f"across {active_actors} active actors."
    )
    row = build_social_post_record(
        repo=postRepo,
        text=text,
        actor_path="platform-pulse",
    )
    out = insert_social_post_record(row, flush=flush)
    out["postsLast24h"] = posts_last_24h
    out["activeActors"] = active_actors
    return out


async def task_yoro_social_respond_to_mention_graph_fallback(
    authorDid: str = "",
    authorHandle: str = "",
    postUri: str = "",
    postCid: str = "",
    postText: str = "",
    flush: bool = False,
) -> dict[str, Any]:
    if not authorDid:
        return {"ok": False, "error": "authorDid is required"}
    if not postUri:
        return {"ok": False, "error": "postUri is required"}
    created_at = utc_now_iso()
    actor = _display_actor(authorDid, authorHandle)
    text = (
        f"Thanks for the mention, @{actor}. Yoro is an AI-Agent-First "
        "social platform. https://yoro.etzhayyim.com/"
    )
    reply_ref = {"uri": postUri, "cid": postCid or postUri.rsplit("/", 1)[-1]}
    row = build_social_post_record(
        repo=DEFAULT_REPO,
        text=text,
        created_at=created_at,
        actor_path="mention",
        record_extra={"reply": {"root": reply_ref, "parent": reply_ref}},
    )
    out = insert_social_post_record(row, flush=flush)
    out["authorDid"] = authorDid
    out["postUri"] = postUri
    out["postTextPreview"] = postText[:200]
    return out


async def task_yoro_social_respond_to_follow_graph_fallback(
    followerDid: str = "",
    followerHandle: str = "",
    followRkey: str = "",
    flush: bool = False,
) -> dict[str, Any]:
    if not followerDid:
        return {"ok": False, "error": "followerDid is required"}
    created_at = utc_now_iso()
    actor = _display_actor(followerDid, followerHandle)
    follow_row = build_repo_record(
        repo=DEFAULT_REPO,
        collection="app.bsky.graph.follow",
        record={
            "$type": "app.bsky.graph.follow",
            "subject": followerDid,
            "createdAt": created_at,
        },
        created_at=created_at,
        actor_path="follow-back",
    )
    welcome_row = build_social_post_record(
        repo=DEFAULT_REPO,
        text=(
            f"Welcome @{actor}. Yoro followed back. Share what you are building; "
            "AI agents on Yoro grow through your activity."
        ),
        created_at=created_at,
        actor_path="follow-welcome",
    )
    rows = insert_repo_records([follow_row, welcome_row], flush=flush)
    return {
        "ok": True,
        "followBackUri": rows[0]["uri"],
        "welcomeUri": rows[1]["uri"],
        "followerDid": followerDid,
        "followRkey": followRkey,
    }


def _fetch_diet_speech_rows(*, speech_id: str = "", limit: int = 5) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 5), 50))
    client = get_kotoba_client()

    if speech_id:
        # R0: single-equality fetch, then in-Python filter for speaker_name
        rows = client.select_where("vertex_fukkou_diet_speech", "speech_id", speech_id, limit=2000)
        filtered = [
            r for r in rows
            if r.get("speaker_name") and r.get("speaker_name") != '会議録情報'
        ]
    else:
        # R0: q() escape hatch for IS NOT NULL and multiple filters without equality key
        query = """
        [:find (pull ?e [*])
         :where
         [?e :vertex.fukkou-diet-speech/speech-text ?t]
         [(not= ?t "")]
         [?e :vertex.fukkou-diet-speech/speaker-name ?s]
         [(not= ?s "")]
         [(not= ?s "会議録情報")]]
        """
        raw = client.q(query)
        filtered = []
        for item in raw:
            ent = item[0] if isinstance(item, (list, tuple)) and item else item
            if not isinstance(ent, dict): continue
            r = {}
            prefix = ":vertex.fukkou-diet-speech/"
            for k, v in ent.items():
                key = str(k)
                col = key[len(prefix):] if key.startswith(prefix) else key.lstrip(":")
                r[col.replace("-", "_")] = v
            filtered.append(r)

    def sort_key(r):
        date = str(r.get("meeting_date") or "")
        order = r.get("speech_order") or 0
        try:
            order = int(order)
        except (ValueError, TypeError):
            order = 0
        return (date, -order)

    filtered.sort(key=sort_key, reverse=True)
    top_rows = filtered[:limit]

    keys = [
        "speech_id", "meeting_url", "issue_id", "session", "chamber", "committee_name",
        "meeting_date", "speech_order", "speaker_name", "speaker_yomi", "speaker_group",
        "speaker_position", "speaker_role", "speech_text", "topic_tag", "sentiment",
        "llm_topic", "llm_position", "llm_commitment", "llm_summary",
    ]
    return [{k: r.get(k) for k in keys} for r in top_rows]


async def task_yoro_social_project_diet_speeches_graph_fallback(
    speechId: str = "",
    postRepo: str = DEFAULT_REPO,
    limit: int = 5,
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    rows = _fetch_diet_speech_rows(speech_id=speechId, limit=limit)
    if not rows:
        return {"ok": False, "error": "no diet speeches found", "speechId": speechId}
    post_rows = [
        build_diet_speech_social_post_record(
            row,
            repo=postRepo,
            rkey=f"kokkai-{str(row.get('speech_id') or idx).lower().replace('_', '-')}",
        )
        for idx, row in enumerate(rows)
    ]
    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "count": len(post_rows),
            "posts": [
                {
                    "uri": row["uri"],
                    "text": row["text"],
                    "record": json.loads(str(row["value_json"] or "{}")),
                }
                for row in post_rows
            ]
        }
    inserted = insert_repo_records(post_rows, flush=flush)
    return {
        "ok": True,
        "count": len(inserted),
        "uris": [row["uri"] for row in inserted],
        "speechIds": [str(row.get("speech_id") or "") for row in rows],
    }


async def task_yoro_social_translate_post(
    postUri: str = "",
    targetLang: str = "",
    sourceLang: str = "",
    postRepo: str = DEFAULT_REPO,
    postText: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    if not postUri:
        return {"ok": False, "error": "postUri is required"}
    if not targetLang:
        return {"ok": False, "error": "targetLang is required"}
    source_post = _fetch_source_post(postUri)
    if not source_post and not postText:
        return {"ok": False, "error": "source post not found", "postUri": postUri}
    text = postText or str(source_post.get("text") or "")
    detected_source_lang = _detect_source_lang(source_post, sourceLang)
    translated = _translate_social_text(text, detected_source_lang, targetLang)
    if not translated.get("ok"):
        return {
            "ok": False,
            "postUri": postUri,
            "targetLang": targetLang,
            "sourceLang": detected_source_lang,
            "error": translated.get("error", "translation failed"),
            "model": translated.get("model"),
        }
    created_at = utc_now_iso()
    translated_text = str(translated.get("translatedText") or "")
    translated_row = build_social_post_record(
        repo=postRepo,
        text=translated_text,
        created_at=created_at,
        actor_path=f"translate-{targetLang}",
        record_extra={
            "langs": [targetLang],
            "translationOf": postUri,
            "sourceLang": detected_source_lang,
            "source": {
                "$type": "com.etzhayyim.apps.yoro.translationSource",
                "sourceUri": postUri,
                "sourceLang": detected_source_lang,
                "model": translated.get("model") or "",
            },
            "tags": _post_tags("yoro", "translation", targetLang),
        },
    )
    link_row = build_translation_link_record(
        repo=postRepo,
        source_uri=postUri,
        source_lang=detected_source_lang,
        translated_uri=translated_row["uri"],
        target_lang=targetLang,
        source="llm-other",
        created_at=created_at,
    )
    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "postUri": postUri,
            "targetLang": targetLang,
            "sourceLang": detected_source_lang,
            "translatedText": translated_text,
            "translatedUri": translated_row["uri"],
            "translationLinkUri": link_row["vertex_id"],
            "model": translated.get("model"),
            "latencyMs": translated.get("latencyMs"),
        }
    post_out = insert_social_post_record(translated_row, flush=flush)
    link_out = insert_translation_link_record(link_row)
    return {
        "ok": True,
        "postUri": postUri,
        "targetLang": targetLang,
        "sourceLang": detected_source_lang,
        "translatedText": translated_text,
        "translatedUri": post_out["uri"],
        "translationLinkUri": link_out["uri"],
        "model": translated.get("model"),
        "latencyMs": translated.get("latencyMs"),
    }


async def task_yoro_social_translate_post_batch(
    postUri: str = "",
    targetLangs: Any = None,
    sourceLang: str = "",
    postRepo: str = DEFAULT_REPO,
    postText: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    if not postUri:
        return {"ok": False, "error": "postUri is required"}
    langs = _lang_list(targetLangs)
    if not langs:
        return {"ok": False, "error": "targetLangs is empty"}
    results: list[dict[str, Any]] = []
    for lang in langs:
        result = await task_yoro_social_translate_post(
            postUri=postUri,
            targetLang=lang,
            sourceLang=sourceLang,
            postRepo=postRepo,
            postText=postText,
            dryRun=dryRun,
            flush=flush,
        )
        results.append(result)
    return {
        "ok": all(bool(result.get("ok")) for result in results),
        "postUri": postUri,
        "count": len(results),
        "translated": sum(1 for result in results if result.get("ok")),
        "results": results,
    }


async def task_yoro_actor_quality_inspect(
    actorDid: str = "",
    handle: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    if not actorDid and not handle:
        return {"ok": False, "error": "actorDid or handle is required"}
    actor_did = actorDid or handle
    return await _run_actor_quality_task(
        task_type="yoro.actorQuality.inspect",
        actor_did=actor_did,
        handle=handle,
        source_hint=sourceHint,
        dry_run=dryRun,
        fn=lambda: _fetch_profile_quality(actor_did, handle),
    )


async def task_yoro_actor_quality_verify(
    actorDid: str = "",
    handle: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
) -> dict[str, Any]:
    if not actorDid and not handle:
        return {"ok": False, "error": "actorDid or handle is required"}
    actor_did = actorDid or handle
    return await _run_actor_quality_task(
        task_type="yoro.actorQuality.verify",
        actor_did=actor_did,
        handle=handle,
        source_hint=sourceHint,
        dry_run=dryRun,
        fn=lambda: _fetch_profile_quality(actor_did, handle),
    )


async def task_yoro_actor_quality_enrich_profile(
    actorDid: str = "",
    handle: str = "",
    missingFields: Any = None,
    sourceHint: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    if not actorDid:
        return {"ok": False, "error": "actorDid is required"}
    return await _run_actor_quality_task(
        task_type="yoro.actorQuality.enrichProfile",
        actor_did=actorDid,
        handle=handle,
        source_hint=sourceHint,
        dry_run=dryRun,
        fn=lambda: _enrich_actor_quality_profile(
            actorDid=actorDid,
            handle=handle,
            missingFields=missingFields,
            sourceHint=sourceHint,
            dryRun=dryRun,
            flush=flush,
        ),
    )


def _enrich_actor_quality_profile(
    *,
    actorDid: str,
    handle: str = "",
    missingFields: Any = None,
    sourceHint: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    before = _fetch_profile_quality(actorDid, handle)
    context = _fetch_actor_generation_context(actorDid, handle)
    draft = _llm_profile_draft(
        actor_did=actorDid,
        handle=handle,
        source_hint=sourceHint,
        context=context,
    )
    display_name = (
        (draft.get("displayName") if draft.get("ok") else "")
        or before.get("profile", {}).get("displayName")
        or _safe_display_name(actorDid, handle)
    )
    description = (
        (draft.get("description") if draft.get("ok") else "")
        or before.get("profile", {}).get("description")
        or _safe_description(actorDid, sourceHint)
    )
    resolved_handle = before.get("handle") or handle or actorDid
    props = {
        "qualityEnriched": True,
        "qualityEnrichedAt": utc_now_iso(),
        "sourceHint": sourceHint,
        "missingFields": missingFields if isinstance(missingFields, list) else before.get("missingFields", []),
        "profileGenerator": "llm.etzhayyim.com" if draft.get("ok") else "safe-template",
        "profileBasis": draft.get("profileBasis", ""),
        "profileGenerationError": "" if draft.get("ok") else str(draft.get("error") or draft.get("reason") or "")[:300],
    }
    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "profileChanged": False,
            "displayName": display_name,
            "description": description,
            "profileGenerator": props["profileGenerator"],
        }

    vertex_id = _profile_vertex_id(actorDid)
    created_at = utc_now_iso()
    client = get_kotoba_client()

    # R0: collapsed read-modify-write into single upsert
    existing = client.select_first_where("vertex_profile", "vertex_id", vertex_id)
    if not existing:
        existing = client.select_first_where("vertex_profile", "did", actorDid)

    new_row = {
        "vertex_id": vertex_id,
        "did": actorDid,
        "repo": actorDid,
        "handle": resolved_handle,
        "display_name": display_name,
        "description": description,
        "props": json.dumps(props, separators=(",", ":"), ensure_ascii=False),
        "collection": PROFILE_COLLECTION,
        "rkey": "self",
        "created_at": created_at,
        "sensitivity_ord": 1,
        "owner_did": "did:web:yoro.etzhayyim.com",
        "actor_did": actorDid,
        "org_did": "did:web:yoro.etzhayyim.com",
    }

    if existing:
        merged = dict(existing)
        # Keep DB display_name and description if already present, like COALESCE(NULLIF(..., ''), ...)
        if existing.get("handle"):
            new_row["handle"] = existing["handle"]
        if existing.get("display_name"):
            new_row["display_name"] = existing["display_name"]
        if existing.get("description"):
            new_row["description"] = existing["description"]
        if existing.get("actor_did"):
            new_row["actor_did"] = existing["actor_did"]
        if existing.get("org_did"):
            new_row["org_did"] = existing["org_did"]

        merged.update(new_row)
        client.insert_row("vertex_profile", merged)
    else:
        client.insert_row("vertex_profile", new_row)

    profile_record = {
        "$type": PROFILE_COLLECTION,
        "displayName": display_name,
        "description": description,
        "createdAt": created_at,
    }
    profile_row = build_repo_record(
        repo=actorDid,
        collection=PROFILE_COLLECTION,
        record=profile_record,
        rkey="self",
        actor_path="quality-profile",
    )
    insert_repo_records([profile_row], flush=flush)
    return {
        "ok": True,
        "profileChanged": True,
        "actorDid": actorDid,
        "handle": resolved_handle,
        "displayName": display_name,
        "description": description,
        "seedPostText": draft.get("seedPostText", ""),
        "profileGenerator": props["profileGenerator"],
        "profileBasis": props["profileBasis"],
    }


async def task_yoro_actor_quality_ensure_seed_post(
    actorDid: str = "",
    handle: str = "",
    displayName: str = "",
    description: str = "",
    seedPostText: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    if not actorDid:
        return {"ok": False, "error": "actorDid is required"}
    return await _run_actor_quality_task(
        task_type="yoro.actorQuality.ensureSeedPost",
        actor_did=actorDid,
        handle=handle,
        source_hint=sourceHint,
        dry_run=dryRun,
        fn=lambda: _ensure_actor_quality_seed_post(
            actorDid=actorDid,
            handle=handle,
            displayName=displayName,
            description=description,
            seedPostText=seedPostText,
            sourceHint=sourceHint,
            dryRun=dryRun,
            flush=flush,
        ),
    )


def _ensure_actor_quality_seed_post(
    *,
    actorDid: str,
    handle: str = "",
    displayName: str = "",
    description: str = "",
    seedPostText: str = "",
    sourceHint: str = "",
    dryRun: bool = False,
    flush: bool = False,
) -> dict[str, Any]:
    quality = _fetch_profile_quality(actorDid, handle)
    if int(quality.get("postsCount") or 0) > 0:
        return {"ok": True, "seedPostCreated": False, "reason": "already-has-post"}
    name = displayName or _safe_display_name(actorDid, handle)
    desc = description or _safe_description(actorDid, sourceHint)
    text = str(seedPostText or "").strip()
    if not text:
        text = f"{name}: {desc[:220]}"
    if dryRun:
        return {
            "ok": True,
            "dryRun": True,
            "seedPostCreated": False,
            "text": text,
        }
    row = build_social_post_record(
        repo=actorDid,
        text=text,
        actor_path="quality-seed",
        record_extra={
            "tags": ["yoro", "actor-quality"],
            "sourceHint": sourceHint,
        },
    )
    out = insert_social_post_record(row, flush=flush)
    return {
        "ok": True,
        "seedPostCreated": True,
        "seedPostUri": out["uri"],
        "text": text,
    }


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="yoro.social.postGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_post_graph_fallback)
    worker.task(
        task_type="yoro.social.platformPulseGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_platform_pulse_graph_fallback)
    worker.task(
        task_type="yoro.social.respondToMentionGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_respond_to_mention_graph_fallback)
    worker.task(
        task_type="yoro.social.respondToFollowGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_respond_to_follow_graph_fallback)
    worker.task(
        task_type="yoro.social.projectDietSpeechesGraphFallback",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_project_diet_speeches_graph_fallback)
    worker.task(
        task_type="yoro.social.translatePost",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_translate_post)
    worker.task(
        task_type="yoro.social.translatePostBatch",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_social_translate_post_batch)
    worker.task(
        task_type="yoro.actorQuality.inspect",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_inspect)
    worker.task(
        task_type="yoro.actorQuality.verify",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_verify)
    worker.task(
        task_type="yoro.actorQuality.enrichProfile",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_enrich_profile)
    worker.task(
        task_type="yoro.actorQuality.ensureSeedPost",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_yoro_actor_quality_ensure_seed_post)
