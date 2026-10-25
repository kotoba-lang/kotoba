#!/usr/bin/env python3
"""Browser draft/upload for arXiv using kotoba-lang/arxiv actor skill steps.

Follows actors/arxiv/skills/{login,submit-draft,final-submit}.edn:
  login → user home → start submission → fill metadata → upload source →
  process → (optional) final submit if --final and APPROVE_FINAL=1.

Secrets from env ARXIV_USER / ARXIV_PASSWORD (loaded by caller via 1Password).
Never prints secret values.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout


ROOT = Path(__file__).resolve().parent
DEFAULT_TAR = ROOT / "build" / "sqrt_space_kv-arxiv-source.tar.gz"
DEFAULT_ABSTRACT = ROOT / "abstract.txt"
SCREEN_DIR = ROOT / "build" / "screenshots"


def env_cred():
    u = os.environ.get("ARXIV_USER") or os.environ.get("ARXIV_USERNAME")
    p = os.environ.get("ARXIV_PASSWORD")
    if not u or not p:
        raise SystemExit("Set ARXIV_USER and ARXIV_PASSWORD (do not pass on CLI)")
    return u, p


def shot(page, name: str):
    SCREEN_DIR.mkdir(parents=True, exist_ok=True)
    path = SCREEN_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"[shot] {path}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tar", type=Path, default=DEFAULT_TAR)
    ap.add_argument("--abstract", type=Path, default=DEFAULT_ABSTRACT)
    ap.add_argument("--title", default=(
        "Simulating Autoregressive Memory with Square-Root Space: "
        "From Williams' Time-Space Theorem to Practical KV-Cache Residency"
    ))
    ap.add_argument("--primary", default="cs.LG")
    ap.add_argument("--cross", default="cs.CL,cs.CC")
    ap.add_argument("--comments", default=(
        "Systems/empirical note grounded in Williams STOC 2025. "
        "Code: https://github.com/gftdcojp/cloud-murakumo"
    ))
    ap.add_argument("--final", action="store_true",
                    help="Also click final Submit (requires APPROVE_FINAL=1)")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--timeout-ms", type=int, default=120_000)
    args = ap.parse_args()

    if not args.tar.exists():
        raise SystemExit(f"missing source archive: {args.tar}")
    abstract = args.abstract.read_text().strip()
    user, password = env_cred()
    want_final = args.final and os.environ.get("APPROVE_FINAL") == "1"
    if args.final and not want_final:
        print("[guard] --final ignored without APPROVE_FINAL=1 "
              "(actor :arxiv.final-submit requires human-approval)", flush=True)

    state = {"steps": [], "url": None, "error": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.set_default_timeout(args.timeout_ms)

        try:
            # --- login skill ---
            print("[login] navigate arxiv.org/login", flush=True)
            page.goto("https://arxiv.org/login", wait_until="domcontentloaded")
            shot(page, "01-login")
            # multiple possible field names across UI generations
            for sel in [
                'input[name="username"]',
                'input#username',
                'input[type="email"]',
                'input[name="user"]',
            ]:
                if page.locator(sel).count():
                    page.fill(sel, user)
                    break
            else:
                page.get_by_label("Username", exact=False).fill(user)

            for sel in [
                'input[name="password"]',
                'input#password',
                'input[type="password"]',
            ]:
                if page.locator(sel).count():
                    page.fill(sel, password)
                    break
            else:
                page.get_by_label("Password", exact=False).fill(password)

            # click log in
            clicked = False
            for role_name in ["Log in", "Login", "Sign in"]:
                btn = page.get_by_role("button", name=role_name)
                if btn.count():
                    btn.first.click()
                    clicked = True
                    break
            if not clicked:
                page.locator('input[type="submit"], button[type="submit"]').first.click()

            page.wait_for_load_state("networkidle")
            time.sleep(1.5)
            shot(page, "02-after-login")
            state["steps"].append("login")
            state["url"] = page.url
            print(f"[login] url={page.url}", flush=True)

            if "login" in page.url.lower() and page.locator('input[type="password"]').count():
                # captcha or bad creds
                state["error"] = "login-still-on-page"
                shot(page, "02b-login-failed")
                raise SystemExit(
                    "Still on login page (bad credentials, captcha, or UI change). "
                    "Screenshots in build/screenshots/."
                )

            # --- user hub ---
            for url in [
                "https://arxiv.org/user/",
                "https://arxiv.org/submit",
                "https://arxiv.org/user",
            ]:
                page.goto(url, wait_until="domcontentloaded")
                time.sleep(1)
                if "login" not in page.url.lower():
                    break
            shot(page, "03-user-home")
            state["url"] = page.url
            print(f"[user] url={page.url}", flush=True)

            # Start new submission
            started = False
            for text in [
                "Start new submission",
                "START NEW SUBMISSION",
                "New submission",
                "Submit",
            ]:
                loc = page.get_by_role("link", name=text)
                if loc.count():
                    loc.first.click()
                    started = True
                    break
                loc = page.get_by_text(text, exact=False)
                if loc.count():
                    loc.first.click()
                    started = True
                    break
            if not started:
                # try submit path
                page.goto("https://arxiv.org/submit", wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle")
            time.sleep(1)
            shot(page, "04-start-submission")
            state["steps"].append("start-submission")

            # License agreement if present
            for text in ["I agree", "Accept", "Continue", "Next"]:
                b = page.get_by_role("button", name=text)
                if b.count():
                    try:
                        b.first.click(timeout=3000)
                        time.sleep(0.8)
                    except PWTimeout:
                        pass

            # Category selection if on that step
            # arXiv often has select for archive/subject class
            try:
                # primary category fields vary
                if page.locator("select").count():
                    # attempt to select cs.LG if options present
                    selects = page.locator("select")
                    for i in range(min(selects.count(), 6)):
                        sel = selects.nth(i)
                        opts = sel.locator("option")
                        for j in range(opts.count()):
                            val = opts.nth(j).get_attribute("value") or ""
                            txt = opts.nth(j).inner_text()
                            if args.primary in val or args.primary in txt:
                                sel.select_option(index=j)
                                print(f"[cat] selected {args.primary}", flush=True)
                                break
            except Exception as e:
                print(f"[cat] skip: {type(e).__name__}", flush=True)
            shot(page, "05-categories")

            # Continue buttons
            for text in ["Continue", "Next", "Save and continue"]:
                b = page.get_by_role("button", name=text)
                if b.count():
                    try:
                        b.first.click(timeout=3000)
                        page.wait_for_load_state("networkidle")
                        time.sleep(0.5)
                    except Exception:
                        pass

            # File upload
            shot(page, "06-before-upload")
            uploaded = False
            file_inputs = page.locator('input[type="file"]')
            if file_inputs.count():
                file_inputs.first.set_input_files(str(args.tar.resolve()))
                uploaded = True
                print(f"[upload] set file {args.tar.name}", flush=True)
                time.sleep(1)
                for text in ["Upload files", "Upload", "Continue", "Next", "Process"]:
                    b = page.get_by_role("button", name=text)
                    if b.count():
                        try:
                            b.first.click(timeout=5000)
                            break
                        except Exception:
                            pass
                # wait for process
                time.sleep(5)
                page.wait_for_load_state("networkidle")
            shot(page, "07-after-upload")
            if uploaded:
                state["steps"].append("upload-source")

            # Metadata: title / abstract
            for sel in ['textarea[name="title"]', 'input[name="title"]', "#title"]:
                if page.locator(sel).count():
                    page.fill(sel, args.title)
                    break
            else:
                try:
                    page.get_by_label("Title", exact=False).fill(args.title)
                except Exception:
                    print("[meta] title field not found", flush=True)

            for sel in ['textarea[name="abstract"]', "#abstract"]:
                if page.locator(sel).count():
                    page.fill(sel, abstract)
                    break
            else:
                try:
                    page.get_by_label("Abstract", exact=False).fill(abstract)
                except Exception:
                    print("[meta] abstract field not found", flush=True)

            for sel in ['textarea[name="comments"]', 'input[name="comments"]']:
                if page.locator(sel).count():
                    page.fill(sel, args.comments)
                    break

            shot(page, "08-metadata")
            state["steps"].append("metadata")

            for text in ["Save", "Continue", "Next", "Preview"]:
                b = page.get_by_role("button", name=text)
                if b.count():
                    try:
                        b.first.click(timeout=4000)
                        page.wait_for_load_state("networkidle")
                        time.sleep(0.8)
                    except Exception:
                        pass
            shot(page, "09-preview")
            state["url"] = page.url

            if want_final:
                print("[final] APPROVE_FINAL=1 — attempting Submit", flush=True)
                shot(page, "10-before-final")
                for text in ["Submit", "Submit to arXiv", "Confirm"]:
                    b = page.get_by_role("button", name=text)
                    if b.count():
                        b.first.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(2)
                        break
                shot(page, "11-after-final")
                state["steps"].append("final-submit")
            else:
                print(
                    "[final] stopped before public submit "
                    "(set APPROVE_FINAL=1 --final to complete; actor gate)",
                    flush=True,
                )
                state["steps"].append("pending-human-final-submit")

            state["status"] = "ok"
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

    out = ROOT / "build" / "submit-result.json"
    out.write_text(json.dumps(state, indent=2))
    print(json.dumps(state, indent=2), flush=True)
    return 0 if state.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
