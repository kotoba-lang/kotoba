# arXiv submission: √S KV residency (Williams transfer)

Uses the **kotoba-lang/arxiv** organism actor (`:actor/arxiv`) workflow:

```text
validate-package → login → create-submission (draft) → upload-source
  → pending-human-final-submit → final-submit (requires human approval)
```

## Package

| Field | Value |
|-------|--------|
| Title | Simulating Autoregressive Memory with Square-Root Space… |
| Primary | `cs.CL` (N24 endorsed; was `cs.LG` but account only unlocked for CL) |
| Cross-list | `cs.CL`, `cs.CC` |
| License | CC BY 4.0 |
| Source | `build/sqrt_space_kv-arxiv-source.tar.gz` |
| PDF | `sqrt_space_kv.pdf` (via `make`) |
| **Account** | **junkawasaki-n24y** (`n24y001j@mail.cc.niigata-u.ac.jp`) |
| 1Password | Private vault → **Arxiv - N24** |
| Draft id | **7807366** (N24, 2026-07-09) |

> Do **not** use the older `junkawasaki` / `root@junkawasaki.com` profile for this paper.

## Build

```bash
cd submissions/sqrt-space-kv
make all      # tectonic → PDF
make arxiv    # tar.gz with .tex + .bib + .bbl
```

## Resume at arXiv (human) — ~5 min

1. Login as **junkawasaki-n24y** → https://arxiv.org/user/
2. Open draft **7807366**  
   https://arxiv.org/submit/7807366/start  
   (or START NEW SUBMISSION if expired)
3. **Start** form:
   - ☑ certify contact (Niigata email is correct)
   - ☑ open Submittal Agreement → **scroll to bottom** → Accept
   - ○ I am submitting as an author
   - ○ **CC BY 4.0**
   - Archive **Computer Science** / Class **Computation and Language (`cs.CL`)**
     (cross-list intended: `cs.LG`, `cs.CC` if/when endorsed)
   - Continue
4. **Add Files**: upload  
   `build/sqrt_space_kv-arxiv-source.tar.gz`
5. Process → Metadata (title/abstract from `package.edn` / `abstract.txt`;
   cross-list `cs.CL`, `cs.CC`) → Preview
6. **Submit** (public record; actor `:arxiv/final-submit` gate)

## Automation notes

- Login verified on **junkawasaki-n24y** with Niigata email on the user page.
- Playwright can fill most Start fields, but agreement-modal + Continue is still
  brittle headless — finish Start → Upload in the browser.
- Actor gate: `:arxiv/final-submit` **requires** `:human-approval`.

## Related code

- Paper body (markdown): `gftdcojp/cloud-murakumo/docs/paper/sqrt_space_llm_kv.md`
- Modal/Mac benches: `gftdcojp/cloud-murakumo/docs/benchmarks/`
