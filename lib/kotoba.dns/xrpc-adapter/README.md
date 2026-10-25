# dns XRPC Adapter

CF Worker that exposes the 6 kotoba commands as XRPC endpoints.

## Endpoints

### Domain Transfer Workflow
- `POST /xrpc/com.etzhayyim.dns.createTransferRequest` — create transfer request
- `GET /xrpc/com.etzhayyim.dns.getTransferRequest` — get transfer by ID
- `POST /xrpc/com.etzhayyim.dns.transferFromSquarespace` — initiate Squarespace transfer
- `POST /xrpc/com.etzhayyim.dns.putTransferStep` — record transfer step
- `GET /xrpc/com.etzhayyim.dns.listTransferSteps` — list steps for transfer
- `POST /xrpc/com.etzhayyim.dns.putTransferOutcome` — record final outcome

## Deploy

```bash
wrangler deploy
# Deploys to dns.etzhayyim.com/xrpc/*
```

See ADR-2605210000 for design context.
