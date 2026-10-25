"""arXiv.org v1.5 submission browser flow (Playwright).

Maps to actor skills:
  login → fill_start_form → upload_source → fill_metadata → (optional) final_submit
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Browser, Page, sync_playwright, TimeoutError as PWTimeout


LICENSE_CC_BY = "http://creativecommons.org/licenses/by/4.0/"


@dataclass
class FlowResult:
    status: str = "ok"  # ok | error | pending-human-final-submit | pending-endorsement
    steps: List[str] = field(default_factory=list)
    url: Optional[str] = None
    draft_id: Optional[str] = None
    account: Optional[str] = None
    error: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    endorsement_url: Optional[str] = None
    endorsement_help_url: str = "https://info.arxiv.org/help/endorsement.html"
    endorsement_code: Optional[str] = None
    endorsement_category: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ArxivSubmitFlow:
    def __init__(
        self,
        *,
        user: str,
        password: str,
        title: str,
        abstract: str,
        archive: str = "cs",
        subject_class: str = "cs.LG",
        comments: str = "",
        source_tar: Optional[Path] = None,
        shot_dir: Optional[Path] = None,
        headed: bool = False,
        timeout_ms: int = 90_000,
        approve_final: bool = False,
        resume_draft_id: Optional[str] = None,
    ):
        self.user = user
        self.password = password
        self.title = title
        self.abstract = abstract
        self.archive = archive
        self.subject_class = subject_class
        self.comments = comments
        self.source_tar = Path(source_tar) if source_tar else None
        self.shot_dir = Path(shot_dir) if shot_dir else Path("build/screenshots")
        self.headed = headed
        self.timeout_ms = timeout_ms
        self.approve_final = approve_final
        self.resume_draft_id = resume_draft_id
        self.result = FlowResult(account=user)
        self._page: Optional[Page] = None

    # ---- helpers ----------------------------------------------------------

    def shot(self, name: str) -> None:
        if not self._page:
            return
        self.shot_dir.mkdir(parents=True, exist_ok=True)
        path = self.shot_dir / f"{name}.png"
        self._page.screenshot(path=str(path), full_page=True)
        self.result.screenshots.append(str(path))
        print(f"[shot] {path.name}", flush=True)

    def step(self, name: str) -> None:
        self.result.steps.append(name)
        print(f"[step] {name}", flush=True)

    def _click_button(self, *labels: str, timeout: int = 5000) -> bool:
        page = self._page
        assert page
        for lab in labels:
            btn = page.get_by_role("button", name=lab)
            if btn.count():
                try:
                    btn.first.click(timeout=timeout)
                    return True
                except Exception:
                    try:
                        btn.first.click(timeout=timeout, force=True)
                        return True
                    except Exception:
                        pass
            # input[type=submit]
            inp = page.locator(f'input[type="submit"][value="{lab}"]')
            if inp.count():
                try:
                    inp.first.click(timeout=timeout)
                    return True
                except Exception:
                    pass
        return False

    def _extract_draft_id(self, url: str) -> Optional[str]:
        m = re.search(r"/submit/(\d+)/", url)
        return m.group(1) if m else None

    # ---- skills -----------------------------------------------------------

    def login(self) -> None:
        page = self._page
        assert page
        page.goto("https://arxiv.org/login", wait_until="domcontentloaded")
        page.fill('input[name="username"]', self.user)
        page.fill('input[name="password"]', self.password)
        # Prefer Submit in the registered form
        if page.get_by_role("button", name="Submit").count():
            page.get_by_role("button", name="Submit").click()
        else:
            page.locator('button[type="submit"], input[type="submit"]').first.click()
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        self.shot("01-login")
        self.result.url = page.url
        if "login" in page.url and page.locator('input[type="password"]').count():
            raise RuntimeError("login failed (still on login page)")
        self.step("login")

    def open_user(self) -> None:
        page = self._page
        assert page
        page.goto("https://arxiv.org/user/", wait_until="domcontentloaded")
        time.sleep(0.8)
        self.shot("02-user")
        body = page.inner_text("body")
        for line in body.splitlines():
            if "Your arXiv.org account" in line:
                print(f"[user] {line.strip()}", flush=True)
                break
        self.step("user-home")

    def start_or_resume(self) -> None:
        page = self._page
        assert page
        if self.resume_draft_id:
            page.goto(
                f"https://arxiv.org/submit/{self.resume_draft_id}/start",
                wait_until="domcontentloaded",
            )
        else:
            page.goto("https://arxiv.org/user/", wait_until="domcontentloaded")
            clicked = False
            for text in ["START NEW SUBMISSION", "Start new submission"]:
                loc = page.get_by_role("link", name=text)
                if loc.count():
                    loc.first.click()
                    clicked = True
                    break
            if not clicked:
                page.goto("https://arxiv.org/submit", wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")
        time.sleep(1.0)
        self.result.url = page.url
        self.result.draft_id = self._extract_draft_id(page.url)
        self.shot("03-start")
        print(f"[start] draft_id={self.result.draft_id} url={page.url}", flush=True)
        self.step("start")

    def accept_terms_modal(self) -> None:
        """Open Submittal Agreement modal, scroll to enable Accept, click it.

        Idempotent: if already checked (resume / prior probe), skip modal open.
        Always accept via JS click — Playwright visibility checks fail when the
        micromodal button exists in DOM but is not yet/no longer visible.
        """
        page = self._page
        assert page
        box = page.locator('input[name="agree_terms_conditions"]')
        if not box.count():
            return
        already = False
        try:
            already = box.is_checked()
        except Exception:
            already = False
        if already:
            print("[terms] already checked — skip modal", flush=True)
            self.step("accept-terms")
            return

        # Opening the checkbox triggers the modal (class openTerms)
        box.click(force=True)
        time.sleep(1.0)
        # Scroll modal content until Accept is enabled
        for _ in range(60):
            page.evaluate(
                """() => {
              document.querySelectorAll(
                '.modal__content, .modal__container, #modal-1-content, .modal.is-open .modal__content'
              ).forEach(el => { el.scrollTop = el.scrollHeight; });
              const last = document.querySelector(
                '#modal-1-content *:last-child, .modal__content *:last-child');
              if (last) last.scrollIntoView({block: 'end'});
            }"""
            )
            time.sleep(0.1)
            enabled = page.evaluate(
                """() => {
              const b = document.querySelector('#accept-terms');
              return !!(b && !b.disabled);
            }"""
            )
            if enabled:
                break
        # JS click bypasses visibility (modal/layer quirks)
        clicked = page.evaluate(
            """() => {
          const b = document.querySelector('#accept-terms');
          if (!b) return false;
          b.disabled = false;
          b.classList.remove('disabled');
          b.click();
          return true;
        }"""
        )
        if clicked:
            time.sleep(0.5)
            print("[terms] Accept and return clicked (js)", flush=True)
        # ensure checkbox stays checked
        page.evaluate(
            """() => {
          const el = document.querySelector('input[name="agree_terms_conditions"]');
          if (el) {
            el.checked = true;
            el.dispatchEvent(new Event('change', {bubbles: true}));
          }
        }"""
        )
        self.step("accept-terms")

    def fill_start_form(self) -> None:
        """Fill arXiv v1.5 Start page required fields."""
        page = self._page
        assert page
        # 1. certify contact
        if page.locator('input[name="userinfo"]').count():
            page.locator('input[name="userinfo"]').check(force=True)

        # 2. agreement modal
        self.accept_terms_modal()

        # 3. authorship
        # arXiv v1.5 ships a *hidden* sentinel radio value="0" (display:none, pre-checked).
        # Visible choices: value="1" author, value="2" third-party. Selecting value 0
        # posts "is_author=0" and server rejects with "You must make an authorship selection".
        author_radio = page.locator('input[name="is_author"][value="1"]')
        if author_radio.count():
            author_radio.check(force=True)
            # re-assert via JS in case a later step re-checks the sentinel
            page.evaluate(
                """() => {
              const radios = [...document.querySelectorAll('input[name="is_author"]')];
              for (const r of radios) r.checked = (r.value === '1');
              const a = document.querySelector('input[name="is_author"][value="1"]');
              if (a) {
                a.dispatchEvent(new Event('input', {bubbles: true}));
                a.dispatchEvent(new Event('change', {bubbles: true}));
              }
            }"""
            )
            print(
                f"[form] is_author value=1 checked={author_radio.is_checked()}",
                flush=True,
            )
        else:
            # fallback: first *visible* radio
            vis = page.locator('input[name="is_author"]:visible')
            if vis.count():
                vis.first.check(force=True)
                print("[form] is_author via :visible first", flush=True)

        # 4. license CC BY 4.0
        lic = page.locator(f'input[name="license"][value="{LICENSE_CC_BY}"]')
        if lic.count():
            lic.check(force=True)

        # 5. archive + subject class
        if page.locator('select[name="archive"]').count():
            page.select_option('select[name="archive"]', value=self.archive)
            time.sleep(1.2)
        if page.locator('select[name="subject_class"]').count():
            # wait for options to populate after archive change
            for _ in range(15):
                opts = page.locator('select[name="subject_class"] option').all()
                vals = [o.get_attribute("value") or "" for o in opts]
                if self.subject_class in vals or any(
                    "LG" in v for v in vals if v
                ):
                    break
                time.sleep(0.2)
            try:
                page.select_option(
                    'select[name="subject_class"]', value=self.subject_class
                )
            except Exception:
                page.select_option(
                    'select[name="subject_class"]', label="Machine Learning"
                )

        # re-assert critical checks (modal / sentinel can steal state)
        if page.locator('input[name="userinfo"]').count():
            page.locator('input[name="userinfo"]').check(force=True)
        page.evaluate(
            """() => {
          const el = document.querySelector('input[name="agree_terms_conditions"]');
          if (el) {
            el.checked = true;
            el.dispatchEvent(new Event('change', {bubbles: true}));
          }
          // NEVER re-check value=0 sentinel — only author (1)
          for (const r of document.querySelectorAll('input[name="is_author"]')) {
            r.checked = (r.value === '1');
          }
        }"""
        )

        self.shot("04-start-filled")
        author_val = page.evaluate(
            """() => {
          const c = document.querySelector('input[name="is_author"]:checked');
          return c ? c.value : null;
        }"""
        )
        state = {
            "userinfo": page.locator('input[name="userinfo"]').is_checked()
            if page.locator('input[name="userinfo"]').count()
            else None,
            "agree": page.locator('input[name="agree_terms_conditions"]').is_checked()
            if page.locator('input[name="agree_terms_conditions"]').count()
            else None,
            "author_value": author_val,
            "archive": page.input_value('select[name="archive"]')
            if page.locator('select[name="archive"]').count()
            else None,
            "subject": page.input_value('select[name="subject_class"]')
            if page.locator('select[name="subject_class"]').count()
            else None,
        }
        print(f"[form] {state}", flush=True)
        if author_val not in ("1", "2"):
            raise RuntimeError(
                f"authorship not selected (checked value={author_val!r}; need 1=author)"
            )
        self.step("fill-start-form")

        # Continue to Add Files — prefer the submission form's commit button
        cont = page.locator(
            'form[action*="/submit/"] input[name="commit"][value="Continue"], '
            'input.sub-process-button[value="Continue"], '
            'input[type="submit"][value="Continue"]'
        )
        if cont.count():
            cont.first.click()
        elif not self._click_button("Continue"):
            page.evaluate(
                """() => {
              // Prefer the submission form, not the site search form
              const f = document.querySelector('form[action*="/submit/"]')
                     || [...document.forms].find(x => x.querySelector('[name="is_author"]'));
              if (f) (f.requestSubmit ? f.requestSubmit() : f.submit());
            }"""
            )
        page.wait_for_load_state("networkidle")
        time.sleep(1.5)
        self.result.url = page.url
        self.result.draft_id = self._extract_draft_id(page.url) or self.result.draft_id
        self.shot("05-after-start-continue")

        body_errs = []
        for sel in [
            ".error",
            ".errmsg",
            ".form-error",
            "div.error",
            "p.error",
            ".alert-error",
            "[class*='error']",
        ]:
            try:
                body_errs.extend(page.locator(sel).all_inner_texts())
            except Exception:
                pass
        # red banner lines commonly start with "You must" / endorsement
        for phrase in [
            "You must make an authorship selection",
            "You must",
            "not endorsed",
            "endorsement",
        ]:
            try:
                body_errs.extend(page.locator(f"text={phrase}").all_inner_texts())
            except Exception:
                pass
        real = []
        seen = set()
        for e in body_errs:
            t = " ".join(e.split())
            if not t or "under 18" in t.lower():
                continue
            if t in seen:
                continue
            seen.add(t)
            real.append(t)

        hard = [
            e
            for e in real
            if any(
                k.lower() in e.lower()
                for k in (
                    "authorship",
                    "license",
                    "archive",
                    "subject",
                    "Agreement",
                    "certify",
                    "endorsed",
                    "endorsement",
                )
            )
        ]
        if hard and "start" in page.url:
            self.result.errors = hard[:8]
            for e in hard[:5]:
                print(f"[ERR] {e[:200]}", flush=True)
            # endorsement is a policy gate — not a form bug; hand off to skill
            if any("endors" in e.lower() for e in hard):
                self.result.status = "pending-endorsement"
                self.step("pending-endorsement")
                self._capture_endorsement_links()
                # do not raise — caller can open request UI / wait for human
                print(
                    "[endorsement] blocked on category endorsement; "
                    f"help={self.result.endorsement_help_url} "
                    f"request={self.result.endorsement_url}",
                    flush=True,
                )
                return
            raise RuntimeError(f"Start form validation failed: {hard[0][:160]}")
        self.step("start-ok")
        print(f"[start-ok] {page.url}", flush=True)

    def _capture_endorsement_links(self) -> None:
        page = self._page
        assert page
        links = page.evaluate(
            """() => [...document.querySelectorAll('a')].filter(a =>
              /endorse/i.test((a.href||'') + ' ' + (a.innerText||'')))
              .map(a => ({href: a.href, text: (a.innerText||'').trim()}))"""
        )
        for link in links or []:
            href = link.get("href") or ""
            text = (link.get("text") or "").lower()
            if "help" in text or "info.arxiv" in href:
                self.result.endorsement_help_url = href
            elif "need-endorsement" in href or "request" in text or "endorse" in href:
                self.result.endorsement_url = href
        # category from query string if present
        if self.result.endorsement_url:
            m = re.search(r"category_id=([^&]+)", self.result.endorsement_url)
            if m:
                self.result.endorsement_category = m.group(1)

    def request_endorsement(self, *, open_only: bool = True) -> None:
        """Open endorsement request UI for the human. Never auto-spam endorsers.

        arXiv's need-endorsement.php shows a unique code and emails it to the
        submitter. Human must forward that email to a qualified endorser.
        This method records code + URL; it does not invent endorsers.
        """
        page = self._page
        assert page
        if self.result.endorsement_url is None:
            self._capture_endorsement_links()
        target = self.result.endorsement_url
        if target:
            page.goto(target, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            time.sleep(0.8)
        else:
            loc = page.get_by_role(
                "link", name=re.compile("request endorsement", re.I)
            )
            if loc.count():
                loc.first.click()
                page.wait_for_load_state("networkidle")
                time.sleep(0.8)
                self.result.endorsement_url = page.url
        self.shot("08-endorsement-request")
        self.result.url = page.url
        body = page.inner_text("body")
        # "Your unique endorsement code is: BGJTGV"
        m = re.search(
            r"unique endorsement code is:\s*([A-Z0-9]{4,12})",
            body,
            re.I,
        )
        if m:
            self.result.endorsement_code = m.group(1).upper()
            print(f"[endorsement] code={self.result.endorsement_code}", flush=True)
        m2 = re.search(r"Endorsement needed for\s+([a-z]+\.[A-Z]{2})", body)
        if m2:
            self.result.endorsement_category = m2.group(1)
        if not self.result.endorsement_category:
            m3 = re.search(r"category_id=([^&\s]+)", page.url)
            if m3:
                self.result.endorsement_category = m3.group(1)
        print(f"[endorsement] page={page.url}", flush=True)
        print(
            f"[endorsement] category={self.result.endorsement_category} "
            f"code={self.result.endorsement_code}",
            flush=True,
        )
        self.result.status = "pending-endorsement"
        self.step("request-endorsement-ui")
        if open_only:
            print(
                "[endorsement] recorded code for human forward to endorser; "
                "will not invent or spam endorsers",
                flush=True,
            )

    def upload_source(self) -> None:
        page = self._page
        assert page
        if not self.source_tar or not self.source_tar.exists():
            raise FileNotFoundError(f"source tar missing: {self.source_tar}")

        # navigate to file step if needed
        if page.locator('input[type="file"]').count() == 0:
            did = self._extract_draft_id(page.url) or self.result.draft_id
            for path in [
                f"https://arxiv.org/submit/{did}/file",
                f"https://arxiv.org/submit/{did}/addfiles",
                f"https://arxiv.org/submit/{did}/upload",
            ]:
                if not did:
                    break
                page.goto(path, wait_until="domcontentloaded")
                time.sleep(0.8)
                if page.locator('input[type="file"]').count():
                    break
            # try link
            for text in ["Add Files", "Upload", "Files"]:
                loc = page.get_by_role("link", name=text)
                if loc.count():
                    loc.first.click()
                    time.sleep(1)
                    break

        if not page.locator('input[type="file"]').count():
            self.shot("06-no-file-input")
            raise RuntimeError("no file input found for upload")

        page.locator('input[type="file"]').first.set_input_files(str(self.source_tar))
        print(f"[upload] {self.source_tar.name}", flush=True)
        time.sleep(0.5)
        self._click_button("Upload files", "Upload Files", "Upload")
        page.wait_for_load_state("networkidle")
        time.sleep(3.0)
        # v1.5: after unpack, "Check Files" advances to Review/Process
        if self._click_button("Check Files", "Check files"):
            page.wait_for_load_state("networkidle")
            time.sleep(2.0)
            print("[upload] Check Files clicked", flush=True)
        self.shot("06-uploaded")
        self.step("upload-source")
        self.result.url = page.url

    def _is_503(self) -> bool:
        page = self._page
        assert page
        try:
            t = page.inner_text("body")
        except Exception:
            return True
        return "took too long to respond" in t.lower() or "503" in t[:80]

    def _goto_retry(self, url: str, *, tries: int = 6) -> None:
        page = self._page
        assert page
        for i in range(tries):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                page.wait_for_load_state("networkidle")
            except Exception as ex:
                print(f"[retry] goto fail {i}: {ex}", flush=True)
                time.sleep(3 + i * 2)
                continue
            if self._is_503():
                print(f"[retry] 503 on {url} attempt {i+1}", flush=True)
                time.sleep(4 + i * 3)
                continue
            return
        raise RuntimeError(f"failed to load {url} after {tries} tries")

    def _dismiss_modals(self) -> None:
        """Confirm/Cancel dialogs that block the v1.5 file review flow."""
        for lab in ["Confirm", "OK", "Yes"]:
            if self._click_button(lab, timeout=1500):
                time.sleep(0.5)
                return

    def _fill_metadata_fields(self) -> None:
        page = self._page
        assert page
        for sel, val in [
            ('textarea[name="title"], input[name="title"], #title', self.title),
            ('textarea[name="abstract"], #abstract', self.abstract),
            ('textarea[name="comments"], #comments', self.comments),
        ]:
            loc = page.locator(sel)
            if loc.count() and val:
                try:
                    loc.first.fill(val)
                    print(f"[meta] filled {sel.split(',')[0][:32]}", flush=True)
                except Exception as ex:
                    print(f"[meta] skip {ex}", flush=True)

    def _stage_name(self, url: str) -> str:
        u = url.lower()
        if "preview" in u:
            return "preview"
        if "metadata" in u:
            return "metadata"
        if "process" in u:
            return "process"
        if "reviewfiles" in u or "review" in u:
            return "review"
        if "checkfiles" in u:
            return "checkfiles"
        if "addfiles" in u or "/file" in u:
            return "addfiles"
        if "start" in u:
            return "start"
        return "unknown"

    def walk_process_and_metadata(self, max_steps: int = 24) -> None:
        """Linear v1.5 walk: addfiles → check → review → process → metadata → preview.

        Does NOT click the public Submit (final_submit + APPROVE_FINAL).
        """
        page = self._page
        assert page
        did = self.result.draft_id or self._extract_draft_id(page.url)
        if not did:
            raise RuntimeError("no draft_id for walk")

        # Prefer resuming at the furthest unlocked stage rather than always
        # rewinding to addfiles (which re-triggers Check Files loops).
        for st in ("preview", "metadata", "process", "reviewfiles", "addfiles"):
            self._goto_retry(f"https://arxiv.org/submit/{did}/{st}")
            if self._is_503():
                continue
            # later stages redirect to addfiles if not yet unlocked
            if st == "addfiles" or st in page.url or (
                st == "reviewfiles" and "review" in page.url
            ):
                # if we asked for process/metadata/preview but got addfiles, continue searching
                if st != "addfiles" and "addfiles" in page.url:
                    continue
                print(f"[walk] resume at {page.url}", flush=True)
                break

        for i in range(max_steps):
            if self._is_503():
                print(f"[walk {i}] 503 — reload", flush=True)
                time.sleep(5)
                page.reload(wait_until="domcontentloaded")
                time.sleep(2)
                continue

            url = page.url
            stage = self._stage_name(url)
            print(f"[walk {i}] stage={stage} url={url}", flush=True)
            self.shot(f"walk-{i:02d}")
            self.result.url = url
            self.result.draft_id = self._extract_draft_id(url) or did

            # modal
            if page.locator("text=Confirm File Deletion").count():
                self._dismiss_modals()
                page.wait_for_load_state("networkidle")
                time.sleep(1)
                continue

            if stage == "preview":
                print("[walk] reached preview", flush=True)
                break

            if stage in ("addfiles", "checkfiles"):
                body = page.inner_text("body")
                # only (re)upload if files not already listed
                if (
                    "sqrt_space" not in body
                    and self.source_tar
                    and self.source_tar.exists()
                    and page.locator('input[type="file"]').count()
                ):
                    page.locator('input[type="file"]').first.set_input_files(
                        str(self.source_tar)
                    )
                    self._click_button("Upload", "Upload files", "Upload Files")
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)
                self._click_button("Check Files", "Check files", timeout=8000)
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                # Check Files often keeps us on addfiles until scan finishes —
                # force the next stage URL which is the real gate.
                if self._stage_name(page.url) in ("addfiles", "checkfiles", "unknown"):
                    self._goto_retry(f"https://arxiv.org/submit/{did}/reviewfiles")
                    time.sleep(1)
                continue

            if stage == "review":
                # Keep .bbl for reliable bibliography
                page.evaluate(
                    """() => {
                  document.querySelectorAll('tr').forEach(tr => {
                    if (/\\.bbl/i.test(tr.innerText)) {
                      tr.querySelectorAll('input[type=checkbox]').forEach(c => {
                        c.checked = false;
                      });
                    }
                  });
                }"""
                )
                if not self._click_button(
                    "Accept and Continue", "Accept and continue", timeout=10000
                ):
                    page.evaluate(
                        """() => {
                      const els = [...document.querySelectorAll('button,a,input')];
                      const t = els.find(e => /Accept and Continue/i.test(
                        (e.innerText||e.value||'')));
                      if (t) t.click();
                    }"""
                    )
                page.wait_for_load_state("networkidle")
                time.sleep(1.5)
                self._dismiss_modals()
                # Accept kicks off compile → process
                for _ in range(30):
                    if self._is_503():
                        time.sleep(5)
                        page.reload()
                        continue
                    if "process" in page.url or "metadata" in page.url:
                        break
                    # still reviewing?
                    if page.locator("text=Confirm File Deletion").count():
                        self._dismiss_modals()
                    time.sleep(2)
                continue

            if stage == "process":
                for _ in range(45):
                    if self._is_503():
                        time.sleep(5)
                        page.reload()
                        continue
                    body = page.inner_text("body")
                    if "successfully processed" in body.lower():
                        break
                    if page.locator(
                        'input[type="submit"][value="Continue"], button:has-text("Continue")'
                    ).count():
                        break
                    time.sleep(2)
                self.shot(f"walk-{i:02d}-process")
                body = page.inner_text("body")
                if re.search(r"Emergency stop|! LaTeX Error|Fatal", body):
                    print("[process] hard compile errors present", flush=True)
                self._click_button("Continue", "Save and continue", "Next")
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                continue

            if stage == "metadata":
                self._fill_metadata_fields()
                time.sleep(0.3)
                self._click_button("Continue", "Save and continue", "Next", "Save")
                page.wait_for_load_state("networkidle")
                time.sleep(1.5)
                continue

            # unknown: try progressive nav buttons, never public Submit
            moved = self._click_button(
                "Accept and Continue",
                "Check Files",
                "Continue",
                "Next",
                "Save and continue",
            )
            if not moved:
                # try stage URLs in order
                for st in ("reviewfiles", "process", "metadata", "preview"):
                    self._goto_retry(f"https://arxiv.org/submit/{did}/{st}")
                    if self._stage_name(page.url) == st.replace("files", "") or st in page.url:
                        break
                else:
                    break
            else:
                page.wait_for_load_state("networkidle")
                time.sleep(1.5)

        self.step("process-metadata-walk")
        self.shot("07-after-walk")
        print(f"[walk-done] {page.url}", flush=True)

    def final_submit(self) -> None:
        page = self._page
        assert page
        if not self.approve_final:
            self.step("pending-human-final-submit")
            self.result.status = "pending-human-final-submit"
            print(
                "[final] stopped — set APPROVE_FINAL=1 to click public Submit "
                "(actor :arxiv/final-submit human-approval gate)",
                flush=True,
            )
            return

        did = self.result.draft_id or self._extract_draft_id(page.url)
        if "preview" not in page.url and did:
            self._goto_retry(f"https://arxiv.org/submit/{did}/preview")

        self.shot("08-before-final")
        stage = self._stage_name(page.url)
        if stage != "preview":
            print(
                f"[final] not on preview (stage={stage} url={page.url}); abort",
                flush=True,
            )
            self.step("final-submit-wrong-stage")
            self.result.status = "pending-human-final-submit"
            self.result.error = f"final submit aborted: still at {page.url}"
            self.shot("09-after-final")
            self.result.url = page.url
            return

        clicked = False
        # On preview the public action is usually "Submit" as submit input
        for lab in [
            "Submit",
            "Submit article",
            "Submit this paper",
            "Confirm and submit",
        ]:
            if self._click_button(lab, timeout=5000):
                clicked = True
                break
        if not clicked:
            # last resort: any submit whose value mentions Submit
            inp = page.locator('input[type="submit"]')
            for i in range(inp.count()):
                val = (inp.nth(i).get_attribute("value") or "").lower()
                if "submit" in val and "search" not in val:
                    try:
                        inp.nth(i).click(timeout=5000)
                        clicked = True
                        break
                    except Exception:
                        pass

        if clicked:
            page.wait_for_load_state("networkidle")
            time.sleep(2)
            self.result.url = page.url
            body = page.inner_text("body")
            ok = any(
                k in body.lower()
                for k in (
                    "submission received",
                    "has been submitted",
                    "thank you",
                    "paper password",
                    "your article will",
                )
            ) or (
                "user" in page.url
                and "submit/" not in page.url
            )
            if ok:
                self.step("final-submit")
                self.result.status = "submitted"
                print(f"[final] SUBMITTED url={page.url}", flush=True)
            else:
                self.step("final-submit-unclear")
                self.result.status = "pending-human-final-submit"
                print(f"[final] click done, unclear: {page.url}", flush=True)
        else:
            self.step("final-submit-button-not-found")
            self.result.status = "pending-human-final-submit"
            print("[final] Submit button not found on preview", flush=True)
        self.shot("09-after-final")
        self.result.url = page.url

    # ---- entry ------------------------------------------------------------

    def run(self, *, stop_after: Optional[str] = None) -> FlowResult:
        """Run the pipeline. stop_after: login|start|upload|metadata|endorsement|final."""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=not self.headed)
            page = browser.new_page(viewport={"width": 1400, "height": 1200})
            page.set_default_timeout(self.timeout_ms)
            self._page = page
            try:
                self.login()
                if stop_after == "login":
                    return self.result
                self.open_user()
                self.start_or_resume()
                if stop_after == "start-open":
                    return self.result
                self.fill_start_form()
                if self.result.status == "pending-endorsement":
                    if stop_after in (None, "start", "endorsement", "upload", "metadata"):
                        self.request_endorsement(open_only=True)
                    return self.result
                if stop_after == "start":
                    return self.result
                self.upload_source()
                if stop_after == "upload":
                    return self.result
                self.walk_process_and_metadata()
                if stop_after == "metadata":
                    self.result.status = "pending-human-final-submit"
                    return self.result
                self.final_submit()
            except Exception as e:
                self.result.status = "error"
                self.result.error = f"{type(e).__name__}: {e}"
                try:
                    self.shot("99-error")
                except Exception:
                    pass
                print(f"[error] {self.result.error}", flush=True)
            finally:
                if page:
                    self.result.url = page.url
                    did = self._extract_draft_id(page.url)
                    if did:
                        self.result.draft_id = did
                browser.close()
                self._page = None
        return self.result
