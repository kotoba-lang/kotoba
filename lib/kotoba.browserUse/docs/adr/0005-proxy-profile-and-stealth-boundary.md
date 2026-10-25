# ADR-0005: Proxy, profile, CDP and stealth boundary

- Status: Accepted
- Date: 2026-07-18
- Supersedes: the Playwright-host exclusions in ADR-0001

## Decision

The JVM Playwright host accepts authenticated proxy configuration, isolated or
persistent Chrome profiles, CDP attachment, browser channel/executable selection,
fingerprint-related context settings, and document-start init scripts.

Credentials are never returned by the capability report. A CDP-attached browser
and its pre-existing context are borrowed and are not closed by session cleanup.
Locally launched browsers and contexts retain deterministic ownership.

`stealth` describes configuration hardening only. Browser fingerprint settings
can be made internally consistent, but this project does not claim automation is
undetectable, does not circumvent access controls, and does not bundle CAPTCHA
bypass. Managed anti-detect infrastructure remains a provider capability.

## Evidence

- `kbb -M:test`
- `kbb -M:lint`
- `kbb -M:playwright:test`
- `browseruse.browser-profile/capability-report` reports the effective boundary
  without proxy passwords.
