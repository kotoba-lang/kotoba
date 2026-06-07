"""
Per-actor handler modules. Importing this package triggers every @udf
decoration, populating the global NSID registry before the arrow-udf
server binds its port.

Add new actors here as they migrate to Mode A. ADR-0047 Phase B pilot
ships `bpmn` and `playwright` first.
"""

# ADR-0047 Phase B pilot actors — imported for their side effect of
# registering handlers. Listed explicitly so a stray import error is
# caught at boot rather than at first XRPC call.
from kotodama.handlers import bpmn  # noqa: F401
from kotodama.handlers import contracts  # noqa: F401
from kotodama.handlers import houbun  # noqa: F401
from kotodama.handlers import ingest  # noqa: F401
from kotodama.handlers import kouza  # noqa: F401
from kotodama.handlers import playwright  # noqa: F401

# ADR-0049 Phase C — shinka/koji/kyumei agent loop (LangGraph).
from kotodama.handlers import shinka  # noqa: F401

# ADR-0050 — Vultr Serverless Inference proxy.
from kotodama.handlers import vultr_inference  # noqa: F401

# ADR-0032 / ADR-0050 — yabai T3 gray-zone phishing classifier.
from kotodama.handlers import classify_t3  # noqa: F401

# ADR-0049 Phase B — gmail contact DID materializer.
from kotodama.handlers import gmail_contact  # noqa: F401

# ADR-0049 Phase B4 — news translation via Vultr Serverless.
from kotodama.handlers import news_translate  # noqa: F401

# news.etzhayyim.com intel source/priority scoring.
from kotodama.handlers import news_intel  # noqa: F401

# ADR-0049 Phase B5 — mangaka storyboard generation from prompt.
from kotodama.handlers import mangaka_storyboard  # noqa: F401

# ADR-0092 L2 — actor embedding (multilingual-e5-small, cpu-only).
from kotodama.handlers import actor_embed  # noqa: F401

# ADR-0049 Phase C — DNS-over-HTTPS resolver (Cloudflare DoH).
# Replaces per-row DoH fetches in 70-tools/scripts/hourly_collect.py +
# collect-dns-global.sh. NSIDs com.etzhayyim.apps.dns.{resolve,resolveJson}.
from kotodama.handlers import dns_resolve  # noqa: F401

# ADR-0049 Phase C — GLEIF LEI lookup. Replaces per-row GLEIF fetch in
# 70-tools/scripts/gleif-reconcile-repo-record.mjs +
# multi-country-direct-ingest.mjs. NSID com.etzhayyim.apps.gleif.lookup.
from kotodama.handlers import gleif_lookup  # noqa: F401

# ADR-0049 Phase C — Wikidata entity claims. Replaces per-QID
# `wbgetentities` fetch in 70-tools/scripts/media_gamers_enrich_sources.py.
# NSID com.etzhayyim.apps.wikidata.entityClaims.
from kotodama.handlers import wikidata_entity  # noqa: F401

# ADR-0049 Phase C — Steam appdetails release-date backfill. Replaces
# 70-tools/scripts/media_gamers_backfill_release_year.py +
# media_gamers_enrich_sources.py --steam-backfill. NSID
# com.etzhayyim.apps.steam.releaseDate.
from kotodama.handlers import steam_release  # noqa: F401

# APQC / ISIC / ISCO migration — deterministic UDF companions for the LangServer +
# LangGraph runtime. These replace the retired WASM execution surface.
from kotodama.handlers import apqc  # noqa: F401
from kotodama.handlers import open_isic  # noqa: F401
from kotodama.handlers import open_isco  # noqa: F401
