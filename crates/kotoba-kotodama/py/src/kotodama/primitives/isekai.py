"""Isekai game XRPC primitives for BPMN/LangServer."""

from __future__ import annotations

import datetime as _dt
import decimal as _decimal
import json
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


ISEKAI_DID = "did:web:isekai.etzhayyim.com"
APP_ID = "is3k41w0"
BIOMES = ["plains", "forest", "desert", "tundra", "nether", "skibidi-dimension"]
BRAINROT_NPCS = [
    {"id": "skibidi-toilet", "name": "Skibidi Toilet", "biome": "plains", "isBoss": False},
    {"id": "sigma-male", "name": "Sigma Male", "biome": "tundra", "isBoss": False},
    {"id": "ohio-boss", "name": "Ohio Boss", "biome": "desert", "isBoss": True},
    {"id": "grimace-shake", "name": "Grimace Shake", "biome": "forest", "isBoss": False},
    {"id": "rizz-master", "name": "Rizz Master", "biome": "plains", "isBoss": False},
    {"id": "fanum-tax", "name": "Fanum Tax", "biome": "forest", "isBoss": False},
]
BRAINROT_LEGENDARIES = [
    {"speciesId": 901, "name": "Skibidion", "types": "water,brainrot", "ability": "Toilet Flush", "catchBiome": "skibidi-dimension"},
    {"speciesId": 902, "name": "Sigmalord", "types": "psychic,brainrot", "ability": "Sigma Stare", "catchBiome": "skibidi-dimension"},
    {"speciesId": 903, "name": "Ohiodon", "types": "dark,brainrot", "ability": "Ohio Final Boss", "catchBiome": "skibidi-dimension"},
    {"speciesId": 904, "name": "Grimaceon", "types": "poison,fairy", "ability": "Shake Heal", "catchBiome": "skibidi-dimension"},
    {"speciesId": 905, "name": "Rizzler", "types": "fairy,brainrot", "ability": "Rizz Charm", "catchBiome": "skibidi-dimension"},
    {"speciesId": 906, "name": "Fanumoth", "types": "ghost,brainrot", "ability": "Tax Steal", "catchBiome": "skibidi-dimension"},
]
RECIPES = [
    {"recipeId": "wooden-pickaxe", "name": "Wooden Pickaxe", "category": "tool", "ingredients": {"oak-log": 3, "stick": 2}, "resultQuantity": 1},
    {"recipeId": "standard-ball", "name": "Standard Ball", "category": "pokoa-ball", "ingredients": {"iron-ingot": 1, "crystal-shard": 2}, "resultQuantity": 5},
    {"recipeId": "brainrot-ball", "name": "Brainrot Ball", "category": "pokoa-ball", "ingredients": {"brainrot-crystal": 3, "diamond": 1}, "resultQuantity": 1},
]
MS_COMPLIANCE_RECORDS = [
    {"id": "pat-us10232272", "type": "patent", "title": "Procedural generation of large-scale environments", "risk": "medium", "status": "granted", "mitigation": "Seed-based value noise and bounded chunk grid."},
    {"id": "pat-us9956475", "type": "patent", "title": "Block placement and destruction in 3D environment", "risk": "high", "status": "granted", "mitigation": "DDA raycast plus original block types."},
    {"id": "td-minecraft-look", "type": "tradeDress", "title": "Minecraft visual trade dress", "risk": "low", "status": "registered", "mitigation": "Distinct PBR/brainrot visual language."},
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return _now()[:10]


def _id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}-{uuid.uuid4().hex[:8]}"


def _int(v: Any, default: int = 0, *, lo: int = -10**9, hi: int = 10**9) -> int:
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        n = default
    return max(lo, min(hi, n))


def _jsonable(v: Any) -> Any:
    if isinstance(v, (datetime, _dt.date)):
        return v.isoformat()
    if isinstance(v, _decimal.Decimal):
        f = float(v)
        return int(f) if f.is_integer() else f
    return v


def _base(table_kind: str, rkey: str, label: str = "") -> dict[str, Any]:
    return {
        "vertex_id": f"at://{ISEKAI_DID}/com.etzhayyim.apps.isekai.{table_kind}/{rkey}",
        "created_date": _today(),
        "sensitivity_ord": 1,
        "owner_did": ISEKAI_DID,
        "rkey": rkey[:64],
        "repo": ISEKAI_DID,
        "label": label,
        "did": ISEKAI_DID,
    }


def _insert(table: str, values: dict[str, Any]) -> None:
    get_kotoba_client().insert_row(table, values)


def _count(table: str) -> int:
    return int(get_kotoba_client().aggregate_where(table, "count", "*", "_seq", 0))


def _moves(species_id: int, level: int) -> list[str]:
    if species_id >= 901:
        return ["brainrot-blast", "tackle", "rizz-charm"]
    return ["tackle", "growl"] + (["scratch"] if level >= 20 else [])


def task_isekai_create_world(seed: Any = 0, nickname: str = "Isekai World", did: str = "anon", **_: Any) -> dict[str, Any]:
    seed_n = _int(seed, random.randint(1, 2**32 - 1), lo=1)
    world_id = f"isekai-{base36(seed_n)}"
    now = _now()
    world = {"worldId": world_id, "ownerDid": did or "anon", "seed": seed_n, "timeOfDay": 0.25, "dayCount": 1, "activeBiome": "plains", "playerCount": 1, "createdAt": now}
    _insert("vertex_isekai_world_state", {
        **_base("worldState", world_id, nickname),
        "world_id": world_id,
        "seed": seed_n,
        "time_of_day": 0.25,
        "day_count": 1,
        "active_biome": "plains",
        "player_count": 1,
        "props": json.dumps(world, ensure_ascii=False),
    })
    return {"status": "created", "world": world}


def base36(n: int) -> str:
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = chars[r] + out
    return out or "0"


def task_isekai_browse_worlds(limit: Any = 20, offset: Any = 0, **_: Any) -> dict[str, Any]:
    limit_n = _int(limit, 20, lo=1, hi=100)
    offset_n = _int(offset, 0, lo=0)
    # R0: In-Python OFFSET and ORDER BY due to shim limitations.
    worlds = get_kotoba_client().select_where(
        "vertex_isekai_world_state",
        "_seq",
        0, # This condition will fetch all items with _seq > 0, which is implicitly true for all valid entries.
        columns=["world_id", "owner_did", "seed", "day_count", "player_count"],
        limit=offset_n + limit_n, # Fetch enough to apply offset and limit
    )
    # Sort and paginate in Python
    worlds = sorted(worlds, key=lambda x: x.get("_seq", 0))[offset_n:offset_n + limit_n]

    return {"worlds": worlds, "total": _count("vertex_isekai_world_state"), "offset": offset_n, "limit": limit_n}


def task_isekai_get_world(worldId: str = "", **_: Any) -> dict[str, Any]:
    world = get_kotoba_client().select_first_where(
        "vertex_isekai_world_state",
        "world_id",
        worldId,
        columns=["world_id", "owner_did", "seed", "time_of_day", "day_count", "active_biome", "player_count"],
    )
    return {"world": world} if world else {"error": "world not found", "worldId": worldId}


def task_isekai_teleport_biome(biome: str = "", **_: Any) -> dict[str, Any]:
    if biome not in BIOMES:
        return {"error": "invalid biome", "valid": BIOMES}
    spawn = {"plains": [0, 64, 0], "forest": [256, 70, 128], "desert": [-300, 62, 400], "tundra": [0, 72, -500], "nether": [128, 40, 128], "skibidi-dimension": [0, 100, 0]}
    return {"biome": biome, "spawnPosition": spawn[biome]}


def task_isekai_mine_block(worldId: str = "", did: str = "anon", blockType: str = "stone", x: Any = 0, y: Any = 0, z: Any = 0, **_: Any) -> dict[str, Any]:
    rkey = _id("mine")
    chunk_x = _int(x) // 16
    chunk_z = _int(z) // 16
    _insert("vertex_isekai_chunk_data", {
        **_base("chunkData", rkey, blockType),
        "world_id": worldId,
        "chunk_x": chunk_x,
        "chunk_z": chunk_z,
        "edit_type": "mine",
        "block_type": blockType,
        "x": _int(x),
        "y": _int(y),
        "z": _int(z),
        "props": json.dumps({"did": did, "at": _now()}),
    })
    item = {"stone": "cobblestone", "oak-log": "oak-log", "iron-ore": "iron-ore", "brainrot-ore": "brainrot-crystal"}.get(blockType, blockType)
    _add_inventory(did, item, item.replace("-", " ").title(), "resource", 1)
    return {"mined": True, "item": item, "quantity": 1}


def task_isekai_place_block(worldId: str = "", blockType: str = "stone", x: Any = 0, y: Any = 0, z: Any = 0, **_: Any) -> dict[str, Any]:
    rkey = _id("place")
    _insert("vertex_isekai_chunk_data", {
        **_base("chunkData", rkey, blockType),
        "world_id": worldId,
        "chunk_x": _int(x) // 16,
        "chunk_z": _int(z) // 16,
        "edit_type": "place",
        "block_type": blockType,
        "x": _int(x),
        "y": _int(y),
        "z": _int(z),
        "props": json.dumps({"at": _now()}),
    })
    return {"placed": True, "blockType": blockType, "position": [_int(x), _int(y), _int(z)]}


def task_isekai_get_chunk(worldId: str = "", chunkX: Any = 0, chunkZ: Any = 0, **_: Any) -> dict[str, Any]:
    # R0: Multi-predicate WHERE clause requires raw Datalog `q()` query, then in-Python ORDER BY.
    query_edn = """[:find (pull ?e [:vertex/edit_type :vertex/block_type :vertex/x :vertex/y :vertex/z :vertex/_seq])
                   :where [?e :vertex/world_id ?world_id]
                          [?e :vertex/chunk_x ?chunk_x]
                          [?e :vertex/chunk_z ?chunk_z]
                   :in $ ?world_id ?chunk_x ?chunk_z]"""
    rows = get_kotoba_client().q(query_edn, args=[worldId, _int(chunkX), _int(chunkZ)])
    edits = []
    for row in rows:
        edit = row[0] # Assuming pull returns a single map
        # Convert Datomic keywords to snake_case dictionary keys
        converted_edit = {k.replace(":vertex/", "").replace(":", ""): v for k, v in edit.items()}
        edits.append(converted_edit)

    # Apply ORDER BY _seq and LIMIT 1000 in Python
    edits = sorted(edits, key=lambda x: x.get("_seq", 0))[:1000]

    return {"worldId": worldId, "chunkX": _int(chunkX), "chunkZ": _int(chunkZ), "edits": edits}


def task_isekai_get_roster(did: str = "anon", **_: Any) -> dict[str, Any]:
    # R0: OR condition requires fetching by each condition and combining in Python.
    roster_by_owner = get_kotoba_client().select_where(
        "vertex_isekai_creature_roster", "owner_did", did, limit=100
    )
    roster_by_did = get_kotoba_client().select_where(
        "vertex_isekai_creature_roster", "did", did, limit=100
    )
    # Combine and deduplicate
    combined_roster = {item["vertex_id"]: item for item in roster_by_owner + roster_by_did}.values()
    roster = list(combined_roster)[:100] # Apply limit after deduplication

    return {"roster": roster, "total": len(roster), "did": did}


def task_isekai_roll_encounter(biome: str = "plains", **_: Any) -> dict[str, Any]:
    species = random.choice([1, 4, 7, 10, 13, 19, 25, 43, 69])
    level = random.randint(3, 12) + (10 if biome == "skibidi-dimension" else 0)
    return {"encounter": {"speciesId": species, "level": level, "biome": biome}, "message": f"Wild Pokoa #{species} appeared!"}


def task_isekai_catch_pokoa(did: str = "anon", speciesId: Any = 1, level: Any = 5, ballType: str = "standard-ball", biome: str = "plains", **_: Any) -> dict[str, Any]:
    catch_rate = 0.9 if ballType == "brainrot-ball" else 0.55
    caught = random.random() < catch_rate
    if not caught:
        return {"caught": False, "message": "The Pokoa broke free!"}
    instance_id = _id("pk")
    _insert("vertex_isekai_creature_roster", {
        **_base("creatureRoster", instance_id, f"Pokoa #{_int(speciesId, 1)}"),
        "instance_id": instance_id,
        "species_id": _int(speciesId, 1),
        "level": _int(level, 5),
        "hp": 20 + _int(level, 5) * 3,
        "max_hp": 20 + _int(level, 5) * 3,
        "friendship": 50,
        "xp": 0,
        "caught_biome": biome,
        "caught_at": _now(),
        "action": "catch",
        "nickname": "",
        "moves_json": json.dumps(_moves(_int(speciesId, 1), _int(level, 5))),
        "props": json.dumps({"ballType": ballType}),
    })
    _insert("vertex_isekai_game_capture", {**_base("gameCapture", _id("cap"), ballType), "species_id": _int(speciesId, 1), "level": _int(level, 5), "ball_type": ballType, "biome": biome, "props": json.dumps({"did": did})})
    return {"caught": True, "instanceId": instance_id, "message": f"Caught Pokoa #{_int(speciesId, 1)}!"}


def task_isekai_heal_party(did: str = "anon", **_: Any) -> dict[str, Any]:
    # R0: OR condition requires fetching by each condition and combining in Python.
    roster_by_owner = get_kotoba_client().select_where(
        "vertex_isekai_creature_roster", "owner_did", did, columns=["instance_id"], limit=100
    )
    roster_by_did = get_kotoba_client().select_where(
        "vertex_isekai_creature_roster", "did", did, columns=["instance_id"], limit=100
    )
    # Combine and deduplicate based on instance_id
    combined_roster = {item["instance_id"]: item for item in roster_by_owner + roster_by_did}.values()
    healed_instances = list(combined_roster)[:100] # Apply limit after deduplication

    return {"healed": len(healed_instances), "did": did}


def task_isekai_get_legendaries(**_: Any) -> dict[str, Any]:
    return {"legendaries": BRAINROT_LEGENDARIES}


def task_isekai_list_recipes(**_: Any) -> dict[str, Any]:
    return {"recipes": RECIPES}


def _add_inventory(did: str, item_id: str, name: str, category: str, quantity: int) -> None:
    _insert("vertex_isekai_inventory_item", {**_base("inventoryItem", _id("inv"), name), "item_id": item_id, "name": name, "category": category, "quantity": quantity, "props": json.dumps({"did": did})})


def task_isekai_craft_item(did: str = "anon", recipeId: str = "", quantity: Any = 1, **_: Any) -> dict[str, Any]:
    recipe = next((r for r in RECIPES if r["recipeId"] == recipeId), None)
    if not recipe:
        return {"error": "recipe_not_found"}
    qty = _int(quantity, 1, lo=1, hi=99)
    _add_inventory(did, str(recipe["recipeId"]), str(recipe["name"]), str(recipe["category"]), int(recipe["resultQuantity"]) * qty)
    _insert("vertex_isekai_game_craft", {**_base("gameCraft", _id("craft"), str(recipe["name"])), "recipe_id": recipeId, "quantity": qty, "props": json.dumps({"did": did})})
    return {"crafted": True, "recipeId": recipeId, "quantity": qty}


def task_isekai_get_inventory(did: str = "anon", **_: Any) -> dict[str, Any]:
    # R0: LIKE operator on JSON column not directly supported by shim, filtering in Python.
    # Assuming 'owner_did' in _base corresponds to the 'did' we want to filter by in props.
    all_inventory_items = get_kotoba_client().select_where(
        "vertex_isekai_inventory_item", "owner_did", did, limit=500
    )
    rows = []
    did_json_str = json.dumps({"did": did}) # To match the LIKE pattern
    for item in all_inventory_items:
        if item.get("props") and did_json_str in item["props"]: # Simple substring match for LIKE
            rows.append(item)

    agg: dict[str, dict[str, Any]] = {}
    for r in rows:
        item = str(r.get("item_id") or "")
        agg.setdefault(item, {"itemId": item, "name": r.get("name"), "category": r.get("category"), "quantity": 0})
        agg[item]["quantity"] += _int(r.get("quantity"), 0)
    return {"inventory": [v for v in agg.values() if v["quantity"] > 0], "did": did}


def task_isekai_roll_brainrot(biome: str = "plains", **_: Any) -> dict[str, Any]:
    chance = 0.8 if biome == "skibidi-dimension" else 0.15
    if random.random() > chance:
        return {"encounter": None, "message": "No brainrot activity nearby... for now."}
    npc = random.choice(BRAINROT_NPCS)
    event_id = _id("br")
    encounter = {"eventId": event_id, "npc": npc["id"], "trigger": "random-walk", "position": [random.randint(-250, 250), 64, random.randint(-250, 250)], "dialogueJson": json.dumps({"opening": npc["name"]}), "rewardJson": json.dumps({"xp": 500 if npc["isBoss"] else 50}), "isBoss": npc["isBoss"]}
    _insert("vertex_isekai_game_brainrot_encounter", {**_base("gameBrainrotEncounter", event_id, str(npc["name"])), "npc": npc["id"], "is_boss": str(npc["isBoss"]).lower(), "props": json.dumps({"biome": biome, **encounter})})
    return {"encounter": encounter, "message": f"{npc['name']} appeared!"}


def task_isekai_get_portal_state(did: str = "anon", **_: Any) -> dict[str, Any]:
    # R0: Multiple WHERE conditions require raw Datalog `q()` query.
    query_edn = """[:find (pull ?e [:vertex/shard_count])
                   :where [?e :vertex/owner_did ?owner_did]
                          [?e :vertex/type "shard-collected"]
                   :in $ ?owner_did]"""
    rows = get_kotoba_client().q(query_edn, args=[did])
    shards = _int((rows[0][0] if rows else {}).get("shard_count"), 0)
    return {"shardsCollected": shards, "shardsRequired": 6, "portalOpen": shards >= 6, "message": "The Brainrot Dimension portal is OPEN!" if shards >= 6 else f"Collect {6-shards} more Brainrot Shards to open the portal."}


def task_isekai_start_ohio_raid(worldId: str = "", **_: Any) -> dict[str, Any]:
    _insert("vertex_isekai_brainrot_event", {**_base("brainrotEvent", _id("ohio"), "Ohio Boss"), "event_id": _id("raid"), "npc": "ohio-boss", "trigger": "raid", "is_boss": "true", "shard_count": 0, "type": "ohio-raid", "reward_json": json.dumps({"xp": 1000}), "dialogue_json": "{}", "props": json.dumps({"worldId": worldId})})
    return {"raidStarted": True, "boss": {"npc": "ohio-boss", "hp": 1000, "phases": 3}, "message": "ONLY IN OHIO!"}


def task_isekai_start_battle(playerSpeciesId: Any = 0, playerLevel: Any = 5, playerInstanceId: str = "unknown", enemySpeciesId: Any = 0, enemyLevel: Any = 5, biome: str = "plains", did: str = "anon", **_: Any) -> dict[str, Any]:
    ps, es = _int(playerSpeciesId), _int(enemySpeciesId)
    if not ps or not es:
        return {"error": "playerSpeciesId and enemySpeciesId are required"}
    pl, el = _int(playerLevel, 5), _int(enemyLevel, 5)
    battle_id = _id("battle")
    return {"battleId": battle_id, "player": {"speciesId": ps, "level": pl, "hp": 20 + pl * 3, "maxHp": 20 + pl * 3, "instanceId": playerInstanceId, "moves": _moves(ps, pl)}, "enemy": {"speciesId": es, "level": el, "hp": 20 + el * 3, "maxHp": 20 + el * 3}, "message": f"Battle started in {biome} for {did}."}


def task_isekai_use_move(playerSpeciesId: Any = 0, playerLevel: Any = 5, enemySpeciesId: Any = 0, enemyLevel: Any = 5, enemyHp: Any = 1, playerHp: Any = 1, turn: Any = 0, moveIndex: Any = 0, **_: Any) -> dict[str, Any]:
    move = _moves(_int(playerSpeciesId), _int(playerLevel, 5))[_int(moveIndex, 0, lo=0, hi=2)]
    dmg = max(1, _int(playerLevel, 5) * 2 + random.randint(0, 5))
    new_enemy = max(0, _int(enemyHp) - dmg)
    enemy_dmg = 0 if new_enemy == 0 else max(1, _int(enemyLevel, 5) + random.randint(0, 4))
    new_player = max(0, _int(playerHp) - enemy_dmg)
    status = "won" if new_enemy == 0 else "lost" if new_player == 0 else "ongoing"
    return {"turn": _int(turn) + 1, "playerMove": move, "playerDmg": dmg, "enemyMove": "tackle" if enemy_dmg else None, "enemyDmg": enemy_dmg, "playerHp": new_player, "enemyHp": new_enemy, "battleStatus": status, "evolved": None, "message": f"Used {move}."}


def task_isekai_flee_battle(**_: Any) -> dict[str, Any]:
    fled = random.random() < 0.5
    return {"fled": fled, "message": "Got away safely!" if fled else "Can't escape!"}


def task_isekai_register_compliance(**_: Any) -> dict[str, Any]:
    for rec in MS_COMPLIANCE_RECORDS:
        _insert("vertex_isekai_compliance_dep", {**_base("complianceDep", rec["id"], rec["title"]), "compliance_id": rec["id"], "type": rec["type"], "title": rec["title"], "risk": rec.get("risk", ""), "status": rec.get("status", ""), "mitigation": rec.get("mitigation", ""), "props": json.dumps(rec)})
    return {"registered": len(MS_COMPLIANCE_RECORDS), "message": "Registered compliance dependency nodes."}


def task_isekai_get_compliance(risk: str = "", **_: Any) -> dict[str, Any]:
    records = [r for r in MS_COMPLIANCE_RECORDS if not risk or r.get("risk") == risk]
    # R0: Filtering by risk is done in Python.
    rows = get_kotoba_client().select_where(
        "vertex_isekai_compliance_dep",
        "_seq",
        0, # This condition will fetch all items with _seq > 0, which is implicitly true for all valid entries.
        columns=["compliance_id", "type", "title", "risk", "status", "mitigation"],
        limit=50,
    )
    return {"complianceDeps": records, "summary": {"total": len(records), "highRisk": sum(1 for r in records if r.get("risk") == "high"), "mediumRisk": sum(1 for r in records if r.get("risk") == "medium"), "lowRisk": sum(1 for r in records if r.get("risk") == "low")}, "graphData": rows}


def task_isekai_list_scenes(worldMapUri: str = "", limit: Any = 100, offset: Any = 0, **_: Any) -> dict[str, Any]:
    limit_n, offset_n = _int(limit, 100, lo=1, hi=500), _int(offset, 0, lo=0)
    # R0: In-Python OFFSET and ORDER BY due to shim limitations.
    if worldMapUri:
        scenes = get_kotoba_client().select_where(
            "vertex_isekai_world_scene",
            "world_map_uri",
            worldMapUri,
            columns=["vertex_id", "world_map_uri", "scene_type", "x_dm", "z_dm", "radius_dm", "label", "params_json", "repo", "rkey"],
            limit=offset_n + limit_n, # Fetch enough to apply offset and limit
        )
    else:
        # If no worldMapUri, fetch all scenes (equivalent to _seq > 0)
        scenes = get_kotoba_client().select_where(
            "vertex_isekai_world_scene",
            "_seq",
            0, # This condition will fetch all items with _seq > 0, which is implicitly true for all valid entries.
            columns=["vertex_id", "world_map_uri", "scene_type", "x_dm", "z_dm", "radius_dm", "label", "params_json", "repo", "rkey"],
            limit=offset_n + limit_n, # Fetch enough to apply offset and limit
        )

    # Sort and paginate in Python
    scenes = sorted(scenes, key=lambda x: x.get("_seq", 0))[offset_n:offset_n + limit_n]

    return {"scenes": scenes, "total": len(scenes), "offset": offset_n, "limit": limit_n}


def task_isekai_analyze(**_: Any) -> dict[str, Any]:
    return {"summary": {"totalWorlds": _count("vertex_isekai_world_state"), "totalCaptures": _count("vertex_isekai_game_capture"), "totalBrainrotEncounters": _count("vertex_isekai_game_brainrot_encounter"), "totalCrafts": _count("vertex_isekai_game_craft")}, "updatedAt": _now()}


def task_isekai_card_home(**_: Any) -> dict[str, Any]:
    return {"contentType": "application/vnd.etzhayyim.card.list", "payload": {"title": "ISEKAI World", "items": [{"id": "worlds", "label": "Worlds", "sublabel": f"{_count('vertex_isekai_world_state')} created", "icon": "globe", "action": "isekai.browseWorlds"}, {"id": "pokoa", "label": "Pokoa", "sublabel": f"{_count('vertex_isekai_game_capture')} caught", "icon": "sparkle", "action": "isekai.getRoster"}]}}


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    tasks = {
        "xrpc.com.etzhayyim.apps.isekai.analyze": task_isekai_analyze,
        "xrpc.com.etzhayyim.apps.isekai.browseWorlds": task_isekai_browse_worlds,
        "xrpc.com.etzhayyim.apps.isekai.cardHome": task_isekai_card_home,
        "xrpc.com.etzhayyim.apps.isekai.catchPokoa": task_isekai_catch_pokoa,
        "xrpc.com.etzhayyim.apps.isekai.craftItem": task_isekai_craft_item,
        "xrpc.com.etzhayyim.apps.isekai.createWorld": task_isekai_create_world,
        "xrpc.com.etzhayyim.apps.isekai.fleeBattle": task_isekai_flee_battle,
        "xrpc.com.etzhayyim.apps.isekai.getChunk": task_isekai_get_chunk,
        "xrpc.com.etzhayyim.apps.isekai.getCompliance": task_isekai_get_compliance,
        "xrpc.com.etzhayyim.apps.isekai.getInventory": task_isekai_get_inventory,
        "xrpc.com.etzhayyim.apps.isekai.getLegendaries": task_isekai_get_legendaries,
        "xrpc.com.etzhayyim.apps.isekai.getPortalState": task_isekai_get_portal_state,
        "xrpc.com.etzhayyim.apps.isekai.getRoster": task_isekai_get_roster,
        "xrpc.com.etzhayyim.apps.isekai.getWorld": task_isekai_get_world,
        "xrpc.com.etzhayyim.apps.isekai.healParty": task_isekai_heal_party,
        "xrpc.com.etzhayyim.apps.isekai.listRecipes": task_isekai_list_recipes,
        "xrpc.com.etzhayyim.apps.isekai.listScenes": task_isekai_list_scenes,
        "xrpc.com.etzhayyim.apps.isekai.mineBlock": task_isekai_mine_block,
        "xrpc.com.etzhayyim.apps.isekai.placeBlock": task_isekai_place_block,
        "xrpc.com.etzhayyim.apps.isekai.registerCompliance": task_isekai_register_compliance,
        "xrpc.com.etzhayyim.apps.isekai.rollBrainrot": task_isekai_roll_brainrot,
        "xrpc.com.etzhayyim.apps.isekai.rollEncounter": task_isekai_roll_encounter,
        "xrpc.com.etzhayyim.apps.isekai.startBattle": task_isekai_start_battle,
        "xrpc.com.etzhayyim.apps.isekai.startOhioRaid": task_isekai_start_ohio_raid,
        "xrpc.com.etzhayyim.apps.isekai.teleportBiome": task_isekai_teleport_biome,
        "xrpc.com.etzhayyim.apps.isekai.useMove": task_isekai_use_move,
    }
    for task_type, handler in tasks.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=timeout_ms)(handler)
