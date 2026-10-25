# kotoba-lang/arxiv

`arxiv` as an organism actor: Clojure/EDN knowledge + **executable Playwright
browser runner** for policy-aware arXiv package validation, draft creation,
source upload, and human-gated final submission.

Not an official arXiv service. Implements ADR-0023:

```text
Actor -> Capability -> Skill -> Yorishiro route
```

## Layout

```text
actors/arxiv/actor.edn          actor manifest
actors/arxiv/facts/*.edn        domain knowledge
actors/arxiv/skills/*.edn       skill recipes (login, start form, upload, final)
actors/arxiv/yorishiro.edn      API/browser/computer/human surfaces
src/arxiv_kotoba/*.cljc         pure dispatcher (validate/plan/invoke)
browser/arxiv_submit/           Playwright runner (implements browser-dom/computer)
bin/arxiv-submit                CLI wrapper (+ optional 1Password --op-item)
submissions/<id>/               package.edn + LaTeX source + status.edn
```

## Commands

```bash
# pure contract tests
kbb -M:test

# package unit tests (Python)
PYTHONPATH=browser python test/arxiv_submit/test_package.py

# validate package (from repo root)
kbb -M -e "(require '[arxiv-kotoba.ops :as o]) (prn (o/validate-package {:package-edn \"submissions/sqrt-space-kv/package.edn\"}))"

# browser pipeline (N24 account)
bin/arxiv-submit submissions/sqrt-space-kv \
  --op-item 'Arxiv - N24' --op-vault Private \
  --stop-after metadata

# resume existing draft
bin/arxiv-submit submissions/sqrt-space-kv \
  --op-item 'Arxiv - N24' \
  --resume-draft 7807366 \
  --stop-after upload

# if blocked on category endorsement (first-time cs.LG etc.)
bin/arxiv-submit submissions/sqrt-space-kv \
  --op-item 'Arxiv - N24' \
  --resume-draft 7807366 \
  --stop-after endorsement
# → status :pending-endorsement + unique code in status.edn notes
# → human forwards arXiv email to a qualified endorser

# public Submit (actor human-approval gate — explicit)
APPROVE_FINAL=1 bin/arxiv-submit submissions/sqrt-space-kv \
  --op-item 'Arxiv - N24' --stop-after final
```

## Browser pipeline stages

```text
login → user-home → start → accept-terms → fill-start-form
  → (optional) pending-endorsement  ← human gate: forward code
  → upload-source → process/metadata walk
  → pending-human-final-submit      ← human gate: APPROVE_FINAL=1
  → final-submit
```

Authorship on the Start form uses `input[name=is_author][value=1]` (author).
There is a **hidden sentinel** `value=0` that must not be selected.

## Credentials

Default account for this monorepo: **junkawasaki-n24y**  
(`n24y001j@mail.cc.niigata-u.ac.jp`, 1Password Private → **Arxiv - N24**).

```bash
# Python deps (repo-local venv preferred by bin/arxiv-submit)
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r browser/requirements.txt
# browsers already under ~/Library/Caches/ms-playwright if previously installed
python -m playwright install chromium   # first time only
```

## Packages

| id | path | primary |
|----|------|---------|
| kotoba | `submissions/kotoba/` | cs.CL |
| sqrt-space-kv | `submissions/sqrt-space-kv/` | cs.LG |

## Final submit policy

`:arxiv/final-submit` **always** requires `:human-approval` (public scholarly
record). The browser runner will not click Submit unless `APPROVE_FINAL=1`.

Endorsement for a category is a separate policy gate (`:pending-endorsement`);
the runner records the unique code but does not invent endorsers.
