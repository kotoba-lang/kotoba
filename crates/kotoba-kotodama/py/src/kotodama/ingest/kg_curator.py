"""KG Curator handlers for BPMN + Zeebe."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import re
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

OWNER_DID = "did:web:media-gamers.etzhayyim.com"
SLUG_RE = re.compile(r"^[a-z0-9-]+$")



def _str(value: Any) -> str:
    return "" if value is None else str(value)


def _post_json(url: str, payload: dict[str, Any], timeout: int = 120) -> Any:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _ollama_json(system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
    base = os.environ.get("OLLAMA_URL", "").rstrip("/")
    if not base:
        raise RuntimeError("kg-curator: OLLAMA_URL not configured")
    out = _post_json(
        f"{base}/v1/chat/completions",
        {
            "model": os.environ.get("OLLAMA_MODEL_EXTRACTION", "gemma4:e4b"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "out", "schema": schema}},
            "temperature": 0.6,
            "max_tokens": 3000,
        },
    )
    return json.loads(out["choices"][0]["message"]["content"])


CHAR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "characters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "slug": {"type": "string"},
                    "name": {"type": "string"},
                    "name_ja": {"type": "string"},
                    "role": {"type": "string"},
                    "character_class": {"type": "string"},
                    "description": {"type": "string", "maxLength": 280},
                },
                "required": ["slug", "name", "role", "description"],
            },
        }
    },
    "required": ["characters"],
}


def analyze_coverage(targetCount: Any = 12, limit: Any = 40, **_: Any) -> dict[str, Any]:
    target = int(targetCount) if targetCount is not None else 12
    # R0: Complex query with LEFT JOIN, COALESCE, ORDER BY, and LIMIT handled in Python.
    # Fetch titles released after 1990
    titles = get_kotoba_client().select_where(
        "vertex_game_title", "release_year", 1990, op=">=", columns=["vertex_id", "title_en", "release_year"]
    )
    # Fetch character counts per title
    character_counts_raw = get_kotoba_client().q(
        '[:find ?title_did (count ?c) :where [?c :vertex_game_character/title_did ?title_did]]'
    )
    character_counts = {title_did: count for title_did, count in character_counts_raw}

    processed_rows = []
    for t_row in titles:
        scope_did = t_row["vertex_id"]
        current_count = character_counts.get(scope_did, 0)
        processed_rows.append({
            "scope_did": scope_did,
            "title_en": t_row["title_en"],
            "current_count": current_count,
            "release_year": t_row["release_year"], # Keep for sorting
        })

    # Apply WHERE, ORDER BY, and LIMIT in Python
    filtered_rows = [row for row in processed_rows if row["current_count"] < target]
    filtered_rows.sort(key=lambda x: (x["current_count"], -x["release_year"])) # ASC by count, DESC by year
    rows = filtered_rows[:max(1, min(int(limit) if limit is not None else 40, 200))]
    tasks = [
        {
            "kind": "expand-characters",
            "scope_did": row["scope_did"],
            "title_en": row.get("title_en"),
            "current_count": row.get("current_count"),
            "target_count": target,
        }
        for row in rows
    ]
    return {"tasks_emitted": len(tasks), "target_per_title": target, "tasks": tasks}


def expand_title(scope_did: str = "", target_count: Any = 12, **_: Any) -> dict[str, Any]:
    if not scope_did:
        return {"error": "scope_did required"}
    existing_rows = get_kotoba_client().select_where("vertex_game_character", "title_did", scope_did, columns=["name", "character_role", "class"])
    title_row = get_kotoba_client().select_first_where("vertex_game_title", "vertex_id", scope_did, columns=["title_en", "release_year"])
    if not title_row:
        return {"skipped": "title not found"}
    need = (int(target_count) if target_count is not None else 12) - len(existing_rows)
    if need <= 0:
        return {"skipped": "already covered"}
    title = title_row.get("title_en")
    year = title_row.get("release_year")
    existing = ", ".join(f"{r.get('name')} ({r.get('character_role')})" for r in existing_rows)
    out = _ollama_json(
        "You are a knowledge graph generator for media-gamers.etzhayyim.com. Output strict JSON only. Slugs MUST match ^[a-z0-9-]+$.",
        f"Game: \"{title}\" ({year}). Existing characters: {existing or '(none)'}. Generate {need} more canonical characters from this game's universe NOT in the existing list. Include name in English + Japanese (name_ja), role, character_class, and one-sentence description. Output JSON: {{\"characters\":[...]}}.",
        CHAR_SCHEMA,
    )
    inserted = 0
    skipped: list[str] = []
    for raw in out.get("characters", []):
        slug_text = _str(raw.get("slug"))
        if not SLUG_RE.match(slug_text):
            skipped.append(f"bad-slug:{slug_text}")
            continue
        slug = f"did:etzhayyim:gamechar:{slug_text}"
        if get_kotoba_client().select_first_where("vertex_game_character", "vertex_id", slug, columns=["vertex_id"]):
            skipped.append(f"dup:{slug_text}")
            continue
        name = _str(raw.get("name"))
        desc = _str(raw.get("description"))
        char_row = {
            "vertex_id": slug,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            "title_did": scope_did,
            "name": name,
            "name_ja": _str(raw.get("name_ja")),
            "character_role": _str(raw.get("role")),
            "class": _str(raw.get("character_class")),
            "first_appearance_title_did": scope_did,
            "voice_actor_did": None,
        }
        get_kotoba_client().insert_row("vertex_game_character", char_row)
        handle = f"{slug_text}.media-gamers.etzhayyim.com"
        actor_row = {
            "vertex_id": slug,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            "did": slug,
            "handle": handle,
            "display_name": name,
            "name": name,
            "execution_tier": "T0",
            "performer_type": "game-character",
            "status": "active",
            "category": "character",
            "classification": os.environ.get("KG_LLM_TIER", "T0"),
            "operator": "etzhayyim.com",
            "agent_type": "logical",
            "runtime_type": "db-only",
            "ui_type": "metadata-only",
            "country": "jp",
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        get_kotoba_client().insert_row("vertex_actor", actor_row)
        profile = {
            "displayName": name,
            "displayNameJa": _str(raw.get("name_ja")),
            "description": desc,
            "role": _str(raw.get("role")),
            "class": _str(raw.get("character_class")),
            "isBot": True,
            "tier": "T0-llm-generated",
            "category": "game-character",
            "llm_generated": True,
            "llm_model": os.environ.get("OLLAMA_MODEL_EXTRACTION", "gemma4:e4b"),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z',
        }
        manifest_row = {
            "vertex_id": slug,
            "sensitivity_ord": 0,
            "owner_did": OWNER_DID,
            "did": slug,
            "name": name,
            "display_name": name,
            "description": desc,
            "execution_tier": "T0",
            "performer_type": "game-character",
            "profile_json": json.dumps(profile, ensure_ascii=False),
            "status": "active",
            "created_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
        get_kotoba_client().insert_row("vertex_actor_manifest", manifest_row)
        inserted += 1
    return {"inserted": inserted, "skipped": skipped}


def status(**_: Any) -> dict[str, Any]:
    # R0: Multi-predicate count (llm_generated) and general status queries.
    # The 'llm_generated' count requires a Datalog query or in-Python filtering.
    # Using Datalog q() for the LIKE clause.

    t0_actors_count = get_kotoba_client().aggregate_where(
        "vertex_actor_manifest", "count", "*", "execution_tier", "T0"
    )

    llm_generated_count_raw = get_kotoba_client().q(
        f"""[:find (count ?e)
             :where
             [?e :vertex_actor_manifest/execution_tier "T0"]
             [?e :vertex_actor_manifest/profile_json ?json_str]
             [(re-find #"{'%llm_generated%true%'}" ?json_str)]
           ]"""
    )
    llm_generated_count = llm_generated_count_raw[0][0] if llm_generated_count_raw else 0

    game_chars_count = get_kotoba_client().aggregate_where(
        "vertex_game_character", "count", "*", "owner_did", OWNER_DID
    )

    row = {
        "t0_actors": int(t0_actors_count),
        "llm_generated": int(llm_generated_count),
        "game_chars": int(game_chars_count),
    }
    return {"status": "alive", "linode_gpu": os.environ.get("OLLAMA_URL", ""), **row}
