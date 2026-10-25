#!/usr/bin/env python3
"""arXiv submit v2 — complete Start form + upload for submission 7807285 or new.

Fills the v1.5 Start page required fields that v1 missed, then walks
Add Files → Process → Metadata → Preview. Final Submit only if APPROVE_FINAL=1.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
TAR = ROOT / "build" / "sqrt_space_kv-arxiv-source.tar.gz"
ABSTRACT = ROOT / "abstract.txt"
SHOT = ROOT / "build" / "screenshots"
TITLE = (
    "Simulating Autoregressive Memory with Square-Root Space: "
    "From Williams' Time-Space Theorem to Practical KV-Cache Residency"
)
COMMENTS = (
    "Systems/empirical note grounded in Williams STOC 2025. "
    "Code and benchmarks: https://github.com/gftdcojp/cloud-murakumo. "
    "Not a TM simulation of Transformers."
)
SUB_ID = os.environ.get("ARXIV_SUB_ID", "7807285")


def shot(page, name):
    SHOT.mkdir(parents=True, exist_ok=True)
    p = SHOT / f"v2-{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"[shot] {p.name}", flush=True)


def click_text(page, *texts, role="button"):
    for t in texts:
        loc = page.get_by_role(role, name=t)
        if loc.count():
            loc.first.click()
            return True
        loc = page.get_by_text(t, exact=False)
        if loc.count():
            try:
                loc.first.click(timeout=3000)
                return True
            except Exception:
                pass
    return False


def main():
    user = os.environ["ARXIV_USER"]
    password = os.environ["ARXIV_PASSWORD"]
    abstract = ABSTRACT.read_text().strip()
    want_final = os.environ.get("APPROVE_FINAL") == "1"
    state = {"steps": [], "url": None, "status": "ok", "error": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        page.set_default_timeout(90_000)

        try:
            # Login
            page.goto("https://arxiv.org/login", wait_until="domcontentloaded")
            page.fill('input[name="username"]', user)
            page.fill('input[name="password"]', password)
            page.locator('button[type="submit"], input[type="submit"]').first.click()
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "01-login")
            assert "login" not in page.url.lower() or "user" in page.url
            state["steps"].append("login")

            # Resume existing submission or start new
            url = f"https://arxiv.org/submit/{SUB_ID}/start"
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(1)
            if "not found" in page.content().lower() or page.locator("text=START NEW").count():
                page.goto("https://arxiv.org/user/", wait_until="domcontentloaded")
                click_text(page, "START NEW SUBMISSION", "Start new submission", role="link")
                page.wait_for_load_state("networkidle")
            shot(page, "02-start")
            state["url"] = page.url
            print(f"[start] {page.url}", flush=True)

            # --- Start form fields ---
            # certify contact
            for label in [
                "I certify that the above information is correct",
                "certify that the above information",
            ]:
                cb = page.get_by_label(label, exact=False)
                if cb.count():
                    cb.first.check()
                    break
            else:
                # fallback: first checkbox in contact section
                boxes = page.locator('input[type="checkbox"]')
                if boxes.count():
                    boxes.first.check()

            # agreement
            for label in [
                "By submitting to arXiv I have read and accept the Submission Agreement",
                "Submission Agreement",
            ]:
                cb = page.get_by_label(label, exact=False)
                if cb.count():
                    cb.first.check()
                    break
            else:
                boxes = page.locator('input[type="checkbox"]')
                if boxes.count() >= 2:
                    boxes.nth(1).check()

            # authorship: first radio "I am submitting as an author"
            radios = page.locator('input[type="radio"]')
            # find by nearby text
            auth = page.get_by_text("I am submitting as an author", exact=False)
            if auth.count():
                # click the radio near this text
                page.locator('input[type="radio"]').first.check()
            elif radios.count():
                radios.first.check()

            # License: CC BY
            # Prefer label containing "CC BY:" without SA/NC
            license_clicked = False
            for txt in [
                "CC BY: Creative Commons Attribution",
                "Creative Commons Attribution",
                "CC BY",
            ]:
                loc = page.get_by_text(txt, exact=False)
                if loc.count():
                    # click associated radio - go to parent
                    try:
                        loc.first.click()
                        license_clicked = True
                        break
                    except Exception:
                        pass
            if not license_clicked and radios.count() >= 3:
                # typical order: CC BY is first license radio after authorship
                pass

            # Archive + subject: Computer Science / Machine Learning
            selects = page.locator("select")
            print(f"[form] selects={selects.count()} radios={radios.count()}", flush=True)
            # First select: archive
            if selects.count() >= 1:
                sel0 = selects.nth(0)
                # try options
                html = sel0.inner_html()
                for val in ["cs", "computer_science", "Computer Science"]:
                    try:
                        sel0.select_option(label="Computer Science")
                        print("[form] archive=Computer Science", flush=True)
                        break
                    except Exception:
                        try:
                            sel0.select_option(value=val)
                            print(f"[form] archive value={val}", flush=True)
                            break
                        except Exception:
                            continue
                time.sleep(0.8)  # subject class may populate

            if selects.count() >= 2:
                sel1 = selects.nth(1)
                for lab in [
                    "Machine Learning",
                    "cs.LG",
                    "Learning",
                ]:
                    try:
                        sel1.select_option(label=lab)
                        print(f"[form] subject={lab}", flush=True)
                        break
                    except Exception:
                        continue
                else:
                    # try value containing LG
                    opts = sel1.locator("option")
                    for i in range(opts.count()):
                        t = opts.nth(i).inner_text()
                        v = opts.nth(i).get_attribute("value") or ""
                        if "LG" in t or "LG" in v or "Machine Learning" in t:
                            sel1.select_option(index=i)
                            print(f"[form] subject idx={i} {t!r}", flush=True)
                            break

            # Re-check licenses radios specifically for CC BY only
            # Many UIs use name=license value=http://creativecommons.org/licenses/by/4.0/
            for sel in [
                'input[value*="by/4.0"]',
                'input[value*="by/3.0"]',
                'input[value="http://creativecommons.org/licenses/by/4.0/"]',
            ]:
                if page.locator(sel).count():
                    page.locator(sel).first.check()
                    print("[form] license=CC-BY via value", flush=True)
                    break

            shot(page, "03-form-filled")
            # Continue
            click_text(page, "Continue")
            page.wait_for_load_state("networkidle")
            time.sleep(1.5)
            shot(page, "04-after-continue")
            state["url"] = page.url
            print(f"[after-continue] {page.url}", flush=True)
            state["steps"].append("start-form")

            # If still on start with errors, dump text
            content = page.content()
            if "You must" in content:
                state["error"] = "start-form-validation-failed"
                shot(page, "04b-still-errors")
                # print error banners only
                for line in page.locator("text=You must").all_inner_texts()[:10]:
                    print(f"[err] {line}", flush=True)
                raise SystemExit("Start form still has validation errors")

            # --- Add Files ---
            # may already be on add files
            if page.locator('input[type="file"]').count() == 0:
                click_text(page, "Add Files", role="link")
                time.sleep(1)
            if page.locator('input[type="file"]').count():
                page.locator('input[type="file"]').first.set_input_files(str(TAR.resolve()))
                print(f"[upload] {TAR.name}", flush=True)
                time.sleep(1)
                click_text(page, "Upload files", "Upload Files", "Upload")
                time.sleep(3)
                page.wait_for_load_state("networkidle")
                shot(page, "05-uploaded")
                state["steps"].append("upload")

            # Continue through review/process
            for _ in range(6):
                shot(page, f"06-step-{_}")
                # Metadata fields if present
                if page.locator('textarea[name="title"], input[name="title"], #title').count():
                    try:
                        page.fill('textarea[name="title"], input[name="title"], #title', TITLE)
                    except Exception:
                        pass
                if page.locator('textarea[name="abstract"], #abstract').count():
                    try:
                        page.fill('textarea[name="abstract"], #abstract', abstract)
                    except Exception:
                        pass
                if page.locator('textarea[name="comments"]').count():
                    try:
                        page.fill('textarea[name="comments"]', COMMENTS)
                    except Exception:
                        pass

                # Process button
                if click_text(page, "Process", "Save and continue", "Continue", "Next", "Preview"):
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                else:
                    break
                state["url"] = page.url
                print(f"[walk] {page.url}", flush=True)

            shot(page, "07-final-stage")
            state["steps"].append("walked")

            if want_final:
                print("[final] APPROVE_FINAL=1", flush=True)
                click_text(page, "Submit", "Submit article", "Confirm")
                page.wait_for_load_state("networkidle")
                time.sleep(2)
                shot(page, "08-submitted")
                state["steps"].append("final-submit")
            else:
                print("[final] stopped (APPROVE_FINAL!=1); draft/process stage kept", flush=True)
                state["steps"].append("pending-human-final-submit")

            state["url"] = page.url
        except SystemExit as e:
            state["status"] = "error"
            state["error"] = str(e)
        except Exception as e:
            state["status"] = "error"
            state["error"] = f"{type(e).__name__}: {e}"
            try:
                shot(page, "99-error")
            except Exception:
                pass
            print(f"[error] {state['error']}", flush=True)
        finally:
            browser.close()

    out = ROOT / "build" / "submit-v2-result.json"
    out.write_text(json.dumps(state, indent=2))
    print(json.dumps(state, indent=2), flush=True)
    return 0 if state.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
