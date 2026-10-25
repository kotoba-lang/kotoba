# Cloud v3 live probe runbook

The command is non-networked and non-billable unless `--execute` is present.

```bash
kbb -M:cloud -m browseruse.cloud.live-probe
```

Review the printed endpoint, task, USD ceiling, timeout, and cleanup policy.
Then provide the key to the process environment without putting it in source,
arguments, shell tracing, or logs:

```bash
read -rs BROWSER_USE_API_KEY
export BROWSER_USE_API_KEY
kbb -M:cloud -m browseruse.cloud.live-probe \
  --execute \
  --task "Open https://example.com and return only the page title." \
  --model bu-mini \
  --max-cost-usd 0.05 \
  --timeout-seconds 120
unset BROWSER_USE_API_KEY
```

Optional flags are `--proxy-country JP`, `--record`, and `--poll-ms 2000`.
Recording can add storage/data exposure and should only be enabled intentionally.

The probe reports session ID, status, output and cost totals. It omits the API
key and signed live/recording URLs. Session stop is attempted in `finally`; if
cleanup reports failure, use the reported session ID with the Cloud dashboard
or `POST /api/v3/sessions/{id}/stop` using strategy `session`.
