"""MCP envelope dispatcher (ADR-2605082000 §2.6 + ADR-0087).

Receives MCP JSON-RPC `tools/call` envelopes at
``POST /xrpc/com.etzhayyim.mcp.message`` on the dispatcher and routes them to a
registered async callable. The route is consumed by LangGraph node bindings
of `kind=mcp_tool ref=mcp://<nsid>` after they resolve the actor_host via
``vertex_mcp_tool_def`` (see ``langgraph_node_resolvers._resolve_mcp_nsid``).

Registry shape:

    MCP_HANDLERS: dict[str, Callable[[dict], Awaitable[dict]]]

Each handler receives the envelope's ``params.arguments`` dict (already
parsed JSON object) and must return a dict. The dispatcher wraps the
return value in the JSON-RPC ``result`` field; LangGraph nodes consume
the entire response under their configured ``result_key``.

Auth, observability, and error envelope are kept minimal here; this is
the first cut. Once more actors are migrated, broaden the registry by
loading from ``vertex_mcp_tool_def`` directly instead of hardcoded imports.
"""

from __future__ import annotations

import importlib
import json
import logging
import re
from typing import Any, Awaitable, Callable

import aiohttp

LOG = logging.getLogger("mcp_dispatch")

# Phase H (2026-05-13): organism actors (saikin/ki/koke) run inside lg-organism pod.
# MCP calls are proxied via XRPC rather than executed in-process.
_LG_ORGANISM_BASE = "http://lg-organism.mitama-udf.svc.cluster.local:8000"
_LG_JUKYU_BASE = "http://lg-jukyu.mitama-udf.svc.cluster.local:8000"
_LG_SUPPLYCHAIN_BASE = "http://lg-supplychain.mitama-udf.svc.cluster.local:8000"

# jukyu: method → REST endpoint on lg-jukyu pod
_LG_JUKYU_ROUTES: dict[str, str] = {
    "runEquilibrium": "/cron/equilibrium",
    "drainOutbox": "/cron/outbox-drain",
    "adaptNaphtha": "/cron/domain-adapter/naphtha",
    "adaptCrudeOil": "/cron/domain-adapter/crude-oil",
    "adaptSemiconductor": "/cron/domain-adapter/semiconductor",
    "adaptTransport": "/cron/domain-adapter/transport",
}

# supplychain: method → REST endpoint on lg-supplychain pod
_LG_SUPPLYCHAIN_ROUTES: dict[str, str] = {
    "runEquilibrium": "/cron/equilibrium",
    "drainOutbox": "/cron/outbox-drain",
    "adaptCleaningRobot": "/cron/domain-adapter/cleaning-robot",
}

_LG_ORGANISM_ACTORS: dict[str, list[str]] = {
    "saikin": ["probeEnvironment", "transferSignal", "formColony", "handoffToKi", "lyse"],
    "ki": ["absorb", "synthesize", "bloom", "ring"],
    "koke": [
        "scanRawSignals",
        "fixSignal",
        "classifyFixation",
        "handoffToHakkou",
        "handoffToSaikin",
    ],
}

McpHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

# Convention-derived registration (ADR-2605082000 §2.6 + ADR-0087):
#
#   NSID                                       → Python target
#   com.etzhayyim.apps.<actor>.<methodCamel>         → kotodama.<actor>_worker_main:task_<method_snake>
#
# Adding a new actor is registry + lexicon work (data) — the dispatcher
# auto-wires by importing the matching ``task_*`` function. Use
# ``register_actor_by_convention`` for default actors and ``register_overrides``
# when the convention does not fit (rename, cross-module, decorator wrap).

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def _camel_to_snake(name: str) -> str:
    return _CAMEL_BOUNDARY.sub("_", name).lower()


def register_actor_by_convention(
    actor: str,
    methods: list[str],
    *,
    module_template: str = "kotodama.{actor}_worker_main",
    fn_template: str = "task_{snake}",
) -> dict[str, McpHandler]:
    """Resolve `com.etzhayyim.apps.{actor}.{method}` → `kotodama.{actor}_worker_main:task_{method_snake}`.

    Methods that fail to import are skipped with a WARN log so a partial
    actor (some methods missing) does not break the dispatcher boot.
    Returns the mapping dict; merge into the default registry to install.
    """
    module_name = module_template.format(actor=actor)
    out: dict[str, McpHandler] = {}
    try:
        mod = importlib.import_module(module_name)
    except Exception as exc:
        LOG.warning("mcp_dispatch: actor %s module %s import failed: %s", actor, module_name, exc)
        return out
    for method in methods:
        nsid = f"com.etzhayyim.apps.{actor}.{method}"
        fn_name = fn_template.format(snake=_camel_to_snake(method))
        fn = getattr(mod, fn_name, None)
        if fn is None or not callable(fn):
            LOG.warning("mcp_dispatch: %s missing %s.%s — skipping", nsid, module_name, fn_name)
            continue
        out[nsid] = fn
    return out


def register_overrides(overrides: dict[str, McpHandler]) -> dict[str, McpHandler]:
    """Pass-through helper for explicit (non-convention) bindings.

    Use for tools where the NSID method name does not map cleanly to a
    `task_<snake>` function, or where the implementation lives in a
    different module than `<actor>_worker_main`.
    """
    return dict(overrides)


def register_actor_by_mapping(
    actor: str,
    mapping: dict[str, str],
) -> dict[str, McpHandler]:
    """Resolve an explicit method → "module:fn" mapping for a single actor.

    Used when the actor's tools are spread across multiple primitive modules
    or use heterogeneous naming that no single fn_template captures (e.g.
    wellbecoming, where some tools are task_wellbecoming_* and others are
    task_belief_* across different modules).

    Mapping shape:
        {"<methodCamel>": "<dotted.module>:<fn_name>"}

    Methods that fail to import are skipped with a WARN log.
    """
    out: dict[str, McpHandler] = {}
    for method, target in mapping.items():
        nsid = f"com.etzhayyim.apps.{actor}.{method}"
        if ":" not in target:
            LOG.warning("mcp_dispatch: %s mapping target %r missing ':<fn>'", nsid, target)
            continue
        module_name, fn_name = target.split(":", 1)
        try:
            mod = importlib.import_module(module_name)
        except Exception as exc:
            LOG.warning("mcp_dispatch: %s module %s import failed: %s", nsid, module_name, exc)
            continue
        fn = getattr(mod, fn_name, None)
        if fn is None or not callable(fn):
            LOG.warning("mcp_dispatch: %s missing %s.%s", nsid, module_name, fn_name)
            continue
        out[nsid] = fn
    return out


# Default actor → method roster. Each entry is a dict that lets the
# convention be overridden per actor for cases where the task_* implementation
# lives outside ``<actor>_worker_main`` or has a non-standard name.
#
#   {"actor": <str>,            # NSID segment com.etzhayyim.apps.<actor>.*
#    "methods": [<camel>, ...],  # NSID method names
#    "module": <dotted>,         # optional, defaults to "kotodama.{actor}_worker_main"
#    "fn_template": <str>,       # optional, defaults to "task_{snake}"
#   }
#
# Adding an actor is data-only work after the lexicons + mcp_tool_def rows
# are seeded — this list is the only Python change. Migrating the bulk-51
# `mcp_tool` candidates surfaced by `audit-langgraph-bulk51-classify.mjs`
# typically requires only a new entry here (with overrides if the task
# lives in `kotodama.primitives.<actor>` etc.).
_DEFAULT_ACTORS: list[dict[str, Any]] = [
    # saikin / ki / koke moved to _LG_ORGANISM_ACTORS (Phase H) — proxied to lg-organism pod.
    # Bulk-51 audit (Phase A, mcp_tool candidate): adsk_ingest_dataset.ingest_all
    # → task_adsk_dataset_ingest_all in kotodama.primitives.adsk.
    # Demonstrates module + fn_template override.
    {
        "actor": "adsk",
        "methods": ["datasetIngestAll"],
        "module": "kotodama.primitives.adsk",
        "fn_template": "task_adsk_{snake}",
    },
    # malak (cybercrime intel) MCP surface — tasks live in
    # kotodama.primitives.malak:task_malak_<snake>.
    # `draftPoliceReport` drives the JP police-format LangGraph pipeline
    # (assemble→6 doc drafts→PEGEL→persist) per ADR-2605091400 (MCP =
    # sole external API; raw victim PII never leaves the worker —
    # response is metadata + sha + tick IDs only).
    {
        "actor": "malak",
        "methods": [
            "buildAgencyReferralEvidenceBundle",
            "draftAgencyBriefing",
            "draftPoliceReport",
            "exportAgencyReferralPackage",
            "exportStixBundle",
            "ingestTrapMessage",
            "listAgencyReferralDrafts",
            "listAgencyReferralExports",
            "listWallets",
            "registerPhishingTrapInbox",
            "reviewAgencyReferralDraft",
            # Phase 0 surveillance + outreach stubs (CXO-LEDGER #32, 2026-05-13)
            # — formerly mehikari, collapsed into malak namespace
            "registerCamera",
            "ingestSurveillanceClip",
            "queryScene",
            "queryPerson",
            "reviewSurveillanceMatches",
            "exportSurveillanceEvidence",
            "listSurveillanceQueries",
            "getSurveillanceAuditTrail",
            "registerAgencyProspect",
            "draftAgencyOutreach",
            "reviewAgencyOutreach",
            "sendAgencyOutreach",
            "handleAgencyOutreachReply",
            "unsubscribeAgencyOutreach",
            "listAgencyOutreach",
        ],
        "module": "kotodama.primitives.malak",
        "fn_template": "task_malak_{snake}",
    },
    # Bulk-51 canonical actor consolidation: 7 aria_* assistants from the
    # bulk-51 file collapse into a single `aria` actor that owns
    # `kotodama.primitives.aria_signal:task_aria_*`. Method names are the
    # camelCase of the task name suffix (e.g. task_aria_market_delta_ingest
    # → marketDeltaIngest). Note: `marketDeltaIngest` is the canonical name —
    # the bulk-51 audit's "marketIngest" was a naming inference miss.
    {
        "actor": "aria",
        "methods": [
            "attentionIngest",
            "emotionIngest",
            "influenceIngest",
            "marketDeltaIngest",
            "minimaxSweep",
            "moneyFlowIngest",
            "requestIngest",
            "reverseTopoReplan",
        ],
        "module": "kotodama.primitives.aria_signal",
        "fn_template": "task_aria_{snake}",
    },
    # Bulk-51 canonical actor consolidation: 7 shosha_* assistants collapse
    # into one `shosha` actor whose 18 methods are derived from the actual
    # task_shosha_* surface in kotodama.primitives.shosha (not the
    # bulk-51 audit's inferred names — those had heavy reordering).
    # Reading task function names as SSoT gives a clean
    # task_shosha_{snake} template with zero manual overrides.
    # Bulk-51 canonical: 6 isbn_ingest_* assistants → one `isbn` actor.
    # Method names use the source-first form (aozoraIngest, gutenbergIngest)
    # which matches the actual task surface (task_isbn_<source>_ingest).
    {
        "actor": "isbn",
        "methods": [
            "aozoraIngest",
            "gutenbergIngest",
            "ndlIngest",
            "hathitrustIngest",
            "internetArchiveIngest",
            "openLibraryIngest",
        ],
        "module": "kotodama.primitives.isbn",
        "fn_template": "task_isbn_{snake}",
    },
    # Bulk-51 canonical: 9 wellbecoming_* assistants → one `wellbecoming` actor.
    # Tools are heterogeneous across 4 sub-modules with 3 prefix conventions
    # (task_wellbecoming_* / task_belief_* / task_trust_*), so explicit
    # `mapping` is required — no single fn_template covers them all.
    {
        "actor": "wellbecoming",
        "mapping": {
            "agentLoop": "kotodama.primitives.wellbecoming_agent:task_wellbecoming_agent_loop",
            "bottleneckDetect": "kotodama.primitives.wellbecoming_agent:task_wellbecoming_bottleneck_detect",
            "proactiveConnect": "kotodama.primitives.wellbecoming_agent:task_wellbecoming_proactive_connect",
            "floorCheck": "kotodama.primitives.wellbecoming_agent:task_wellbecoming_floor_check",
            "floorAlert": "kotodama.primitives.wellbecoming_agent:task_wellbecoming_floor_alert",
            "minimaxSweep": "kotodama.primitives.wellbecoming_agent:task_wellbecoming_minimax_sweep",
            "beliefInfluencePropagate": "kotodama.primitives.wellbecoming_influence:task_belief_influence_propagate",
            "beliefNoiseInject": "kotodama.primitives.wellbecoming_noise:task_belief_noise_inject",
            "beliefRestoringCapture": "kotodama.primitives.wellbecoming_restoring:task_belief_restoring_capture",
            "trustWeightUpdate": "kotodama.primitives.wellbecoming_trust:task_trust_weight_update",
            # Recovered from NO_TASK_IMPORT spot-check (iter25): the analyze
            # function lives in primitives.wellbecoming_process_mining without
            # a `task_` prefix — explicit mapping is the right tool for it.
            "processMiningAnalyze": "kotodama.primitives.wellbecoming_process_mining:analyze",
        },
    },
    # Bulk-51 standalone (recovered from NO_TASK_IMPORT spot-check, iter25):
    # yoro_platform_pulse used multi-line `from primitives.yoro_social import (...)`
    # which the generator's regex missed. The primitive exposes 8 task_yoro_*
    # functions covering social posts and actor-quality flows.
    # Bulk-51 standalone (recovered from "primitive 未存在" claim, iter39):
    # task_shinka_* now lives in primitives.shinka so the LangServer/MCP path
    # does not import the deprecated LangServer entrypoint.
    # 5 task functions: tick / load_and_resolve / compose / write_heartbeat / emit_evolution.
    {
        "actor": "shinka",
        "methods": [
            "tick",
            "loadAndResolve",
            "compose",
            "writeHeartbeat",
            "emitEvolution",
        ],
        "module": "kotodama.primitives.shinka",
        "fn_template": "task_shinka_{snake}",
    },
    {
        "actor": "yoro",
        "methods": [
            "socialPostGraphFallback",
            "socialPlatformPulseGraphFallback",
            "socialRespondToMentionGraphFallback",
            "socialRespondToFollowGraphFallback",
            "actorQualityInspect",
            "actorQualityVerify",
            "actorQualityEnrichProfile",
            "actorQualityEnsureSeedPost",
        ],
        "module": "kotodama.primitives.yoro_social",
        "fn_template": "task_yoro_{snake}",
    },
    # Bulk-51 standalone: agent_runtime_lease_autopilot →
    #   kotodama.primitives.agent_economy:task_agent_*  (9 methods, 2 sub-prefixes)
    {
        "actor": "agentEconomy",
        "methods": [
            "runtimeQuote",
            "runtimeReserve",
            "runtimeRenew",
            "runtimeHibernate",
            "runtimeAutopilotTick",
            "incomeRecord",
            "usageRecord",
            "slashRecord",
            "spawnChildOrg",
        ],
        "module": "kotodama.primitives.agent_economy",
        "fn_template": "task_agent_{snake}",
    },
    # Bulk-51 standalone: coverage_gap_bridge → 5 methods
    {
        "actor": "coverageGap",
        "methods": ["scan", "ingest", "infer", "generate", "statsSync"],
        "module": "kotodama.primitives.coverage_gap",
        "fn_template": "task_coverage_gap_{snake}",
    },
    # Bulk-51 standalone: onion_crawl_seeds → 2 methods (no actor prefix in tasks)
    {
        "actor": "onion",
        "methods": ["queueSeeds", "processQueue"],
        "module": "kotodama.primitives.onion_crawl",
        "fn_template": "task_{snake}",
    },
    # Bulk-51 standalone: os_messaging_crawl_open_channels → 2 methods
    {
        "actor": "osMessaging",
        "methods": ["queueSeedRuns", "processQueue"],
        "module": "kotodama.primitives.os_messaging_open_channels",
        "fn_template": "task_{snake}",
    },
    # Bulk-51 standalone: patent_ingest_uspto_weekly → 3 methods
    {
        "actor": "patent",
        "methods": [
            "usptoPatentsviewIngestPatent",
            "usptoPatentsviewIngestCitation",
            "epoOpsFillCitations",
        ],
        "module": "kotodama.primitives.patent_ingest",
        "fn_template": "task_patent_{snake}",
    },
    # Bulk-51 standalone: public_malak_crawl_ads → 5 methods (no actor prefix)
    {
        "actor": "publicMalakAds",
        "methods": [
            "queueSeedRuns",
            "processQueue",
            "analyzeCreative",
            "analyzeRecent",
            "clusterRecent",
        ],
        "module": "kotodama.primitives.public_malak_ads",
        "fn_template": "task_{snake}",
    },
    # Bulk-51 standalone: shinshi_seed_gap_fill → 3 methods
    {
        "actor": "shinshi",
        "methods": [
            "sceneRender",
            "sceneBulkSeed",
            "coverageFindIncomplete",
        ],
        "module": "kotodama.primitives.shinshi_image",
        "fn_template": "task_shinshi_{snake}",
    },
    {
        "actor": "shosha",
        "methods": [
            "intelIngestPrices",
            "intelIngestFreight",
            "marketViewSynth",
            "sanctionsRefreshOfac",
            "sanctionsRefreshUn",
            "complySanctionsCheck",
            "tradeSubmit",
            "exposureRecompute",
            "pnlDailyRecompute",
            "tradeSynth",
            "tradeSettle",
            "tradeApprove",
            "tradeReject",
            "hedgePropose",
            "dailyReportCompose",
            "agentChat",
            "reactiveScanUpstream",
            "coverageSnapshot",
        ],
        "module": "kotodama.primitives.shosha",
        "fn_template": "task_shosha_{snake}",
    },
    {
        "actor": "openIsic",
        "methods": [
            "classifyEntity",
            "recordConcordance",
            "flagDualUseIndustry",
            "classifyArmsManufacturing",
            "getTaxonomy",
        ],
        "module": "kotodama.primitives.open_isic",
        "fn_template": "task_open_isic_{snake}",
    },
    {
        "actor": "openIsic0111",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0111",
        "fn_template": "task_open_isic_0111_{snake}",
    },
    {
        "actor": "openIsic0112",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0112",
        "fn_template": "task_open_isic_0112_{snake}",
    },
    {
        "actor": "openIsic0113",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0113",
        "fn_template": "task_open_isic_0113_{snake}",
    },
    {
        "actor": "openIsic0114",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0114",
        "fn_template": "task_open_isic_0114_{snake}",
    },
    {
        "actor": "openIsic0115",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0115",
        "fn_template": "task_open_isic_0115_{snake}",
    },
    {
        "actor": "openIsic0116",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0116",
        "fn_template": "task_open_isic_0116_{snake}",
    },
    {
        "actor": "openIsic0119",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0119",
        "fn_template": "task_open_isic_0119_{snake}",
    },
    {
        "actor": "openIsic0121",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0121",
        "fn_template": "task_open_isic_0121_{snake}",
    },
    {
        "actor": "openIsic0122",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0122",
        "fn_template": "task_open_isic_0122_{snake}",
    },
    {
        "actor": "openIsic0123",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0123",
        "fn_template": "task_open_isic_0123_{snake}",
    },
    {
        "actor": "openIsic0124",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0124",
        "fn_template": "task_open_isic_0124_{snake}",
    },
    {
        "actor": "openIsic0125",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0125",
        "fn_template": "task_open_isic_0125_{snake}",
    },
    {
        "actor": "openIsic0126",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0126",
        "fn_template": "task_open_isic_0126_{snake}",
    },
    {
        "actor": "openIsic0127",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0127",
        "fn_template": "task_open_isic_0127_{snake}",
    },
    {
        "actor": "openIsic0128",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0128",
        "fn_template": "task_open_isic_0128_{snake}",
    },
    {
        "actor": "openIsic0129",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0129",
        "fn_template": "task_open_isic_0129_{snake}",
    },
    {
        "actor": "openIsic0130",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0130",
        "fn_template": "task_open_isic_0130_{snake}",
    },
    {
        "actor": "openIsic0141",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0141",
        "fn_template": "task_open_isic_0141_{snake}",
    },
    {
        "actor": "openIsic0142",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0142",
        "fn_template": "task_open_isic_0142_{snake}",
    },
    {
        "actor": "openIsic0143",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0143",
        "fn_template": "task_open_isic_0143_{snake}",
    },
    {
        "actor": "openIsic0144",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0144",
        "fn_template": "task_open_isic_0144_{snake}",
    },
    {
        "actor": "openIsic0145",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0145",
        "fn_template": "task_open_isic_0145_{snake}",
    },
    {
        "actor": "openIsic0146",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0146",
        "fn_template": "task_open_isic_0146_{snake}",
    },
    {
        "actor": "openIsic0149",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0149",
        "fn_template": "task_open_isic_0149_{snake}",
    },
    {
        "actor": "openIsic0150",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0150",
        "fn_template": "task_open_isic_0150_{snake}",
    },
    {
        "actor": "openIsic0161",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0161",
        "fn_template": "task_open_isic_0161_{snake}",
    },
    {
        "actor": "openIsic0162",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0162",
        "fn_template": "task_open_isic_0162_{snake}",
    },
    {
        "actor": "openIsic0163",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0163",
        "fn_template": "task_open_isic_0163_{snake}",
    },
    {
        "actor": "openIsic0164",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0164",
        "fn_template": "task_open_isic_0164_{snake}",
    },
    {
        "actor": "openIsic0170",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0170",
        "fn_template": "task_open_isic_0170_{snake}",
    },
    {
        "actor": "openIsic0210",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0210",
        "fn_template": "task_open_isic_0210_{snake}",
    },
    {
        "actor": "openIsic0220",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0220",
        "fn_template": "task_open_isic_0220_{snake}",
    },
    {
        "actor": "openIsic0230",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0230",
        "fn_template": "task_open_isic_0230_{snake}",
    },
    {
        "actor": "openIsic0240",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0240",
        "fn_template": "task_open_isic_0240_{snake}",
    },
    {
        "actor": "openIsic0311",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0311",
        "fn_template": "task_open_isic_0311_{snake}",
    },
    {
        "actor": "openIsic0312",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0312",
        "fn_template": "task_open_isic_0312_{snake}",
    },
    {
        "actor": "openIsic0321",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0321",
        "fn_template": "task_open_isic_0321_{snake}",
    },
    {
        "actor": "openIsic0322",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0322",
        "fn_template": "task_open_isic_0322_{snake}",
    },
    {
        "actor": "openIsic0510",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0510",
        "fn_template": "task_open_isic_0510_{snake}",
    },
    {
        "actor": "openIsic0520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0520",
        "fn_template": "task_open_isic_0520_{snake}",
    },
    {
        "actor": "openIsic0610",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0610",
        "fn_template": "task_open_isic_0610_{snake}",
    },
    {
        "actor": "openIsic0620",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0620",
        "fn_template": "task_open_isic_0620_{snake}",
    },
    {
        "actor": "openIsic0710",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0710",
        "fn_template": "task_open_isic_0710_{snake}",
    },
    {
        "actor": "openIsic0721",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0721",
        "fn_template": "task_open_isic_0721_{snake}",
    },
    {
        "actor": "openIsic0729",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0729",
        "fn_template": "task_open_isic_0729_{snake}",
    },
    {
        "actor": "openIsic0810",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0810",
        "fn_template": "task_open_isic_0810_{snake}",
    },
    {
        "actor": "openIsic0891",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0891",
        "fn_template": "task_open_isic_0891_{snake}",
    },
    {
        "actor": "openIsic0892",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0892",
        "fn_template": "task_open_isic_0892_{snake}",
    },
    {
        "actor": "openIsic0893",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0893",
        "fn_template": "task_open_isic_0893_{snake}",
    },
    {
        "actor": "openIsic0899",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0899",
        "fn_template": "task_open_isic_0899_{snake}",
    },
    {
        "actor": "openIsic0910",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0910",
        "fn_template": "task_open_isic_0910_{snake}",
    },
    {
        "actor": "openIsic0990",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_0990",
        "fn_template": "task_open_isic_0990_{snake}",
    },
    {
        "actor": "openIsic1010",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1010",
        "fn_template": "task_open_isic_1010_{snake}",
    },
    {
        "actor": "openIsic1020",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1020",
        "fn_template": "task_open_isic_1020_{snake}",
    },
    {
        "actor": "openIsic1030",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1030",
        "fn_template": "task_open_isic_1030_{snake}",
    },
    {
        "actor": "openIsic1040",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1040",
        "fn_template": "task_open_isic_1040_{snake}",
    },
    {
        "actor": "openIsic1050",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1050",
        "fn_template": "task_open_isic_1050_{snake}",
    },
    {
        "actor": "openIsic1061",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1061",
        "fn_template": "task_open_isic_1061_{snake}",
    },
    {
        "actor": "openIsic1062",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1062",
        "fn_template": "task_open_isic_1062_{snake}",
    },
    {
        "actor": "openIsic1071",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1071",
        "fn_template": "task_open_isic_1071_{snake}",
    },
    {
        "actor": "openIsic1072",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1072",
        "fn_template": "task_open_isic_1072_{snake}",
    },
    {
        "actor": "openIsic1073",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1073",
        "fn_template": "task_open_isic_1073_{snake}",
    },
    {
        "actor": "openIsic1074",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1074",
        "fn_template": "task_open_isic_1074_{snake}",
    },
    {
        "actor": "openIsic1075",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1075",
        "fn_template": "task_open_isic_1075_{snake}",
    },
    {
        "actor": "openIsic1079",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1079",
        "fn_template": "task_open_isic_1079_{snake}",
    },
    {
        "actor": "openIsic1080",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1080",
        "fn_template": "task_open_isic_1080_{snake}",
    },
    {
        "actor": "openIsic1101",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1101",
        "fn_template": "task_open_isic_1101_{snake}",
    },
    {
        "actor": "openIsic1102",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1102",
        "fn_template": "task_open_isic_1102_{snake}",
    },
    {
        "actor": "openIsic1103",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1103",
        "fn_template": "task_open_isic_1103_{snake}",
    },
    {
        "actor": "openIsic1104",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1104",
        "fn_template": "task_open_isic_1104_{snake}",
    },
    {
        "actor": "openIsic1200",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1200",
        "fn_template": "task_open_isic_1200_{snake}",
    },
    {
        "actor": "openIsic1311",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1311",
        "fn_template": "task_open_isic_1311_{snake}",
    },
    {
        "actor": "openIsic1312",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1312",
        "fn_template": "task_open_isic_1312_{snake}",
    },
    {
        "actor": "openIsic1313",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1313",
        "fn_template": "task_open_isic_1313_{snake}",
    },
    {
        "actor": "openIsic1391",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1391",
        "fn_template": "task_open_isic_1391_{snake}",
    },
    {
        "actor": "openIsic1392",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1392",
        "fn_template": "task_open_isic_1392_{snake}",
    },
    {
        "actor": "openIsic1393",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1393",
        "fn_template": "task_open_isic_1393_{snake}",
    },
    {
        "actor": "openIsic1394",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1394",
        "fn_template": "task_open_isic_1394_{snake}",
    },
    {
        "actor": "openIsic1395",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1395",
        "fn_template": "task_open_isic_1395_{snake}",
    },
    {
        "actor": "openIsic1396",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1396",
        "fn_template": "task_open_isic_1396_{snake}",
    },
    {
        "actor": "openIsic1399",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1399",
        "fn_template": "task_open_isic_1399_{snake}",
    },
    {
        "actor": "openIsic1410",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1410",
        "fn_template": "task_open_isic_1410_{snake}",
    },
    {
        "actor": "openIsic1420",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1420",
        "fn_template": "task_open_isic_1420_{snake}",
    },
    {
        "actor": "openIsic1430",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1430",
        "fn_template": "task_open_isic_1430_{snake}",
    },
    {
        "actor": "openIsic1511",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1511",
        "fn_template": "task_open_isic_1511_{snake}",
    },
    {
        "actor": "openIsic1512",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1512",
        "fn_template": "task_open_isic_1512_{snake}",
    },
    {
        "actor": "openIsic1520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1520",
        "fn_template": "task_open_isic_1520_{snake}",
    },
    {
        "actor": "openIsic1610",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1610",
        "fn_template": "task_open_isic_1610_{snake}",
    },
    {
        "actor": "openIsic1621",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1621",
        "fn_template": "task_open_isic_1621_{snake}",
    },
    {
        "actor": "openIsic1622",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1622",
        "fn_template": "task_open_isic_1622_{snake}",
    },
    {
        "actor": "openIsic1623",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1623",
        "fn_template": "task_open_isic_1623_{snake}",
    },
    {
        "actor": "openIsic1629",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1629",
        "fn_template": "task_open_isic_1629_{snake}",
    },
    {
        "actor": "openIsic1701",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1701",
        "fn_template": "task_open_isic_1701_{snake}",
    },
    {
        "actor": "openIsic1702",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1702",
        "fn_template": "task_open_isic_1702_{snake}",
    },
    {
        "actor": "openIsic1709",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1709",
        "fn_template": "task_open_isic_1709_{snake}",
    },
    {
        "actor": "openIsic1811",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1811",
        "fn_template": "task_open_isic_1811_{snake}",
    },
    {
        "actor": "openIsic1812",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1812",
        "fn_template": "task_open_isic_1812_{snake}",
    },
    {
        "actor": "openIsic1820",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1820",
        "fn_template": "task_open_isic_1820_{snake}",
    },
    {
        "actor": "openIsic1910",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1910",
        "fn_template": "task_open_isic_1910_{snake}",
    },
    {
        "actor": "openIsic1920",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_1920",
        "fn_template": "task_open_isic_1920_{snake}",
    },
    {
        "actor": "openIsic2011",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2011",
        "fn_template": "task_open_isic_2011_{snake}",
    },
    {
        "actor": "openIsic2012",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2012",
        "fn_template": "task_open_isic_2012_{snake}",
    },
    {
        "actor": "openIsic2013",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2013",
        "fn_template": "task_open_isic_2013_{snake}",
    },
    {
        "actor": "openIsic2021",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2021",
        "fn_template": "task_open_isic_2021_{snake}",
    },
    {
        "actor": "openIsic2022",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2022",
        "fn_template": "task_open_isic_2022_{snake}",
    },
    {
        "actor": "openIsic2023",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2023",
        "fn_template": "task_open_isic_2023_{snake}",
    },
    {
        "actor": "openIsic2029",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2029",
        "fn_template": "task_open_isic_2029_{snake}",
    },
    {
        "actor": "openIsic2030",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2030",
        "fn_template": "task_open_isic_2030_{snake}",
    },
    {
        "actor": "openIsic2100",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2100",
        "fn_template": "task_open_isic_2100_{snake}",
    },
    {
        "actor": "openIsic2211",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2211",
        "fn_template": "task_open_isic_2211_{snake}",
    },
    {
        "actor": "openIsic2219",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2219",
        "fn_template": "task_open_isic_2219_{snake}",
    },
    {
        "actor": "openIsic2220",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2220",
        "fn_template": "task_open_isic_2220_{snake}",
    },
    {
        "actor": "openIsic2310",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2310",
        "fn_template": "task_open_isic_2310_{snake}",
    },
    {
        "actor": "openIsic2391",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2391",
        "fn_template": "task_open_isic_2391_{snake}",
    },
    {
        "actor": "openIsic2392",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2392",
        "fn_template": "task_open_isic_2392_{snake}",
    },
    {
        "actor": "openIsic2393",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2393",
        "fn_template": "task_open_isic_2393_{snake}",
    },
    {
        "actor": "openIsic2394",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2394",
        "fn_template": "task_open_isic_2394_{snake}",
    },
    {
        "actor": "openIsic2395",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2395",
        "fn_template": "task_open_isic_2395_{snake}",
    },
    {
        "actor": "openIsic2396",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2396",
        "fn_template": "task_open_isic_2396_{snake}",
    },
    {
        "actor": "openIsic2399",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2399",
        "fn_template": "task_open_isic_2399_{snake}",
    },
    {
        "actor": "openIsic2410",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2410",
        "fn_template": "task_open_isic_2410_{snake}",
    },
    {
        "actor": "openIsic2420",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2420",
        "fn_template": "task_open_isic_2420_{snake}",
    },
    {
        "actor": "openIsic2431",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2431",
        "fn_template": "task_open_isic_2431_{snake}",
    },
    {
        "actor": "openIsic2432",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2432",
        "fn_template": "task_open_isic_2432_{snake}",
    },
    {
        "actor": "openIsic2511",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2511",
        "fn_template": "task_open_isic_2511_{snake}",
    },
    {
        "actor": "openIsic2512",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2512",
        "fn_template": "task_open_isic_2512_{snake}",
    },
    {
        "actor": "openIsic2513",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2513",
        "fn_template": "task_open_isic_2513_{snake}",
    },
    {
        "actor": "openIsic2520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2520",
        "fn_template": "task_open_isic_2520_{snake}",
    },
    {
        "actor": "openIsic2591",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2591",
        "fn_template": "task_open_isic_2591_{snake}",
    },
    {
        "actor": "openIsic2592",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2592",
        "fn_template": "task_open_isic_2592_{snake}",
    },
    {
        "actor": "openIsic2593",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2593",
        "fn_template": "task_open_isic_2593_{snake}",
    },
    {
        "actor": "openIsic2599",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2599",
        "fn_template": "task_open_isic_2599_{snake}",
    },
    {
        "actor": "openIsic2610",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2610",
        "fn_template": "task_open_isic_2610_{snake}",
    },
    {
        "actor": "openIsic2620",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2620",
        "fn_template": "task_open_isic_2620_{snake}",
    },
    {
        "actor": "openIsic2630",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2630",
        "fn_template": "task_open_isic_2630_{snake}",
    },
    {
        "actor": "openIsic2640",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2640",
        "fn_template": "task_open_isic_2640_{snake}",
    },
    {
        "actor": "openIsic2651",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2651",
        "fn_template": "task_open_isic_2651_{snake}",
    },
    {
        "actor": "openIsic2652",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2652",
        "fn_template": "task_open_isic_2652_{snake}",
    },
    {
        "actor": "openIsic2660",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2660",
        "fn_template": "task_open_isic_2660_{snake}",
    },
    {
        "actor": "openIsic2670",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2670",
        "fn_template": "task_open_isic_2670_{snake}",
    },
    {
        "actor": "openIsic2680",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2680",
        "fn_template": "task_open_isic_2680_{snake}",
    },
    {
        "actor": "openIsic2710",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2710",
        "fn_template": "task_open_isic_2710_{snake}",
    },
    {
        "actor": "openIsic2720",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2720",
        "fn_template": "task_open_isic_2720_{snake}",
    },
    {
        "actor": "openIsic2731",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2731",
        "fn_template": "task_open_isic_2731_{snake}",
    },
    {
        "actor": "openIsic2732",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2732",
        "fn_template": "task_open_isic_2732_{snake}",
    },
    {
        "actor": "openIsic2740",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2740",
        "fn_template": "task_open_isic_2740_{snake}",
    },
    {
        "actor": "openIsic2750",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2750",
        "fn_template": "task_open_isic_2750_{snake}",
    },
    {
        "actor": "openIsic2790",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2790",
        "fn_template": "task_open_isic_2790_{snake}",
    },
    {
        "actor": "openIsic2811",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2811",
        "fn_template": "task_open_isic_2811_{snake}",
    },
    {
        "actor": "openIsic2812",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2812",
        "fn_template": "task_open_isic_2812_{snake}",
    },
    {
        "actor": "openIsic2813",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2813",
        "fn_template": "task_open_isic_2813_{snake}",
    },
    {
        "actor": "openIsic2814",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2814",
        "fn_template": "task_open_isic_2814_{snake}",
    },
    {
        "actor": "openIsic2815",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2815",
        "fn_template": "task_open_isic_2815_{snake}",
    },
    {
        "actor": "openIsic2816",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2816",
        "fn_template": "task_open_isic_2816_{snake}",
    },
    {
        "actor": "openIsic2817",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2817",
        "fn_template": "task_open_isic_2817_{snake}",
    },
    {
        "actor": "openIsic2818",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2818",
        "fn_template": "task_open_isic_2818_{snake}",
    },
    {
        "actor": "openIsic2819",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2819",
        "fn_template": "task_open_isic_2819_{snake}",
    },
    {
        "actor": "openIsic2821",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2821",
        "fn_template": "task_open_isic_2821_{snake}",
    },
    {
        "actor": "openIsic2822",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2822",
        "fn_template": "task_open_isic_2822_{snake}",
    },
    {
        "actor": "openIsic2823",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2823",
        "fn_template": "task_open_isic_2823_{snake}",
    },
    {
        "actor": "openIsic2824",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2824",
        "fn_template": "task_open_isic_2824_{snake}",
    },
    {
        "actor": "openIsic2825",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2825",
        "fn_template": "task_open_isic_2825_{snake}",
    },
    {
        "actor": "openIsic2826",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2826",
        "fn_template": "task_open_isic_2826_{snake}",
    },
    {
        "actor": "openIsic2829",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2829",
        "fn_template": "task_open_isic_2829_{snake}",
    },
    {
        "actor": "openIsic2910",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2910",
        "fn_template": "task_open_isic_2910_{snake}",
    },
    {
        "actor": "openIsic2920",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2920",
        "fn_template": "task_open_isic_2920_{snake}",
    },
    {
        "actor": "openIsic2930",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_2930",
        "fn_template": "task_open_isic_2930_{snake}",
    },
    {
        "actor": "openIsic3011",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3011",
        "fn_template": "task_open_isic_3011_{snake}",
    },
    {
        "actor": "openIsic3012",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3012",
        "fn_template": "task_open_isic_3012_{snake}",
    },
    {
        "actor": "openIsic3020",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3020",
        "fn_template": "task_open_isic_3020_{snake}",
    },
    {
        "actor": "openIsic3030",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3030",
        "fn_template": "task_open_isic_3030_{snake}",
    },
    {
        "actor": "openIsic3040",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3040",
        "fn_template": "task_open_isic_3040_{snake}",
    },
    {
        "actor": "openIsic3091",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3091",
        "fn_template": "task_open_isic_3091_{snake}",
    },
    {
        "actor": "openIsic3092",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3092",
        "fn_template": "task_open_isic_3092_{snake}",
    },
    {
        "actor": "openIsic3099",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3099",
        "fn_template": "task_open_isic_3099_{snake}",
    },
    {
        "actor": "openIsic3100",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3100",
        "fn_template": "task_open_isic_3100_{snake}",
    },
    {
        "actor": "openIsic3211",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3211",
        "fn_template": "task_open_isic_3211_{snake}",
    },
    {
        "actor": "openIsic3212",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3212",
        "fn_template": "task_open_isic_3212_{snake}",
    },
    {
        "actor": "openIsic3220",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3220",
        "fn_template": "task_open_isic_3220_{snake}",
    },
    {
        "actor": "openIsic3230",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3230",
        "fn_template": "task_open_isic_3230_{snake}",
    },
    {
        "actor": "openIsic3240",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3240",
        "fn_template": "task_open_isic_3240_{snake}",
    },
    {
        "actor": "openIsic3250",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3250",
        "fn_template": "task_open_isic_3250_{snake}",
    },
    {
        "actor": "openIsic3291",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3291",
        "fn_template": "task_open_isic_3291_{snake}",
    },
    {
        "actor": "openIsic3292",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3292",
        "fn_template": "task_open_isic_3292_{snake}",
    },
    {
        "actor": "openIsic3299",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3299",
        "fn_template": "task_open_isic_3299_{snake}",
    },
    {
        "actor": "openIsic3311",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3311",
        "fn_template": "task_open_isic_3311_{snake}",
    },
    {
        "actor": "openIsic3312",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3312",
        "fn_template": "task_open_isic_3312_{snake}",
    },
    {
        "actor": "openIsic3313",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3313",
        "fn_template": "task_open_isic_3313_{snake}",
    },
    {
        "actor": "openIsic3314",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3314",
        "fn_template": "task_open_isic_3314_{snake}",
    },
    {
        "actor": "openIsic3315",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3315",
        "fn_template": "task_open_isic_3315_{snake}",
    },
    {
        "actor": "openIsic3319",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3319",
        "fn_template": "task_open_isic_3319_{snake}",
    },
    {
        "actor": "openIsic3320",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3320",
        "fn_template": "task_open_isic_3320_{snake}",
    },
    {
        "actor": "openIsic3510",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3510",
        "fn_template": "task_open_isic_3510_{snake}",
    },
    {
        "actor": "openIsic3520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3520",
        "fn_template": "task_open_isic_3520_{snake}",
    },
    {
        "actor": "openIsic3530",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3530",
        "fn_template": "task_open_isic_3530_{snake}",
    },
    {
        "actor": "openIsic3600",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3600",
        "fn_template": "task_open_isic_3600_{snake}",
    },
    {
        "actor": "openIsic3700",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3700",
        "fn_template": "task_open_isic_3700_{snake}",
    },
    {
        "actor": "openIsic3811",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3811",
        "fn_template": "task_open_isic_3811_{snake}",
    },
    {
        "actor": "openIsic3812",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3812",
        "fn_template": "task_open_isic_3812_{snake}",
    },
    {
        "actor": "openIsic3821",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3821",
        "fn_template": "task_open_isic_3821_{snake}",
    },
    {
        "actor": "openIsic3822",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3822",
        "fn_template": "task_open_isic_3822_{snake}",
    },
    {
        "actor": "openIsic3830",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3830",
        "fn_template": "task_open_isic_3830_{snake}",
    },
    {
        "actor": "openIsic3900",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_3900",
        "fn_template": "task_open_isic_3900_{snake}",
    },
    {
        "actor": "openIsic4100",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4100",
        "fn_template": "task_open_isic_4100_{snake}",
    },
    {
        "actor": "openIsic4210",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4210",
        "fn_template": "task_open_isic_4210_{snake}",
    },
    {
        "actor": "openIsic4220",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4220",
        "fn_template": "task_open_isic_4220_{snake}",
    },
    {
        "actor": "openIsic4290",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4290",
        "fn_template": "task_open_isic_4290_{snake}",
    },
    {
        "actor": "openIsic4311",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4311",
        "fn_template": "task_open_isic_4311_{snake}",
    },
    {
        "actor": "openIsic4312",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4312",
        "fn_template": "task_open_isic_4312_{snake}",
    },
    {
        "actor": "openIsic4313",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4313",
        "fn_template": "task_open_isic_4313_{snake}",
    },
    {
        "actor": "openIsic4321",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4321",
        "fn_template": "task_open_isic_4321_{snake}",
    },
    {
        "actor": "openIsic4322",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4322",
        "fn_template": "task_open_isic_4322_{snake}",
    },
    {
        "actor": "openIsic4329",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4329",
        "fn_template": "task_open_isic_4329_{snake}",
    },
    {
        "actor": "openIsic4330",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4330",
        "fn_template": "task_open_isic_4330_{snake}",
    },
    {
        "actor": "openIsic4390",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4390",
        "fn_template": "task_open_isic_4390_{snake}",
    },
    {
        "actor": "openIsic4510",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4510",
        "fn_template": "task_open_isic_4510_{snake}",
    },
    {
        "actor": "openIsic4520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4520",
        "fn_template": "task_open_isic_4520_{snake}",
    },
    {
        "actor": "openIsic4530",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4530",
        "fn_template": "task_open_isic_4530_{snake}",
    },
    {
        "actor": "openIsic4540",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4540",
        "fn_template": "task_open_isic_4540_{snake}",
    },
    {
        "actor": "openIsic4610",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4610",
        "fn_template": "task_open_isic_4610_{snake}",
    },
    {
        "actor": "openIsic4620",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4620",
        "fn_template": "task_open_isic_4620_{snake}",
    },
    {
        "actor": "openIsic4630",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4630",
        "fn_template": "task_open_isic_4630_{snake}",
    },
    {
        "actor": "openIsic4641",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4641",
        "fn_template": "task_open_isic_4641_{snake}",
    },
    {
        "actor": "openIsic4649",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4649",
        "fn_template": "task_open_isic_4649_{snake}",
    },
    {
        "actor": "openIsic4651",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4651",
        "fn_template": "task_open_isic_4651_{snake}",
    },
    {
        "actor": "openIsic4652",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4652",
        "fn_template": "task_open_isic_4652_{snake}",
    },
    {
        "actor": "openIsic4653",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4653",
        "fn_template": "task_open_isic_4653_{snake}",
    },
    {
        "actor": "openIsic4659",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4659",
        "fn_template": "task_open_isic_4659_{snake}",
    },
    {
        "actor": "openIsic4661",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4661",
        "fn_template": "task_open_isic_4661_{snake}",
    },
    {
        "actor": "openIsic4662",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4662",
        "fn_template": "task_open_isic_4662_{snake}",
    },
    {
        "actor": "openIsic4663",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4663",
        "fn_template": "task_open_isic_4663_{snake}",
    },
    {
        "actor": "openIsic4664",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4664",
        "fn_template": "task_open_isic_4664_{snake}",
    },
    {
        "actor": "openIsic4665",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4665",
        "fn_template": "task_open_isic_4665_{snake}",
    },
    {
        "actor": "openIsic4669",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4669",
        "fn_template": "task_open_isic_4669_{snake}",
    },
    {
        "actor": "openIsic4690",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4690",
        "fn_template": "task_open_isic_4690_{snake}",
    },
    {
        "actor": "openIsic4711",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4711",
        "fn_template": "task_open_isic_4711_{snake}",
    },
    {
        "actor": "openIsic4719",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4719",
        "fn_template": "task_open_isic_4719_{snake}",
    },
    {
        "actor": "openIsic4721",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4721",
        "fn_template": "task_open_isic_4721_{snake}",
    },
    {
        "actor": "openIsic4722",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4722",
        "fn_template": "task_open_isic_4722_{snake}",
    },
    {
        "actor": "openIsic4723",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4723",
        "fn_template": "task_open_isic_4723_{snake}",
    },
    {
        "actor": "openIsic4730",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4730",
        "fn_template": "task_open_isic_4730_{snake}",
    },
    {
        "actor": "openIsic4741",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4741",
        "fn_template": "task_open_isic_4741_{snake}",
    },
    {
        "actor": "openIsic4742",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4742",
        "fn_template": "task_open_isic_4742_{snake}",
    },
    {
        "actor": "openIsic4751",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4751",
        "fn_template": "task_open_isic_4751_{snake}",
    },
    {
        "actor": "openIsic4752",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4752",
        "fn_template": "task_open_isic_4752_{snake}",
    },
    {
        "actor": "openIsic4753",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4753",
        "fn_template": "task_open_isic_4753_{snake}",
    },
    {
        "actor": "openIsic4759",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4759",
        "fn_template": "task_open_isic_4759_{snake}",
    },
    {
        "actor": "openIsic4761",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4761",
        "fn_template": "task_open_isic_4761_{snake}",
    },
    {
        "actor": "openIsic4762",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4762",
        "fn_template": "task_open_isic_4762_{snake}",
    },
    {
        "actor": "openIsic4763",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4763",
        "fn_template": "task_open_isic_4763_{snake}",
    },
    {
        "actor": "openIsic4764",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4764",
        "fn_template": "task_open_isic_4764_{snake}",
    },
    {
        "actor": "openIsic4771",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4771",
        "fn_template": "task_open_isic_4771_{snake}",
    },
    {
        "actor": "openIsic4772",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4772",
        "fn_template": "task_open_isic_4772_{snake}",
    },
    {
        "actor": "openIsic4773",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4773",
        "fn_template": "task_open_isic_4773_{snake}",
    },
    {
        "actor": "openIsic4774",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4774",
        "fn_template": "task_open_isic_4774_{snake}",
    },
    {
        "actor": "openIsic4775",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4775",
        "fn_template": "task_open_isic_4775_{snake}",
    },
    {
        "actor": "openIsic4776",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4776",
        "fn_template": "task_open_isic_4776_{snake}",
    },
    {
        "actor": "openIsic4777",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4777",
        "fn_template": "task_open_isic_4777_{snake}",
    },
    {
        "actor": "openIsic4778",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4778",
        "fn_template": "task_open_isic_4778_{snake}",
    },
    {
        "actor": "openIsic4779",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4779",
        "fn_template": "task_open_isic_4779_{snake}",
    },
    {
        "actor": "openIsic4781",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4781",
        "fn_template": "task_open_isic_4781_{snake}",
    },
    {
        "actor": "openIsic4782",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4782",
        "fn_template": "task_open_isic_4782_{snake}",
    },
    {
        "actor": "openIsic4789",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4789",
        "fn_template": "task_open_isic_4789_{snake}",
    },
    {
        "actor": "openIsic4791",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4791",
        "fn_template": "task_open_isic_4791_{snake}",
    },
    {
        "actor": "openIsic4799",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4799",
        "fn_template": "task_open_isic_4799_{snake}",
    },
    {
        "actor": "openIsic4911",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4911",
        "fn_template": "task_open_isic_4911_{snake}",
    },
    {
        "actor": "openIsic4912",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4912",
        "fn_template": "task_open_isic_4912_{snake}",
    },
    {
        "actor": "openIsic4921",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4921",
        "fn_template": "task_open_isic_4921_{snake}",
    },
    {
        "actor": "openIsic4922",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4922",
        "fn_template": "task_open_isic_4922_{snake}",
    },
    {
        "actor": "openIsic4923",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4923",
        "fn_template": "task_open_isic_4923_{snake}",
    },
    {
        "actor": "openIsic4930",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_4930",
        "fn_template": "task_open_isic_4930_{snake}",
    },
    {
        "actor": "openIsic5011",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5011",
        "fn_template": "task_open_isic_5011_{snake}",
    },
    {
        "actor": "openIsic5012",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5012",
        "fn_template": "task_open_isic_5012_{snake}",
    },
    {
        "actor": "openIsic5021",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5021",
        "fn_template": "task_open_isic_5021_{snake}",
    },
    {
        "actor": "openIsic5022",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5022",
        "fn_template": "task_open_isic_5022_{snake}",
    },
    {
        "actor": "openIsic5110",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5110",
        "fn_template": "task_open_isic_5110_{snake}",
    },
    {
        "actor": "openIsic5120",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5120",
        "fn_template": "task_open_isic_5120_{snake}",
    },
    {
        "actor": "openIsic5210",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5210",
        "fn_template": "task_open_isic_5210_{snake}",
    },
    {
        "actor": "openIsic5221",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5221",
        "fn_template": "task_open_isic_5221_{snake}",
    },
    {
        "actor": "openIsic5222",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5222",
        "fn_template": "task_open_isic_5222_{snake}",
    },
    {
        "actor": "openIsic5223",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5223",
        "fn_template": "task_open_isic_5223_{snake}",
    },
    {
        "actor": "openIsic5224",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5224",
        "fn_template": "task_open_isic_5224_{snake}",
    },
    {
        "actor": "openIsic5229",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5229",
        "fn_template": "task_open_isic_5229_{snake}",
    },
    {
        "actor": "openIsic5310",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5310",
        "fn_template": "task_open_isic_5310_{snake}",
    },
    {
        "actor": "openIsic5320",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5320",
        "fn_template": "task_open_isic_5320_{snake}",
    },
    {
        "actor": "openIsic5510",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5510",
        "fn_template": "task_open_isic_5510_{snake}",
    },
    {
        "actor": "openIsic5520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5520",
        "fn_template": "task_open_isic_5520_{snake}",
    },
    {
        "actor": "openIsic5590",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5590",
        "fn_template": "task_open_isic_5590_{snake}",
    },
    {
        "actor": "openIsic5610",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5610",
        "fn_template": "task_open_isic_5610_{snake}",
    },
    {
        "actor": "openIsic5621",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5621",
        "fn_template": "task_open_isic_5621_{snake}",
    },
    {
        "actor": "openIsic5629",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5629",
        "fn_template": "task_open_isic_5629_{snake}",
    },
    {
        "actor": "openIsic5630",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5630",
        "fn_template": "task_open_isic_5630_{snake}",
    },
    {
        "actor": "openIsic5811",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5811",
        "fn_template": "task_open_isic_5811_{snake}",
    },
    {
        "actor": "openIsic5812",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5812",
        "fn_template": "task_open_isic_5812_{snake}",
    },
    {
        "actor": "openIsic5813",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5813",
        "fn_template": "task_open_isic_5813_{snake}",
    },
    {
        "actor": "openIsic5819",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5819",
        "fn_template": "task_open_isic_5819_{snake}",
    },
    {
        "actor": "openIsic5820",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5820",
        "fn_template": "task_open_isic_5820_{snake}",
    },
    {
        "actor": "openIsic5911",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5911",
        "fn_template": "task_open_isic_5911_{snake}",
    },
    {
        "actor": "openIsic5912",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5912",
        "fn_template": "task_open_isic_5912_{snake}",
    },
    {
        "actor": "openIsic5913",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5913",
        "fn_template": "task_open_isic_5913_{snake}",
    },
    {
        "actor": "openIsic5914",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5914",
        "fn_template": "task_open_isic_5914_{snake}",
    },
    {
        "actor": "openIsic5920",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_5920",
        "fn_template": "task_open_isic_5920_{snake}",
    },
    {
        "actor": "openIsic6010",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6010",
        "fn_template": "task_open_isic_6010_{snake}",
    },
    {
        "actor": "openIsic6020",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6020",
        "fn_template": "task_open_isic_6020_{snake}",
    },
    {
        "actor": "openIsic6110",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6110",
        "fn_template": "task_open_isic_6110_{snake}",
    },
    {
        "actor": "openIsic6120",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6120",
        "fn_template": "task_open_isic_6120_{snake}",
    },
    {
        "actor": "openIsic6130",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6130",
        "fn_template": "task_open_isic_6130_{snake}",
    },
    {
        "actor": "openIsic6190",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6190",
        "fn_template": "task_open_isic_6190_{snake}",
    },
    {
        "actor": "openIsic6201",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6201",
        "fn_template": "task_open_isic_6201_{snake}",
    },
    {
        "actor": "openIsic6202",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6202",
        "fn_template": "task_open_isic_6202_{snake}",
    },
    {
        "actor": "openIsic6209",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6209",
        "fn_template": "task_open_isic_6209_{snake}",
    },
    {
        "actor": "openIsic6311",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6311",
        "fn_template": "task_open_isic_6311_{snake}",
    },
    {
        "actor": "openIsic6312",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6312",
        "fn_template": "task_open_isic_6312_{snake}",
    },
    {
        "actor": "openIsic6391",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6391",
        "fn_template": "task_open_isic_6391_{snake}",
    },
    {
        "actor": "openIsic6399",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6399",
        "fn_template": "task_open_isic_6399_{snake}",
    },
    {
        "actor": "openIsic6411",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6411",
        "fn_template": "task_open_isic_6411_{snake}",
    },
    {
        "actor": "openIsic6419",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6419",
        "fn_template": "task_open_isic_6419_{snake}",
    },
    {
        "actor": "openIsic6420",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6420",
        "fn_template": "task_open_isic_6420_{snake}",
    },
    {
        "actor": "openIsic6430",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6430",
        "fn_template": "task_open_isic_6430_{snake}",
    },
    {
        "actor": "openIsic6491",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6491",
        "fn_template": "task_open_isic_6491_{snake}",
    },
    {
        "actor": "openIsic6492",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6492",
        "fn_template": "task_open_isic_6492_{snake}",
    },
    {
        "actor": "openIsic6499",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6499",
        "fn_template": "task_open_isic_6499_{snake}",
    },
    {
        "actor": "openIsic6511",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6511",
        "fn_template": "task_open_isic_6511_{snake}",
    },
    {
        "actor": "openIsic6512",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6512",
        "fn_template": "task_open_isic_6512_{snake}",
    },
    {
        "actor": "openIsic6520",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6520",
        "fn_template": "task_open_isic_6520_{snake}",
    },
    {
        "actor": "openIsic6530",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6530",
        "fn_template": "task_open_isic_6530_{snake}",
    },
    {
        "actor": "openIsic6611",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6611",
        "fn_template": "task_open_isic_6611_{snake}",
    },
    {
        "actor": "openIsic6612",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6612",
        "fn_template": "task_open_isic_6612_{snake}",
    },
    {
        "actor": "openIsic6619",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6619",
        "fn_template": "task_open_isic_6619_{snake}",
    },
    {
        "actor": "openIsic6621",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6621",
        "fn_template": "task_open_isic_6621_{snake}",
    },
    {
        "actor": "openIsic6622",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6622",
        "fn_template": "task_open_isic_6622_{snake}",
    },
    {
        "actor": "openIsic6629",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6629",
        "fn_template": "task_open_isic_6629_{snake}",
    },
    {
        "actor": "openIsic6630",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6630",
        "fn_template": "task_open_isic_6630_{snake}",
    },
    {
        "actor": "openIsic6810",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6810",
        "fn_template": "task_open_isic_6810_{snake}",
    },
    {
        "actor": "openIsic6820",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6820",
        "fn_template": "task_open_isic_6820_{snake}",
    },
    {
        "actor": "openIsic6910",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6910",
        "fn_template": "task_open_isic_6910_{snake}",
    },
    {
        "actor": "openIsic6920",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_6920",
        "fn_template": "task_open_isic_6920_{snake}",
    },
    {
        "actor": "openIsic7010",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7010",
        "fn_template": "task_open_isic_7010_{snake}",
    },
    {
        "actor": "openIsic7020",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7020",
        "fn_template": "task_open_isic_7020_{snake}",
    },
    {
        "actor": "openIsic7110",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7110",
        "fn_template": "task_open_isic_7110_{snake}",
    },
    {
        "actor": "openIsic7120",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7120",
        "fn_template": "task_open_isic_7120_{snake}",
    },
    {
        "actor": "openIsic7210",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7210",
        "fn_template": "task_open_isic_7210_{snake}",
    },
    {
        "actor": "openIsic7220",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7220",
        "fn_template": "task_open_isic_7220_{snake}",
    },
    {
        "actor": "openIsic7310",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7310",
        "fn_template": "task_open_isic_7310_{snake}",
    },
    {
        "actor": "openIsic7320",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7320",
        "fn_template": "task_open_isic_7320_{snake}",
    },
    {
        "actor": "openIsic7410",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7410",
        "fn_template": "task_open_isic_7410_{snake}",
    },
    {
        "actor": "openIsic7420",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7420",
        "fn_template": "task_open_isic_7420_{snake}",
    },
    {
        "actor": "openIsic7490",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7490",
        "fn_template": "task_open_isic_7490_{snake}",
    },
    {
        "actor": "openIsic7500",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7500",
        "fn_template": "task_open_isic_7500_{snake}",
    },
    {
        "actor": "openIsic7710",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7710",
        "fn_template": "task_open_isic_7710_{snake}",
    },
    {
        "actor": "openIsic7721",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7721",
        "fn_template": "task_open_isic_7721_{snake}",
    },
    {
        "actor": "openIsic7722",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7722",
        "fn_template": "task_open_isic_7722_{snake}",
    },
    {
        "actor": "openIsic7729",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7729",
        "fn_template": "task_open_isic_7729_{snake}",
    },
    {
        "actor": "openIsic7730",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7730",
        "fn_template": "task_open_isic_7730_{snake}",
    },
    {
        "actor": "openIsic7740",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7740",
        "fn_template": "task_open_isic_7740_{snake}",
    },
    {
        "actor": "openIsic7810",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7810",
        "fn_template": "task_open_isic_7810_{snake}",
    },
    {
        "actor": "openIsic7820",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7820",
        "fn_template": "task_open_isic_7820_{snake}",
    },
    {
        "actor": "openIsic7830",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7830",
        "fn_template": "task_open_isic_7830_{snake}",
    },
    {
        "actor": "openIsic7911",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7911",
        "fn_template": "task_open_isic_7911_{snake}",
    },
    {
        "actor": "openIsic7912",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7912",
        "fn_template": "task_open_isic_7912_{snake}",
    },
    {
        "actor": "openIsic7990",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_7990",
        "fn_template": "task_open_isic_7990_{snake}",
    },
    {
        "actor": "openIsic8010",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8010",
        "fn_template": "task_open_isic_8010_{snake}",
    },
    {
        "actor": "openIsic8020",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8020",
        "fn_template": "task_open_isic_8020_{snake}",
    },
    {
        "actor": "openIsic8030",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8030",
        "fn_template": "task_open_isic_8030_{snake}",
    },
    {
        "actor": "openIsic8110",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8110",
        "fn_template": "task_open_isic_8110_{snake}",
    },
    {
        "actor": "openIsic8121",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8121",
        "fn_template": "task_open_isic_8121_{snake}",
    },
    {
        "actor": "openIsic8129",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8129",
        "fn_template": "task_open_isic_8129_{snake}",
    },
    {
        "actor": "openIsic8130",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8130",
        "fn_template": "task_open_isic_8130_{snake}",
    },
    {
        "actor": "openIsic8211",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8211",
        "fn_template": "task_open_isic_8211_{snake}",
    },
    {
        "actor": "openIsic8219",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8219",
        "fn_template": "task_open_isic_8219_{snake}",
    },
    {
        "actor": "openIsic8220",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8220",
        "fn_template": "task_open_isic_8220_{snake}",
    },
    {
        "actor": "openIsic8230",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8230",
        "fn_template": "task_open_isic_8230_{snake}",
    },
    {
        "actor": "openIsic8291",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8291",
        "fn_template": "task_open_isic_8291_{snake}",
    },
    {
        "actor": "openIsic8292",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8292",
        "fn_template": "task_open_isic_8292_{snake}",
    },
    {
        "actor": "openIsic8299",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8299",
        "fn_template": "task_open_isic_8299_{snake}",
    },
    {
        "actor": "openIsic8410",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8410",
        "fn_template": "task_open_isic_8410_{snake}",
    },
    {
        "actor": "openIsic8421",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8421",
        "fn_template": "task_open_isic_8421_{snake}",
    },
    {
        "actor": "openIsic8422",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8422",
        "fn_template": "task_open_isic_8422_{snake}",
    },
    {
        "actor": "openIsic8423",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8423",
        "fn_template": "task_open_isic_8423_{snake}",
    },
    {
        "actor": "openIsic8430",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8430",
        "fn_template": "task_open_isic_8430_{snake}",
    },
    {
        "actor": "openIsic8510",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8510",
        "fn_template": "task_open_isic_8510_{snake}",
    },
    {
        "actor": "openIsic8521",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8521",
        "fn_template": "task_open_isic_8521_{snake}",
    },
    {
        "actor": "openIsic8522",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8522",
        "fn_template": "task_open_isic_8522_{snake}",
    },
    {
        "actor": "openIsic8530",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8530",
        "fn_template": "task_open_isic_8530_{snake}",
    },
    {
        "actor": "openIsic8541",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8541",
        "fn_template": "task_open_isic_8541_{snake}",
    },
    {
        "actor": "openIsic8542",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8542",
        "fn_template": "task_open_isic_8542_{snake}",
    },
    {
        "actor": "openIsic8549",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8549",
        "fn_template": "task_open_isic_8549_{snake}",
    },
    {
        "actor": "openIsic8550",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8550",
        "fn_template": "task_open_isic_8550_{snake}",
    },
    {
        "actor": "openIsic8610",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8610",
        "fn_template": "task_open_isic_8610_{snake}",
    },
    {
        "actor": "openIsic8620",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8620",
        "fn_template": "task_open_isic_8620_{snake}",
    },
    {
        "actor": "openIsic8690",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8690",
        "fn_template": "task_open_isic_8690_{snake}",
    },
    {
        "actor": "openIsic8710",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8710",
        "fn_template": "task_open_isic_8710_{snake}",
    },
    {
        "actor": "openIsic8720",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8720",
        "fn_template": "task_open_isic_8720_{snake}",
    },
    {
        "actor": "openIsic8730",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8730",
        "fn_template": "task_open_isic_8730_{snake}",
    },
    {
        "actor": "openIsic8790",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8790",
        "fn_template": "task_open_isic_8790_{snake}",
    },
    {
        "actor": "openIsic8810",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8810",
        "fn_template": "task_open_isic_8810_{snake}",
    },
    {
        "actor": "openIsic8890",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_8890",
        "fn_template": "task_open_isic_8890_{snake}",
    },
    {
        "actor": "openIsic9000",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9000",
        "fn_template": "task_open_isic_9000_{snake}",
    },
    {
        "actor": "openIsic9101",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9101",
        "fn_template": "task_open_isic_9101_{snake}",
    },
    {
        "actor": "openIsic9102",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9102",
        "fn_template": "task_open_isic_9102_{snake}",
    },
    {
        "actor": "openIsic9103",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9103",
        "fn_template": "task_open_isic_9103_{snake}",
    },
    {
        "actor": "openIsic9200",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9200",
        "fn_template": "task_open_isic_9200_{snake}",
    },
    {
        "actor": "openIsic9311",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9311",
        "fn_template": "task_open_isic_9311_{snake}",
    },
    {
        "actor": "openIsic9312",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9312",
        "fn_template": "task_open_isic_9312_{snake}",
    },
    {
        "actor": "openIsic9319",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9319",
        "fn_template": "task_open_isic_9319_{snake}",
    },
    {
        "actor": "openIsic9321",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9321",
        "fn_template": "task_open_isic_9321_{snake}",
    },
    {
        "actor": "openIsic9329",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9329",
        "fn_template": "task_open_isic_9329_{snake}",
    },
    {
        "actor": "openIsic9411",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9411",
        "fn_template": "task_open_isic_9411_{snake}",
    },
    {
        "actor": "openIsic9412",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9412",
        "fn_template": "task_open_isic_9412_{snake}",
    },
    {
        "actor": "openIsic9420",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9420",
        "fn_template": "task_open_isic_9420_{snake}",
    },
    {
        "actor": "openIsic9491",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9491",
        "fn_template": "task_open_isic_9491_{snake}",
    },
    {
        "actor": "openIsic9492",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9492",
        "fn_template": "task_open_isic_9492_{snake}",
    },
    {
        "actor": "openIsic9499",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9499",
        "fn_template": "task_open_isic_9499_{snake}",
    },
    {
        "actor": "openIsic9511",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9511",
        "fn_template": "task_open_isic_9511_{snake}",
    },
    {
        "actor": "openIsic9512",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9512",
        "fn_template": "task_open_isic_9512_{snake}",
    },
    {
        "actor": "openIsic9521",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9521",
        "fn_template": "task_open_isic_9521_{snake}",
    },
    {
        "actor": "openIsic9522",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9522",
        "fn_template": "task_open_isic_9522_{snake}",
    },
    {
        "actor": "openIsic9523",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9523",
        "fn_template": "task_open_isic_9523_{snake}",
    },
    {
        "actor": "openIsic9524",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9524",
        "fn_template": "task_open_isic_9524_{snake}",
    },
    {
        "actor": "openIsic9529",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9529",
        "fn_template": "task_open_isic_9529_{snake}",
    },
    {
        "actor": "openIsic9601",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9601",
        "fn_template": "task_open_isic_9601_{snake}",
    },
    {
        "actor": "openIsic9602",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9602",
        "fn_template": "task_open_isic_9602_{snake}",
    },
    {
        "actor": "openIsic9603",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9603",
        "fn_template": "task_open_isic_9603_{snake}",
    },
    {
        "actor": "openIsic9609",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9609",
        "fn_template": "task_open_isic_9609_{snake}",
    },
    {
        "actor": "openIsic9700",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9700",
        "fn_template": "task_open_isic_9700_{snake}",
    },
    {
        "actor": "openIsic9810",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9810",
        "fn_template": "task_open_isic_9810_{snake}",
    },
    {
        "actor": "openIsic9820",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9820",
        "fn_template": "task_open_isic_9820_{snake}",
    },
    {
        "actor": "openIsic9900",
        "methods": ["classify"],
        "module": "kotodama.primitives.open_isic_9900",
        "fn_template": "task_open_isic_9900_{snake}",
    },
    {
        "actor": "openIsco",
        "methods": [
            "classifyWorker",
            "recordConcordance",
        ],
        "module": "kotodama.primitives.open_isco",
        "fn_template": "task_open_isco_{snake}",
    },
    {
        "actor": "apqc",
        "methods": [
            "materializeSubprocesses",
            "emitEvent",
            "coverageSnapshot",
        ],
        "module": "kotodama.primitives.apqc",
        "fn_template": "task_apqc_{snake}",
    },
    {
        "actor": "openNaics",
        "methods": [
            "classifyEntity",
            "recordConcordance",
        ],
        "module": "kotodama.primitives.open_naics",
        "fn_template": "task_open_naics_{snake}",
    },
]


def _build_const_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.const.* — generic primitives outside the actor convention."""
    try:
        from kotodama.tools_const_worker_main import task_echo
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: const tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.const.echo": task_echo}


def _build_audit_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.audit.* — generic OCEL emitter (ADR-2605082000 §2.5)."""
    try:
        from kotodama.tools_audit_worker_main import task_audit_emit
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: audit tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.audit.emit": task_audit_emit}


def _build_llm_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.llm.* — generic LLM chat (ADR-2605082000 §2)."""
    try:
        from kotodama.tools_llm_worker_main import task_llm_chat
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: llm tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.llm.chat": task_llm_chat}


def _build_sql_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.sql.* — generic SELECT + write exec + dynamic-row INSERT
    (ADR-2605082000 §2 + Phase E0)."""
    out: dict[str, McpHandler] = {}
    try:
        from kotodama.tools_sql_worker_main import (
            task_sql_query,
            task_sql_exec,
            task_sql_insert_row,
        )
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: sql tools unavailable: %s", exc)
        return out
    out["com.etzhayyim.tools.sql.query"] = task_sql_query
    out["com.etzhayyim.tools.sql.exec"] = task_sql_exec
    out["com.etzhayyim.tools.sql.insert_row"] = task_sql_insert_row
    return out


def _build_http_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.http.* — generic HTTP fetch (ADR-2605082000 §2)."""
    try:
        from kotodama.tools_http_worker_main import task_http_fetch
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: http tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.http.fetch": task_http_fetch}


def _build_json_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.json.* — generic JSON extract (ADR-2605082000 §2)."""
    try:
        from kotodama.tools_json_worker_main import task_json_extract
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: json tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.json.extract": task_json_extract}


def _build_transform_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.transform.* — per-row declarative mapping (ADR-2605082000 §2)."""
    try:
        from kotodama.tools_transform_worker_main import task_transform_map
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: transform tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.transform.map": task_transform_map}


def _build_time_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.time.* — wall-clock readout (ADR-2605082000 Phase D)."""
    try:
        from kotodama.tools_time_worker_main import task_time_now
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: time tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.time.now": task_time_now}


def _build_crypto_overrides() -> dict[str, McpHandler]:
    """com.etzhayyim.tools.crypto.* — content-addressing hash (ADR-2605082000 Phase D)."""
    try:
        from kotodama.tools_crypto_worker_main import task_crypto_hash
    except Exception as exc:  # pragma: no cover — defensive
        LOG.warning("mcp_dispatch: crypto tools unavailable: %s", exc)
        return {}
    return {"com.etzhayyim.tools.crypto.hash": task_crypto_hash}


def _make_lg_pod_proxy(base_url: str, endpoint: str, nsid: str) -> McpHandler:
    """Return an async handler that forwards an MCP call to a LangGraph pod REST endpoint.

    Unlike the organism proxy (which speaks XRPC with an `output` wrapper), the
    jukyu/supplychain pods return plain JSON dicts from their `/cron/*` endpoints.
    """
    url = f"{base_url}{endpoint}"

    async def _proxy(**arguments: Any) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=arguments or {}) as resp:
                data = await resp.json()
                if not isinstance(data, dict):
                    raise RuntimeError(f"{nsid} unexpected response type: {type(data)!r}")
                return data

    return _proxy


def _build_jukyu_handlers() -> dict[str, McpHandler]:
    """Build proxy handlers for jukyu actor routed to lg-jukyu pod."""
    out: dict[str, McpHandler] = {}
    for method, endpoint in _LG_JUKYU_ROUTES.items():
        nsid = f"com.etzhayyim.apps.jukyu.{method}"
        out[nsid] = _make_lg_pod_proxy(_LG_JUKYU_BASE, endpoint, nsid)
    return out


def _build_supplychain_handlers() -> dict[str, McpHandler]:
    """Build proxy handlers for supplychain actor routed to lg-supplychain pod."""
    out: dict[str, McpHandler] = {}
    for method, endpoint in _LG_SUPPLYCHAIN_ROUTES.items():
        nsid = f"com.etzhayyim.apps.supplychain.{method}"
        out[nsid] = _make_lg_pod_proxy(_LG_SUPPLYCHAIN_BASE, endpoint, nsid)
    return out


def _make_organism_proxy(nsid: str) -> McpHandler:
    """Return an async handler that forwards the MCP call to lg-organism via XRPC."""
    url = f"{_LG_ORGANISM_BASE}/xrpc/{nsid}"

    async def _proxy(**arguments: Any) -> dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=arguments or {}) as resp:
                data = await resp.json()
                if not isinstance(data, dict) or "output" not in data:
                    raise RuntimeError(f"lg-organism {nsid} unexpected response: {data!r}")
                return data["output"]

    return _proxy


def _build_organism_handlers() -> dict[str, McpHandler]:
    """Build proxy handlers for all organism actors routed to lg-organism pod."""
    out: dict[str, McpHandler] = {}
    for actor, methods in _LG_ORGANISM_ACTORS.items():
        for method in methods:
            nsid = f"com.etzhayyim.apps.{actor}.{method}"
            out[nsid] = _make_organism_proxy(nsid)
    return out


def build_default_handlers() -> dict[str, McpHandler]:
    """Compose the default MCP handler registry across all actors."""
    handlers: dict[str, McpHandler] = {}
    handlers.update(_build_organism_handlers())
    handlers.update(_build_jukyu_handlers())
    handlers.update(_build_supplychain_handlers())
    for entry in _DEFAULT_ACTORS:
        if "mapping" in entry:
            # Heterogeneous: explicit method → "module:fn" dict.
            handlers.update(register_actor_by_mapping(entry["actor"], entry["mapping"]))
            continue
        kwargs: dict[str, Any] = {}
        if "module" in entry:
            kwargs["module_template"] = entry["module"]
        if "fn_template" in entry:
            kwargs["fn_template"] = entry["fn_template"]
        handlers.update(
            register_actor_by_convention(entry["actor"], entry["methods"], **kwargs),
        )
    handlers.update(_build_const_overrides())
    handlers.update(_build_audit_overrides())
    handlers.update(_build_llm_overrides())
    handlers.update(_build_sql_overrides())
    handlers.update(_build_http_overrides())
    handlers.update(_build_json_overrides())
    handlers.update(_build_transform_overrides())
    handlers.update(_build_time_overrides())
    handlers.update(_build_crypto_overrides())
    return handlers


def build_actor_handlers(
    actor_names: list[str] | set[str] | tuple[str, ...],
) -> dict[str, McpHandler]:
    """Compose MCP handlers for selected convention actors only.

    This is useful for narrow CI/verifier checks where importing unrelated
    actors would produce noise or require optional dependencies outside the
    actor under test.
    """
    wanted = set(actor_names)
    handlers: dict[str, McpHandler] = {}
    for entry in _DEFAULT_ACTORS:
        if entry["actor"] not in wanted:
            continue
        if "mapping" in entry:
            handlers.update(register_actor_by_mapping(entry["actor"], entry["mapping"]))
            continue
        kwargs: dict[str, Any] = {}
        if "module" in entry:
            kwargs["module_template"] = entry["module"]
        if "fn_template" in entry:
            kwargs["fn_template"] = entry["fn_template"]
        handlers.update(
            register_actor_by_convention(entry["actor"], entry["methods"], **kwargs),
        )
    return handlers


async def handle_envelope(
    envelope: dict[str, Any],
    handlers: dict[str, McpHandler],
) -> tuple[int, dict[str, Any]]:
    """Process a single MCP envelope. Returns (http_status, response_body).

    Recognized envelopes:

      {"method": "tools/call", "params": {"name": "<nsid>", "arguments": {...}}}

    Other methods (initialize / tools/list / ping) are out of scope here —
    the canonical MCP server (mcp.etzhayyim.com/xrpc/com.etzhayyim.mcp.message) owns
    those. This dispatcher is the per-actor delegate that only handles
    tools/call routed via vertex_mcp_tool_def.
    """
    if not isinstance(envelope, dict):
        return 400, {"error": "envelope must be a JSON object"}

    method = envelope.get("method")
    params = envelope.get("params") or {}
    if method != "tools/call":
        return 400, {"error": f"unsupported method {method!r}; expected 'tools/call'"}
    if not isinstance(params, dict):
        return 400, {"error": "params must be a JSON object"}

    name = params.get("name")
    if not name or not isinstance(name, str):
        return 400, {"error": "params.name (NSID) required"}

    handler = handlers.get(name)
    if handler is None:
        return 404, {"error": f"no MCP handler registered for {name!r}"}

    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        return 400, {"error": "params.arguments must be a JSON object"}

    try:
        result = await handler(**arguments)
    except TypeError as exc:
        # Caller passed unexpected kwargs — surface as 400 with the tool name.
        return 400, {"error": f"{name}: invalid arguments — {exc}"}
    except Exception as exc:  # pragma: no cover — defensive
        LOG.exception("mcp handler %s failed", name)
        return 500, {"error": f"{name}: handler raised {type(exc).__name__}: {exc}"}

    if not isinstance(result, dict):
        return 500, {"error": f"{name}: handler must return dict, got {type(result).__name__}"}

    return 200, {"result": result}


# aiohttp adapter — kept thin so the pure-logic surface stays unit-testable.
async def aiohttp_route(request: Any) -> Any:  # pragma: no cover — exercised in dispatcher
    from aiohttp import web

    if not request.body_exists or request.method != "POST":
        return web.json_response({"error": "POST required"}, status=405)
    try:
        envelope = await request.json()
    except json.JSONDecodeError as exc:
        return web.json_response({"error": f"invalid JSON: {exc}"}, status=400)

    handlers = request.app.get("mcp_handlers") or build_default_handlers()
    status, body = await handle_envelope(envelope, handlers)
    return web.json_response(body, status=status)
