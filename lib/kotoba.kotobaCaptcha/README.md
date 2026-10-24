# kotoba-captcha

Self-hosted CAPTCHA task orchestration for **synthetic tests, first-party
properties, accessibility, and human-assisted verification**. It provides the
portable task contract beneath HTTP and worker adapters; it is not an anti-bot
evasion product.

## CapSolver-compatible API core

- `kotoba.captcha.api/create-task!` accepts `clientKey`, `task`, and an explicit
  `authorization` object, and returns `{errorId, taskId}`.
- `kotoba.captcha.api/get-task-result` returns CapSolver-compatible
  `processing`, `ready`, and error responses.
- `kotoba.captcha.api/transition-task!` is the worker-facing state transition.

Supported safe task types are `SyntheticChallengeTask`,
`HumanVerificationTask`, and `ImageToTextTask`. Common anti-bot service task
types such as `ReCaptchaV2TaskProxyLess` are intentionally rejected. First-party
tasks require both `owner-confirmed?` and an auditable `reason`.

```clojure
(def tasks (kotoba.captcha.store/memory-store))
(kotoba.captcha.api/create-task!
 tasks
 {:task {:type "SyntheticChallengeTask"
         :prompt "2 + 2"
         :authorization {:scope :synthetic :reason "CI fixture"}}})
```

The portable `.cljc` core retains neither `clientKey` nor worker credentials.
Production adapters must encrypt sensitive payloads, authenticate callers,
apply quotas, and expire task data.

## Verify

```sh
kbb -M:test
kbb -M:lint
```

## Run locally

The local host binds to loopback, fails closed when no key is configured, and
runs the synthetic provider in a leased background worker:

```sh
export KOTOBA_CAPTCHA_API_KEYS='replace-with-a-local-secret'
kbb -M:server
```

`POST /createTask` and `POST /getTaskResult` accept `clientKey` or a Bearer
token. `/health` and `/metrics` expose no task payloads. The in-memory store is
for development; production deployments must inject a durable `TaskStore` and
encrypt retained payloads.

The worker layer provides leases, bounded retries, deadlines, cancellation,
redacted audit retention, human hand-off, synthetic fixtures, and a
first-party-only vision backend boundary. See
[`docs/worker-runtime.md`](docs/worker-runtime.md).
