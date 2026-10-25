# etzhayyim-project-tenso - Signal E2E Secure File Transfer

## Overview

Zero-knowledge file transfer. Signal Protocol (X3DH + Double Ratchet) wraps per-transfer AES-256-GCM file keys. Chunked encrypted blobs on B2. Server stores ciphertext only.

- **URL**: https://tenso.etzhayyim.com
- **API**: https://t3ns0f1l.etzhayyim.com/xrpc
- **Nanoid**: `t3ns0f1l`
- **Execution Tier**: T3 (TS Native)
- **Actor Manifest**: `20-actors/tenso/actor-manifest.jsonld`

## Build & Deploy

```bash
cd wasm/etzhayyim-wasm-tenso-t3ns0f1l
etzhayyim deploy --smoke-url https://t3ns0f1l.etzhayyim.com/health
```
