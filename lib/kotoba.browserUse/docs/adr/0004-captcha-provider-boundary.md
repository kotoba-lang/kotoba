# ADR-0004: CAPTCHA detection and resolution provider boundary

- Status: Accepted (2026-07-18)
- Supersedes: none; extends ADR-0002

## Context

Browser sessions encounter reCAPTCHA, hCaptcha, Turnstile and site-specific
verification. A browser engine must recognize that automation is blocked and
support an authorized recovery flow without coupling portable agent code to a
solver vendor or leaking provider credentials and solution tokens into model
prompts, Datomic facts, hooks or exported history.

## Decision

`browseruse.captcha` owns three separate capabilities:

1. Pure DOM-state detection returns only public challenge metadata.
2. Human mode pauses the `AgentSession`, invokes an injected operator handler,
   and resumes only after affirmative completion.
3. External mode uses the portable `CaptchaProvider` protocol (`submit`, `poll`,
   `cancel`). Provider credentials remain encapsulated by the adapter. Polling
   is bounded by both elapsed timeout and maximum polls, and timed-out jobs are
   cancelled best-effort.

External solutions are private runtime values. They may be consumed by an
injected `apply-solution` callback, but `audit-result` removes tokens, provider
payloads and job identifiers before hooks, recipes or history can observe them.
Only serializable public policy is retained in `AgentHistory`.

Agent integration is opt-in through `:settings {:captcha ...}` and defaults to
`:disabled` for backward compatibility. Detection occurs before each model
turn. Recipe integration adds an explicit `:captcha` step; the existing generic
`:wait-human` step remains unchanged.

The API supports testing and accessibility workflows on sites where the caller
is authorized. It does not claim to defeat anti-bot controls: stealth, proxy
selection and any provider-specific service remain independent host adapters
and must comply with the target service's terms and applicable law.

## Evidence

- `test/browseruse/captcha_test.cljk` covers detection, session pause/resume,
  redacted audit events, bounded polling, timeout cancellation and settings
  sanitization.
- `test/browseruse/recipe_test.cljk` covers an end-to-end human hand-off recipe.
- Portable tests and clj-kondo lint are CI gates.

