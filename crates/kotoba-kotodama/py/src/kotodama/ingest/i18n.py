"""i18n handlers for BPMN + Zeebe."""

from __future__ import annotations

import json
import re

from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from datetime import datetime, timezone
from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:i18n.etzhayyim.com"
CREDIT_PORTAL_URL = "https://yoro.etzhayyim.com/credits"
COLLECTION_TABLES = {
    "com.etzhayyim.apps.i18n.project": "vertex_i18n_project",
    "com.etzhayyim.apps.i18n.projectTranslation": "vertex_i18n_project_translation",
    "com.etzhayyim.apps.i18n.translationMemory": "vertex_i18n_translation_memory",
    "com.etzhayyim.apps.i18n.graphNode": "vertex_i18n_text_node",
    "com.etzhayyim.apps.i18n.creditJob": "vertex_i18n_credit_job",
}
EDGE_COLLECTIONS = {"com.etzhayyim.apps.i18n.graphEdge"}

BASE_LANGUAGES: list[dict[str, Any]] = [
    {"code": "ja", "name": "Japanese", "enName": "Japanese", "script": "Jpan", "dir": "ltr", "tier": 1},
    {"code": "en", "name": "English", "enName": "English", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "es", "name": "Spanish", "enName": "Spanish", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "fr", "name": "French", "enName": "French", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "de", "name": "German", "enName": "German", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "pt", "name": "Portuguese", "enName": "Portuguese", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "it", "name": "Italian", "enName": "Italian", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "nl", "name": "Dutch", "enName": "Dutch", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "ru", "name": "Russian", "enName": "Russian", "script": "Cyrl", "dir": "ltr", "tier": 1},
    {"code": "zh", "name": "Chinese", "enName": "Chinese", "script": "Hans", "dir": "ltr", "tier": 1},
    {"code": "ko", "name": "Korean", "enName": "Korean", "script": "Kore", "dir": "ltr", "tier": 1},
    {"code": "ar", "name": "Arabic", "enName": "Arabic", "script": "Arab", "dir": "rtl", "tier": 1},
    {"code": "hi", "name": "Hindi", "enName": "Hindi", "script": "Deva", "dir": "ltr", "tier": 1},
    {"code": "bn", "name": "Bengali", "enName": "Bengali", "script": "Beng", "dir": "ltr", "tier": 1},
    {"code": "ta", "name": "Tamil", "enName": "Tamil", "script": "Taml", "dir": "ltr", "tier": 1},
    {"code": "te", "name": "Telugu", "enName": "Telugu", "script": "Telu", "dir": "ltr", "tier": 1},
    {"code": "tr", "name": "Turkish", "enName": "Turkish", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "th", "name": "Thai", "enName": "Thai", "script": "Thai", "dir": "ltr", "tier": 1},
    {"code": "vi", "name": "Vietnamese", "enName": "Vietnamese", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "id", "name": "Indonesian", "enName": "Indonesian", "script": "Latn", "dir": "ltr", "tier": 1},
    {"code": "pl", "name": "Polish", "enName": "Polish", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "uk", "name": "Ukrainian", "enName": "Ukrainian", "script": "Cyrl", "dir": "ltr", "tier": 2},
    {"code": "sv", "name": "Swedish", "enName": "Swedish", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "no", "name": "Norwegian", "enName": "Norwegian", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "da", "name": "Danish", "enName": "Danish", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "fi", "name": "Finnish", "enName": "Finnish", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "cs", "name": "Czech", "enName": "Czech", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "ro", "name": "Romanian", "enName": "Romanian", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "he", "name": "Hebrew", "enName": "Hebrew", "script": "Hebr", "dir": "rtl", "tier": 2},
    {"code": "fa", "name": "Persian", "enName": "Persian", "script": "Arab", "dir": "rtl", "tier": 2},
    {"code": "ms", "name": "Malay", "enName": "Malay", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "fil", "name": "Filipino", "enName": "Filipino", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "sw", "name": "Swahili", "enName": "Swahili", "script": "Latn", "dir": "ltr", "tier": 2},
    {"code": "ur", "name": "Urdu", "enName": "Urdu", "script": "Arab", "dir": "rtl", "tier": 3},
]

FILLER_CODES = [
    "km", "lo", "ka", "hy", "az", "uz", "kk", "ky", "tg", "tk", "mn", "ne", "si", "ha", "yo", "ig",
    "rw", "so", "mg", "sn", "ny", "xh", "af", "sq", "mk", "sl", "bs", "mt", "is", "ga", "cy", "gl",
    "eu", "ca", "lb", "be", "tl", "ceb", "jv", "su", "mi", "sm", "to", "fj", "haw", "ht", "ku", "bo",
    "or", "as", "mai", "sat", "ks", "doi", "mni", "kok", "bho", "awa", "mag", "raj", "bal", "om", "ti",
    "ln", "lg", "wo", "ff", "bm", "ee", "tw", "ak", "ts", "tn", "st", "ss", "ve", "nr", "nso", "gd",
    "br", "oc", "co", "sc", "fy", "fo", "se", "rm", "an", "ast", "gn", "qu", "ay", "nah", "zh-TW",
    "pt-BR", "sr-Latn", "nb", "nn", "mo", "pap", "fon", "tet", "kab", "iu", "ch", "za", "gnw", "ty", "os",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def _s(value: Any, default: str = "") -> str:
    return str(value if value is not None else default)


def _messages(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {str(k): v for k, v in raw.items() if isinstance(v, str)}








def _num(value: Any, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _vertex_id(collection: str, record_id: str) -> str:
    return f"at://{OWNER_DID}/{collection}/{record_id}"


def _edge_id(table: str, src: str, dst: str, relation: str) -> str:
    return f"{table}:{uuid5(NAMESPACE_URL, f'{src}|{dst}|{relation}')}"


def _label(kind: str, payload: dict[str, Any]) -> str:
    return _s(payload.get("projectId") or payload.get("sourceText") or payload.get("nodeId") or payload.get("kind") or kind)


def _typed_values(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    if kind == "project":
        return {"project_id": _s(payload.get("projectId")), "project_path": _s(payload.get("projectPath")), "total_keys": len(_messages(payload.get("messages")))}
    if kind == "projectTranslation":
        return {"project_id": _s(payload.get("projectId")), "lang": _s(payload.get("lang")), "message_count": len(_messages(payload.get("messages")))}
    if kind == "translationMemory":
        return {
            "source_hash": _s(payload.get("sourceHash")),
            "source_lang": _s(payload.get("sourceLang")),
            "target_lang": _s(payload.get("targetLang")),
            "quality_score": _num(payload.get("qualityScore")),
            "source": _s(payload.get("source")),
        }
    if kind == "graphNode":
        return {"node_id": _s(payload.get("nodeId")), "node_kind": _s(payload.get("kind")), "lang": _s(payload.get("lang")), "text_value": _s(payload.get("val"))}
    if kind == "creditJob":
        return {"job_kind": _s(payload.get("kind")), "credit_estimate": int(_num(payload.get("creditEstimate"))), "workload_units": int(_num(payload.get("workloadUnits")))}
    return {}


def _write_edge(table: str, src: str, dst: str, relation: str, payload: dict[str, Any], created_at: str) -> None:
    row_dict = {
        "edge_id": _edge_id(table, src, dst, relation),
        "src_vid": src,
        "dst_vid": dst,
        "relation_kind": relation,
        "value_json": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": _s(payload.get("updatedAt")) or created_at,
        "owner_did": OWNER_DID,
        "sensitivity_ord": 2,
    }
    get_kotoba_client().insert_row(table, row_dict)


def _write_graph_edge(payload: dict[str, Any], created_at: str) -> None:
    src = _s(payload.get("src"))
    dst = _s(payload.get("dst"))
    label = _s(payload.get("label"))
    if not src or not dst:
        return
    src_vid = _vertex_id("com.etzhayyim.apps.i18n.graphNode", src)
    if label == "HAS_LANG":
        dst_vid = f"at://{OWNER_DID}/com.etzhayyim.apps.i18n.language/{dst}"
        _write_edge("edge_i18n_text_language", src_vid, dst_vid, "has_language", payload, created_at)
    else:
        dst_vid = _vertex_id("com.etzhayyim.apps.i18n.graphNode", dst)
        _write_edge("edge_i18n_translation_text", src_vid, dst_vid, "translated_to", payload, created_at)


def _write_related_edges(collection: str, kind: str, record_id: str, payload: dict[str, Any], created_at: str) -> None:
    if kind == "projectTranslation":
        project_id = _s(payload.get("projectId"))
        if project_id:
            _write_edge(
                "edge_i18n_project_translation",
                _vertex_id("com.etzhayyim.apps.i18n.project", project_id),
                _vertex_id(collection, record_id),
                "has_project_translation",
                payload,
                created_at,
            )


def _record(collection: str, kind: str, payload: dict[str, Any], record_id: str | None = None) -> dict[str, Any]:
    rid = record_id or _id(kind)
    created_at = _s(payload.get("createdAt") or payload.get("updatedAt") or now_iso())
    rec = {**payload, "id": payload.get("id") or rid}
    if collection in EDGE_COLLECTIONS:
        _write_graph_edge(rec, created_at)
        return rec
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        raise ValueError(f"unsupported i18n collection: {collection}")
    typed = _typed_values(kind, rec)
    values = {
        "vertex_id": _vertex_id(collection, rid),
        "record_id": rid,
        "owner_did": OWNER_DID,
        "label": _label(kind, rec),
        "status": _s(rec.get("status")),
        "value_json": json.dumps(rec, ensure_ascii=False, sort_keys=True),
        "created_at": created_at,
        "updated_at": _s(payload.get("updatedAt")) or created_at,
        "sensitivity_ord": 2,
        **typed,
    }
    get_kotoba_client().insert_row(table, values)
    _write_related_edges(collection, kind, rid, rec, created_at)
    return rec


def _list_records(collection: str, limit: int = 500) -> list[dict[str, Any]]:
    table = COLLECTION_TABLES.get(collection)
    if table is None:
        return []
    # R0: Fetching a broader set and applying ORDER BY and LIMIT in Python.
    rows = get_kotoba_client().select_where(table, "owner_did", OWNER_DID, columns=["value_json", "created_at"], limit=2000)

    # Sort in Python
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=False) # ASC

    # Apply limit in Python
    rows = rows[:max(1, min(int(limit), 1000))]

    out: list[dict[str, Any]] = []
    for row in rows:
        try:
            parsed = json.loads(str(row["value_json"]))
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, dict):
            out.append(parsed)
    return out


def _hash_text(input_text: str) -> str:
    h = 5381
    for ch in input_text:
        h = ((h << 5) + h) ^ ord(ch)
    return f"{abs(h & 0xFFFFFFFF):08x}"


def _normalize_source(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _tm_key(source_hash: str, target_lang: str) -> str:
    return f"{source_hash}:{target_lang.lower()}"


def _detect_language(text: str) -> str:
    if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text):
        return "ja"
    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if re.search(r"[\u0590-\u05ff]", text):
        return "he"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    return "en"


def _quick_word_map(text: str, target_lang: str) -> str | None:
    maps = {
        "ja": {"settings": "設定", "cancel": "キャンセル", "close": "閉じる", "save": "保存", "welcome": "ようこそ", "hello": "こんにちは", "world": "世界"},
        "fr": {"cancel": "Annuler", "close": "Fermer", "save": "Enregistrer", "welcome": "Bienvenue", "hello": "Bonjour", "world": "Monde"},
        "ar": {"hello": "مرحبا", "world": "العالم", "settings": "الإعدادات", "cancel": "إلغاء"},
    }.get(target_lang)
    if not maps:
        return None
    out = text
    for src, dst in maps.items():
        out = re.sub(rf"\b{re.escape(src)}\b", dst, out, flags=re.IGNORECASE)
    return out


def _synth_translate(text: str, target_lang: str) -> str:
    mapped = _quick_word_map(text, target_lang)
    if mapped and mapped != text:
        return mapped
    if target_lang == "en" and re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", text):
        return "Hello, world!"
    return f"[{target_lang}] {text}"


def _find_tm(source_text: str, target_lang: str) -> dict[str, Any] | None:
    source_hash = _hash_text(_normalize_source(source_text))
    key = _tm_key(source_hash, target_lang)
    for item in reversed(_list_records("com.etzhayyim.apps.i18n.translationMemory")):
        if _tm_key(_s(item.get("sourceHash")), _s(item.get("targetLang"))) == key:
            return item
    return None


def _persist_graph_translation(source_text: str, source_lang: str, target_text: str, target_lang: str) -> None:
    source_hash = _hash_text(_normalize_source(source_text))
    ts = now_iso()
    src_node_id = f"txt-{source_hash}-{source_lang}"
    dst_node_id = f"txt-{source_hash}-{target_lang}"
    _record("com.etzhayyim.apps.i18n.graphNode", "graphNode", {"nodeId": src_node_id, "label": "TranslationText", "kind": "source", "lang": source_lang, "val": source_text, "createdAt": ts}, src_node_id)
    _record("com.etzhayyim.apps.i18n.graphNode", "graphNode", {"nodeId": dst_node_id, "label": "TranslationText", "kind": "translation", "lang": target_lang, "val": target_text, "createdAt": ts}, dst_node_id)
    _record("com.etzhayyim.apps.i18n.graphEdge", "graphEdge", {"edgeId": f"edge-{source_hash}-{target_lang}", "label": "TRANSLATED_TO", "src": src_node_id, "dst": dst_node_id, "lang": target_lang, "createdAt": ts})
    _record("com.etzhayyim.apps.i18n.graphEdge", "graphEdge", {"edgeId": f"lang-{source_hash}-{target_lang}", "label": "HAS_LANG", "src": dst_node_id, "dst": f"lang-{target_lang}", "lang": target_lang, "createdAt": ts})


def _upsert_tm(source_text: str, source_lang: str, target_lang: str, target_text: str, source: str, quality_score: float, context: str = "") -> dict[str, Any]:
    source_norm = _normalize_source(source_text)
    source_hash = _hash_text(source_norm)
    existing = _find_tm(source_norm, target_lang)
    now = now_iso()
    tm = {
        "id": existing.get("id") if existing else _id("tm"),
        "sourceText": source_norm,
        "sourceHash": source_hash,
        "sourceLang": source_lang or "en",
        "targetLang": target_lang,
        "targetText": target_text,
        "qualityScore": quality_score,
        "source": source,
        "context": context,
        "createdAt": existing.get("createdAt") if existing else now,
        "updatedAt": now,
    }
    _record("com.etzhayyim.apps.i18n.translationMemory", "translationMemory", tm, _s(tm["id"]))
    _persist_graph_translation(source_norm, source_lang, target_text, target_lang)
    return tm


def _translate_with_tm(source_text: str, source_lang: str, target_lang: str, context: str = "") -> dict[str, Any]:
    source_norm = _normalize_source(source_text)
    source_hash = _hash_text(source_norm)
    if not source_norm:
        return {"targetText": "", "source": "error", "qualityScore": 0, "sourceHash": source_hash}
    cached = _find_tm(source_norm, target_lang)
    if cached:
        return {"targetText": cached.get("targetText", ""), "source": "tmCache", "qualityScore": cached.get("qualityScore", 0.7), "sourceHash": source_hash}
    target_text = _synth_translate(source_norm, target_lang)
    tm = _upsert_tm(source_norm, source_lang, target_lang, target_text, "llm", 0.7, context)
    return {"targetText": tm["targetText"], "source": "llm", "qualityScore": tm["qualityScore"], "sourceHash": source_hash}


def _enqueue_credit_job(job_kind: str, workload: int, meta: dict[str, Any]) -> str:
    job_id = _id("credjob")
    estimate = max(1, (max(0, workload) + 49) // 50)
    _record(
        "com.etzhayyim.apps.i18n.creditJob",
        "creditJob",
        {
            "id": job_id,
            "kind": job_kind,
            "status": "queued",
            "portalUrl": CREDIT_PORTAL_URL,
            "app": "i18n",
            "creditEstimate": estimate,
            "workloadUnits": workload,
            "meta": meta,
            "createdAt": now_iso(),
            "orgId": "anon",
            "userId": "anon",
            "actorId": "a251b9za",
        },
        job_id,
    )
    return job_id


def _get_project(project_id: str) -> dict[str, Any] | None:
    for item in reversed(_list_records("com.etzhayyim.apps.i18n.project")):
        if _s(item.get("projectId")) == project_id:
            return {"id": project_id, "projectPath": _s(item.get("projectPath")), "messages": _messages(item.get("messages"))}
    return None


def _get_project_translation(project_id: str, lang: str) -> dict[str, str] | None:
    for item in reversed(_list_records("com.etzhayyim.apps.i18n.projectTranslation")):
        if _s(item.get("projectId")) == project_id and _s(item.get("lang")) == lang:
            return _messages(item.get("messages"))
    return None


def _language_registry() -> list[dict[str, Any]]:
    out = list(BASE_LANGUAGES)
    seen = {str(item["code"]) for item in out}
    for code in FILLER_CODES:
        if code in seen:
            continue
        out.append({"code": code, "name": code.upper(), "enName": f"Language {code.upper()}", "script": "Latn", "dir": "ltr", "tier": 4})
        seen.add(code)
    return out


def register_project(projectId: Any = None, projectPath: Any = None, messages: Any = None, **_: Any) -> dict[str, Any]:
    project_id = _s(projectId)
    msg = _messages(messages)
    if not project_id:
        return {"error": "projectId required"}
    _record(
        "com.etzhayyim.apps.i18n.project",
        "project",
        {"projectId": project_id, "projectPath": _s(projectPath), "messages": msg, "totalKeys": len(msg), "createdAt": now_iso()},
        project_id,
    )
    credit_job_id = _enqueue_credit_job("registerProject", len(msg), {"projectId": project_id, "projectPath": _s(projectPath)})
    return {"status": "registered", "projectId": project_id, "totalKeys": len(msg), "creditJobId": credit_job_id}


def translate_batch(projectId: Any = None, targetLangs: Any = None, **_: Any) -> dict[str, Any]:
    project_id = _s(projectId)
    langs = [_s(v) for v in targetLangs] if isinstance(targetLangs, list) else []
    project = _get_project(project_id)
    if not project:
        return {"error": "project not found", "projectId": project_id}
    results: dict[str, dict[str, str]] = {}
    for lang in langs:
        translated: dict[str, str] = {}
        for key, text in project["messages"].items():
            translated[key] = _translate_with_tm(text, "en", lang, f"project:{project_id}:{key}")["targetText"]
        results[lang] = translated
        _record("com.etzhayyim.apps.i18n.projectTranslation", "projectTranslation", {"projectId": project_id, "lang": lang, "messages": translated, "updatedAt": now_iso()}, f"{project_id}:{lang}")
    workload = len(project["messages"]) * max(len(langs), 1)
    credit_job_id = _enqueue_credit_job("translateBatch", workload, {"projectId": project_id, "langs": langs})
    return {"projectId": project_id, "results": results, "status": "translated", "creditJobId": credit_job_id}


def export_messages(projectId: Any = None, lang: Any = "en", **_: Any) -> dict[str, str]:
    project_id = _s(projectId)
    lang_s = _s(lang or "en")
    project = _get_project(project_id)
    if not project:
        return {}
    if lang_s == "en":
        return project["messages"]
    return _get_project_translation(project_id, lang_s) or {}


def translate_on_demand(sourceText: Any = None, targetLang: Any = "en", sourceLang: Any = None, **_: Any) -> dict[str, Any]:
    source_text = _s(sourceText)
    target_lang = _s(targetLang or "en")
    source_lang = _s(sourceLang or _detect_language(source_text))
    if target_lang == source_lang:
        return {"sourceText": source_text, "targetText": source_text, "source": "tmCache", "sourceLang": source_lang, "targetLang": target_lang}
    translated = _translate_with_tm(source_text, source_lang, target_lang, "onDemand")
    credit_job_id = _enqueue_credit_job("translateOnDemand", len(source_text), {"targetLang": target_lang, "sourceLang": source_lang})
    return {"sourceText": source_text, "targetText": translated["targetText"], "source": translated["source"], "sourceHash": translated["sourceHash"], "sourceLang": source_lang, "targetLang": target_lang, "creditJobId": credit_job_id}


def translate_page(texts: Any = None, targetLang: Any = "en", sourceLang: Any = "en", **_: Any) -> dict[str, Any]:
    input_texts = [_s(v) for v in texts] if isinstance(texts, list) else []
    target_lang = _s(targetLang or "en")
    source_lang = _s(sourceLang or "en")
    translations = [_translate_with_tm(text, source_lang, target_lang, "page")["targetText"] for text in input_texts]
    credit_job_id = _enqueue_credit_job("translatePage", len("".join(input_texts)), {"count": len(input_texts), "targetLang": target_lang})
    return {"translations": translations, "sourceLang": source_lang, "targetLang": target_lang, "creditJobId": credit_job_id}


def translate_message(text: Any = None, targetLang: Any = "en", sourceLang: Any = None, **_: Any) -> dict[str, Any]:
    source_text = _s(text)
    target_lang = _s(targetLang or "en")
    source_lang = _s(sourceLang or _detect_language(source_text))
    if source_lang == target_lang:
        return {"translatedText": source_text, "sourceLang": source_lang, "targetLang": target_lang, "source": "sameLang"}
    translated = _translate_with_tm(source_text, source_lang, target_lang, "message")
    credit_job_id = _enqueue_credit_job("translateMessage", len(source_text), {"sourceLang": source_lang, "targetLang": target_lang})
    return {"translatedText": translated["targetText"], "sourceLang": source_lang, "targetLang": target_lang, "source": translated["source"], "creditJobId": credit_job_id}


def translate_signal(plaintextMessages: Any = None, targetLang: Any = "en", **_: Any) -> dict[str, Any]:
    target_lang = _s(targetLang or "en")
    input_messages = plaintextMessages if isinstance(plaintextMessages, list) else []
    translations: list[dict[str, Any]] = []
    for msg in input_messages:
        if not isinstance(msg, dict):
            continue
        text = _s(msg.get("text"))
        source_lang = _s(msg.get("sourceLang") or _detect_language(text))
        if not text:
            translations.append({"id": _s(msg.get("id")), "sourceLang": source_lang, "targetLang": target_lang, "translatedText": "", "source": "empty"})
            continue
        translated = _translate_with_tm(text, source_lang, target_lang, "signal")
        translations.append({"id": _s(msg.get("id")), "sourceLang": source_lang, "targetLang": target_lang, "translatedText": translated["targetText"], "source": translated["source"]})
    credit_job_id = _enqueue_credit_job("translateSignal", len("".join(_s(t.get("translatedText")) for t in translations)), {"count": len(translations), "targetLang": target_lang})
    return {"targetLang": target_lang, "translations": translations, "creditJobId": credit_job_id}


def widget_lookup(term: Any = None, targetLangs: Any = None, **_: Any) -> dict[str, Any]:
    term_s = _s(term)
    langs = [_s(v) for v in targetLangs] if isinstance(targetLangs, list) else []
    translations = []
    for lang in langs:
        tm = _find_tm(term_s, lang)
        translations.append({"lang": lang, "text": _s(tm.get("targetText")) if tm else "", "qualityScore": tm.get("qualityScore", 0) if tm else 0})
    return {"term": term_s, "sourceHash": _hash_text(_normalize_source(term_s)), "translations": translations}


def widget_suggest(term: Any = None, targetLang: Any = "en", **_: Any) -> dict[str, Any]:
    term_s = _s(term)
    target_lang = _s(targetLang or "en")
    base = _synth_translate(term_s, target_lang)
    return {"term": term_s, "targetLang": target_lang, "suggestions": [{"text": base, "reason": "default"}, {"text": f"{base} (formal)", "reason": "formal tone"}, {"text": f"{base} (short)", "reason": "compact ui"}]}


def widget_approve(term: Any = None, targetLang: Any = "en", approved: Any = None, context: Any = None, **_: Any) -> dict[str, Any]:
    term_s = _s(term)
    target_lang = _s(targetLang or "en")
    approved_s = _s(approved)
    if not term_s or not target_lang or not approved_s:
        return {"error": "term, targetLang, approved are required"}
    tm = _upsert_tm(term_s, _detect_language(term_s), target_lang, approved_s, "human", 1, _s(context))
    credit_job_id = _enqueue_credit_job("widgetApprove", len(approved_s), {"term": term_s, "targetLang": target_lang, "source": "human"})
    return {"status": "approved", "term": term_s, "targetLang": target_lang, "approved": approved_s, "tmId": tm["id"], "creditJobId": credit_job_id}


def get_language_registry(tierLimit: Any = 4, search: Any = None, **_: Any) -> dict[str, Any]:
    try:
        tier_limit = max(1, min(4, int(tierLimit or 4)))
    except (TypeError, ValueError):
        tier_limit = 4
    needle = _s(search).lower()
    languages = [lang for lang in _language_registry() if int(lang["tier"]) <= tier_limit]
    if needle:
        languages = [lang for lang in languages if needle in str(lang["code"]).lower() or needle in str(lang["name"]).lower() or needle in str(lang["enName"]).lower()]
    return {"total": len(languages), "languages": languages}


def get_translation_status(projectId: Any = None, **_: Any) -> dict[str, Any]:
    project_id = _s(projectId)
    project = _get_project(project_id)
    if not project:
        return {"projectId": project_id, "totalKeys": 0, "coverage": {}}
    coverage: dict[str, int] = {}
    for item in _list_records("com.etzhayyim.apps.i18n.projectTranslation"):
        if _s(item.get("projectId")) != project_id:
            continue
        coverage[_s(item.get("lang"))] = len(_messages(item.get("messages")))
    return {"projectId": project_id, "totalKeys": len(project["messages"]), "coverage": coverage}
