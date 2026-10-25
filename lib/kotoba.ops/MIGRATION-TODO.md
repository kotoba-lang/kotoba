# Migration TODO — etzhayyim-project-ops

**Status**: 🔄 TRANSFORM — thin-edge appview migrated from etzhayyim archive 2026-06-01.

This is a thin-edge dispatcher (edge-proxy → AgentGateway MCP → pod-side LangServer).
No worker-side RisingWave/fiat dependency; business logic runs in the dispatcher/pod.

**Codemod pending** (substrate-boundary ADR-2605172000 / 2605172100):
- Confirm `DISPATCHER_URL` targets an etzhayyim-substrate dispatcher (kotoba).
- Any settlement path → USDC + ERC-4337 (no Stripe/fiat).
- appview wiring + `kotoba/` reference slice TBD.
