# hil

Portable Human-in-the-Loop approval contract for kotoba-lang agents.

`hil.core/IHumanApproval` is an injected host capability. It accepts a minimal
request (`title`, `summary`, `action`, and optional `impact`) and returns one
of `:approved`, `:rejected`, or `:dismissed`. The library intentionally has no
browser, credential, or UI dependency.

Use it only at a real decision boundary. Do not include credentials, API keys,
MFA codes, or full page content in an approval request.
