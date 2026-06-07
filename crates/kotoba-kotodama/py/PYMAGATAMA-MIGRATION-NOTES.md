<!-- ⚠️  STEP 8 CUTOVER MATERIAL — DO NOT RENAME IN ISOLATION ⚠️  -->
<!--
  This file is part of the Step 8 cutover sequence (CLAUDE.md status table).
  Renaming or moving it without updating deps.toml [[migrations]] and
  the ADR reference in ADR-2605215200 will break the cutover runbook.
-->

# kotodama RunPod-free migration — Step 8 cutover targets

⚠️ **Step 8 cutover material**: do not rename in isolation. Per-file rename happens
during the 220-file Step 8 cutover wave (legal registration master gate).

Authoritative ADR: **constitutional — etzhayyim is RunPod-free per user directive 2026-05-21**
(no separate ADR file persistent on disk; rule encoded in CHARTER-RIDER.md §2(i)).

Related migration notes: SHINKA-MIGRATION-NOTES.md, YORO-PYTHON-MIGRATION-NOTES.md.

## Migration verdicts

Verdict taxonomy (mirrors lexicon port rules):
- **REDIRECT** — env URL swap sufficient; LiteLLM gateway abstracts backend
- **VENDOR-ONLY** — business logic vendor uses for paid SaaS; religious-corp callers avoid (consent capability boundary)
- **REIMPLEMENT** — religious-corp needs different implementation on Murakumo fleet

## File-by-file targets

| File | Line(s) | Current (vendor) | Target (etzhayyim) | Verdict | Reason |
|---|---|---|---|---|---|
| pyproject.toml | (comment only) | RunPod commentary | etzhayyim-LiteLLM commentary | REDIRECT | Doc comments only |
| primitives/llm.py | (routing) | RunPod L40S text-gen routing | LiteLLM (192.168.1.70:4000) via etzhayyim_sdk.llm | REDIRECT | All LLM calls funnel through LiteLLM |
| primitives/llm.py | (timing) | RunPod cold-start timing | EVO-X2 (warm by default) | REDIRECT | Timing constants only |
| zeebe_worker_main.py | ComfyUI | RunPod Serverless /runsync for ComfyUI | EVO-X2 ComfyUI :8188 native /prompt protocol | REIMPLEMENT | Different protocol shape |
| zeebe_worker_main.py | workflow | RunPod Serverless workflow build + submit + poll | Religious-corp variant unwired (M5+) | REIMPLEMENT | Workflow logic vendor-only |
| zeebe_worker_main.py | routing | api.runpod.ai URL branch | LiteLLM URL branch | REDIRECT | Conditional URL routing |
| training_http_server.py | (all) | RunPod Serverless training | Religious-corp doesn't train; out-of-scope | VENDOR-ONLY | Training pipeline = vendor-only |
| primitives/mangaka.py | ComfyUI proxy | RunPod ComfyUI proxy URL | EVO-X2 ComfyUI URL | REDIRECT | Mangaka uses ComfyUI for image gen |
| primitives/maps_sentinel.py | GPU analysis | RunPod Serverless GPU analysis | maps_sentinel_murakumo.py (T0-T4 tiers per ADR-2605215100) | REIMPLEMENT | Full rewrite per tier matrix |
| primitives/billing.py | pricing | RunPod 6000 Ada / H100 NVL pricing | Religious-corp cost model = donation only | VENDOR-ONLY | No paid GPU in religious-corp |
| primitives/business_person.py | LLM extraction | RunPod LLM extraction | LiteLLM extraction | REDIRECT | Generic LLM call |
| primitives/otakiage.py | comment | RunPod cold-start comment | n/a (no cold start) | VENDOR-ONLY | Comment only, vendor concern |
| primitives/training_run.py | training | RunPod Serverless training/eval | Religious-corp doesn't train locally | VENDOR-ONLY | Same as training_http_server |
| primitives/training_run.py | GPU handler | RunPod-side handler entry | n/a | VENDOR-ONLY | GPU-side container entry |
| primitives/chat.py | vLLM URL | RunPod Pod vLLM URL | LiteLLM URL | REDIRECT | OpenAI-compat chat |
| primitives/projector.py | routing | RunPod fallback | LiteLLM | REDIRECT | LLM router |
| primitives/karma_resident.py | mode enum | "runpod" mode docstring | "litellm" mode | REDIRECT | Mode enum |
| primitives/kaisya_ai_org.py | comments | RunPod 6000 Ada SSoT comments | LiteLLM SSoT (per ADR-2605215000) | REDIRECT | Comments only |
| primitives/kaisya_master.py | comments | Same as kaisya_ai_org | LiteLLM | REDIRECT | Comments only |
| voxelforge/runpod_client.py | (entire file) | RunPod HTTP client | n/a | VENDOR-ONLY | Whole module is vendor-only |
| langgraph_graphs/webya_site_generation.py | comment | RunPod 6000 Ada comment | LiteLLM | REDIRECT | Comment only |
| langgraph_graphs/etzhayyim_company_ops.py | comments | RunPod SSoT comments | LiteLLM | REDIRECT | Comments only |
| handlers/news_translate.py | model | RunPod gemma4:26b replaced | LiteLLM | REDIRECT | Translation pipeline |
| sdk/kotoba-kotodama-host-sdk/src/llm-model-types.ts | refs | RunPod refs | LiteLLM | REDIRECT | Model registry comments |
| sdk/kotoba-kotodama-host-sdk/src/llm-model-registry.ts | entries | RunPod entries | LiteLLM | REDIRECT | Model registry |

## Known intentional remainders (NOT renamed)

| File | Reason |
|---|---|
| voxelforge/runpod_client.py | Vendor-only paid SaaS module; religious-corp never invokes |
| training_*.py | Religious-corp doesn't train locally (no fine-tuning workflow yet) |
| billing.py pricing constants | Vendor cost model only |

## Cutover procedure (when Step 8 fires)

1. Branch from main: `git checkout -b step8-kotodama-runpod-free`
2. Apply REDIRECT changes (env URL swap + comment updates) — single commit
3. Apply REIMPLEMENT changes (maps_sentinel handled separately per ADR-2605215100; zeebe_worker_main ComfyUI dispatch needs new code path)
4. VENDOR-ONLY files: add module-level guard `if os.environ.get("ETZHAYYIM_BUILD"): raise ImportError("vendor-only")`
5. Run pytest 20-actors/kotoba-kotodama/py/tests/ → all green
6. Smoke deploy on one Mac mini (dan)
7. Soak 24h
8. Roll out to remaining nodes

## Do not

- Backward-compat shims for RUNPOD env vars (clean break)
- Partial rename (REDIRECT or VENDOR-ONLY guards must apply atomically)
- Mix this cutover with the cluster runtime rename — they share the legal registration master gate but are separate commits

## Last updated

2026-05-21
