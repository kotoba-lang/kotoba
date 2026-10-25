"""Playwright browser runner for kotoba-lang/arxiv organism actor.

Implements browser-dom routes for:
  :arxiv/login
  :arxiv/create-submission  (Start form)
  :arxiv/upload-source
  :arxiv/check-status
  :arxiv/final-submit       (requires APPROVE_FINAL=1)

Secrets via env ARXIV_USER / ARXIV_PASSWORD (load from 1Password outside).
"""

__version__ = "0.2.0"
